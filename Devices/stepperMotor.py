from Devices.device import Device


class StepperMotor(Device):
    """
    Class for managing stepper motors
    """
    def __init__(self, stepper_obj, motor_en_obj, device_config, serial_lock):
        """
        :param stepper_obj: commanduino object for controlling the stepper motor
        :param motor_en_obj: commandduino object for toggling the enable pin with digitalWrite
        :param device_config: Dictionary containing the configuration information for the motor.
        """
        super(StepperMotor, self).__init__(motor_en_obj, serial_lock)
        self.cmd_stepper = stepper_obj
        self.steps_per_rev = device_config['steps_per_rev']
        self.position = 0
        self.acceleration = 0.0
        self.stopped = False
        self.en_motor()

    def en_motor(self, en=False):
        if en:
            self.digital_write(0)
        else:
            self.digital_write(1)

    def enable_acceleration(self, enable=True):
        self.serial_lock.acquire()
        if enable:
            self.cmd_stepper.enable_acceleration()
        else:
            self.cmd_stepper.disable_acceleration()
        self.serial_lock.release()

    def set_acceleration(self, acceleration):
        if acceleration is int and acceleration > 0:
            self.serial_lock.acquire()
            self.cmd_stepper.set_acceleration(acceleration)
            self.serial_lock.release()
            return True
        else:
            print("That is not a valid acceleration")
            return False

    def set_running_speed(self, speed):
        if speed is int and speed > 0:
            self.serial_lock.acquire()
            self.cmd_stepper.set_running_speed(speed)
            self.serial_lock.release()
            return True
        else:
            print("That is not a valid running speed")
            return False

    def set_max_speed(self, speed):
        if speed is int and speed > 0:
            self.serial_lock.acquire()
            self.cmd_stepper.set_max_speed(speed)
            self.serial_lock.release()
            return True
        else:
            print("That is not a valid max speed")
            return False

    def revert_direction(self, direction):
        """
        :param direction: True - clockwise, False, anticlockwise
        :return:
        """
        self.serial_lock.acquire()
        self.cmd_stepper.revert_direction(direction)
        self.serial_lock.release()

    def get_current_position(self):
        self.serial_lock.acquire()
        current_pos = self.cmd_stepper.get_current_position()
        self.serial_lock.release()
        return current_pos

    def set_current_position(self, position):
        if position is int:
            if position > self.steps_per_rev:
                position %= self.steps_per_rev
            elif position < 0:
                position = abs(position) % self.steps_per_rev
                position = self.steps_per_rev - position
            self.serial_lock.acquire()
            self.cmd_stepper.set_current_position(position)
            self.serial_lock.release()

    def move_steps(self, steps):
        self.stopped = False
        self.en_motor(True)
        self.serial_lock.acquire()
        self.cmd_stepper.move(steps)
        self.serial_lock.release()

    def stop(self):
        self.serial_lock.acquire()
        self.cmd_stepper.stop()
        self.serial_lock.release()
        self.stopped = True

    @property
    def is_moving(self):
        self.serial_lock.acquire()
        moving = self.cmd_stepper.is_moving
        self.serial_lock.release()
        return moving


class LinearStepperMotor(StepperMotor):
    def __init__(self, stepper_obj, motor_en_obj, device_config, serial_lock):
        super(LinearStepperMotor, self).__init__(stepper_obj, motor_en_obj, device_config, serial_lock)

    def check_endstop(self):
        self.serial_lock.acquire()
        switch_state = self.cmd_stepper.get_switch_state()
        self.serial_lock.release()
        return switch_state

    def home(self, wait=False):
        self.serial_lock.acquire()
        self.cmd_stepper.home(wait)
        self.serial_lock.release()
