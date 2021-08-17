from UJ_FB.Modules import modules
from threading import Thread
import math
import time


class Reactor(modules.FBFlask):
    """
    Class for managing reactors
    """
    def __init__(self, name, module_info, cmduino, manager):
        super(Reactor, self).__init__(name, module_info, cmduino, manager)
        self.type = "RCT"
        self.num_heaters = module_info['mod_config']['num_heaters']
        # specific heat capacity, volume, density
        self.heat_rate = 880 * 67.7e-6 * 2770
        self.pid_constants = [10, 0, 5]
        self.pid_range = 255
        self.last_voltage = 0
        self.cur_temp = 0.0
        self.heating = False
        self.res_heating = False
        self.stirring = False
        self.res_stirring = False
        self.target = False
        self.precooling = False
        self.preheating = False
        self.heat_time_threshold = 30
        self.temp_change_threshold = 1
        self.temp = 0.0
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
        self.thread = Thread(target=self.run, name=self.name, daemon=True)
        self.thread.start()

    def start_heat(self, temp, heat_secs, target):
        cart_voltage = self.calc_voltage(temp)
        if cart_voltage == -273.15:
            self.write_to_gui("Temperature sensor is not connected")
            return False
        else:
            self.last_voltage = cart_voltage
        with self.stop_lock:
            self.heating = True
            self.ready = False
            if target:
                self.target = True
        self.write_to_gui(f'{self.name} started heating')
        self.target_temp = temp
        for heater in self.heaters:
            heater.start_heat(cart_voltage)
        self.heat_time = heat_secs

    def start_stir(self, speed, stir_secs):
        self.stirring = True
        if speed < 3000:
            self.mag_stirrers[0].start_stir(3000)
        self.mag_stirrers[0].start_stir(speed)
        self.stir_start_time = time.time()
        self.stir_time = stir_secs
        self.write_to_gui(f'{self.name} started stirring at {speed}')

    def run(self):
        while True:
            time.sleep(1/self.polling_rate)
            with self.stop_lock:
                if self.target:
                    self.target = False
                    self.cur_temp = self.temp_sensors[0].read_temp()
                    if self.cur_temp < self.target_temp:
                        self.preheating = True
                        preheat_start = time.time()
                    else:
                        self.precooling = True
                if self.preheating:
                    self.preheat(preheat_start)
                elif self.precooling:
                    self.cur_temp = self.temp_sensors[0].read_temp()
                    if self.cur_temp <= self.target_temp:
                        with self.stop_lock:
                            self.precooling = False
                elif self.heating:
                    if self.heat_time > 0:
                        if time.time() - self.heat_start_time > self.heat_time:
                            self.stop_heat()
                    new_voltage = self.calc_voltage(self.target_temp)
                    if new_voltage != self.last_voltage:
                        for heater in self.heaters:
                            heater.start_heat(new_voltage)
                        self.last_voltage = new_voltage
                if self.stirring:
                    if self.stir_time > 0:
                        if time.time() - self.stir_start_time > self.stir_time:
                            with self.stop_lock:
                                self.stirring = False
                if self.stop_cmd:
                    self.stop_cmd = False
                    if self.heating:
                        self.stop_heat()
                        elapsed_time = time.time() - self.heat_start_time
                        if self.heat_time > elapsed_time:
                            self.heat_rem_time = self.heat_time - elapsed_time
                        self.res_heating = True
                    if self.stirring:
                        self.stop_stir()
                        elapsed_time = time.time() - self.stir_start_time
                        if self.stir_time > elapsed_time:
                            self.stir_rem_time = self.stir_time - elapsed_time
                        self.res_stirring = True
                    self.ready = True                 

    def preheat(self, preheat_start):
        self.cur_temp = self.temp_sensors[0].read_temp()
        if self.cur_temp < self.target_temp:
            self.calc_voltage(self.target_temp)
        else:
            with self.stop_lock:
                self.preheating = False
                self.heat_start_time = time.time()
        if time.time() - preheat_start > 1200:
            with self.stop_lock:
                self.preheating = False
                self.heat_start_time = time.time()

    def calc_voltage(self, temp):
        """
        Calculates the voltage for the heater element using a PID controller.
        :param temp: the target temperature
        :return: voltage: the new required voltage for the heater element.
        """
        kd, ki, kp,  = self.pid_constants
        self.cur_temp = self.temp_sensors[0].read_temp()
        if self.cur_temp == -273.15:
            return self.cur_temp
        if self.cur_temp >= self.temp:
            self.write_to_gui(f"Reactor reached {self.temp}°C")
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
        voltage = math.sqrt(((control_signal/dt)*3.6*self.heat_rate))
        voltage = max(0.0, min(voltage, 12))
        voltage = voltage/12 * 255
        self.prev_error = error
        return voltage

    def read_temp(self):
        temp = self.temp_sensors[0].read_temp()
        self.write_to_gui(f"Current temp is {temp} °C")

    def stop(self):
        """
        Stops all reactor operations when stop override received. Stores time remaining to resume.
        """
        with self.stop_lock:
            self.stop_cmd = True 
    
    def stop_stir(self):
        with self.stop_lock:
            self.stirring = False
            self.mag_stirrers[0].stop_stir()

    def stop_heat(self):
        with self.stop_lock:
            self.heating = False
            for heater in self.heaters:
                heater.stop_heat()
            self.integral_error = 0

    def resume(self, command_dicts):
        """
        Resumes heating and stirring once signal received.
        :param command_dicts: dictionary representing heat and stir command
        :return: True if resuming, else returns False.
        """
        heat_flag, stir_flag = False, False
        if self.heat_rem_time > 0:
            command_dicts[0]['heat_secs'] = self.heat_rem_time
            self.heat_rem_time = 0
        if self.stir_rem_time > 0:
            command_dicts[0]['stir_secs'] = self.stir_rem_time
            self.stir_rem_time = 0
        if self.res_heating or self.res_stirring:
            return True
        return False
