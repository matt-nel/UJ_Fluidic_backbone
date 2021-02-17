import os
import json
from threading import Thread, Lock
from fbexceptions import *
from commanduino import CommandManager
from Modules.syringePump import SyringePump
from Modules.selectorValve import SelectorValve


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
        self.connections = self.json_loader("Configs/module_connections.json")
        # connections = {valve_name : { 'inlet': 'syringe_name', 1: conn_module/reagent, 2: conn_module/reagent, ..}
        self.serial_lock = Lock()
        self.input_buffer = {}
        self.command_dict = {}
        self.input_buffer_lock = Lock()
        self.interrupt = False
        self.exit = False
        # list of threads for purposes of stopping all
        self.threads = []
        self.valves = {}
        self.syringes = {}
        self.reactors = {}
        self.modules = ['Manager']
        # list of all connected modules
        self.populate_modules()
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
            if "valve" in module_name:
                valve_info = self.module_info[module_name]
                self.valves[module_name] = SelectorValve(module_name, valve_info, self.cmd_mng, self)
            elif "syringe" in module_name:
                syr_info = self.module_info[module_name]
                self.syringes[module_name] = SyringePump(module_name, syr_info, self.cmd_mng, self)
            elif "reactor" in module_name:
                pass
        all_modules = list(self.valves.keys()) + list(self.syringes.keys()) + list(self.reactors.keys())
        self.modules += all_modules

    def check_connections(self):
        for key in self.connections.keys():
            if key not in self.valves.keys():
                self.gui_main.write_message(f'{key} is not present in the manager configuration')

    def run(self):
        while not self.interrupt:
            self.read_input_buffer()
            if self.command_dict:
                if self.command_module(self.command_dict):
                    # todo add log of sent command
                    pass
                else:
                    pass
                    # log failed command

                self.command_dict = {}
            for thread in self.threads:
                if not thread.is_alive():
                    self.threads.pop(self.threads.index(thread))
        if self.exit:
            for thread in self.threads:
                thread.join()
            self.cmd_mng.commandhandlers[0].stop()

    def read_input_buffer(self):
        with self.input_buffer_lock:
            if self.input_buffer:
                self.command_dict = self.input_buffer
                self.input_buffer = {}

    def write_input_buffer(self, command_dict):
        with self.input_buffer_lock:
            if self.input_buffer:
                return False
            else:
                self.input_buffer = command_dict
                return True

    def command_module(self, command_dict):
        """
        :param command_dict:dictionary containing module type, module name, command, and other module specific
                parameters
        :return: Boolean - successful/unsuccessful
        """
        try:
            mod_type, name = command_dict['module_type'], command_dict['module_name']
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
            return True
        elif command == 'withdraw':
            with_thread = Thread(target=self.syringes[name].move_syringe, name=name, args=(vol, flow, True))
            with_thread.start()
            self.threads.append(with_thread)
            return True
        elif command == 'home':
            home_thread = Thread(target=self.syringes[name].home, name=name, args=())
            home_thread.start()
            self.threads.append(home_thread)
            return True
        elif command == 'jog':
            steps = parameters['steps']
            if parameters['direction'] == 'aspirate':
                direction = False
            else:
                direction = True
            jog_thread = Thread(target=self.syringes[name].jog, name=name, args=(steps, direction))
            jog_thread.start()
            self.threads.append(jog_thread)
            return True
        else:
            self.gui_main.write_message(f"Command {command} is not recognised")
            return False

    def command_valve(self, name, command, parameters):
        if type(command) is int and 0 <= command < 9:
            valve_thread = Thread(target=self.valves[name].move_to_pos, name=name, args=(command,))
            valve_thread.start()
            self.threads.append(valve_thread)
            return True
        else:
            self.gui_main.write_message(f"{command} is not a valid port")
            return False

