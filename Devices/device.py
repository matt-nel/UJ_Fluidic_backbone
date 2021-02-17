class Device:
    def __init__(self, cmd_mng, s_lock):
        # todo add error handling
        self.cmd_device = cmd_mng
        self.digital_state = None
        self.analog_level = None
        self.serial_lock = s_lock

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
