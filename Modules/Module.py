from Devices.stepperMotor import StepperMotor
from Devices.device import Device


class Module:
    """
    Class for representing generic modules. __init__ associates attached devices and creates attributes having those
    names.
    """
    def __init__(self, module_info, manager_obj):
        """
        :param module_info: dictionary containing device info for module and configuration info for module.
        :param manager_obj: commanduino object that deals with low-level commands to Arduino.
        """
        # todo add method for adding modules after initialisation.
        assoc_devices = module_info["devices"]
        self.steppers = []
        self.endstops = []
        self.he_sensors = []
        for item in assoc_devices.keys():
            if 'stepper' in item:
                # stepper dict: {..."stepper" : [ "cmd_stepper", "cmd_enabler"]...}
                stepper = getattr(manager_obj, assoc_devices[item]["name"])
                enable_pin = getattr(manager_obj, assoc_devices[item]["enable_pin"])
                self.steppers.append(StepperMotor(stepper, enable_pin, assoc_devices[item]["device_config"]))
            if 'endstop' in item:
                endstop = getattr(manager_obj, assoc_devices[item]["cmd_id"])
                self.endstops.append(Device(endstop))
            if 'he_sens' in item:
                he_sens = getattr(manager_obj, assoc_devices[item]["cmd_id"])
                self.he_sensors.append(Device(he_sens))
