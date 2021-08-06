import os
import json
import networkx as nx
import time
from networkx.readwrite.json_graph import node_link_graph
from queue import Queue
from threading import Thread, Lock
from commanduino import CommandManager
from UJ_FB import web_listener
from UJ_FB.Modules import syringepump, selectorvalve, reactor, modules
from UJ_FB import fbexceptions


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
    def __init__(self, gui_main, simulation=False):
        Thread.__init__(self)
        self.name = "Manager"
        self.id = "UJFB1"
        self.gui_main = gui_main
        # get absolute directory of script
        self.script_dir = os.path.dirname(__file__)
        cm_config = os.path.join(self.script_dir, "Configs/cmd_config.json")
        self.cmd_mng = CommandManager.from_configfile(cm_config, simulation)
        self.module_info = self.json_loader("Configs/module_info.json")
        self.prev_run_config = self.json_loader("Configs/running_config.json", object_hook=object_hook_int)
        self.q = Queue()
        self.pipeline = Queue()
        # list to hold current Task objects.
        self.tasks = []
        self.serial_lock = Lock()
        self.interrupt_lock = Lock()
        self.waiting = False
        self.interrupt = False
        self.exit_flag = False
        self.stop_flag = False
        self.pause_flag = False
        self.paused = False
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
        self.listener = web_listener.WebListener(self)
        self.listener.start()
        self.write_running_config("Configs/running_config.json")
        self.rc_changes = False

    def json_loader(self, fp, object_hook=None):
        fp = os.path.join(self.script_dir, fp)
        try:
            with open(fp) as file:
                return json.load(file, object_hook=object_hook)
        except (FileNotFoundError, json.decoder.JSONDecodeError) as e:
            raise fbexceptions.FBConfigurationError(f'The JSON provided {fp} is invalid. \n {e}')

    def write_running_config(self, fp):
        fp = os.path.join(self.script_dir, fp)
        rc_file = open(fp, 'w')
        running_config = json.dumps(self.prev_run_config, indent=4)
        rc_file.write(running_config)
        rc_file.close()

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
            #todo add module_type == camera
        if syringes == 0:
            self.command_gui('write', 'No pumps configured')
            time.sleep(2)
            self.interrupt = True
            self.exit_flag = True
        for valve in self.valves:
            self.valves[valve].init_valve()
        for syringe in self.syringes:
            self.syringes[syringe].init_syringe()

    def check_connections(self):
        # todo update objects from graph config info
        g = self.graph
        valves_list = []
        for n in list(g.nodes):
            if g.degree[n] < 1:
                self.gui_main.write_message(f'Node {n} is not connected to the system!')
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

    def run(self):
        while not self.exit_flag:
            self.check_task_completion()
            with self.interrupt_lock:
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
                pause = self.pause_flag
                waiting = self.waiting
                if self.q.empty():
                    continue
            if not pause:
                if waiting:
                    if not self.tasks:
                        with self.interrupt_lock:
                            self.waiting = False
                else:
                    command_dict = self.q.get()
                    if self.command_module(command_dict):
                        # todo add log of sent command
                        pass
                    else:
                        pass
                        # log failed command
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
            self.gui_main.write_message("That is not a valid JSON file")
            return False
        if overwrite:
            self.pipeline.queue.clear()
        self.add_to_queue(queue_list)

    def start_queue(self):
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
                pass
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
            # todo: change this to a log message
            self.gui_main.write_message("Missing parameters: module type, name, command, parameters")
            return False
        if mod_type == 'valve':
            return self.command_valve(name, command, parameters, command_dict)
        elif mod_type == 'syringe':
            return self.command_syringe(name, command, parameters, command_dict)
        elif mod_type == 'reactor':
            return self.command_reactor(name, command, parameters, command_dict)
        elif mod_type == 'gui':
            message = command_dict['message']
            return self.command_gui(command, message)
        else:
            self.gui_main.write_message(f'{mod_type} is not recognised')
            return False

    def command_gui(self, command, message):
        if command == "write":
            self.gui_main.write_message(message)
        self.q.task_done()

    def command_syringe(self, name, command, parameters, command_dict):
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
                                args=(target, volume, flow_rate, direction))
        elif command == 'home':
            cmd_thread = Thread(target=self.syringes[name].home, name=name + 'home', args=())
        elif command == 'jog':
            cmd_thread = Thread(target=self.syringes[name].jog, name=name + 'jog',
                                args=(parameters['steps'], parameters['direction']))
        elif command == 'setpos':
            position = parameters['pos']
            cmd_thread = Thread(target=self.syringes[name].set_pos, name=name + 'setpos', args=(position,))
        else:
            self.gui_main.write_message(f"Command {command} is not recognised")
            return False
        self.tasks.append(Task(command_dict, self.syringes[name], cmd_thread))
        cmd_thread.start()
        if parameters['wait']:
            self.wait_until_ready()
        self.q.task_done()
        return True

    def find_target(self, target):
        target_name = target.lower()
        if "syringe" in target_name:
            target = self.syringes[target]
        elif "flask" in target_name:
            target = self.flasks[target]
        elif "reactor" in target_name:
            target = self.reactors[target]
        return target

    def command_valve(self, name, command, parameters, command_dict):
        if type(command) is int and 0 <= command < 9:
            port = command
            cmd_thread = Thread(target=self.valves[name].move_to_pos, name=name + 'movepos', args=(port,))
        elif command == "target":
            target = parameters["target"]
            cmd_thread = Thread(target=self.valves[name].move_to_target, name=name + "targetmove", args=(target,))
        elif command == 'home':
            cmd_thread = Thread(target=self.valves[name].home_valve, name=name + 'home', args=())
        elif command == 'zero':
            cmd_thread = Thread(target=self.valves[name].zero, name=name + 'zero', args=())
        elif command == 'jog':
            steps = parameters['steps']
            direction = parameters['direction']
            cmd_thread = Thread(target=self.valves[name].jog, name=name + 'jog', args=(steps, direction))
        elif command == 'he_sens':
            cmd_thread = Thread(target=self.valves[name].he_read, name=name + 'sens')
        else:
            self.gui_main.write_message(f"{command} is not a valid command")
            return False
        self.tasks.append(Task(command_dict, self.valves[name], cmd_thread))
        cmd_thread.start()
        if parameters['wait']:
            self.wait_until_ready()
        self.q.task_done()
        return True

    def command_reactor(self, name, command, parameters, command_dict):
        preheat = parameters['preheat']
        heat_secs = parameters['heat_secs']
        temp = parameters['temp']
        stir_secs = parameters['stir_secs']
        speed = parameters['speed']
        if command == 'heatstir':
            cmd_thread = Thread(target=self.reactors[name].start_reactor, name=name + 'heatstir',
                                args=(preheat, temp, heat_secs, speed, stir_secs))
        elif command == "heat":
            cmd_thread = Thread(target=self.reactors[name].start_reactor, name=name + 'heat',
                                args=(preheat, temp, heat_secs, 0.0, 0.0))
        elif command == 'stir':
            cmd_thread = Thread(target=self.reactors[name].start_reactor, name=name + 'stir',
                                args=(preheat, 0.0, 0.0, speed, stir_secs))
        else:
            self.gui_main.write_message(f"{command} is not a valid command")
            return False
        self.tasks.append(Task(command_dict, self.reactors[name], cmd_thread))
        cmd_thread.start()
        if parameters['wait']:
            self.wait_until_ready()
        self.q.task_done()
        return True

    def wait_until_ready(self):
        with self.interrupt_lock:
            self.waiting = True

    def move_liquid(self, source, target, volume, flow_rate):
        """
        Generates all the required commands to move liquid between two points in the robot
        :param source: String - name of the source
        :param target: String - name of the target
        :param volume: Float - volume to be moved
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
            full_move = self.generate_moves(source, target, valves, max_volume, flow_rate)
            for i in range(0, nr_full_moves):
                pipelined_steps += full_move
        if remaining_volume > 0.0:
            partial_move = self.generate_moves(source, target, valves, remaining_volume, flow_rate)
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
            self.gui_main.write_message(f"{source} not present")
        if not target_found:
            self.gui_main.write_message(f"{target} not present")
        return []

    def generate_moves(self, source, target, valves, volume, flow_rate):
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
        moves += self.generate_sp_move(source, valve, valve.syringe, volume,
                                       flow_rate)
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

    @classmethod
    def generate_cmd_dict(cls, mod_type, mod_name, command, parameters):
        return [{'mod_type': mod_type, 'module_name': mod_name, 'command': command,
                 "parameters": parameters}]


class Task:
    """
    Class to represent queued tasks. Primarily used to pause, resume, or stop all queued tasks.
    """

    def __init__(self, command_dict, module, thread):
        self.command_dict = command_dict
        self.command_dicts = [self.command_dict]
        self.module = module
        self.worker = thread
        self.complete = False
        self.paused = False

    def pause(self):
        self.command_dict = self.module.stop()
        self.paused = True

    def wait_for_completion(self):
        self.worker.join()

    def resume(self):
        resume_flag = self.module.resume(self.command_dicts)
        return resume_flag

    @property
    def is_complete(self):
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
