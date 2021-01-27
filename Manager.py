import os
import json
from fbexceptions import *
from commanduino import CommandManager
from Modules.syringePump import SyringePump
from Modules.selectorValve import SelectorValve


class Manager:
    def __init__(self, simulation=False):
        self.script_dir = os.path.dirname(__file__)  # get absolute directory of script
        cm_config = os.path.join(self.script_dir, "Configs/cmd_config.json")
        self.cmd_mng = CommandManager.from_configfile(cm_config, simulation)
        self.module_info = self.json_loader("Configs/module_info.json")
        # module_info = {module_name:device_dict}
        # device dict = {device_name: {"cmd_id": "cmid", "config":{}}
        self.connections = self.json_loader("Configs/module_connections.json")
        # connections = {valve_name : { 1: conn_module/reagent, 2: conn_module/reagent, ..}
        self.valves = {}
        self.syringes = {}
        self.reactors = {}
        self.modules = []
        # list of all connected modules
        self.populate_modules()

    def populate_modules(self):
        for module_name in self.module_info.keys():
            if "valve" in module_name:
                self.add_valve(module_name)
            elif "syringe" in module_name:
                self.add_syringe(module_name)
            elif "reactor" in module_name:
                self.add_reactor(module_name)
        self.modules = list(self.valves.keys()) + list(self.syringes.keys()) + list(self.reactors.keys())

    def add_valve(self, valve_name):
        valve_info = self.module_info[valve_name]
        self.valves[valve_name] = SelectorValve(valve_name, valve_info, self.cmd_mng)

    def add_syringe(self, syringe_name):
        syr_info = self.module_info[syringe_name]
        self.syringes[syringe_name] = SyringePump(syringe_name, syr_info, self.cmd_mng)

    def add_reactor(self, reactor):
        pass

    def json_loader(self, fp):
        fp = os.path.join(self.script_dir, fp)
        try:
            with open(fp) as file:
                return json.load(file)
        except (FileNotFoundError, json.decoder.JSONDecodeError) as e:
            raise FBConfigurationError(f'The JSON provided {fp} is invalid. \n {e}')

    def command_module(self, gui, command_dict):
        """
        :param gui: the GUI calling this function
        :param command_dict:dictionary containing module type, module name, command, and other module specific
                parameters
        :return: Boolean - successful/unsuccessful
        """
        try:
            mod_type, name = command_dict['module_type'], command_dict['module_name']
        except KeyError:
            gui.write_message("Missing parameters: module type, name")
            return False
        if name not in self.modules:
            gui.write_message(f"{name} is not present in the Manager")
            return False
        if mod_type == 'syringe':
            self.command_syringe(gui, command_dict)
        elif mod_type == 'valve':
            self.command_valve(gui, command_dict)
        else:
            gui.write_message(f'{mod_type} is not recognised')

    def command_syringe(self, gui, command_dict, name):
        try:
            command, vol, flow = command_dict['command'], command_dict['volume'], command_dict['flow_rate']
        except KeyError:
            gui.write_message("Required parameters not present, required: command, volume, flow rate")
            return False
        if command == 'aspirate':
            return self.syringes[name].move_syringe(vol, flow, True)
        elif command == 'withdraw':
            return self.syringes[name].move_syringe(vol, flow, False)
        else:
            gui.write_message(f"Command {command} is not recognised")
            return False

    def command_valve(self, gui, command_dict, name, command):
        if type(command) is not int or command < 0 or command > 9:
            gui.write_message(f"{command} is not a valid port")
            return False
        if command == 0:
            self.valves[name].home_valve()
            return True
        else:
            self.valves[name].move_to_pos(command)
            return True

