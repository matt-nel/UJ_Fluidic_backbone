from UJ_FB.Modules import modules
import time
import logging

DIFF_THRESHOLD = 20
ERROR_THRESHOLD = 20
POS_THRESHOLD = 580
NEG_THRESHOLD = 480
HOMING_SPEED = 5000


class SelectorValve(modules.Module):
    """
    Class for managing selector valves with one central inlet and multiple outlets.
    """

    def __init__(self, name, module_info, cmduino, manager):
        """
        :param name: String: name of the valve
        :param module_info: Dictionary: contains the configuration information
        :param cmduino: Commanduino Object: object for communicating with steppermotor and hall-effect sensor over the
        serial connection
        :param manager: Manager Object: coordinates modules
        """
        super(SelectorValve, self).__init__(name, module_info, cmduino, manager)
        self.type = "SV"
        self.syringe = None
        module_config = module_info["mod_config"]
        self.num_ports = module_config["ports"]
        # todo add ability to accommodate variable number of ports
        # {port: position in steps}
        self.pos_dict = {0: 0, 1: 320, 2: 640, 3: 960, 4: 1280, 5: 1600, 6: 1920, 7: 2240, 8: 2560, 9: 2880}
        # Dictionary keeps track of names of modules attached to each port and their associated object.
        self.ports = {-1: None, 0: None, 1: None, 2: None, 3: None, 4: None, 5: None, 6: None, 7: None,
                      8: None, 9: None}
        self.magnet_readings = self.manager.prev_run_config['magnet_readings'][self.name]
        if self.magnet_readings[0] == 0:
            self.magnet_readings = {0: POS_THRESHOLD, 2: NEG_THRESHOLD, 4: NEG_THRESHOLD,
                                    6: NEG_THRESHOLD, 8: NEG_THRESHOLD}
        self.adj_valves = []
        self.current_port = None
        # kd, kp
        self.pd_constants = [2, 0.5]
        self.check_spd = 3000
        self.pos_he = []
        geared = module_config['gear']
        self.spr = self.steppers[0].steps_per_rev
        if geared[0] != 'D':
            gear_ratio = float(geared.split(':')[0])
            # with 1/16 microstep ratio (3200 steps/rev) and 2:1 gear ratio, spr = 6400
            self.spr *= gear_ratio
            self.steppers[0].reverse_direction(True)
            self.geared = True
        else:
            self.geared = False
        if self.spr != 3200:
            for position in range(10):
                self.pos_dict[position] =int((self.spr / 10) * position)

    def init_valve(self):
        """
        Homes the valve before use
        """
        reading = self.he_sensors[0].analog_read()
        #if stepper between magnets
        #if reading near positive magnet
        if self.magnet_readings[0] - reading >  DIFF_THRESHOLD:
            self.find_opt(self.magnet_readings[0] + DIFF_THRESHOLD*2)
        else:
            self.home_valve()
        self.manager.prev_run_config['magnet_readings'][self.name] = self.magnet_readings

    def move_to_pos(self, position):
        """Moves the valve to a specific port

        Args:
            position (int): The number of the destination port
            task (Task object): Task associated with this function call
        """
        if self.current_port != position:
            self.ready = False
            stepper = self.steppers[0]
            stepper.move_to(self.pos_dict[position])
            self.check_pos(position)
            cur_pos = int(stepper.get_current_position())
            if cur_pos != self.pos_dict[position]:
                self.pos_dict[position] = cur_pos
            self.current_port = position
            self.ready = True

    def move_to_target(self, target, task):
        """ 
        Gets the required port for movement and moves to that port using move_to_pos
        string: name of module
        Args:
            target (string): name of the target module
        """
        target_found = False
        for port in self.ports.items():
            if port[1] is None:
                continue
            elif target in port[1].name:
                target_found = True
                self.move_to_pos(port[0])
                break
        if not target_found:
            self.write_log(f"{target} not found on valve {self.name}", level=logging.WARNING)
            task.error = True

    def jog(self, steps, direction, task):
        """Jogs the pump a number of steps

        Args:
            steps (int): number of steps to move
            direction (string): cc if counterclockwise
        """
        self.ready = False
        if direction == 'cc':
            steps = -steps
        self.steppers[0].move_steps(steps)
        self.ready = True

    def home_valve(self,):
        """
        Homes the valve using the hall-effect sensor
        """
        # todo add logging of information
        self.ready = False
        with self.stop_lock:
            self.stop_cmd = False
        stepper = self.steppers[0]
        he_sens = self.he_sensors[0]
        prev_speed = self.steppers[0].running_speed
        stepper.set_max_speed(HOMING_SPEED)
        stepper.set_current_position(0)
        max_reading = he_sens.analog_read()
        # Keep looking for home pos (reading >= max saved reading)
        while (max_reading < self.magnet_readings[0] - DIFF_THRESHOLD) or (max_reading > 1000) :
            reading = he_sens.analog_read()
            # if close to home pos
            if reading > POS_THRESHOLD:
                if self.find_opt(self.magnet_readings[0] + 100):
                    max_reading = he_sens.analog_read()
                    self.magnet_readings[0] = max_reading
                else:
                    max_reading = he_sens.analog_read()
            # Close to one of the negative magnets
            elif reading < NEG_THRESHOLD:
                if self.find_opt(NEG_THRESHOLD - 100):
                    # Move between magnets until close to home position
                    max_reading = self.check_all_positions()
            else:
                # We must be between magnets. Move 1/4 magnet distance looking for magnet positions. Testing shows magnet detection at ~1/4 spr to either side
                iterations = 0
                while NEG_THRESHOLD < reading < POS_THRESHOLD and iterations < 4:
                    stepper.move_steps(self.spr/20)
                    reading = he_sens.analog_read()
                    iterations += 1
            if self.check_stop:
                break
        #found the positive magnet
        if not self.check_stop:
            stepper.set_current_position(0)
            self.current_port = 0
            reading = he_sens.analog_read()
            if abs(self.magnet_readings[0] - reading) > 20:
                self.magnet_readings[0] = reading
                for i in range(1, 5):
                    stepper.move_steps(self.spr / 5)
                    self.magnet_readings[i * 2] = he_sens.analog_read()
                stepper.move_steps(self.spr / 5)
        else:
            self.current_port = None
        stepper.set_running_speed(prev_speed)
        self.current_port = 0
        self.ready = True

    def find_opt(self, target):
        """Finds a local optimum for the magnet reading from the hall effect sensor using a PID controller

        Args:
            target (int): The target reading

        Returns:
            bool: True if optimum found, False otherwise
        """
        kd, kp = self.pd_constants
        direction = True
        dir_changes = 0
        iters = 0
        readings = [self.he_sensors[0].analog_read()]
        opt_pos = self.steppers[0].get_current_position()
        error = abs(target - readings[-1])
        last_error = error
        prev_time = time.time()
        errors = [error]
        while abs(error) > ERROR_THRESHOLD:
            iters += 1
            dt = time.time() - prev_time
            if dt == 0.0:
                dt += 0.1
            prop_error = kp * error
            # if error < last error, kd*de/dt = neg
            deriv_error = kd * ((error - last_error) / dt)
            # moving in wrong direction
            if error > last_error + 15:
                direction = not direction
                dir_changes += 1
            #if stepper moving anticlockwise
            if direction is False:
                prop_error = -prop_error
            u = prop_error + deriv_error
            last_error = error
            prev_time = time.time()
            self.steppers[0].move_steps(u)
            readings.append(self.he_sensors[0].analog_read())
            # Found new minimum
            if target < NEG_THRESHOLD and readings[-1] < min(readings):
                opt_pos = self.steppers[0].get_current_position()
            # Found new_maximum
            elif target > POS_THRESHOLD and readings[-1] > max(readings[0:-1]):
                opt_pos = self.steppers[0].get_current_position()
            error = abs(target - readings[-1])
            errors.append(error)
            if self.check_stop:
                return False
            if iters > 10 or dir_changes > 2:
                self.steppers[0].move_to(opt_pos)
                opt = self.he_sensors[0].analog_read()
                if opt > self.magnet_readings[0]:
                    self.magnet_readings[0] = opt
                return True
        return True

    def check_all_positions(self):
        """Looks for the magnet at the home position (0), which has a reading above 600

        Args:
            max_reading (int): Current maximum reading

        Returns:
            int: Returns the max reading parameter if no new maximum found, or returns the new maximum reading
        """
        #keys are HE readings, values are stepper positions
        readings = {}
        for i in range(0, 5):
            self.steppers[0].move_steps(self.spr / 5)
            reading = self.he_sensors[0].analog_read()
            readings[reading] = self.steppers[0].get_current_position()
            if reading >= 600:
                return readings[reading]
            if self.check_stop:
                break
            if 500 < reading < 550:
                return reading
        # move to the maximum of these positions
        max_reading = max(readings.keys())
        self.steppers[0].move_to(readings[max_reading])
        return max_reading

    def check_pos(self, position):
        """Checks whether the magnet reading at position is within 20 of the reference value

        Args:
            position (int): The port number to check
        """
        if position in self.magnet_readings:
            reading = self.he_sensors[0].analog_read()
            if position == 0:
                if reading < self.magnet_readings[position] + DIFF_THRESHOLD:
                    self.find_opt(self.magnet_readings[position])
            else:
                if reading > self.magnet_readings[position] + DIFF_THRESHOLD:
                    self.find_opt(self.magnet_readings[position])
            new_read = self.he_sensors[0].analog_read()
            if position == 0:
                if reading < self.magnet_readings[position] + DIFF_THRESHOLD:
                    self.home_valve()
                    self.move_to_pos(position)
            else:
                if reading > self.magnet_readings[position] + DIFF_THRESHOLD:
                    self.home_valve()
                    self.move_to_pos(position)
            self.manager.prev_run_config['magnet_readings'][self.name] = self.magnet_readings
            self.manager.rc_changes = True

    def zero(self):
        """
        Sets the position of the valve to zero, making this the home position
        """
        self.steppers[0].set_current_position(0)
        self.current_port = 0

    def he_read(self):
        """
        Reads the hall effect sensor
        """
        reading = self.he_sensors[0].analog_read()
        self.write_to_gui( f'{self.name} he sensor reading is {reading}', level=logging.INFO)

    @staticmethod
    def reverse_steps(steps, fwd):
        """Reverses the steps if direction needs to be reversed

        Args:
            steps (int): The number of steps to move
            fwd (bool): True if moving clockwise, False otherwise

        Returns:
            int: the steps, reversed if necessary.
        """
        if not fwd:
            steps = -steps
        return steps

    @property
    def check_stop(self):
        with self.stop_lock:
            return self.stop_cmd

    def stop(self):
        """
        Stops the valve movement
        """
        with self.stop_lock:
            self.stop_cmd = True
        with self.steppers[0].stop_lock:
            self.steppers[0].stop_cmd = True
        self.steppers[0].stop()

    def resume(self, command_dicts):
        """
        Checks if the command can be resumed.

        Args:
            command_dicts (dictionary): The dictionaries representing the commands

        Returns:
            bool: True if resuming, False otherwise
        """
        if command_dicts[0]['command'] == 'home':
            return True
        else:
            # add home and then valve move cmds to task command dict list.
            command_home = {'mod_type': 'valve', 'module_name': self.name, 'command': 'home',
                            'parameters': {'wait': True}}
            command_move_pos = {'mod_type': 'valve', 'module_name': self.name, 'command': command_dicts[0]['command'],
                                'parameters': {'wait': True}}
            command_dicts[0] = command_home
            command_dicts.append(command_move_pos)
            return True
