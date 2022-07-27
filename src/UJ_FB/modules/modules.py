"""This script defines the Module base class and the FBFlask derived class
"""

import logging
from UJ_FB.devices import devices, steppermotor
from threading import Lock


class Module:
    """
    Class for representing generic modules. __init__ associates attached devices and creates instance attributes having
    those names.
    """
    def __init__(self, name, module_info, cmduino, manager):
        """Initialise the module and associate its devices to it

        Args:
            name (str): the module's name
            module_info (dict): configuration for the module
            cmduino (CommandManager): the Commanduino CommandManager used to control the Arduino
            manager (UJ_FB.Manager): the Manager object for this robot.
        """
        assoc_devices = module_info.get("devices")
        self.name = name
        self.mod_type = "misc"
        self.steppers = []
        self.endstops = []
        self.he_sensors = []
        self.mag_stirrers = []
        self.heaters = []
        self.temp_sensors = []
        self.manager = manager
        self.lock = Lock()
        self.stop_lock = Lock()
        self.stop_cmd = False
        self.ready = True
        mod_type = module_info["mod_type"]
        if mod_type not in ("flask", "waste", "camera"):
            for item in assoc_devices.keys():
                if "stepper" in item:
                    stepper = getattr(cmduino, assoc_devices[item]["name"])
                    if module_info["mod_config"]["linear_stepper"]:
                        self.steppers.append(steppermotor.LinearStepperMotor(stepper,
                                                                             assoc_devices[item]["device_config"],
                                                                             manager))
                    else:
                        self.steppers.append(steppermotor.StepperMotor(stepper, assoc_devices[item]["device_config"],
                                                                       manager))
                elif "endstop" in item:
                    endstop = getattr(cmduino, assoc_devices[item]["cmd_id"])
                    self.endstops.append(devices.Device(endstop, manager))
                elif "he_sens" in item:
                    he_sens = getattr(cmduino, assoc_devices[item]["cmd_id"])
                    self.he_sensors.append(devices.Device(he_sens, manager))
                elif "mag_stirrer" in item:
                    stirrer = getattr(cmduino, assoc_devices[item]["cmd_id"])
                    self.mag_stirrers.append(devices.MagStirrer(stirrer, assoc_devices[item]["device_config"],
                                                                manager))
                elif "heater" in item:
                    heater = getattr(cmduino, assoc_devices[item]["cmd_id"])
                    self.heaters.append(devices.Heater(heater, manager))
                elif "temp_sensor" in item:
                    temp_sensor = getattr(cmduino, assoc_devices[item]["cmd_id"])
                    self.temp_sensors.append(devices.TempSensor(temp_sensor, assoc_devices[item]["device_config"],
                                                                manager))

    def write_log(self, message, level=logging.INFO):
        self.manager.write_log(message, level)

    def stop(self):
        pass

    def resume(self, command_dict):
        return False


class FBFlask(Module):
    """
    Class to represent flasks in the fluidic backbone.
    """
    def __init__(self, name, module_info, cmd_mng, manager):
        """Initialise the flask object

        Args:
            name (str): the name of the flask
            module_info (dict): configuration information for the flask
            cmd_mng (CommandManager): Commanduino CommandManager for this robot
            manager (UJ_FB.Manager): Manager object for this robot
        """
        super(FBFlask, self).__init__(name, module_info, cmd_mng, manager)
        module_config = module_info["mod_config"]
        self.mod_type = module_info["mod_type"]
        self.contents = [module_config.get("contents"), float(module_config.get("cur_volume"))*1000]
        self.cur_vol = float(module_config["cur_volume"])*1000
        self.max_volume = float(module_config["max_volume"])*1000

    def change_volume(self, new_contents, vol):
        """Changes the record of the volume within the flask

        Args:
            new_contents (str): the name of the new contents
            vol (float): the volume being added or removed.

        Returns:
            bool: True if volume changed correctly
        """
        self.cur_vol += vol
        # neg vol means syringe aspirated from this vessel (volume decreased)
        if vol < 0:
            if self.cur_vol <= 0:
                self.contents[0] = "empty"
                self.contents[1] = 0
                self.cur_vol = 0
            else:
                self.contents[1] = self.cur_vol
        # dispensed to this vessel
        elif self.contents[0] == "empty":
            self.contents[0] = new_contents
            self.contents[1] = self.cur_vol
        else:
            self.contents[0] = f"{new_contents}"
            self.contents[1] += self.cur_vol
        return True

    def check_volume(self, vol):
        """Checks whether the volume change is possible

        Args:
            vol (float): the change in volume in uL

        Returns:
            bool: True if volume can be successfully changed.
        """
        # if syringe withdrawing from this vessel
        if vol < 0:
            if self.cur_vol + vol < 0:
                self.manager.write_log(f"Insufficient {self.contents} in {self.name}",  level=logging.WARNING)
        else:
            if self.cur_vol + vol > self.max_volume:
                self.write_log(f"Max volume of {self.name} would be exceeded", level=logging.WARNING)
                return False                
        return True
