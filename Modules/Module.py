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
        self.serial_lock = manager.serial_lock
        self.lock = Lock()
        for item in assoc_devices.keys():
            if 'stepper' in item:
                # stepper dict: {..."stepper" : [ "cmd_stepper", "cmd_enabler"]...}
                stepper = getattr(cmduino, assoc_devices[item]["name"])
                enable_pin = getattr(cmduino, assoc_devices[item]["enable_pin"])
                if module_info["mod_config"]["linear_stepper"]:
                    self.steppers.append(LinearStepperMotor(stepper, enable_pin, assoc_devices[item]["device_config"],
                                                            self.serial_lock))
                else:
                    self.steppers.append(StepperMotor(stepper, enable_pin, assoc_devices[item]["device_config"],
                                                      self.serial_lock))
            if 'endstop' in item:
                endstop = getattr(cmduino, assoc_devices[item]["cmd_id"])
                self.endstops.append(Device(endstop, self.serial_lock))
            if 'he_sens' in item:
                he_sens = getattr(cmduino, assoc_devices[item]["cmd_id"])
                self.he_sensors.append(Device(he_sens, self.serial_lock))
