from threading import Lock
import time


class StepperMotor:
    """
    Class for managing stepper motors. Motors are communicated with using the Commandduino library with a Serial
    connection. Target library uses the Accelstepper stepper library.
    """
    def __init__(self, stepper_obj, device_config, serial_lock):
        """
        :param stepper_obj: commanduino object for controlling the stepper motor
        :param device_config: Dictionary containing the configuration information for the motor.
        :param: serial_lock: threading.Lock() object for controlling access to serial connection
        """
        self.serial_lock = serial_lock
        self.cmd_stepper = stepper_obj
        self.stop_lock = Lock()
        self.stop_cmd = False
        self.enabled = True
        self.steps_per_rev = device_config['steps_per_rev']
        self.enabled_acceleration = device_config['enabled_acceleration']
        self.running_speed = device_config['speed']
        self.max_speed = device_config['max_speed']
        self.acceleration = device_config["acceleration"]
        self.reversed_direction = False
        self.position = 0

    def enable_acceleration(self, enable=True):
        """
        Enables or disables acceleration for the motor. Uses the serial connection
        :param enable: Boolean. Toggles enabling or disabling acceleration
        :return:
        """
        with self.serial_lock:
            if enable:
                self.cmd_stepper.enable_acceleration()
                self.enabled_acceleration = True
            else:
                self.cmd_stepper.disable_acceleration()
                self.enabled_acceleration = False

    def set_acceleration(self, acceleration):
        """
        Sets the acceleration of the motor via the serial connection
        :param acceleration: Integer value for the motor acceleration
        :return: Boolean. True if successful, False otherwise.
        """
        if type(acceleration) is int and acceleration > 0:
            with self.serial_lock:
                self.cmd_stepper.set_acceleration(acceleration)
            self.acceleration = acceleration
            return True
        else:
            print("That is not a valid acceleration")
            return False

    def set_running_speed(self, speed):
        """
        Sets the running speed of the motor via the serial connection
        :param speed: Integer: the desired speed
        :return: Boolean: True if successful, False otherwise.
        """
        if type(speed) is int and speed > 0:
            with self.serial_lock:
                self.cmd_stepper.set_running_speed(speed)
            self.running_speed = speed
            return True
        else:
            print("That is not a valid running speed")
            return False

    def set_max_speed(self, speed):
        """
        Sets the maximum speed of the stepper motor via the serial connection
        :param speed:
        :return:
        """
        if type(speed) is int and speed > 0:
            with self.serial_lock:
                self.cmd_stepper.set_max_speed(speed)
            self.max_speed = speed
            return True
        else:
            print("That is not a valid max speed")
            return False

    def reverse_direction(self, reverse):
        """
        :param reverse: True - clockwise, False, anticlockwise
        :return:
        """
        if reverse != self.reversed_direction:
            with self.serial_lock:
                self.cmd_stepper.revert_direction(reverse)
            self.reversed_direction = reverse

    def get_current_position(self):
        """
        Queries the motor for its current position.
        :return: Position of the motor in steps. Positive is clockwise from zeroed position. Negative is anti-clockwise.
        """
        with self.serial_lock:
            self.position = self.cmd_stepper.get_current_position()
        return self.position

    def set_current_position(self, position):
        """
        Sets the current position of the motor as referenced by the Accelstepper library.
        :param position: The desired position of the motor. Sets the current step position to be the desired step
        position.
        """
        with self.serial_lock:
            self.cmd_stepper.set_current_position(position)
        self.position = position

    def move_steps(self, steps, subs_moves=False):
        """
        Moves the motor by a number of steps. :param steps: Integer: the number of steps for the motor to move.
        :param subs_moves: Boolean: whether subsequent moves are expected. determines whether to disable motor after
        movement complete.
        :param steps: Integer number of steps to move
        :return: True
        """
        with self.serial_lock:
            self.cmd_stepper.move(steps, False)
        self.watch_move(subs_moves)
        return True

    def move_to(self, position, subs_moves=False):
        """
        Moves the motor to a specific step position.
        :param position: Integer: the desired step position
        :param subs_moves: Boolean: whether subsequent moves are expected. determines whether to disable motor after
        movement complete.
        :return: True
        """
        with self.serial_lock:
            self.cmd_stepper.move_to(position, False)
        self.watch_move(subs_moves)
        return True

    def stop(self):
        """
        Stops the motor.
        """
        with self.serial_lock:
            self.cmd_stepper.stop()

    def watch_move(self, subs_moves=False):
        """
        Forces the executing thread to wait until the motor is finished moving or is told to stop. This allows the
        thread to be monitored for Task completion.
        """
        moving = True
        prev_time = time.time()
        while moving:
            if time.time() > prev_time + 2:
                if not self.is_moving:
                    moving = False
            with self.stop_lock:
                if self.stop_cmd:
                    self.stop_cmd = False
                    break

    @property
    def is_moving(self):
        """
        Queries whether step pulses are still being sent to the motor.
        :return: Boolean: False - no pulses.
        """
        with self.serial_lock:
            moving = self.cmd_stepper.is_moving
        return moving


class LinearStepperMotor(StepperMotor):
    """
    Class for managing stepper motors with a finite linear travel.
    """
    def __init__(self, stepper_obj, device_config, serial_lock):
        """
        :param stepper_obj: commanduino object for controlling the stepper motor
        :param device_config: Dictionary containing the configuration information for the motor.
        :param: serial_lock: threading.Lock() object for controlling access to serial connection
        """
        super(LinearStepperMotor, self).__init__(stepper_obj, device_config, serial_lock)
        self.switch_state = 0

    def check_endstop(self):
        """
        Queries the attached end-switch state.
        :return: 1 - switch triggered. 0 - switch open
        """
        with self.serial_lock:
            self.switch_state = self.cmd_stepper.get_switch_state()
        return self.switch_state

    def home(self):
        """
        Sends command over serial to run the motor until the end-switch is triggered.
        """
        if not self.check_endstop():
            with self.serial_lock:
                self.cmd_stepper.home(False)
            self.watch_move()
            self.set_running_speed(self.running_speed)
