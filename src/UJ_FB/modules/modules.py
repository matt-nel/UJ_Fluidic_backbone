import logging
from UJ_FB.devices import devices, steppermotor
from threading import Lock


class Module:
    """
    Class for representing generic modules. __init__ associates attached devices and creates instance attributes having
    those names.
    """
    def __init__(self, name, module_info, cmduino, manager):
        """
        :param name: String: the name of the module. E.g: "selectorvalve1", "syringepump2"
        :param manager: Manager object that is overseeing the robot functions
        :param module_info: dictionary containing device info for module and configuration info for module.
        :param cmduino: commanduino object that deals with low-level commands to Arduino.
        """
        # todo add method for adding modules after initialisation.
        assoc_devices = module_info.get("devices")
        self.name = name
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
        if mod_type != "flask" and mod_type != "camera":
            for item in assoc_devices.keys():
                if "stepper" in item:
                    # stepper dict: {..."stepper" : [ "cmd_stepper", "cmd_enabler"]...}
                    stepper = getattr(cmduino, assoc_devices[item]["name"])
                    if module_info["mod_config"]["linear_stepper"]:
                        self.steppers.append(steppermotor.LinearStepperMotor(stepper,
                                                                             assoc_devices[item]["device_config"],
                                                                             manager.serial_lock))
                    else:
                        self.steppers.append(steppermotor.StepperMotor(stepper, assoc_devices[item]["device_config"],
                                                                       manager.serial_lock))
                elif "endstop" in item:
                    endstop = getattr(cmduino, assoc_devices[item]["cmd_id"])
                    self.endstops.append(devices.Device(endstop, manager.serial_lock))
                elif "he_sens" in item:
                    he_sens = getattr(cmduino, assoc_devices[item]["cmd_id"])
                    self.he_sensors.append(devices.Device(he_sens, manager.serial_lock))
                elif "mag_stirrer" in item:
                    stirrer = getattr(cmduino, assoc_devices[item]["cmd_id"])
                    self.mag_stirrers.append(devices.MagStirrer(stirrer, assoc_devices[item]["device_config"],
                                                                manager.serial_lock))
                elif "heater" in item:
                    heater = getattr(cmduino, assoc_devices[item]["cmd_id"])
                    self.heaters.append(devices.Heater(heater, manager.serial_lock))
                elif "temp_sensor" in item:
                    temp_sensor = getattr(cmduino, assoc_devices[item]["cmd_id"])
                    self.temp_sensors.append(devices.TempSensor(temp_sensor, assoc_devices[item]["device_config"],
                                                                manager.serial_lock))

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
        super(FBFlask, self).__init__(name, module_info, cmd_mng, manager)
        self.type = "FSK"
        module_config = module_info["mod_config"]
        self.contents = [module_config.get("contents"), float(module_config.get("cur_volume"))*1000]
        self.cur_vol = float(module_config["cur_volume"])*1000
        self.max_volume = float(module_config["max_volume"])*1000

    def change_volume(self, new_contents, vol):
        self.cur_vol += vol
        # neg vol means syringe aspirated from this vessel (volume decreased)
        if vol < 0:
            if self.cur_vol <= 0:
                self.contents[0] = "empty"
                self.contents[1] = 0
                self.cur_vol = 0
            else:
                self.contents[1] += self.cur_vol
        # dispensed to this vessel
        elif self.contents[0] == "empty":
            self.contents[0] = new_contents
            self.contents[1] = self.cur_vol
        else:
            self.contents[0] += f", {new_contents}"
            self.contents[1] += self.cur_vol
        return True

    def check_volume(self, vol):
        # if syringe withdrawing from this vessel
        if vol < 0:
            if self.cur_vol + vol < 0:
                self.manager.write_log(f"Insufficient {self.contents} in {self.name}",  level=logging.WARNING)
        else:
            if self.cur_vol + vol > self.max_volume:
                self.write_log(f"Max volume of {self.name} would be exceeded", level=logging.WARNING)
                return False                
        return True
