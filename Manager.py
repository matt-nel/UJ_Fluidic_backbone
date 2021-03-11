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
from Modules.Module import FBFlask
from fbexceptions import *


def load_graph(graph_config):
    graph = node_link_graph(graph_config, directed=True, multigraph=True)
    return graph


class Manager(Thread):
    def __init__(self, gui_main, simulation=False):
        Thread.__init__(self)
        self.name = "Manager"
        self.gui_main = gui_main
        self.script_dir = os.path.dirname(__file__)  # get absolute directory of script
        cm_config = os.path.join(self.script_dir, "Configs/cmd_config.json")
        self.cmd_mng = CommandManager.from_configfile(cm_config, simulation)
        self.module_info = self.json_loader("Configs/module_info.json")
        # module_info = {module_name:device_dict}
        # device dict = {device_name: {"cmd_id": "cmid", "config":{}}
        graph_config = self.json_loader("Configs/module_connections.json")
        # connections = {valve_name : { 'inlet': 'syringe_name', 1: conn_module/reagent, 2: conn_module/reagent, ..}
        self.q = Queue()
        self.serial_lock = Lock()
        self.interrupt = False
        self.exit = False
        # list of threads for purposes of stopping all
        self.threads = []
        self.valves = {}
        self.num_valves = 0
        self.syringes = {}
        self.reactors = {}
        self.flasks = {}
        # list of all connected modules
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
            if module_type == "valve":
                self.num_valves += 1
                valve_info = self.module_info[module_name]
                self.valves[module_name] = SelectorValve(module_name, valve_info, self.cmd_mng, self)
            elif module_type == "syringe":
                syringes += 1
                syr_info = self.module_info[module_name]
                self.syringes[module_name] = SyringePump(module_name, syr_info, self.cmd_mng, self)
            elif module_type == "reactor":
                pass
        if syringes == 0:
            self.command_gui('write', 'No pumps configured')
            time.sleep(2)
            self.interrupt = True
            self.exit = True

    def check_connections(self):
        # todo update objects from graph config info
        g = self.graph
        for n in list(g.nodes):
            if g.degree[n] < 1:
                self.gui_main.write_message(f'Node {n} is not connected to the system!')
            else:
                name = g.nodes[n]['name']
                mod_type = g.nodes[n]['type']
                if 'syringe' in mod_type:
                    g.nodes[n]['obj'] = self.syringes[name]
                    self.syringes[name].change_contents(g.nodes[n]['Contents'], g.nodes[n]['Current volume'])
                elif 'valve' in mod_type:
                    g.nodes[n]['obj'] = self.valves[name]
                elif 'flask' in mod_type:
                    config_dict = dict(g.nodes[n].items())
                    self.flasks[name] = FBFlask(self, config_dict)
                    g.nodes[n]['obj'] = self.flasks[name]
                elif 'reactor' in mod_type:
                    g.nodes[n]['obj'] = self.reactors[name]

    def run(self):
        while not self.interrupt:
            if self.q.empty():
                time.sleep(0.1)
            else:
                command_dict = self.q.get()
                if self.command_module(command_dict):
                    # todo add log of sent command
                    pass
                else:
                    pass
                    # log failed command
                for thread in self.threads:
                    if not thread.is_alive():
                        self.threads.pop(self.threads.index(thread))
        if self.exit:
            for thread in self.threads:
                thread.join()
            self.cmd_mng.commandhandlers[0].stop()

    def add_to_queue(self, commands):
        for command in commands:
            self.q.put(command)

    def move_liquid(self, source, target, volume, flow_rate):
        # currently a single path will be returned containing at least 1 syringe
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
            step_groups = path
        while volume > 0:
            vol_to_move = 0
            for num, step_group in enumerate(step_groups):
                group_source = step_group[0]
                group_target = step_group[-1]
                if g.nodes[group_source]['type'] == 'syringe':
                    syr_name = group_source
                    withdraw = False
                else:
                    syr_name = g.nodes[group_target]['name']
                    withdraw = True
                syringe_target = g.nodes[syr_name]['obj']
                syringe_max_vol = g.nodes[syr_name]['Maximum volume']
                syr_command_dict = {'mod_type': 'syringe', 'module_name': syr_name, 'command': 'move', 'max_vol': syringe_max_vol, 'parameters': {}}
                for i, step in enumerate(step_group[1:-1]):
                    prev_node = step_group[i-1]
                    follow_node = step_group[i+1]
                    req_port = g.edges[prev_node, follow_node]['port'][1]
                    valve_command_dict = dict(g.nodes[step])
                    valve_command_dict['command'] = req_port
                    valve_command_dict['parameters'] = {'wait': True}
                    pipelined_steps.append(valve_command_dict)
                if volume > syr_command_dict['max_vol']:
                    vol_to_move = syr_command_dict['max_vol']
                else:
                    vol_to_move = volume
                parameters = {'volume': vol_to_move, 'flow_rate': flow_rate, 'target': syringe_target, 'withdraw': withdraw, 'wait':True}
                syr_command_dict['parameters'] = parameters
                pipelined_steps.append(syr_command_dict)
            volume -= vol_to_move
        self.add_to_queue(pipelined_steps)
        return True

    def find_path(self, source, target):
        valid_path = []
        if self.num_valves < 2:
            path = nx.algorithms.all_simple_paths(self.graph, source, target)
            path = next(path)
            valve = path[1]
            for node in self.graph.adj[valve]:
                if 'syringe' in node:
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
            return self.command_valve(name, command, parameters)
        elif mod_type == 'syringe':
            return self.command_syringe(name, command, parameters)
        elif mod_type == 'gui':
            message = command_dict['message']
            return self.command_gui(command, message)
        elif mod_type == 'manager':
            if command == 'interrupt':
                self.interrupt = True
                if parameters['exit']:
                    self.exit = True
        else:
            self.gui_main.write_message(f'{mod_type} is not recognised')
            return False

    def command_gui(self, command, message):
        if command == "write":
            self.gui_main.write_message(message)

    def command_syringe(self, name, command, parameters):
        if command == 'move':
            cmd_thread = Thread(target=self.syringes[name].move_syringe, name=name, args=(parameters,))
        elif command == 'home':
            cmd_thread = Thread(target=self.syringes[name].home, name=name, args=())
        elif command == 'jog':
            cmd_thread = Thread(target=self.syringes[name].jog, name=name, args=(parameters['steps'], parameters['withdraw']))
        elif command == 'setpos':
            cmd_thread = Thread(target=self.syringes[name].set_pos, name=name, args=(parameters['pos'],))
        else:
            self.gui_main.write_message(f"Command {command} is not recognised")
            return False
        cmd_thread.start()
        self.threads.append(cmd_thread)
        if parameters['wait']:
            if not self.syringes[name].ready:
                time.sleep(0.2)
        return True

    def command_valve(self, name, command, parameters):
        if type(command) is int and 0 <= command < 9:
            cmd_thread = Thread(target=self.valves[name].move_to_pos, name=name, args=(command,))
        elif command == 'zero':
            cmd_thread = Thread(target=self.valves[name].zero, name=name, args=())
        elif command == 'jog':
            cmd_thread = Thread(target=self.valves[name].jog, name=name, args=(parameters['steps'], parameters['direction']))
        elif command == 'he_sens':
            cmd_thread = Thread(target=self.valves[name].he_read, name=name)
        else:
            self.gui_main.write_message(f"{command} is not a valid command")
            return False
        cmd_thread.start()
        self.threads.append(cmd_thread)
        if parameters['wait']:
            self.wait_until_ready(self.valves[name])
        return True

    @staticmethod
    def wait_until_ready(obj):
        if not obj.ready:
            time.sleep(0.2)

