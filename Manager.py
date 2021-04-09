import os
import json
import networkx as nx
import time
from networkx.readwrite.json_graph import node_link_graph
from queue import Queue
from threading import Thread, Lock
from commanduino import CommandManager
from Modules.syringePump import SyringePump
from Modules.selectorValve import SelectorValve
from Modules.modules import FBFlask
from fbexceptions import *


def load_graph(graph_config):
    graph = node_link_graph(graph_config, directed=True, multigraph=True)
    return graph


class Manager(Thread):
    def __init__(self, gui_main, simulation=False):
        Thread.__init__(self)
        self.name = "Manager"
        self.gui_main = gui_main
        # get absolute directory of script
        self.script_dir = os.path.dirname(__file__)
        cm_config = os.path.join(self.script_dir, "Configs/cmd_config.json")
        self.cmd_mng = CommandManager.from_configfile(cm_config, simulation)
        self.module_info = self.json_loader("Configs/module_info.json")
        graph_config = self.json_loader("Configs/module_connections.json")
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
        self.valves = {}
        self.num_valves = 0
        self.syringes = {}
        self.reactors = {}
        self.flasks = {}
        self.populate_modules()
        self.graph = load_graph(graph_config)
        self.check_connections()

    def json_loader(self, fp):
        fp = os.path.join(self.script_dir, fp)
        try:
            with open(fp) as file:
                return json.load(file)
        except (FileNotFoundError, json.decoder.JSONDecodeError) as e:
            raise FBConfigurationError(f'The JSON provided {fp} is invalid. \n {e}')

    def populate_modules(self):
        syringes = 0
        for module_name in self.module_info.keys():
            module_type = self.module_info[module_name]['mod_type']
            module_info = self.module_info[module_name]
            if module_type == "valve":
                self.num_valves += 1
                self.valves[module_name] = SelectorValve(module_name, module_info, self.cmd_mng, self)
            elif module_type == "syringe":
                syringes += 1
                self.syringes[module_name] = SyringePump(module_name, module_info, self.cmd_mng, self)
            elif module_type == "reactor":
                pass
            elif module_type == "flask":
                self.flasks[module_name] = FBFlask(module_name, module_info, self.cmd_mng, self)
        if syringes == 0:
            self.command_gui('write', 'No pumps configured')
            time.sleep(2)
            self.interrupt = True
            self.exit_flag = True

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
                if 'syringe' in mod_type:
                    syringe = self.syringes[name]
                    node = g.nodes[n]
                    node['object'] = syringe
                    syringe.set_volume(node['Maximum volume'])
                    syringe.change_contents(node['Contents'], float(node['Current volume'])*1000)
                    syringe.set_pos(node['Current volume'])
                elif 'valve' in mod_type:
                    valves_list.append(n)
                elif 'flask' in mod_type:
                    g.nodes[n]['object'] = self.flasks[name]
                elif 'reactor' in mod_type:
                    g.nodes[n]['object'] = self.reactors[name]
        for valve in valves_list:
            name = g.nodes[valve]['name']
            g.nodes[valve]['object'] = self.valves[name]
            for node_name in g.adj[valve]:
                port = g.adj[valve][node_name][0]['port'][1]
                self.valves[name].ports[port]['name'] = node_name
                self.valves[name].ports[port]['object'] = g.nodes[node_name]['object']

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
                if self.q.empty():
                    continue
                elif not self.pause_flag:
                    if self.waiting:
                        if not self.tasks:
                            self.waiting = False
                    else:
                        command_dict = self.q.get()
                        if self.command_module(command_dict):
                            # todo add log of sent command
                            pass
                        else:
                            pass
                            # log failed command
        self.pause_all()
        self.cmd_mng.commandhandlers[0].stop()

    @staticmethod
    def add_to_queue(commands, queue):
        for command in commands:
            queue.put(command)

    def start_queue(self):
        with self.interrupt_lock:
            self.pause_flag = True
        while not self.pipeline.empty():
            command_dict = self.pipeline.get(block=False)
            self.q.put(command_dict)
        self.pipeline.queue.clear()
        with self.interrupt_lock:
            self.pause_flag = False

    def check_task_completion(self):
        complete_tasks = []
        for cnt, task in enumerate(self.tasks):
            if task.is_complete and not task.is_paused:
                complete_tasks.append(cnt)
        for index in complete_tasks:
            self.tasks.pop(index)

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

    def move_liquid(self, source, target, volume, flow_rate):
        # currently a single path will be returned containing at least 1 syringe
        volume *= 1000
        g = self.graph
        pipelined_steps = []
        path = self.find_path(source, target)
        if len(path) == 0:
            return False
        syr_index = None
        index = 0
        step_groups = []
        for index, step in enumerate(path):
            if 'syringe' in step:
                syr_index = index
        if index > syr_index:
            step_groups.append(path[0:syr_index+1])
            step_groups.append(path[syr_index:])
        else:
            step_groups = [path]
        while volume > 0:
            vol_to_move = 0
            for num, step_group in enumerate(step_groups):
                group_source = step_group[0]
                group_target = step_group[-1]
                if g.nodes[group_source]['mod_type'] == 'syringe':
                    syr_name = group_source
                    withdraw = False
                    syr_source = True
                    syr_target = g.nodes[group_target]['object']
                else:
                    syr_name = g.nodes[group_target]['name']
                    withdraw = True
                    syr_source = False
                    syr_target = g.nodes[group_source]['object']

                syringe_max_vol = float(g.nodes[syr_name]['Maximum volume'])*1000
                syringe_min_vol = float(g.nodes[syr_name]['Minimum volume'])*1000
                syr_command_dict = {'mod_type': 'syringe', 'module_name': syr_name, 'command': 'move',
                                    'max_vol': syringe_max_vol, 'min_vol': syringe_min_vol, 'parameters': {}}
                if syr_source:
                    upper = -1
                    lower = 1
                else:
                    upper = -2
                    lower = 0
                for i, step in enumerate(step_group[lower:upper]):
                    node = step_group[lower + i]
                    follow_node = step_group[lower + i + 1]
                    if 'syringe' != node[:-1] and 'syringe' != follow_node[:-1]:
                        port = g.edges[node, follow_node, 0]['port']
                        valve_name = f'valve{port[0]+1}'
                        req_port = port[1]
                        valve_command_dict = {'mod_type': 'valve', 'module_name': valve_name, 'command': req_port,
                                              'parameters': {'wait': True}}
                        pipelined_steps.append(valve_command_dict)
                max_movable = syr_command_dict['max_vol'] - syr_command_dict['min_vol']
                if volume > max_movable:
                    vol_to_move = max_movable
                else:
                    vol_to_move = volume
                syr_command_dict['parameters'] = {'volume': vol_to_move, 'flow_rate': flow_rate, 'target': syr_target, 'withdraw': withdraw, 'wait': True}
                pipelined_steps.append(syr_command_dict)
            volume -= vol_to_move
        self.add_to_queue(pipelined_steps, self.pipeline)
        return True

    def find_path(self, source, target):
        valid_path = []
        if self.num_valves < 2:
            path = nx.algorithms.all_simple_paths(self.graph, source, target)
            path = next(path)
            valve = path[1]
            for node in self.graph.adj[valve]:
                if 'syringe' in node and 'syringe' not in target:
                    last_step = path.pop(2)
                    path.append(node)
                    path.append(valve)
                    path.append(last_step)
                    break
            valid_path = path
        else:
            paths = nx.algorithms.all_simple_paths(self.graph, source, target)
            path_list = [p for p in paths]
            for p in path_list:
                for step in p:
                    if 'syringe' in step:
                        valid_paths = p
                        break
        return valid_path

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
            if parameters['target'] is None:
                adj = [key for key in self.graph.adj[name].keys()]
                valve = adj[0]
                valve = self.graph.nodes[valve]['object']
                try:
                    parameters['target'] = valve.port_objects[valve.current_port]
                    cmd_thread = Thread(target=self.syringes[name].move_syringe, name=name+'move', args=(parameters,))
                except KeyError:
                    self.gui_main.write_message('Please set valve position or home valve')
                    return False
            else:
                cmd_thread = Thread(target=self.syringes[name].move_syringe, name=name+'move', args=(parameters,))
        elif command == 'home':
            cmd_thread = Thread(target=self.syringes[name].home, name=name+'home', args=())
        elif command == 'jog':
            cmd_thread = Thread(target=self.syringes[name].jog, name=name+'jog', args=(parameters['steps'], parameters['withdraw']))
        elif command == 'setpos':
            cmd_thread = Thread(target=self.syringes[name].set_pos, name=name+'setpos', args=(parameters['pos'],))
        else:
            self.gui_main.write_message(f"Command {command} is not recognised")
            return False
        self.tasks.append(Task(command_dict, self.syringes[name], cmd_thread))
        cmd_thread.start()
        if parameters['wait']:
            self.waiting = True
        self.q.task_done()
        return True

    def command_valve(self, name, command, parameters, command_dict):
        if type(command) is int and 0 <= command < 9:
            cmd_thread = Thread(target=self.valves[name].move_to_pos, name=name+'movepos', args=(command,))
        elif command == 'home':
            cmd_thread = Thread(target=self.valves[name].home_valve, name=name+'home', args=())
        elif command == 'zero':
            cmd_thread = Thread(target=self.valves[name].zero, name=name+'zero', args=())
        elif command == 'jog':
            cmd_thread = Thread(target=self.valves[name].jog, name=name+'jog', args=(parameters['steps'], parameters['direction']))
        elif command == 'he_sens':
            cmd_thread = Thread(target=self.valves[name].he_read, name=name+'sens')
        else:
            self.gui_main.write_message(f"{command} is not a valid command")
            return False
        self.tasks.append(Task(command_dict, self.valves[name], cmd_thread))
        cmd_thread.start()
        if parameters['wait']:
            self.waiting = True
        self.q.task_done()
        return True

    def command_reactor(self, name, command, parameters, command_dict):
        if command == "heat":
            heat_secs = parameters['heat_secs']
            temp = parameters['temp']
            cmd_thread = Thread(target=self.reactors[name].start_reactor, name=name+'heat',
                                args=(temp, heat_secs, 0.0, 0.0))
        elif command == 'stir':
            stir_secs = parameters['stir_secs']
            speed = parameters['speed']
            cmd_thread = Thread(target=self.reactors[name].start_reactor, name=name+'stir',
                                args=(0.0, 0.0, speed, stir_secs))


class Task:
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
