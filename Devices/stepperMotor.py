from Devices.device import Device


class StepperMotor(Device):
    """
    Class for managing stepper motors
    """
    def __init__(self, stepper_obj, motor_en_obj, device_config):
        """
        :param stepper_obj: commanduino object for controlling the stepper motor
        :param motor_en_obj: commandduino object for toggling the enable pin with digitalWrite
        :param device_config: Dictionary containing the configuration information for the motor.
        """
        super(StepperMotor, self).__init__(motor_en_obj)
        self.cmd_stepper = stepper_obj
        self.steps_per_rev = device_config['steps_per_rev']
        self.position = 0
        self.acceleration = 0.0
        self.stopped = False

    def en_motor(self, en=False):
        if en:
            self.digital_write(0)
        else:
            self.digital_write(1)

    def enable_acceleration(self, enable=True):
        if enable:
            self.cmd_stepper.enable_acceleration()
        else:
            self.cmd_stepper.disable_acceleration()

    def set_acceleration(self, acceleration):
        # todo find maximum acceleration?
        if acceleration is int and acceleration > 0:
            self.cmd_stepper.set_acceleration(acceleration)
            return True
        else:
            print("That is not a valid acceleration")
            return False

    def set_running_speed(self, speed):
        if speed is int and speed > 0:
            self.cmd_stepper.set_running_speed(speed)
            return True
        else:
            print("That is not a valid running speed")
            return False

    def set_max_speed(self, speed):
        if speed is int and speed > 0:
            self.cmd_stepper.set_max_speed(speed)
            return True
        else:
            print("That is not a valid max speed")
            return False

    def revert_direction(self, direction):
        """
        :param direction: True - clockwise, False, anticlockwise
        :return:
        """
        self.cmd_stepper.revert_direction(direction)

    def get_current_pos(self):
        return self.cmd_stepper.get_current_position()

    def set_current_pos(self, position):
        if position is int:
            if position > self.steps_per_rev:
                position -= self.steps_per_rev
            elif position < 0:
                position += self.steps_per_rev
            self.cmd_stepper.set_current_position(position)

    def move_steps(self, steps):
        self.stopped = False
        self.en_motor(True)
        self.cmd_stepper.move(steps)

    def stop(self):
        self.cmd_stepper.stop()
        self.stopped = True

    @property
    def is_moving(self):
        return self.cmd_stepper.is_moving
