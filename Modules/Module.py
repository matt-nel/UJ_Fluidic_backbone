from Devices.stepperMotor import StepperMotor, LinearStepperMotor
from Devices.device import Device
from threading import Lock


class Module:
    """
    Class for representing generic modules. __init__ associates attached devices and creates attributes having those
    names.
    """
    def __init__(self, module_info, cmduino, manager):
        """
        :param module_info: dictionary containing device info for module and configuration info for module.
        :param cmduino: commanduino object that deals with low-level commands to Arduino.
        """
        # todo add method for adding modules after initialisation.
        assoc_devices = module_info["devices"]
        self.steppers = []
        self.endstops = []
        self.he_sensors = []
        self.manager = manager
        self.lock = Lock()
        self.ready = True
        for item in assoc_devices.keys():
            if 'stepper' in item:
                # stepper dict: {..."stepper" : [ "cmd_stepper", "cmd_enabler"]...}
                stepper = getattr(cmduino, assoc_devices[item]["name"])
                enable_pin = getattr(cmduino, assoc_devices[item]["enable_pin"])
                if module_info["mod_config"]["linear_stepper"]:
                    self.steppers.append(LinearStepperMotor(stepper, enable_pin, assoc_devices[item]["device_config"],
                                                            manager.serial_lock))
                else:
                    self.steppers.append(StepperMotor(stepper, enable_pin, assoc_devices[item]["device_config"],
                                                      manager.serial_lock))
            if 'endstop' in item:
                endstop = getattr(cmduino, assoc_devices[item]["cmd_id"])
                self.endstops.append(Device(endstop, manager.serial_lock))
            if 'he_sens' in item:
                he_sens = getattr(cmduino, assoc_devices[item]["cmd_id"])
                self.he_sensors.append(Device(he_sens, manager.serial_lock))

    def write_to_gui(self, message):
        command_dict = {'mod_type': 'gui', 'module_name': 'gui', 'command': 'write', 'message': message, 'parameters': {}}
        self.manager.q.put(command_dict)


class FBFlask:
    """
    Class to represent flasks in the fluidic backbone.
    """
    def __init__(self, manager, module_info):
        self.name = module_info['Name']
        self.manager = manager
        self.contents = module_info['Contents']
        self.contents_hist = []
        self.cur_vol = float(module_info['Current volume'])*1000
        self.max_vol = float(module_info['Maximum volume'])*1000

    def change_volume(self, vol):
        if self.check_vol(vol):
            self.cur_vol += vol
            if self.cur_vol == 0:
                self.contents = 'empty'
            return True
        return False

    def check_vol(self, vol):
        if self.cur_vol + vol > self.max_vol:
            self.write_to_gui(f'Max volume of {self.name} would be exceeded')
            return False
        elif self.cur_vol + vol < 0:
            self.write_to_gui(f'Insufficient {self.contents} in {self.name}')
            return False
        return True

    def change_contents(self, new_contents, vol):
        if self.change_vol(vol):
            self.contents_hist.append(self.contents)
            self.contents = new_contents

    def write_to_gui(self, message):
        command_dict = {'mod_type': 'gui', 'module_name': 'gui', 'command': 'write', 'message': message, 'parameters': {}}
        self.manager.q.put(command_dict)
