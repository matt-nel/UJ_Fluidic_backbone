import math
from commanduino.exceptions import CMDeviceReplyTimeout


class Device:
    """Class to represent a generic device, in this case a digital/analog pin.
    """
    def __init__(self, cmd_mng, serial_lock):
        """Initialise the device object

        Args:
            cmd_mng (CommandManager): the Commanduino commandmanager for this robot
            serial_lock (Lock): Lock used to maintain thread safety for the serial connection
        """
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
    """Class to represent a thermistor
    """
    def __init__(self, ts_obj, device_config, s_lock):
        """Initialise the temperature sensor

        Args:
            ts_obj (CommandHandler): the Commanduino CommandHandler for this sensor
            device_config (dict): dictionary containing the device configuration
            serial_lock (Lock): Lock used to maintain thread safety for the serial connection
        """
        super(TempSensor, self).__init__(ts_obj, s_lock)
        self.coefficients = device_config["SH_C"]
        self.last_temp = 0.0

    def read_temp(self):
        """Reads the temperature from the thermistor, derived from the voltage and the Steinhart-Hart coefficients for the thermistor

        Returns:
            float: the temperature in °C
        """
        v = []
        num_readings = 0
        for i in range(5):
            try:
                v.append(self.analog_read())
                num_readings += 1
            except CMDeviceReplyTimeout:
                pass
        if num_readings < 1:
            return self.last_temp
        v_ave = sum(v)/5
        v_ave = (v_ave/1023) * 5.00
        if v_ave == 5.00:
            return -273.15
        r2 = (4700*v_ave)/(5.00-v_ave)
        rln = math.log(r2, math.e)
        a, b, c = self.coefficients
        self.last_temp = 1/(a + (b * rln) + (c * pow(rln, 3))) - 273.15
        return self.last_temp


class Heater(Device):
    """Class to represent a heating element
    """
    def __init__(self, heater_obj, s_lock):
        """Initialise the heater

       Args:
            heater_obj (CommandHandler): the Commanduino CommandHandler for this heater
            s_lock (Lock): Lock used to maintain thread safety for the serial connection
        """
        super(Heater, self).__init__(heater_obj, s_lock)
        self.voltage = 0.0

    def start_heat(self, voltage):
        voltage = max(0.0, min(voltage, 255))
        self.voltage = voltage
        self.analog_write(voltage)

    def stop_heat(self):
        self.voltage = 0.0
        self.analog_write(0.0)


class MagStirrer(Device):
    """
    Class for managing magnetic stirrers
    """

    def __init__(self, stirrer_obj, device_config, s_lock):
        """Initialise the stirrer

        Args:
            stirrer_obj (CommandHandler): the Commanduino CommandHandler for this stirrer
            device_config (dict): dictionary containing the device configuration
            s_lock (Lock): Lock used to maintain thread safety for the serial connection
        """
        super(MagStirrer, self).__init__(stirrer_obj, s_lock)
        self.max_speed = device_config["fan_speed"]
        self.speed = 0.0

    def start_stir(self, speed):
        self.speed = max(0, min(speed, self.max_speed))
        voltage = int((self.speed/self.max_speed) * 255)
        self.analog_write(voltage)
        return speed

    def stop_stir(self):
        self.speed = 0.0
        self.analog_write(0)
