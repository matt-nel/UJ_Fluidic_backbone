from UJ_FB.Modules import modules
import time
import logging

DEFAULT_LOWER_LIMIT = 350
DEFAULT_UPPER_LIMIT = 650
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
            self.magnet_readings = {0: DEFAULT_UPPER_LIMIT, 2: DEFAULT_LOWER_LIMIT, 4: DEFAULT_LOWER_LIMIT,
                                    6: DEFAULT_LOWER_LIMIT, 8: DEFAULT_LOWER_LIMIT}
        self.adj_valves = []
        self.current_port = None
        # kd, kp
        self.pd_constants = [2, 0.5]
        self.check_spd = 3000
        self.pos_threshold = 0
        self.neg_threshold = 0
        self.pos_he = []
        geared = module_config['gear']
        self.spr = self.steppers[0].steps_per_rev
        if geared[0] != 'D':
            gear_ratio = float(geared.split(':')[0])
            self.spr *= gear_ratio
            self.steppers[0].reverse_direction(True)
            self.geared = True
        else:
            self.geared = False
        if self.spr != 3200:
            for position in range(10):
                self.pos_dict[position] = (self.spr / 10) * position

    def init_valve(self):
        reading = self.he_sensors[0].analog_read()
        if 500 < reading < 550:
            self.steppers[0].move_steps(self.spr/10)
        max_read = self.he_sensors[0].analog_read()
        if max_read < self.magnet_readings[0] - 10:
            if max_read < 600:
                max_read = self.check_all_positions(max_read)
        if max_read < (self.magnet_readings[0] - 10):
            self.home_valve()
        self.manager.prev_run_config['magnet_readings'][self.name] = self.magnet_readings

    def move_to_pos(self, position):
        if self.current_port != position:
            self.ready = False
            stepper = self.steppers[0]
            stepper.move_to(self.pos_dict[position])
            self.check_pos(position)
            cur_pos = stepper.get_current_position()
            if cur_pos != self.pos_dict[position]:
                self.pos_dict[position] = cur_pos
            self.current_port = position
            self.ready = True

    def move_to_target(self, target):
        """
        Gets the required port for movement and moves to that port using move_to_pos
        :param target: string: name of module
        :return:
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

    def jog(self, steps, direction):
        self.ready = False
        if direction == 'cc':
            steps = -steps
        self.steppers[0].move_steps(steps)
        self.ready = True

    def home_valve(self):
        # todo add logging of information
        self.ready = False
        with self.stop_lock:
            self.stop_cmd = False
        stepper = self.steppers[0]
        he_sens = self.he_sensors[0]
        prev_speed = self.steppers[0].running_speed
        stepper.set_running_speed(HOMING_SPEED)
        stepper.set_current_position(0)
        max_reading = he_sens.analog_read()
        # Keep looking for home pos (reading > 700)
        while max_reading < self.magnet_readings[0] - 10:
            read = he_sens.analog_read()
            # Close to home pos
            if read > 600:
                if self.find_opt(self.magnet_readings[0]):
                    max_reading = he_sens.analog_read()
                    self.magnet_readings[0] = max_reading
                else:
                    max_reading = he_sens.analog_read()
            # Close to one of the negative magnets
            elif read < 500:
                if self.find_opt(330):
                    # Move between magnets until close to home position
                    max_reading = self.check_all_positions(max_reading)
            else:
                # Move around looking for magnet positions
                move = self.spr / 10
                stepper.move_steps(move, True)
                read = he_sens.analog_read()
                iterations = 0
                # Move smaller increments looking for magnets
                while 450 < read < 550 and iterations < 3:
                    move = move / 2
                    stepper.move_steps(move, True)
                    read = he_sens.analog_read()
                    iterations += 1
            if self.check_stop:
                break
        if not self.check_stop:
            stepper.set_current_position(0)
            self.current_port = 0
            reading = he_sens.analog_read()
            if abs(self.magnet_readings[0] - reading) > 20:
                self.magnet_readings[0] = he_sens.analog_read()
                for i in range(1, 5):
                    stepper.move_steps(self.spr / 5, True)
                    self.magnet_readings[i * 2] = he_sens.analog_read()
                stepper.move_steps(self.spr / 5, True)
        else:
            self.current_port = None
        stepper.set_running_speed(prev_speed)
        self.current_port = 0
        self.ready = True

    def find_opt(self, target):
        kd, kp = self.pd_constants
        direction = True
        iters = 0
        readings = [self.he_sensors[0].analog_read()]
        opt_pos = self.steppers[0].get_current_position()
        error = abs(target - readings[-1])
        last_error = error
        last_u = 0
        prev_time = time.time()
        errors = [error]
        while abs(error) > 20:
            iters += 1
            dt = time.time() - prev_time
            if dt == 0.0:
                dt += 0.1
            prop_error = kp * error
            # if error < last error, kd*de/dt = neg
            derv_error = kd * ((error - last_error) / dt)
            # moving in wrong direction
            if error - last_error > 20:
                direction = not direction
            if direction is False:
                prop_error = -prop_error
            u = prop_error + derv_error
            last_error = error
            prev_time = time.time()
            self.steppers[0].move_steps(u, True)
            readings.append(self.he_sensors[0].analog_read())
            # Found new minimum
            if target < 400 and readings[-1] < min(readings):
                opt_pos = self.steppers[0].get_current_position()
            # found new_maximum
            elif readings[-1] > max(readings[0:-1]):
                opt_pos = self.steppers[0].get_current_position()
            error = abs(target - readings[-1])
            errors.append(error)
            last_u = u
            if self.check_stop:
                return False
            elif readings[-1] > self.magnet_readings[0] or readings[-1] < DEFAULT_LOWER_LIMIT:
                break
            if iters > 10:
                self.steppers[0].move_to(opt_pos)
                opt = self.he_sensors[0].analog_read()
                if opt > 700:
                    self.magnet_readings[0] = opt
                break
        return True

    def check_all_positions(self, max_reading):
        for i in range(0, 5):
            self.steppers[0].move_steps(self.spr / 5, True)
            read = self.he_sensors[0].analog_read()
            if read >= 600:
                return read
            if self.check_stop:
                break
        return max_reading

    def check_pos(self, position):
        """
        :param position: position to move to
        :return:
        """
        if position in self.magnet_readings:
            reading = self.he_sensors[0].analog_read()
            if position == 0:
                if reading < self.magnet_readings[position] + 10:
                    self.find_opt(self.magnet_readings[position])
            else:
                if reading > self.magnet_readings[position] + 10:
                    self.find_opt(self.magnet_readings[position])
            self.manager.prev_run_config['magnet_readings'][self.name] = self.magnet_readings
            self.manager.rc_changes = True

    def zero(self):
        self.steppers[0].set_current_position(0)
        self.current_port = 0

    def he_read(self):
        reading = self.he_sensors[0].analog_read()
        self.write_to_gui( f'{self.name} he sensor reading is {reading}', level=logging.INFO)

    @staticmethod
    def reverse_steps(steps, fwd):
        if not fwd:
            steps = -steps
        return steps

    @property
    def check_stop(self):
        with self.stop_lock:
            return self.stop_cmd

    def stop(self):
        with self.stop_lock:
            self.stop_cmd = True
        with self.steppers[0].stop_lock:
            self.steppers[0].stop_cmd = True
        self.steppers[0].stop()

    def resume(self, command_dicts):
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
