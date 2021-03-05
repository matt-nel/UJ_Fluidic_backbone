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
        self.syringes = {}
        self.reactors = {}
        self.flasks = {}
        self.modules = ['Manager']
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
        for module_name in self.module_info.keys():
            module_type = self.module_info[module_name]['mod_type']
            if module_type == "valve":
                valve_info = self.module_info[module_name]
                self.valves[module_name] = SelectorValve(module_name, valve_info, self.cmd_mng, self)
            elif module_type == "syringe":
                syr_info = self.module_info[module_name]
                self.syringes[module_name] = SyringePump(module_name, syr_info, self.cmd_mng, self)
            elif module_type == "reactor":
                pass

        all_modules = list(self.valves.keys()) + list(self.syringes.keys()) + list(self.reactors.keys())
        self.modules += all_modules

    def check_connections(self):
        g = self.graph
        for n in list(g.nodes):
            if g.degree[n] < 1:
                self.gui_main.write_message(f'Node {n} is not connected to the system!')
            else:
                name = g.nodes[n]['name']
                mod_type = g.nodes[n]['type']
                if 'syringe' in mod_type:
                    g.nodes[n]['obj'] = self.syringes[name]
                elif 'valve' in mod_type:
                    g.nodes[n]['obj'] = self.valves[name]
                elif 'flask' in mod_type:
                    config_dict = dict(g.nodes[n].items())
                    self.flasks[name] = FBFlask(config_dict)
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
                    syr_command_dict = dict(g.nodes[group_source])
                    syr_command_dict['command'] = 'aspirate'
                    syr_command_dict['parameters']['target'] = group_target
                else:
                    syr_command_dict = dict(g.nodes[group_target])
                    syr_command_dict['command'] = 'withdraw'
                    syr_command_dict['parameters']['target'] = group_source
                for i, step in enumerate(step_group[1:-1]):
                    prev_node = step_group[i-1]
                    follow_node = step_group[i+1]
                    req_port = g.edges[prev_node, follow_node]['port'][1]
                    valve_command_dict = dict(g.nodes[step])
                    valve_command_dict['command'] = req_port
                    valve_command_dict['parameters'] = {'wait': True}
                    pipelined_steps.append(valve_command_dict)
                if volume > syr_command_dict['Maximum volume']:
                    vol_to_move = syr_command_dict['Maximum volume']
                else:
                    vol_to_move = volume
                syr_command_dict['flow_rate'] = flow_rate
                pipelined_steps.append(syr_command_dict)
            volume -= vol_to_move
        self.add_to_queue(pipelined_steps)
        return True

    def find_path(self, source, target):
        paths = nx.algorithms.all_simple_paths(self.graph, source, target)
        pathlist = [p for p in paths]
        valid_paths = []
        for p in pathlist:
            for step in p:
                if 'syringe' in step:
                    valid_paths.append(p)
                    break
        return valid_paths

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
        if name not in self.modules:
            self.gui_main.write_message(f"{name} is not present in the Manager")
            return False
        if mod_type == 'syringe':
            return self.command_syringe(name, command, parameters)
        elif mod_type == 'valve':
            return self.command_valve(name, command, parameters)
        elif mod_type == 'gui':
            return self.command_gui(command, parameters)
        elif mod_type == 'manager':
            if command == 'interrupt':
                self.interrupt = True
                if parameters['exit']:
                    self.exit = True
        else:
            self.gui_main.write_message(f'{mod_type} is not recognised')
            return False

    def command_gui(self, command, parameters):
        if command == "write":
            self.gui_main.write_message(parameters)

    def command_syringe(self, name, command, parameters):
        try:
            vol, flow = parameters['volume'], parameters['flow_rate']
        except KeyError:
            self.gui_main.write_message("Required parameters not present, required: volume, flow rate")
            return False
        if command == 'aspirate':
            asp_thread = Thread(target=self.syringes[name].move_syringe, name=name, args=(vol, flow, False))
            asp_thread.start()
            self.threads.append(asp_thread)
        elif command == 'withdraw':
            with_thread = Thread(target=self.syringes[name].move_syringe, name=name, args=(vol, flow, True))
            with_thread.start()
            self.threads.append(with_thread)
        elif command == 'home':
            home_thread = Thread(target=self.syringes[name].home, name=name, args=())
            home_thread.start()
            self.threads.append(home_thread)
        elif command == 'jog':
            steps = parameters['steps']
            if parameters['direction'] == 'aspirate':
                direction = False
            else:
                direction = True
            jog_thread = Thread(target=self.syringes[name].jog, name=name, args=(steps, direction))
            jog_thread.start()
            self.threads.append(jog_thread)
        else:
            self.gui_main.write_message(f"Command {command} is not recognised")
            return False
        if parameters['wait']:
            if not self.syringes[name].ready:
                time.sleep(0.2)
        return True

    def command_valve(self, name, command, parameters):
        if type(command) is int and 0 <= command < 9:
            valve_thread = Thread(target=self.valves[name].move_to_pos, name=name, args=(command,))
            valve_thread.start()
            self.threads.append(valve_thread)
            if parameters['wait']:
                self.wait_until_ready(self.valves[name])
            return True
        elif command == 'zero':
            valve_thread = Thread(target=self.valves[name].zero, name=name, args=())
            valve_thread.start()
            self.threads.append(valve_thread)
            if parameters['wait']:
                self.wait_until_ready(self.valves[name])
        elif command == 'jog':
            direction = parameters['direction']
            steps = parameters['steps']
            valve_thread=Thread(target=self.valves[name].jog, name=name, args=(steps, direction))
            valve_thread.start()
            self.threads.append(valve_thread)
            if parameters['wait']:
                self.wait_until_ready(self.valves[name])
        else:
            self.gui_main.write_message(f"{command} is not a valid port")
            return False

    @staticmethod
    def wait_until_ready(self, obj):
        if not obj.ready:
            time.sleep(0.2)

