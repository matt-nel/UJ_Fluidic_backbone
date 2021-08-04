import math


class Device:
    def __init__(self, cmd_mng, serial_lock):
        # todo add error handling
        self.cmd_device = cmd_mng
        self.digital_state = None
        self.analog_level = None
        self.serial_lock = serial_lock
        self.start_time = 0.0
        self.elapsed_time = 0.0

    def digital_read(self):
        with self.serial_lock:
            self.digital_state = self.cmd_device.get_state()
        return self.digital_state

    def digital_write(self, state):
        with self.serial_lock:
            if state == 1:
                self.cmd_device.high()
                self.digital_state = 1
            else:
                self.cmd_device.low()
                self.digital_state = 0

    def analog_read(self):
        with self.serial_lock:
            self.analog_level = self.cmd_device.get_level()
        return self.analog_level

    def analog_write(self, value):
        with self.serial_lock:
            self.cmd_device.set_pwm_value(value)


class TempSensor(Device):
    def __init__(self, ts_obj, device_config, s_lock):
        super(TempSensor, self).__init__(ts_obj, s_lock)
        self.coefficients = device_config['SH_C']

    def read_temp(self):
        v = []
        for i in range(5):
            v.append(self.analog_read())
        v_ave = sum(v)/5
        if v_ave == 5.00:
            return -273.15
        v_ave = (v_ave/1023) * 5.00
        r2 = (4700*v_ave)/(5.00-v_ave)
        rln = math.log(r2, math.e)
        a, b, c = self.coefficients
        temp = 1/(a + (b * rln) + (c * pow(rln, 3))) - 273.15
        return temp


class Heater(Device):
    def __init__(self, heater_obj, device_config, s_lock):
        super(Heater, self).__init__(heater_obj, s_lock)
        self.voltage = 0.0

    def start_heat(self, voltage):
        voltage = max(0.0, min(voltage, 255))
        self.voltage = voltage
        self.analog_write(voltage)

    def stop_heat(self):
        self.voltage = 0.0
        self.analog_write(0)


class MagStirrer(Device):
    """
    Class for managing magnetic stirrers
    """

    def __init__(self, stirrer_obj, device_config, s_lock):
        super(MagStirrer, self).__init__(stirrer_obj, s_lock)
        self.max_speed = device_config['fan_speed']
        self.speed = 0.0

    def start_stir(self, speed):
        self.speed = max(0, min(speed, self.max_speed))
        voltage = int((self.speed/self.max_speed) * 255)
        self.analog_write(voltage)
        return speed

    def stop_stir(self):
        self.speed = 0.0
        self.analog_write(0)

