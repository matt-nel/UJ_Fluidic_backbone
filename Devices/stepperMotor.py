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
        self.enabled_acceleration = device_config['enabled_acceleration']
        self.running_speed = device_config['speed']
        self.max_speed = device_config['max_speed']
        self.acceleration = device_config["acceleration"]
        self.homing_params = {"running_speed": 6000, "enabled_acceleration": True, "acceleration": 2000}
        self.position = 0
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
            self.enabled_acceleration = True
        else:
            self.cmd_stepper.disable_acceleration()
            self.enabled_acceleration = False
        self.serial_lock.release()

    def set_acceleration(self, acceleration):
        if acceleration is int and acceleration > 0:
            self.serial_lock.acquire()
            self.cmd_stepper.set_acceleration(acceleration)
            self.serial_lock.release()
            self.acceleration = acceleration
            return True
        else:
            print("That is not a valid acceleration")
            return False

    def set_running_speed(self, speed):
        if speed is int and speed > 0:
            self.serial_lock.acquire()
            self.cmd_stepper.set_running_speed(speed)
            self.serial_lock.release()
            self.running_speed = speed
            return True
        else:
            print("That is not a valid running speed")
            return False

    def set_max_speed(self, speed):
        if speed is int and speed > 0:
            self.serial_lock.acquire()
            self.cmd_stepper.set_max_speed(speed)
            self.serial_lock.release()
            self.max_speed = speed
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
        self.position = self.cmd_stepper.get_current_position()
        self.serial_lock.release()
        return self.position

    def set_current_position(self, position):
        if type(position) is int:
            if position > self.steps_per_rev:
                position %= self.steps_per_rev
            elif position < 0:
                position = abs(position) % self.steps_per_rev
                position = self.steps_per_rev - position
            self.serial_lock.acquire()
            self.cmd_stepper.set_current_position(position)
            self.serial_lock.release()
            self.position = position

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
        self.switch_state = 1

    def check_endstop(self):
        with self.serial_lock:
            self.switch_state = self.cmd_stepper.get_switch_state()
        return self.switch_state

    def home(self, wait=False):
        original_params = {"running_speed": self.running_speed, "enabled_acceleration": self.enabled_acceleration,
                           "acceleration": self.acceleration}
        with self.serial_lock:
            self.enable_acceleration(self.homing_params["enabled_acceleration"])
            self.set_running_speed(self.homing_params["running_speed"])
            self.set_acceleration(self.homing_params["acceleration"])
            self.cmd_stepper.home(wait)
            self.enable_acceleration(original_params["enabled_acceleration"])
            self.set_running_speed(original_params["running_speed"])
            self.set_acceleration(original_params["acceleration"])
