from UJ_FB.Modules import modules
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
        self.stirring = False
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

    def start_reactor(self, preheat, temp, heat_secs, speed, stir_secs):
        """
        Starts the heating or stirring operation
        :param preheat: Should preheat True/False
        :param temp: Temperature to heat
        :param heat_secs: Time to heat
        :param speed: Speed to stir in rpm
        :param stir_secs: Time to stir
        :return: False if no temp sensor connected
        """
        self.ready = False
        self.stirring = False
        self.heating = False
        if preheat:
            self.wait_for_temp(temp)
        self.prev_time = time.time()
        if temp > 25 and heat_secs > 0.0:
            self.temp = temp
            cart_voltage = self.calc_voltage(temp)
            if cart_voltage == -273.15:
                self.write_to_gui("Temperature sensor is not connected")
                return False
            for heater in self.heaters:
                heater.start_heat(cart_voltage)
            self.heat_start_time = self.prev_time
            self.heating = True
            self.write_to_gui(f'{self.name} started heating to {temp}')
            if preheat:
                self.heat_time = 600
            else:
                self.heat_time = heat_secs
        if speed > 0.0 and stir_secs > 0.0:
            if speed < 3000:
                self.mag_stirrers[0].start_stir(3000)
            self.mag_stirrers[0].start_stir(speed)
            self.stir_start_time = time.time()
            self.stir_time = stir_secs
            self.stirring = True
            self.write_to_gui(f'{self.name} started stirring at {speed}')
        self.wait_for_completion()

    def wait_for_completion(self):
        """
        Keeps heating and stirring until completed.
        """
        while self.heating or self.stirring:
            cur_time = time.time()
            if self.heating:
                # heat operation complete
                if cur_time - self.heat_start_time > self.heat_time:
                    for heater in self.heaters:
                        heater.stop_heat()
                        self.heating = False
                        self.integral_error = 0
                # update cartridge voltage
                elif (cur_time - self.prev_time) >= (1/self.polling_rate):
                    new_voltage = self.calc_voltage(self.temp)
                    if new_voltage != self.last_voltage:
                        for heater in self.heaters:
                            heater.start_heat(new_voltage)
                    self.last_voltage = new_voltage
            # check for stirring completion
            if self.stirring:
                if cur_time - self.stir_start_time > self.stir_time:
                    self.mag_stirrers[0].stop_stir()
                    self.stirring = False
            with self.stop_lock:
                if self.stop_cmd:
                    self.stop_cmd = False
                    if self.heating:
                        for heater in self.heaters:
                            heater.stop_heat()
                        self.heating = False
                        elapsed_time = cur_time - self.heat_start_time
                        if self.heat_time > elapsed_time:
                            self.heat_rem_time = self.heat_time - elapsed_time
                    if self.stirring:
                        self.mag_stirrers[0].stop_stir()
                        self.stirring = False
                        elapsed_time = cur_time - self.stir_start_time
                        if self.stir_time > elapsed_time:
                            self.stir_rem_time = self.stir_time - elapsed_time
                    break
        self.ready = True

    def wait_for_temp(self, temp):
        """
        Waits until desired temperature reached. If heating, will time out when temperature has
        not increased by 1C in the last 30 seconds.
        :param temp: the target temperature
        :return: None
        """
        self.cur_temp = self.temp_sensors[0].read_temp()
        # Current temp lower than desired temp
        if self.cur_temp < temp:
            prev_temp = self.cur_temp
            last_check_time = time.time()
            while self.cur_temp < temp:
                cur_time = time.time()
                if (cur_time - self.prev_time) > (1/self.polling_rate):
                    self.calc_voltage(temp)
                if (cur_time - last_check_time) > self.heat_time_threshold:
                    if (self.cur_temp - prev_temp) < self.temp_change_threshold:
                        return
                    else:
                        prev_temp = self.cur_temp
                        last_check_time = time.time()
        elif self.cur_temp > temp:
            self.prev_time = time.time()
            while self.cur_temp > temp:
                if time.time() - self.prev_time >= 1/self.polling_rate:
                    self.cur_temp = self.temp_sensors.analog_read()

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

    def resume(self, command_dicts):
        """
        Resumes heating and stirring once signal received.
        :param command_dicts: dictionary representing heat and stir command
        :return: True if resuming, else returns False.
        """
        heat_flag, stir_flag = False, False
        if self.heat_rem_time > 0:
            command_dicts[0]['heat_secs'] = self.heat_rem_time
            heat_flag = True
        if self.stir_rem_time > 0:
            command_dicts[0]['stir_secs'] = self.stir_rem_time
            stir_flag = True
        if heat_flag or stir_flag:
            self.heat_rem_time = 0
            self.stir_rem_time = 0
            return True
        return False
