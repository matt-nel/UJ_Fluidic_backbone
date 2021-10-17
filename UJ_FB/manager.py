import os
import logging
import json
import networkx as nx
import datetime
import time
import math
from networkx.readwrite.json_graph import node_link_graph
from queue import Queue
from threading import Thread, Lock
from commanduino import CommandManager
import UJ_FB.fluidic_backbone_gui as fluidic_backbone_gui
import UJ_FB.web_listener as  web_listener
from UJ_FB.Modules import syringepump, selectorvalve, reactor, modules, camera
import UJ_FB.fbexceptions as fbexceptions

def load_graph(graph_config):
    graph = node_link_graph(graph_config, directed=True, multigraph=True)
    return graph


def object_hook_int(obj):
    """
    :param obj: dictionary converted from JSON
    :return: dictionary of JSON data with integers formatted
    """
    output = {}
    for k, v in obj.items():
        key = k
        if isinstance(k, str):
            try:
                key = int(k)
            except ValueError:
                pass
        output[key] = v
    return output


class Manager(Thread):
    def __init__(self, gui=True, simulation=False, web_enabled=False):
        Thread.__init__(self)
        # get absolute directory of script
        self.script_dir = os.path.dirname(__file__)
        cm_config = os.path.join(self.script_dir, "Configs/cmd_config.json")
        self.cmd_mng = CommandManager.from_configfile(cm_config, simulation)
        self.module_info = self.json_loader("Configs/module_info.json")
        self.key = self.module_info['key']
        self.id = self.module_info['id']
        self.module_info = self.module_info['modules']
        self.prev_run_config = self.json_loader("Configs/running_config.json", object_hook=object_hook_int)
        self.name = "Manager" + self.id
        logfile = 'UJ_FB/Logs/log' + datetime.datetime.today().strftime('%Y%m%d')
        logging.basicConfig(filename=logfile, level=logging.INFO)
        self.logger = logging.getLogger(self.id)
        self.q = Queue()
        self.pipeline = Queue()
        # list to hold current Task objects.
        self.tasks = []
        self.serial_lock = Lock()
        self.interrupt_lock = Lock()
        self.user_wait_flag = False
        self.waiting = False
        self.interrupt = False
        self.exit_flag = False
        self.stop_flag = False
        self.pause_flag = False
        self.paused = False
        self.ready = True
        self.reaction_ready = False
        self.reaction_name = ""
        self.reaction_id = None
        self.clean_step = False
        self.error = False
        self.error_start = None
        self.valid_nodes = []
        self.valves = {}
        self.num_valves = 0
        self.syringes = {}
        self.reactors = {}
        self.flasks = {}
        self.cameras ={}
        self.populate_modules()
        graph_config = self.json_loader("Configs/module_connections.json")
        self.graph = load_graph(graph_config)
        self.check_connections()
        self.init_syringes()
        self.listener = web_listener.WebListener(self, self.id, self.key)
        self.web_enabled = web_enabled
        self.execute = False
        self.write_running_config("Configs/running_config.json")
        self.rc_changes = False
        self.xdl = ''
        if gui:
            self.gui_main = fluidic_backbone_gui.FluidicBackboneUI(self)
        else:
            self.gui_main = None
        if web_enabled:
            self.listener.test_connection()
        self.start()

    def mainloop(self):
        if self.gui_main is not None:
            self.gui_main.primary.mainloop()

    def update_url(self, url):
        self.listener.update_url(url)

    def json_loader(self, fp, object_hook=None):
        fp = os.path.join(self.script_dir, fp)
        try:
            with open(fp) as file:
                return json.load(file, object_hook=object_hook)
        except (FileNotFoundError, json.decoder.JSONDecodeError) as e:
            raise fbexceptions.FBConfigurationError(f'The JSON provided {fp} is invalid. \n {e}')

    def write_log(self, message, level):
        if self.gui_main is not None:
            if level > 9:
                self.gui_main.write_message(message)
        if level > 49:
            self.logger.critical(message)
        elif level > 39:
            self.logger.error(message)
        elif level > 29:
            self.logger.warning(message)
        elif level > 19:
            self.logger.info(message)
        elif level > 9:
            self.logger.info(message)

    def write_running_config(self, fp):
        fp = os.path.join(self.script_dir, fp)
        rc_file = open(fp, 'w+')
        running_config = json.dumps(self.prev_run_config, indent=4)
        rc_file.write(running_config)
        rc_file.close()
        self.rc_changes = False

    def populate_modules(self):
        syringes = 0
        for module_name in self.module_info.keys():
            module_type = self.module_info[module_name]['mod_type']
            module_info = self.module_info[module_name]
            if module_type == "valve":
                self.num_valves += 1
                self.valves[module_name] = selectorvalve.SelectorValve(module_name, module_info, self.cmd_mng, self)
            elif module_type == "syringe":
                syringes += 1
                self.syringes[module_name] = syringepump.SyringePump(module_name, module_info, self.cmd_mng, self)
            elif module_type == "reactor":
                self.reactors[module_name] = reactor.Reactor(module_name, module_info, self.cmd_mng, self)
            elif module_type == "flask":
                self.flasks[module_name] = modules.FBFlask(module_name, module_info, self.cmd_mng, self)
            elif module_type == "camera":
                self.cameras[module_name] = camera.Camera(module_name, module_info, None, self)
        if syringes == 0:
            self.write_log('No pumps configured', level=logging.WARNING)
            time.sleep(2)
            self.interrupt = True
            self.exit_flag = True
        self.reaction_name = self.module_info.get('reaction_config')
        if self.reaction_name:
            self.write_log(f"Robot {self.id} is configured for reaction {self.reaction_name}")

    def check_connections(self):
        # todo update objects from graph config info
        g = self.graph
        valves_list = []
        for n in list(g.nodes):
            if g.degree[n] < 1:
                self.write_log(f'Node {n} is not connected to the system!', level=logging.WARNING)
            else:
                name = g.nodes[n]['name']
                mod_type = g.nodes[n]['mod_type']
                self.valid_nodes.append(name)
                if 'syringe' in mod_type:
                    syringe = self.syringes[name]
                    node = g.nodes[n]
                    node['object'] = syringe
                    syringe.set_max_volume(node['Maximum volume'])
                    syringe.change_contents(node['Contents'], float(node['Current volume']) * 1000)
                    syringe.set_pos(node['Current volume'])
                elif 'valve' in mod_type:
                    valves_list.append(n)
                    g.nodes[n]['object'] = self.valves[name]
                elif 'flask' in mod_type:
                    g.nodes[n]['object'] = self.flasks[name]
                elif 'reactor' in mod_type:
                    g.nodes[n]['object'] = self.reactors[name]
        for valve in valves_list:
            name = g.nodes[valve]['name']
            g.nodes[valve]['object'] = self.valves[name]
            for node_name in g.adj[valve]:
                port = g.adj[valve][node_name][0]['port'][1]
                self.valves[name].ports[port] = g.nodes[node_name]['object']
                if "valve" in node_name:
                    self.valves[name].adj_valves.append((node_name, port))
            self.valves[name].syringe = self.valves[name].ports[-1]

    def init_syringes(self):
        """
            Initialises the syringes by moving them to their endstop, dispensing contents into the nearest
            waste container. If no waste container is found,  prints a message warning the user.
        """
        for valve in self.valves:
            # home and prepare valve for running
            self.valves[valve].init_valve()
            syringe = self.valves[valve].syringe
            # check if syringe needs to be homed
            if not syringe.stepper.check_endstop():
                # search for waste containers looking for shortest path
                waste_containers = [item for item in list(self.graph.nodes) if "waste" in item.lower()]
                if not waste_containers:
                    self.write_log(f"No waste containers are attached. Please manually empty {syringe.name} using the GUI", level=logging.WARNING)
                    continue
                shortest_waste_path = []
                for waste in waste_containers:
                    path_gen = nx.algorithms.simple_paths.all_simple_paths(self.graph, syringe.name, waste)
                    path_list = [p for p in path_gen]
                    if len(path_list[0]) < len(shortest_waste_path) or not shortest_waste_path:
                        shortest_waste_path = path_list[0]
                # Align valves without dispensing much liquid
                self.move_liquid(source=syringe.name, target=shortest_waste_path[-1], volume=0.1, flow_rate=10000, init_move=True)
                # with valves at waste can move to 0
                self.add_to_queue(Manager.generate_cmd_dict('syringe', syringe.name, 'home', {'wait': True}))
            self.start_queue()
    
    def reload_graph(self):
        graph_config = self.json_loader("Configs/module_connections.json")
        self.graph = load_graph(graph_config)
        self.check_connections()

    def run(self):
        while not self.exit_flag:
            if self.web_enabled:
                execute = self.listener.update_execution()
                if self.clean_step:
                    self.execute = False
            else:
                execute = self.execute
            if self.error:
                if self.web_enabled:
                    self.listener.update_status(self.ready, error=True)
                elif time.time() - self.error_start > 300:
                    self.ensure_reactors_disabled()
            self.check_task_completion()
            # interrupt lock used to synchronise access to pause, stop, and exit flags
            with self.interrupt_lock:
                pause_flag = self.pause_flag
                if not execute and execute is not None:
                    if not self.ready:
                        self.pause_flag = True
                if self.interrupt:
                    if self.exit_flag:
                        break
                    elif self.pause_flag and not self.paused:
                        self.pause_all()
                        if self.stop_flag:
                            self.stop_all()
                    elif not self.pause_flag and self.paused:
                        self.resume()
                    self.interrupt = False
            if self.q.empty() and not self.tasks:
                self.ready = True
                self.ensure_reactors_disabled()
                if self.web_enabled:
                    self.listener.update_status(ready=self.ready)
                if not self.reaction_ready:
                    # log reaction completion once
                    if self.reaction_name:
                        self.write_log(f"Completed {self.reaction_name}")
                        self.reaction_name = ""
                    # Attempt to request reaction from server
                    if self.web_enabled:
                        if self.listener.request_reaction():
                            self.reaction_ready = True
                            self.write_log(f"Prepared to run {self.reaction_name} reaction.", level=logging.INFO)
                # a reaction has been queued
                else:
                    if execute:
                        self.start_queue()
                        self.reaction_ready = False
                        self.ready = False
                continue
            # execution ongoing
            if not pause_flag:
                # waiting for task completion
                if self.waiting:
                    if not self.tasks:
                        with self.interrupt_lock:
                            self.waiting = False
                #  move on to next queued item
                else:
                    command_dict = self.q.get()
                    if self.command_module(command_dict):
                        self.write_log(f"Added command {command_dict['command']} for {command_dict['module_name']}", level=logging.INFO)
                    else:
                        self.write_log(f"Failed to add command {command_dict['command']} for {command_dict['module_name']}")
            if self.rc_changes:
                self.write_running_config("Configs\\running_config.json")
        self.pause_all()
        self.cmd_mng.commandhandlers[0].stop()

    def add_to_queue(self, commands, queue=None):
        if queue is None:
            queue = self.pipeline
        for command in commands:
            queue.put(command)

    def echo_queue(self):
        pipeline = []
        while not self.pipeline.empty():
            command_dict = self.pipeline.get(block=False)
            pipeline.append(command_dict)
        self.add_to_queue(pipeline)
        return pipeline

    def export_queue(self):
        output = {"pipeline": list(self.pipeline.queue)}
        export_queue = json.dumps(output, indent=4)
        pipeline_path = os.path.join(self.script_dir, "Configs/Pipeline.json")
        file = open(pipeline_path, 'w+')
        file.write(export_queue)
        file.close()

    def import_queue(self, file, overwrite=False):
        file = os.path.join(self.script_dir, file)
        try:
            with open(file) as queue_file:
                queue_list = json.load(queue_file)['pipeline']
        except json.decoder.JSONDecodeError:
            self.write_log("That is not a valid JSON file", level=logging.WARNING)
            return False
        if overwrite:
            self.pipeline.queue.clear()
        protocol = queue_list.get('protocol')
        if protocol:
            self.xdl = protocol
        if queue_list.get('pipeline'):
            self.add_to_queue(queue_list)
        else:
            if not self.listener.load_xdl(self.xdl, is_file=False):
                return False

    def start_queue(self):
        self.execute = 1
        with self.interrupt_lock:
            self.pause_flag = True
            self.interrupt = True
        while not self.pipeline.empty():
            command_dict = self.pipeline.get(block=False)
            self.q.put(command_dict)
        self.pipeline.queue.clear()
        with self.interrupt_lock:
            self.pause_flag = False

    def check_task_completion(self):
        incomplete_tasks = []
        for task in self.tasks:
            if task.is_complete and not task.is_paused:
                if task.error:
                    self.pause_all()
                    with self.interrupt_lock:
                        self.pause_flag = True
                    self.error = True
                    self.error_start = time.time()
                    self.listener.update_status(self.ready, self.error)
            else:
                incomplete_tasks.append(task)
        self.tasks = incomplete_tasks

    def pause_all(self):
        # should pause first then flush queue and tasks if required
        self.paused = True
        for task in self.tasks:
            if not task.module_ready:
                task.pause()
        if self.stop_flag:
            self.stop_all()

    def stop_all(self):
        for i in range(len(self.tasks)):
            self.tasks.pop(i)
        with self.q.mutex:
            self.q.queue.clear()

    def resume(self):
        new_q = Queue()
        for cnt, task in enumerate(self.tasks):
            # module's resume method determines appropriate resume command based on module type.
            resume_flag = task.resume()
            if resume_flag is not False:
                for cmd in task.command_dicts:
                    new_q.put(cmd)
            self.tasks.pop(cnt)
        while not self.q.empty():
            command_dict = self.q.get(block=False)
            new_q.put(command_dict)
        self.q = new_q

    def command_module(self, command_dict):
        """
        :param command_dict:dictionary containing module type, module name, command, and other module specific
                parameters
        :return: Boolean - successful/unsuccessful
        """
        try:
            mod_type, name = command_dict['mod_type'], command_dict['module_name']
            command, parameters = command_dict["command"], command_dict["parameters"]
        except KeyError:
            self.write_log("Missing parameters: module type, name, command, parameters", level=logging.WARNING)
            return False
        if mod_type == 'valve':
            return self.command_valve(name, command, parameters, command_dict)
        elif mod_type == 'syringe':
            return self.command_syringe(name, command, parameters, command_dict)
        elif mod_type == 'reactor':
            return self.command_reactor(name, command, parameters, command_dict)
        elif mod_type == 'camera':
            return self.command_camera(name, command, parameters, command_dict)
        elif mod_type == 'wait':
            return self.command_wait(name, command, parameters, command_dict)
        else:
            self.write_log(f'{mod_type} is not recognised', level=logging.WARNING)
            return False

    def command_syringe(self, name, command, parameters, command_dict):
        new_task = Task(command_dict, self.syringes[name])
        self.tasks.append(new_task)
        if command == 'move':
            target = parameters["target"]
            volume = parameters["volume"]
            flow_rate = parameters["flow_rate"]
            direction = parameters["direction"]
            if target is None:
                adj = [key for key in self.graph.adj[name].keys()]
                try:
                    valve = adj[0]
                    valve = self.graph.nodes[valve]['object']
                    parameters['target'] = valve.ports[valve.current_port]
                    target = parameters["target"]
                except KeyError:
                    target = None
            elif isinstance(target, str):
                parameters['target'] = self.find_target(target)
                target = parameters['target']
            cmd_thread = Thread(target=self.syringes[name].move_syringe, name=name + 'move',
                                args=(target, volume, flow_rate, direction, new_task))
        elif command == 'home':
            cmd_thread = Thread(target=self.syringes[name].home, name=name + 'home', args=(new_task,))
        elif command == 'jog':
            cmd_thread = Thread(target=self.syringes[name].jog, name=name + 'jog',
                                args=(parameters['steps'], parameters['direction'], new_task))
        elif command == 'setpos':
            position = parameters['pos']
            cmd_thread = Thread(target=self.syringes[name].set_pos, name=name + 'setpos', args=(position,))
        else:
            self.write_log(f"Command {command} is not recognised", level=logging.WARNING)
            return False
        new_task.add_worker(cmd_thread)
        cmd_thread.start()
        if parameters['wait']:
            self.wait_until_ready()
        self.q.task_done()
        return True

    def command_valve(self, name, command, parameters, command_dict):
        new_task = Task(command_dict, self.valves[name])
        self.tasks.append(new_task)
        if type(command) is int and 0 <= command < 9:
            port = command
            cmd_thread = Thread(target=self.valves[name].move_to_pos, name=name + 'movepos', args=(port,))
        elif command == "target":
            target = parameters["target"]
            cmd_thread = Thread(target=self.valves[name].move_to_target, name=name + "targetmove", args=(target, new_task))
        elif command == 'home':
            cmd_thread = Thread(target=self.valves[name].home_valve, name=name + 'home', args=(new_task,))
        elif command == 'zero':
            cmd_thread = Thread(target=self.valves[name].zero, name=name + 'zero', args=(new_task,))
        elif command == 'jog':
            steps = parameters['steps']
            invert_direction = parameters['invert_direction']
            cmd_thread = Thread(target=self.valves[name].jog, name=name + 'jog', args=(steps, invert_direction, new_task))
        elif command == 'he_sens':
            cmd_thread = Thread(target=self.valves[name].he_read, name=name + 'sens')
        else:
            self.write_log(f"{command} is not a valid command", level=logging.WARNING)
            return False
        new_task.add_worker(cmd_thread)
        cmd_thread.start()
        if parameters['wait']:
            self.wait_until_ready()
        self.q.task_done()
        return True

    def find_target(self, target):
        target_name = target.lower()
        if "syringe" in target_name:
            target = self.syringes.get(target)
            if target is None: 
                for syringe in self.syringes:
                    target = self.syringes[syringe]
                    break
        elif "flask" in target_name:
            target = self.flasks.get(target)
            if target is None: 
                for flask in self.flasks:
                    target = self.flasks[flask]
                    break
        elif "reactor" in target_name:
            target = self.reactors.get(target)
            if target is None: 
                for reactor in self.reactors:
                    target = self.reactors[reactor]
                    break
        elif "camera" in target_name:
            target = self.cameras.get(target)
            if target is None: 
                for camera in self.cameras:
                    target = self.cameras[camera]
                    break
        elif "waste" in target_name:
            target = self.flasks.get(target)
            if target is None: 
                for flask in self.flasks:
                    target = self.flasks.get(flask)
                    break
        return target

    def find_reagent(self, reagent_name):
        reagent_name = reagent_name.lower()
        for flask in self.flasks:
            if self.flasks[flask].contents == reagent_name:
                return self.flasks[flask].name
        return ""

    def command_reactor(self, name, command, parameters, command_dict):
        new_task = Task(command_dict, self.reactors[name], single_action=False)
        self.tasks.append(new_task)
        if command == 'start_stir':
            speed = parameters['speed']
            stir_secs = parameters['stir_secs']
            self.reactors[name].start_stir(speed, stir_secs, new_task)
            self.reactors[name].stir_task = new_task
        elif command == 'stop_stir':
            self.reactors[name].stop_stir(new_task)
        elif command == "start_heat":
            temp = parameters['temp']
            heat_secs = parameters['heat_secs']
            target = parameters['target']
            self.reactors[name].start_heat(temp, heat_secs, target, new_task)
            self.reactors[name].heat_task = new_task
        elif command == 'stop_heat':
            self.reactors[name].stop_heat(new_task)
        else:
            self.write_log(f"{command} is not a valid command", level=logging.WARNING)
            return False
        new_task.add_worker(self.reactors[name].thread)
        if parameters['wait']:
            self.wait_until_ready()
        self.q.task_done()
        return True

    def command_camera(self, name, command, parameters, command_dict):
        new_task = Task(command_dict, self.cameras[name])
        self.tasks.append(new_task)
        if command == "send_img":
            img_num = parameters['img_num']
            img_processing = parameters['img_processing']
            cmd_thread = Thread(target=self.send_image, name=name+'send_image', args=(img_num, img_processing))
        self.write_log(f"Taking image {img_num}", level=logging.INFO)
        new_task.add_worker(cmd_thread)
        cmd_thread.start()
        if parameters['wait']:
            self.wait_until_ready()
        self.q.task_done()
        return True        

    def command_wait(self, name, command, parameters, command_dict):
        new_task = Task(command_dict, name)
        self.tasks.append(new_task)
        wait_reason = parameters['wait_reason']
        if command == 'wait_user':
            self.user_wait_flag = False
            cmd_thread = Thread(target=self.wait_user, name=name+'wait_user', args=())
            self.write_log(f'Waiting for user resume, reason: {wait_reason}', level=logging.INFO)
        elif command == "wait":
            wait_time = parameters['time']
            cmd_thread = Thread(target=self.wait_until, name=name+"wait_until", args=(wait_time,))
            self.write_log(f"Waiting for {wait_time} s, reason: {wait_reason}")
        new_task.add_worker(cmd_thread)
        cmd_thread.start()
        if parameters['wait']:
            self.wait_until_ready()
        self.q.task_done()
        return True

    def wait_until_ready(self):
        with self.interrupt_lock:
            self.waiting = True
    
    def wait_user(self):
        if self.gui_main is not None:
            ans = input('Ready to resume? Press any key')
        else:
            self.gui_main.wait_user()
            while not self.user_wait_flag:
                time.sleep(1)

    def wait_until(self, wait_time):
        start_time = time.time()
        while time.time() - start_time < wait_time:
            time.sleep(1)
        
    def move_liquid(self, source, target, volume, flow_rate, init_move=False):
        """
        Generates all the required commands to move liquid between two points in the robot
        :param source: String - name of the source
        :param target: String - name of the target
        :param volume: Float - volume to be moved (ml)
        :param flow_rate: Int - flow rate in ul/min
        :return: Boolean - successful or unsuccessful
        """
        volume *= 1000
        pipelined_steps = []
        prev_max_vol = 999999.00
        min_vol = 0
        # Returns a simple path from source to target. No nodes are repeated.
        path = self.find_path(source, target)
        if len(path) < 1:
            return False
        # Grab intervening valves between source and target
        valves = path[1:-1]
        #find the dead volume between the source and target
        volume += self.dead_volume(path)*1000
        # Find lowest maximum volume amongst syringes
        for valve in valves:
            cur_max_vol = self.valves[valve].syringe.max_volume
            if cur_max_vol < prev_max_vol:
                max_vol = cur_max_vol
                min_vol = self.valves[valve].syringe.min_volume
        max_volume = max_vol - min_vol
        # Determine number of moves required
        nr_full_moves = int(volume / max_volume)
        remaining_volume = volume % max_volume
        if nr_full_moves >= 1:
            full_move = self.generate_moves(source, target, valves, max_volume, flow_rate, init_move)
            for i in range(0, nr_full_moves):
                pipelined_steps += full_move
        if remaining_volume > 0.0:
            partial_move = self.generate_moves(source, target, valves, remaining_volume, flow_rate, init_move)
            pipelined_steps += partial_move
        self.add_to_queue(pipelined_steps, self.pipeline)
        return True

    def find_path(self, source, target):
        source_found = False
        target_found = False
        if source in self.valid_nodes:
            source_found = True
        if target in self.valid_nodes:
            target_found = True
        if source_found and target_found:
            valid_path = []
            paths = nx.algorithms.all_simple_paths(self.graph, source, target)
            path_list = [p for p in paths]
            if path_list:
                return path_list[0]
        if not source_found:
            self.write_log(f"{source} not present", level=logging.WARNING)
        if not target_found:
            self.write_log(f"{target} not present")
        return []

    def dead_volume(self, path):
        """Find the dead volume between two points in the network along path

        Args:
            path (list): list giving the path that the liquid will follow along the backbone.
        Return:
            dead_volume (float): the dead volume in ml between the 
        """
        def calc_volume(tubing_length):
            #assume 1/16" tubing ID
            mm3 = math.pow((1.5875/2), 2) * math.pi * tubing_length
            return mm3/1000
        # along path, syringe lines, valve-valve lines, and output lines will hold dead volume,
        #  assuming input lines have been primed before operation.
        dead_volume = 0.0
        # get dead volume for intervening nodes between source and target
        for i, node in enumerate(path[1:]):
            if 'syringe' in node:
                tubing_length = self.graph.adj[node][path[i-1]][0]['tubing_length']
                dead_volume += calc_volume(tubing_length)
            elif 'valve' in node:
                if 'valve' in path[i-1]:
                    tubing_length = self.graph.adj[node][path[i-1]][0]['tubing_length']
                    dead_volume += calc_volume(tubing_length)
        tubing_length = self.graph.adj[node][path[i-1]][0]['tubing_length']
        dead_volume += calc_volume(tubing_length)
        return dead_volume

    def generate_moves(self, source, target, valves, volume, flow_rate, init_move=False):
        """
        Generates the moves required to transfer liquid from source to target
        :param source: String - name of the source
        :param target: String - name of the target
        :param valves: List - Intervening valves between source and target
        :param volume: Float - Volume to be moved
        :param flow_rate: Int - Flow rate in ul/min
        :return:
        """
        moves = []
        # Move liquid into first syringe pump
        valve = self.valves[valves[0]]
        source = self.graph.nodes[source]["object"]
        target = self.graph.nodes[target]["object"]
        # does syringe need to fill?
        if not init_move:
            moves += self.generate_sp_move(source, valve, valve.syringe, volume, flow_rate)
        # transfer liquid along backbone
        if len(valves) > 1:
            # Go until second to last valve
            for i in range(len(valves) - 1):
                valve = self.valves[valves[i]]
                next_valve = self.valves[valves[i + 1]]
                moves += self.generate_sp_transfer(valve, next_valve, volume, flow_rate)
        # Move liquid from last syringe pump into target
        valve = self.valves[valves[-1]]
        moves += self.generate_sp_move(valve.syringe, valve, target, volume, flow_rate)
        return moves

    @staticmethod
    def generate_sp_move(source, valve, target, volume, flow_rate):
        """
        Generates the command to dispense or aspirate a syringe
        :return: list of command dicts
        """
        commands = []
        if source.type == "SP":
            direction = "D"
            name = source.name
            valve_target = target
            syringe_target = target
        else:
            direction = "A"
            name = target.name
            valve_target = source
            syringe_target = source
        # Command to index valve to required position
        commands.append({'mod_type': 'valve', 'module_name': valve.name, 'command': 'target',
                         'parameters': {'target': valve_target.name, 'wait': True}})
        # Command to dispense/withdraw syringe
        commands.append({'mod_type': 'syringe', 'module_name': name, 'command': 'move',
                         'parameters': {'volume': volume, 'flow_rate': flow_rate, 'target': syringe_target.name,
                                        'direction': direction, 'wait': True}})
        return commands

    @staticmethod
    def generate_sp_transfer(source_valve, target_valve, volume, flow_rate):
        """
        Generates the commands necessary to transfer liquid between two adjacent valves
        :param source_valve: SelectorValve - source valve object
        :param target_valve: SelectorValve - target valve object
        :param volume: Float - volume to be transferred
        :param flow_rate: Int - flow rate in ul/min
        :return: list of command dicts
        """
        commands = []
        source_port = None
        target_port = None
        #if flow_rate > 
        for adj_valve in source_valve.adj_valves:
            if target_valve.name in adj_valve[0]:
                source_port = adj_valve[1]
        for adj_valve in target_valve.adj_valves:
            if source_valve.name in adj_valve[0]:
                target_port = adj_valve[1]
        if source_port is None or target_port is None:
            return False
        # add commands to index valves to required ports for transfer
        valve_commands = [{'mod_type': 'valve', 'module_name': source_valve.name, 'command': source_port,
                           'parameters': {'wait': True}},
                          {'mod_type': 'valve', 'module_name': target_valve.name, 'command': target_port,
                           'parameters': {'wait': True}}]
        commands += valve_commands
        source_syringe = source_valve.ports[-1]
        target_syringe = target_valve.ports[-1]
        # Command to dispense source syringe into target syringe. Does not signal Manager to wait for completion.
        commands.append({'mod_type': 'syringe', 'module_name': source_syringe.name, 'command': 'move', 'parameters':
            {'volume': volume, 'flow_rate': flow_rate, 'target': target_syringe.name,
             'direction': "D", 'wait': False}})
        # Command to aspirate target syringe to accept contents of source syringe. Signals manager to
        # wait for completion.
        commands.append({'mod_type': 'syringe', 'module_name': target_syringe.name, 'command': 'move', 'parameters':
            {'volume': volume, 'flow_rate': flow_rate, 'target': source_syringe.name,
             'direction': "A", 'wait': True}})
        return commands

    def start_stirring(self, reactor_name, command, speed, stir_secs, wait):
        params = {'speed': speed, "stir_secs": stir_secs, "wait": wait}
        command_dict = Manager.generate_cmd_dict('reactor', reactor_name, command, params)
        self.add_to_queue(command_dict)

    def start_heating(self, reactor_name, command, temp, heat_secs, wait,  target=False):
        """Adds a command to start heating the reactor to the manager queue

        Args:
            reactor_name (str): Name of the reactor to start heating
            command (str): command name (start_heat)
            temp (float): Temperature to heat the reactor to
            heat_secs (int): Time in seconds to heat reactor for. If 0, then reactor will just maintain the set temperature until the Manager's queue is exhausted.
            wait ([type]): [description]
            target (bool, optional): [description]. Defaults to False.
        """
        params = {'temp': temp, 'heat_secs': heat_secs, 'wait': wait, 'target': target}
        command_dict = Manager.generate_cmd_dict('reactor', reactor_name, command, params)
        self.add_to_queue(command_dict)

    def stop_reactor(self, reactor_name, command):
        if command == 'stop_stir':
            command_dict = Manager.generate_cmd_dict('reactor', reactor_name, command, {})
            self.add_to_queue(command_dict)
        elif command == 'stop_heat':
            command_dict = Manager.generate_cmd_dict('reactor', reactor_name, command, {})
            self.add_to_queue(command_dict)
    
    def send_image(self, img_num, img_processing):
        camera = self.cameras['camera1']
        camera.capture_image()
        data = camera.encode_image()
        image_metadata = {'robot_id': self.id, 'robot_key': self.key, 'reaction_id': self.reaction_id, 'img_number': img_num,
                                        'reaction_name': self.reaction_name, 'img_processing': img_processing, 'img_roi': camera.roi}
        response = self.listener.send_image(image_metadata, data)
        # add error checking?
    
    def wait(self, wait_time, actions):
        pic_info = actions.get('picture')
        wait_info = actions.get('wait_user')
        wait_reason = actions.get('wait_reason')
        if wait_reason is None:
            wait_reason = ""
        if pic_info is not None:
            command_dict = Manager.generate_cmd_dict(mod_type='camera', mod_name='camera1', command="send_img",
                                                                             parameters={"img_num": pic_info, 'wait': True})
            self.add_to_queue(command_dict)
        if wait_info is not None:
            command_dict = Manager.generate_cmd_dict(mod_type='wait', mod_name='wait', command="wait_user",
                                                                                    parameters={'wait': True, 'wait_reason': wait_reason})
            self.add_to_queue(command_dict)
        else:
            command_dict = Manager.generate_cmd_dict(mod_type='wait', mod_name='wait', command='wait', 
                                                                                    parameters = {'time': wait_time, 'wait': True, 'wait_reason': wait_reason})
            self.add_to_queue(command_dict)

    @classmethod
    def generate_cmd_dict(cls, mod_type, mod_name, command, parameters):
        return [{'mod_type': mod_type, 'module_name': mod_name, 'command': command,
                 "parameters": parameters}]

    def ensure_reactors_disabled(self):
        for reactor in self.reactors:
            if self.reactors[reactor].heating:
                reactor.stop_heat()
            if self.reactors[reactor].stirring:
                reactor.stop_stir()

class Task:
    """
    Class to represent queued tasks. Primarily used to pause, resume, or stop all queued tasks.
    """

    def __init__(self, command_dict, module, single_action=True):
        self.command_dict = command_dict
        self.command_dicts = [self.command_dict]
        self.module = module
        self.worker = None
        self.single_action = single_action
        self.complete = False
        self.paused = False
        self.error = False
        
    def add_worker(self, thread):
        self.worker = thread

    def pause(self):
        self.command_dict = self.module.stop()
        self.paused = True

    def resume(self):
        resume_flag = self.module.resume(self.command_dicts)
        return resume_flag

    @property
    def is_complete(self):
        if self.single_action:
            if self.worker.is_alive() or self.paused:
                self.complete = False
            else:
                self.complete = True
        return self.complete

    @property
    def is_paused(self):
        return self.paused

    @property
    def module_ready(self):
        return self.module.ready
