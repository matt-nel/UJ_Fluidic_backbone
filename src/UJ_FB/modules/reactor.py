from UJ_FB.modules import modules
from threading import Thread, Lock
from commanduino import exceptions
import math
import time
import logging


class Reactor(modules.FBFlask):
    """
    Class for managing reactors
    """
    def __init__(self, name, module_info, cmduino, manager):
        """Initialise the reactor object

        Args:
            name (str): the name of the reactor
            module_info (dict): configuration infomration for the reactor
            cmduino (CommandManager): the Commanduino CommandManager used to control the Arduino
            manager (UJ_FB.Manager): the Manager object for this robot
        """
        super(Reactor, self).__init__(name, module_info, cmduino, manager)
        self.mod_type = "reactor"
        # specific heat capacity, volume, density
        volume = module_info["mod_config"]["aluminium_volume"]
        split_num = volume.split("e")
        if len(split_num) > 1:
            volume = float(split_num[0]) * math.pow(10, int(split_num[1]))
        else:
            volume = float(split_num[0])
        # Joule/K
        self.heat_rate = 880 * volume * 2770
        self.pid_constants = [10, 0.25, 5]
        self.pid_range = 255
        self.last_voltage = 0
        self.cur_temp = 0.0
        self.heat_update_delay = 20
        self.heat_last_update_time = time.time()-30
        self.heating = False
        self.resume_heating = False
        self.stirring = False
        self.resume_stirring = False
        self.target = False
        self.cooling = False
        self.preheating = False
        self.heat_task = None
        self.stir_task = None
        self.heat_time_threshold = 30
        self.temp_change_threshold = 1
        self.target_temp = 0.0
        self.prev_error = 0.0
        self.integral_error = 0.0
        self.prev_time = 0.0
        self.polling_rate = 2
        self.heat_time = 0.0
        self.heat_start_time = 0.0
        self.heat_rem_time = 0.0
        self.stir_time = 0.0
        self.stir_start_time = 0.0
        self.stir_rem_time = 0.0
        self.exit = False
        self.stir_lock = Lock()
        self.heat_lock = Lock()
        self.thread = Thread(target=self.run, name=self.name, daemon=True)
        self.thread.start()

    def start_heat(self, temp, heat_secs, target, task):
        """Starts temperature regulation

        Args:
            temp (float): the temperature to maintain
            heat_secs (int): seconds to heat for. Does not count preheating
            target (bool): whether to heat to a defined target temperature
            task (UJ_FB.fluidicbackbone.Task): the task for this heating operation
        """
        with self.heat_lock:
            self.target_temp = temp
            self.prev_time = time.time()
            cart_voltage = self.calc_voltage(temp)
            if cart_voltage == -273.15:
                self.write_log("Temperature sensor is not connected", level=logging.ERROR)
                task.error = True
            else:
                self.last_voltage = cart_voltage
            self.heating = True
            self.cooling = False
            self.ready = False
            if target:
                self.target = True
            self.write_log(f"{self.name} started heating", level=logging.INFO)
            for heater in self.heaters:
                heater.start_heat(cart_voltage)
            self.heat_time = heat_secs

    def start_stir(self, speed, stir_secs):
        """Starts stirring using the magnetic stirrer bar

        Args:
            speed (int): the speed in RPM to stir at
            stir_secs (int): the number of seconds to stir the reactor for.
        """
        with self.stir_lock:
            self.stirring = True
            self.ready = False
            max_speed = self.mag_stirrers[0].max_speed
            if speed < (0.5 * max_speed):
                self.mag_stirrers[0].start_stir(max_speed)
                time.sleep(1.5)
                self.mag_stirrers[0].start_stir(0.5 * max_speed)
                time.sleep(1.5)
                if speed > (0.2 * max_speed):
                    self.mag_stirrers[0].start_stir(speed)
                else:
                    self.mag_stirrers[0].start_stir(0.2 * max_speed)
            else:
                self.mag_stirrers[0].start_stir(speed)
            self.stir_start_time = time.time()
            self.stir_time = stir_secs
            self.write_log(f"{self.name} started stirring at {speed}", level=logging.INFO)

    def run(self):
        """This method is run continuously to maintain heating, stirring, and updates to the sensor readings 
        """
        while not self.exit:
            time.sleep(1/self.polling_rate)
            with self.heat_lock:
                if self.target:
                    self.target = False
                    self.cur_temp = self.read_temp()
                    if self.cur_temp < self.target_temp:
                        self.preheating = True
                        preheat_start = time.time()
                    else:
                        self.cooling = True
                        cooling_start = time.time()
            with self.heat_lock:
                if self.preheating:
                    self.preheat(preheat_start)
                elif self.cooling:
                    self.cur_temp = self.read_temp()
                    if self.cur_temp <= self.target_temp:
                        self.cooling = False
                        self.integral_error = 0
                        self.heat_time = time.time() - cooling_start
                        self.heat_start_time = time.time()
                elif self.heating:
                    if self.heat_time > 0:
                        if time.time() - self.heat_start_time > self.heat_time:
                            self.stop_heat()
                    else:
                        if self.heat_task:
                            self.heat_task.complete = True
                    new_voltage = self.calc_voltage(self.target_temp)
                    if new_voltage != self.last_voltage:
                        for heater in self.heaters:
                            heater.start_heat(new_voltage)
                        self.last_voltage = new_voltage
            with self.stir_lock:
                if self.stirring:
                    if self.stir_time > 0:
                        if time.time() - self.stir_start_time > self.stir_time:
                            self.stirring = False
                    else:
                        if self.stir_task:
                            self.stir_task.complete = True
            with self.heat_lock:
                if not self.heating and time.time() - self.heat_last_update_time > self.heat_update_delay:
                    self.cur_temp = self.read_temp()
                    self.heat_last_update_time = time.time()
            with self.stop_lock:
                if self.stop_cmd:
                    self.stop_cmd = False
                    if self.heating:
                        self.stop_heat()
                        elapsed_time = time.time() - self.heat_start_time
                        if self.heat_time > elapsed_time:
                            self.heat_rem_time = self.heat_time - elapsed_time
                        self.resume_heating = True
                    if self.stirring:
                        self.stop_stir()
                        elapsed_time = time.time() - self.stir_start_time
                        if self.stir_time > elapsed_time:
                            self.stir_rem_time = self.stir_time - elapsed_time
                        self.resume_stirring = True
                    self.ready = True                 

    def preheat(self, preheat_start):
        """Preheats the reactor to the desired temperature

        Args:
            preheat_start (float): the time that the preheat was started.
        """
        self.cur_temp = self.temp_sensors[0].read_temp()
        if self.cur_temp < self.target_temp:
            cart_voltage = self.calc_voltage(self.target_temp)
            for heater in self.heaters:
                heater.start_heat(cart_voltage)
        else:
            self.preheating = False
            self.heat_start_time = time.time()
            self.integral_error = 0 
            self.write_log(f"Reactor reached {self.target_temp}°C", level=logging.INFO)
        if time.time() - preheat_start > 1200:
            self.preheating = False
            self.heat_start_time = time.time()

    def calc_voltage(self, temp):
        """Calculates the voltage for the heating element to maintain a desired temperature using a PID controller

        Args:
            temp (float): the target temperature

        Returns:
            float: voltage for the heating element
        """
        kd, ki, kp,  = self.pid_constants
        try:
            self.cur_temp = self.temp_sensors[0].read_temp()
        except exceptions.CMDeviceReplyTimeout:
            return self.last_voltage
        if self.cur_temp == -273.15:
            return self.cur_temp
        cur_time = time.time()
        error = temp - self.cur_temp
        dt = cur_time - self.prev_time
        self.prev_time = cur_time
        d = (error - self.prev_error)/dt
        i = error * dt
        self.integral_error += i
        raw_signal = kp*error + ki*self.integral_error + kd*d
        control_signal = max(0, raw_signal)
        # J/k = Cp*vol*rho
        # DT/dt = V^2/(R*Cp*Vol*rho)
        # DT = V^2/(R*Cp*Vol*rho) * dt
        # R = ~1.16ohm
        voltage = math.sqrt(((control_signal/dt)*1.15*self.heat_rate))
        voltage = max(0.0, min(voltage, 12))
        voltage = voltage/12 * 255
        self.prev_error = error
        return voltage

    def read_temp(self):
        if not self.manager.simulation:
            temp = self.temp_sensors[0].read_temp()
        else:
            temp = -999
        return temp

    def log_temp(self):
        temp = self.read_temp()
        self.write_log(f"Current temp is {temp} °C", level=logging.INFO)

    def stop(self):
        """
        Stops all reactor operations when stop override received. Stores time remaining to resume.
        """
        with self.stop_lock:
            self.stop_cmd = True
    
    def stop_stir(self):
        self.stirring = False
        self.mag_stirrers[0].stop_stir()
        self.stir_task.complete = True

    def stop_heat(self):
        self.heating = False
        for heater in self.heaters:
            heater.stop_heat()
        self.preheating = False
        self.integral_error = 0
        self.heat_task.complete = True

    def resume(self, command_dicts):
        """
        Resumes heating and stirring once signal received.
        :param command_dicts: dictionary representing heat and stir command
        :return: True if resuming, else returns False.
        """
        if self.heat_rem_time > 0:
            command_dicts[0]["heat_secs"] = self.heat_rem_time
            self.heat_rem_time = 0
        if self.stir_rem_time > 0:
            command_dicts[0]["stir_secs"] = self.stir_rem_time
            self.stir_rem_time = 0
        if self.resume_heating or self.resume_stirring:
            return True
        return False
