class Device:
    def __init__(self, manager_obj, serial_lock):
        # todo add error handling
        self.cmd_device = manager_obj
        self.digital_state = None
        self.analog_level = None
        self.serial_lock = serial_lock

    def digital_read(self):
        self.serial_lock.acquire()
        self.digital_state = self.cmd_device.get_state()
        self.serial_lock.release()
        return self.digital_state

    def digital_write(self, state):
        self.serial_lock.acquire()
        if state == 1:
            self.cmd_device.high()
            self.digital_state = 1
        else:
            self.cmd_device.low()
            self.digital_state = 0
        self.serial_lock.release()

    def analog_read(self):
        self.serial_lock.acquire()
        self.analog_level = self.cmd_device.get_level()
        self.serial_lock.release()
        return self.analog_level

    def analog_write(self, value):
        self.serial_lock.acquire()
        self.cmd_device.set_pwm_value(value)
        self.serial_lock.release()
