from threading import Lock
from modules import FBFlask
import time


class Reactor(FBFlask):
    """
    Class for managing reactors
    """
    def __init__(self, name, module_info, cmduino, manager):
        super(Reactor, self).__init__(name, module_info, cmduino, manager)
        self.num_heaters = module_info['num_heaters']
        self.stop_lock = Lock()
        self.stop_cmd = False
        self.heating = False
        self.stirring = False
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

    def start_stirring(self, secs, speed):
        speed = self.mag_stirrers[0].start_stir(secs, speed)
        self.write_to_gui(f'{self.name} started stirring at {speed}')

    def start_reactor(self, temp, heat_secs, speed, stir_secs):
        self.temp = temp
        cart_voltage = self.calc_voltage(temp)
        if temp > 25 and heat_secs > 0.0:
            for heater in self.heaters:
                heater.start_heat(cart_voltage)
            heat_start_time = time.time()
            self.heat_start_time = heat_start_time
            self.prev_time = heat_start_time
            self.heat_time = heat_secs
            self.heating = True
            self.write_to_gui(f'{self.name} started heating to {temp}')
        else:
            self.heat_rem_time = 0.0
        if speed > 0.0 and stir_secs > 0.0:
            self.mag_stirrers[0].start_stir(speed)
            self.stir_start_time = time.time()
            self.stir_time = stir_secs
            self.stirring = True
            self.write_to_gui(f'{self.name} started stirring at {speed}')
        else:
            self.stir_rem_time = 0.0
        self.wait_for_completion()

    def wait_for_completion(self):
        while self.heating or self.stirring:
            cur_time = time.time()
            if self.heating:
                if cur_time - self.heat_start_time > self.heat_time:
                    for heater in self.heaters:
                        heater.stop_heat()
                        self.heating = False
                if (cur_time - self.prev_time) >= (1/self.polling_rate):
                    new_voltage = self.calc_voltage(self.temp)
                    for heater in self.heaters:
                        heater.start_heat(new_voltage)
            if self.stirring:
                if cur_time - self.stir_start_time > self.stir_time:
                    self.mag_stirrers[0].stop_stir()
                    self.stirring = False
            with self.stop_lock:
                if self.stop_cmd:
                    self.stop_cmd = False
                    break

    def calc_voltage(self, temp):
        kp, ki, kd = 10, 10, 10
        cur_temp = self.temp_sensors[0].read_temp()
        cur_time = time.time()
        error = temp - cur_temp
        dt = cur_time - self.prev_time
        d = (error - self.prev_error)/dt
        i = error * dt
        self.integral_error += i
        control_signal = kp*error + ki*self.integral_error + kd*d
        voltage = max(0.0, min(control_signal, 12.0))
        return voltage

    def stop(self):
        with self.stop_lock:
            self.stop_cmd = True
        cur_time = time.time()
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

    def resume(self, command_dict):
        heat_flag, stir_flag = False, False
        if self.heat_rem_time > 0:
            command_dict['heat_secs'] = self.heat_rem_time
            heat_flag = True
        if self.stir_rem_time > 0:
            command_dict['stir_secs'] = self.stir_rem_time
            stir_flag = True
        if heat_flag or stir_flag:
            return True
        return False
