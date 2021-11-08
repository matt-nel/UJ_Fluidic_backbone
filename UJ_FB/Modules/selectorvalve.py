from UJ_FB.Modules import modules
import time
import logging

DIFF_THRESHOLD = 20
ERROR_THRESHOLD = 20
POS_THRESHOLD = 600
NEG_THRESHOLD = 490
HOMING_SPEED = 5000
OPT_SPEED = 2000


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
        self.pos_dict = {1: 0, 2: 320, 3: 640, 4: 960, 5: 1280, 6: 1600, 7: 1920, 8: 2240, 9: 2560, 10: 2880}
        # Dictionary keeps track of names of modules attached to each port and their associated object.
        self.ports = {-1: None, 1: None, 2: None, 3: None, 4: None, 5: None, 6: None, 7: None, 8: None,
                      9: None, 10: None}
        self.magnet_readings = self.manager.prev_run_config['magnet_readings'][self.name]
        if self.magnet_readings[1] == 0:
            self.magnet_readings = {1: POS_THRESHOLD, 3: NEG_THRESHOLD, 5: NEG_THRESHOLD,
                                    7: NEG_THRESHOLD, 9: NEG_THRESHOLD}
        self.times_checked = 0
        self.readings_history = []
        self.adj_valves = []
        self.current_port = None
        # kd, kp
        self.pd_constants = [1.5, 0.5]
        self.check_spd = 3000
        self.pos_he = []
        geared = module_config['gear']
        self.stepper = self.steppers[0]
        self.he_sensor = self.he_sensors[0]
        self.reading = self.he_sensor.analog_read()
        self.spr = self.stepper.steps_per_rev
        self.last_direction = 'F'
        self.current_direction = 'F'
        if geared[0] != 'D':
            gear_ratio = float(geared.split(':')[0])
            # with 1/16 microstep ratio (3200 steps/rev) and 2:1 gear ratio, spr = 6400
            self.spr *= gear_ratio
            self.stepper.reverse_direction(True)
            self.geared = True
            self.backlash = self.manager.prev_run_config['backlash']['backlash_steps']
        else:
            self.geared = False
        if self.spr != 3200:
            for position in range(1, 11):
                self.pos_dict[position] = int((self.spr / 10) * (position-1))

    def init_valve(self):
        """
        Homes the valve before use
        """
        self.reading = self.he_sensors[0].analog_read()
        # if reading near positive magnet
        if self.reading > POS_THRESHOLD:
            self.find_opt(POS_THRESHOLD + 150)
        # if near negative magnet
        elif self.reading < NEG_THRESHOLD:
            self.find_opt(NEG_THRESHOLD -  150)
            self.check_all_positions()
        # ended up between magnets
        self.reading = self.he_sensor.analog_read()
        if self.reading < POS_THRESHOLD or self.reading < self.magnet_readings[1]:
            self.home_valve()
        # check magnet positions against config
        check_value = False
        for value in self.magnet_readings.values():
            if 500 < value < 550:
                check_value = True
        if check_value:
            self.check_magnets()
            self.find_opt(self.magnet_readings[1] + 40)
        # Counter goes up each time robot started or homes. When counter at 5, check the magnet positions
        if self.manager.prev_run_config['magnet_readings']['check_magnets'] % 10 == 0 and not check_value:
            self.check_magnets()
        if self.geared:
            if self.manager.prev_run_config['backlash']['check_backlash'] % 10 == 0 or self.backlash == 0:
                self.check_backlash()
        self.manager.prev_run_config['magnet_readings']['check_magnets'] += 1
        self.manager.prev_run_config['backlash']['check_backlash'] += 1
        self.current_port = 1
        self.stepper.set_current_position(0)

    def move_to_pos(self, position, check=True):
        """Moves the valve to a specific port

        Args:
            position (int): The number of the destination port
            task (Task object): Task associated with this function call
        """
        if self.current_port != position:
            backlash = 0
            # we need to move backwards
            if self.current_port > position:
                self.last_direction = self.current_direction
                self.current_direction = 'R'
            elif self.current_port < position:
                self.last_direction = self.current_direction
                self.current_direction = 'F'
            if self.last_direction != self.current_direction:
                backlash = self.backlash
                if self.current_direction == 'R':
                    backlash = -backlash
            self.ready = False
            self.stepper.move_to(self.pos_dict[position] + backlash)
            if check:
                self.check_pos(position)
            cur_stepper_pos = int(self.stepper.get_current_position())
            if cur_stepper_pos != self.pos_dict[position]:
                self.stepper.set_current_position(self.pos_dict[position])
            self.current_port = position
            self.ready = True

    def move_to_target(self, target, task):
        """ 
        Gets the required port for movement and moves to that port using move_to_pos
        string: name of module
        Args:
            target (string): name of the target module
        """
        for i, port in enumerate(self.ports.items()):
            if port[1] is None:
                if target == 'empty':
                    self.move_to_pos(i)
                    return
                continue
            elif target in port[1].name:
                self.move_to_pos(port[0])
                return
        self.write_log(f"{target} not found on valve {self.name}", level=logging.WARNING)
        task.error = True

    def find_target(self, target):
        target_found = False
        for port in self.ports.items():
            if port[1] is None:
                continue
            elif target in port[1].name:
                target_found = True
        return target_found

    def jog(self, steps, invert_direction):
        """Jogs the pump a number of steps

        Args:
            steps (int): number of steps to move
            direction (string): cc if counterclockwise
        """
        self.ready = False
        if invert_direction:
            steps = -steps
        self.stepper.move_steps(steps)
        self.ready = True

    def home_valve(self):
        """
        Homes the valve using the hall-effect sensor
        """
        # Counter goes up each time robot started or homes. When counter at 5, check the magnet positions
        self.manager.prev_run_config['magnet_readings']['check_magnets'] += 1
        self.manager.rc_changes = True
        self.ready = False
        with self.stop_lock:
            self.stop_cmd = False
        prev_speed = self.stepper.running_speed
        self.stepper.set_max_speed(HOMING_SPEED)
        if self.current_port is not None:
            self.move_to_pos(1, check=False)
        self.stepper.set_current_position(0)
        self.reading = self.he_sensor.analog_read()
        # Keep looking for home pos (reading >= max saved reading)
        while (self.reading < self.magnet_readings[1] - DIFF_THRESHOLD) or (self.reading > 1000) or self.reading < POS_THRESHOLD :
            self.reading = self.he_sensor.analog_read()
            # if close to home pos
            if self.reading > POS_THRESHOLD:
                if self.find_opt(POS_THRESHOLD + 250):
                    self.magnet_readings[1] = self.reading
            # Close to one of the negative magnets
            elif self.reading < NEG_THRESHOLD:
                if self.find_opt(NEG_THRESHOLD - 150):
                    # Move between magnets until close to home position
                    self.reading = self.check_all_positions()
            else:
                # We must be between magnets. Move 1/4 magnet distance looking for magnet positions. Testing shows magnet detection at ~1/4 spr to either side
                self.find_next_magnet()
            if self.check_stop:
                break
        # found the positive magnet
        if not self.check_stop:
            self.stepper.set_current_position(0)
            self.current_port = 1
            self.reading = self.he_sensor.analog_read()
        # had to stop unexpectedly
        else:
            self.current_port = None
        if self.manager.prev_run_config['magnet_readings']['check_magnets'] % 10 == 0:
            self.check_magnets()
        self.stepper.set_max_speed(prev_speed)
        self.ready = True

    def find_opt(self, target):
        """Finds a local optimum for the magnet reading from the hall effect sensor using a PID controller

        Args:
            target (int): The target reading

        Returns:
            bool: True if optimum found, False otherwise
        """
        self.stepper.set_max_speed(OPT_SPEED)
        kd, kp = self.pd_constants
        direction = True
        dir_changes = 0
        iters = 0
        readings = [self.reading]
        opt_pos = self.stepper.get_current_position()
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
            u = prop_error + deriv_error
            # moving in wrong direction
            if error > last_error + 10:
                direction = not direction
                dir_changes += 1
                u += self.backlash
            if direction is False:
                u = -u
            last_error = error
            prev_time = time.time()
            self.stepper.move_steps(u)
            readings.append(self.he_sensor.analog_read())
            # Found new minimum
            if target < NEG_THRESHOLD and readings[-1] < min(readings):
                opt_pos = self.stepper.get_current_position()
            # Found new_maximum
            elif target > POS_THRESHOLD and readings[-1] > max(readings[0:-1]):
                opt_pos = self.stepper.get_current_position()
            error = abs(target - readings[-1])
            errors.append(error)
            if self.check_stop:
                self.stepper.set_max_speed(HOMING_SPEED)
                return False
            if iters > 10 or dir_changes > 3:
                self.stepper.move_to(opt_pos)
                opt = self.he_sensor.analog_read()
                if opt > self.magnet_readings[1]:
                    self.magnet_readings[1] = opt
                self.reading = opt
                self.stepper.set_max_speed(HOMING_SPEED)
                break
        return True

    def check_all_positions(self):
        """Looks for the magnet at the home position (0), which has a reading above 600

        Args:
            max_reading (int): Current maximum reading

        Returns:
            int: Returns the max reading parameter if no new maximum found, or returns the new maximum reading
        """
        # keys are HE readings, values are stepper positions
        readings = {}
        for i in range(5):
            self.stepper.move_steps(self.spr / 5)
            self.reading = self.he_sensors[0].analog_read()
            readings[self.reading] = self.stepper.get_current_position()
            if self.reading >= POS_THRESHOLD:
                break
            if self.check_stop:
                break
        # move to the maximum of these positions
        max_reading = max(readings.keys())
        self.find_opt(self.magnet_readings[1] + 40)
        return max_reading

    def check_magnets(self):
        """Checks all the magnet positions and updates the configuration
        """
        if self.reading < POS_THRESHOLD:
            self.home_valve()
        for i in range(1, 5):
            self.stepper.move_steps(self.spr/5)
            # move to position 3, 5, 7, 9
            reading = self.he_sensors[0].analog_read()
            self.magnet_readings[i*2+1] = reading
        self.manager.prev_run_config['magnet_readings'][self.name] = self.magnet_readings
        self.manager.rc_changes = True
        # move back to 0
        self.stepper.move_steps(self.spr/5)

    def check_pos(self, position):
        """Checks whether the magnet reading at position is within 20 of the reference value

        Args:
            position (int): The port number to check
        """
        magnets_passed = self.stepper.magnets_passed
        positions_moved = 0
        pos_diff = abs(self.current_port - position)
        invert_direction = False
        # moving CCW
        if self.current_port > position:
            invert_direction = True
        req_magnets = pos_diff//2
        # if we start on an even position, will pass an additional magnet (magnets on starting position aren't counted)
        if self.current_port % 2 == 0 and position % 2 == 1:
            req_magnets += 1
        # If position has a magnet, check against the magnets dictionary.
        if magnets_passed < req_magnets:
            if position in self.magnet_readings:
                self.reading = self.he_sensors[0].analog_read()
                if position == 1:
                    if self.reading < self.magnet_readings[position] + DIFF_THRESHOLD:
                        self.find_opt(self.magnet_readings[position]+50)
                        self.reading = self.he_sensor.analog_read()
                    # if this is still true, we must have lost position.
                    if self.reading < self.magnet_readings[position] + DIFF_THRESHOLD:
                        self.home_valve()
                        self.move_to_pos(position)
                else:
                    if self.reading > self.magnet_readings[position] + DIFF_THRESHOLD:
                        self.find_opt(self.magnet_readings[position]-50)
                        self.reading = self.he_sensor.analog_read()
                    # if this is still true, we must have lost position.
                    if self.reading > self.magnet_readings[position] + DIFF_THRESHOLD and self.times_checked < 2:
                        self.readings_history.append(self.reading)
                        self.home_valve()
                        self.times_checked += 1
                        self.move_to_pos(position)
                    # we've homed 3 times, this must be the position
                    elif self.times_checked >= 2:
                        self.magnet_readings[position] = min(self.readings_history)
            else:
                self.home_valve()
                self.move_to_pos(position)
            self.manager.prev_run_config['magnet_readings'][self.name] = self.magnet_readings
            self.manager.rc_changes = True
        self.times_checked = 0
    
    def find_next_magnet(self, invert_direction=False):
        reading = self.he_sensor.analog_read()
        iterations = 0
        steps = self.spr/20
        if invert_direction:
            steps = -steps
        while NEG_THRESHOLD < reading < POS_THRESHOLD and iterations < 4:
            self.stepper.move_steps(steps)
            reading = self.he_sensor.analog_read()
            iterations += 1

    def check_backlash(self):
        i = 0
        start_pos = self.stepper.get_current_position()
        # we start at zero.
        # move in fwd direction to next magnet
        self.stepper.move_steps(self.spr/5)
        # move back
        self.stepper.move_steps(-self.spr/5)
        # get within 10 of reading
        start_reading = self.he_sensor.analog_read()
        last_reading = start_reading
        reading = start_reading
        while reading < (self.magnet_readings[1] - 20):
            self.stepper.move_steps(-10)
            if last_reading > reading:
                if last_reading <= start_reading:
                    self.stepper.move_to(start_pos)
                break
            i += 1
            last_reading = reading
            reading = self.he_sensor.analog_read()
        self.backlash = i * 10
        self.manager.prev_run_config['backlash']['backlash'] = self.backlash

    def zero(self):
        """
        Sets the position of the valve to zero, making this the home position
        """
        self.stepper.set_current_position(0)
        self.current_port = 1

    def he_read(self):
        """
        Reads the hall effect sensor
        """
        reading = self.he_sensor.analog_read()
        self.write_log( f'{self.name} he sensor reading is {reading}', level=logging.INFO)

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
        with self.stepper.stop_lock:
            self.stepper.stop_cmd = True
        self.stepper.stop()

    def resume(self, command_dicts):
        """
        Checks if the command can be resumed.

        Args:
            command_dicts (list): The dictionaries representing the commands

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
