class Device:
    def __init__(self, manager_obj):
        # todo add error handling
        self.cmd_device = manager_obj
        self.digital_state = None
        self.analog_level = None

    def digital_read(self):
        self.digital_state = self.cmd_device.get_state()
        return self.digital_state

    def digital_write(self, state):
        if state == 1:
            self.cmd_device.high()
            self.digital_state = 1
        else:
            self.cmd_device.low()
            self.digital_state = 0

    def analog_read(self):
        self.analog_level = self.cmd_device.get_level()
        return self.analog_level

    def analog_write(self, value):
        self.cmd_device.set_pwm_value(value)
