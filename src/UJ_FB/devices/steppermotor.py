from threading import Lock
import time
from commanduino import exceptions


class StepperMotor:
    """
    Class for managing stepper motors. Motors are communicated with using the Commandduino library with a Serial
    connection. Target library uses the Accelstepper stepper library.
    """
    def __init__(self, stepper_obj, device_config, manager):
        """Initialise the stepper motor

        Args:
            stepper_obj (CommandHandler): Commanduino CommandHandler for this motor
            device_config (dict): configuration information for the motor
            manager (UJ_FB.Manager): Manager object for this robot
        """
        self.manager = manager
        self.serial_lock = manager.serial_lock
        self.cmd_stepper = stepper_obj
        self.stop_lock = Lock()
        self.stop_cmd = False
        self.enabled = True
        self.steps_per_rev = device_config["steps_per_rev"]
        self.enabled_acceleration = device_config["enabled_acceleration"]
        self.running_speed = device_config["speed"]
        self.max_speed = device_config["max_speed"]
        self.acceleration = device_config["acceleration"]
        self.set_max_speed(self.max_speed)
        self.enable_acceleration(self.enabled_acceleration)
        self.reversed_direction = False
        self.position = 0
        self.magnets_passed = 0

    def enable_acceleration(self, enable=True):
        """Enables or disables acceleration for the motor. Uses the serial connection

        Args:
            enable (bool, optional): Toggles enabling or disabling acceleration. Defaults to True.
        """
        with self.serial_lock:
            if enable:
                self.cmd_stepper.enable_acceleration()
                self.enabled_acceleration = True
            else:
                self.cmd_stepper.disable_acceleration()
                self.enabled_acceleration = False

    def set_acceleration(self, acceleration):
        """Sets the acceleration of the motor via the serial connection

        Args:
            acceleration (int): Integer value for the motor acceleration

        Returns:
            bool: True if successful, False otherwise.
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

        Args:
            speed (int): the desired speed

        Returns:
            bool: True if successful, False otherwise.
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
        """Sets the maximum speed of the stepper motor via the serial connection

        Args:
            speed (int): the speed of the motor in steps/sec

        Returns:
            bool: True if successful, False otherwise.
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
        """Configures the motor to run in the reverse direction.

        Args:
            reverse (bool): True - clockwise, False, anticlockwise
        """
        if reverse != self.reversed_direction:
            with self.serial_lock:
                self.cmd_stepper.revert_direction(reverse)
            self.reversed_direction = reverse

    def get_current_position(self, retries=0):
        """Queries the motor for its current position.

        Returns:
            int: Position of the motor in steps. Positive is clockwise from zeroed position. Negative is anti-clockwise.
        """
        try:
            with self.serial_lock:
                self.position = self.cmd_stepper.get_current_position()
        except exceptions.CMDeviceReplyTimeout as e:
            self.position = self.retry_query(self.get_current_position, e, retries)
        return self.position

    def set_current_position(self, position):
        """Sets the current position of the motor in steps from the zero, as referenced by the Accelstepper library.

        Args:
            position (int): The desired position of the motor. Sets the current step position to be the desired step
                            position.
        """
        if self.reversed_direction:
            position = -position
        with self.serial_lock:
            self.cmd_stepper.set_current_position(position)
        self.position = position

    def move_steps(self, steps):
        """Moves the motor by a number of steps. :param steps: Integer: the number of steps for the motor to move.

        Args:
            steps (int): Integer number of steps to move

        Returns:
            bool: True if movement successful
        """
        with self.serial_lock:
            self.cmd_stepper.move(steps, False)
        self.position = self.position + steps
        self.watch_move()
        return True

    def move_to(self, position):
        """Moves the motor to a specific step position.

        Args:
            position (_type_): the desired step position

        Returns:
            bool: True if movement successful
        """
        with self.serial_lock:
            self.cmd_stepper.move_to(position, False)
        self.watch_move()
        return True

    def stop(self):
        """
        Stops the motor.
        """
        with self.serial_lock:
            self.cmd_stepper.stop()

    def watch_move(self):
        """
        Forces the executing thread to wait until the motor is finished moving or is told to stop. This allows the
        thread to be monitored for Task completion.
        """
        moving = True
        prev_time = time.time()
        while moving:
            if time.time() > prev_time:
                if not self.is_moving:
                    moving = False
                    self.magnets_passed = self.cmd_stepper.magnets_passed
            with self.stop_lock:
                if self.stop_cmd:
                    self.stop_cmd = False
                    break

    @property
    def is_moving(self):
        return not self.cmd_stepper.get_move_complete()

    @staticmethod
    def retry_query(func, error, retries=0):
        if retries < 3:
            retries += 1
            time.sleep(0.1)
            return func(retries)
        else:
            raise error


class LinearStepperMotor(StepperMotor):
    """
    Class for managing stepper motors with a finite linear travel.
    """
    def __init__(self, stepper_obj, device_config, serial_lock):
        """Initialise the linear stepper motor, consisting of a stepper motor with a limit switch

        Args:
            stepper_obj (CommandLinearAccelStepper): Commanduino object to send commands to the stepper motor
            device_config (dict): dictionary containing the configuration information
            serial_lock (Lock): Lock to maintain thread safety for serial connection.
        """
        super(LinearStepperMotor, self).__init__(stepper_obj, device_config, serial_lock)
        self.switch_state = 0
        self.encoder_error = False

    def check_endstop(self, retries=0):
        """
        Queries the attached limit switch state.

        Returns:
            int: 1 - switch triggered. 0 - switch open
        """
        try:
            with self.serial_lock:
                self.switch_state = self.cmd_stepper.get_switch_state()
        except exceptions.CMDeviceReplyTimeout as e:
            self.switch_state = self.retry_query(self.check_endstop, e, retries)
        return self.switch_state

    def refresh_switch_state(self):
        """Update the state of the limit switch from the CommandLinearAccelstepper object
        """
        self.switch_state = self.cmd_stepper.switch_state

    def home(self):
        """
        Sends command over serial to run the motor until the end-switch is triggered.
        """
        if not self.check_endstop():
            with self.serial_lock:
                self.cmd_stepper.home(False)
            self.watch_move()
            self.set_running_speed(self.running_speed)

    def watch_move(self):
        """
        Forces the executing thread to wait until the motor is finished moving or is told to stop. This allows the
        thread to be monitored for Task completion.
        """
        moving = True
        prev_time = time.time()
        while moving:
            if time.time() > prev_time + 0.2:
                if not self.is_moving:
                    moving = False
                    self.encoder_error = self.cmd_stepper.encoder_error
            with self.stop_lock:
                if self.stop_cmd:
                    self.stop_cmd = False
                    break
