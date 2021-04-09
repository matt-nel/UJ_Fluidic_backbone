from Modules.modules import Module
import time


class SelectorValve(Module):
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
        module_config = module_info["mod_config"]
        self.num_ports = module_config["ports"]
        # todo add ability to accommodate variable number of ports
        # {port: position in steps}
        self.pos_dict = {0: 0, 1: 320, 2: 640, 3: 960, 4: 1280, 5: 1600, 6: 1920, 7: 2240, 8: 2560, 9: 2880}
        # Dictionary keeps track of names of modules attached to each port and their associated object.
        self.ports = {-1: {'name': '', 'object': None}, 0: {'name': '', 'object': None}, 1: {'name': '', 'object': None},
                      2: {'name': '', 'object': None}, 3: {'name': '', 'object': None}, 4: {'name': '', 'object': None},
                      5: {'name': '', 'object': None}, 6: {'name': '', 'object': None}, 7: {'name': '', 'object': None},
                      8: {'name': '', 'object': None}, 9: {'name': '', 'object': None}}
        self.current_port = None
        self.homing_spd = 5000
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
                self.pos_dict[position] = (self.spr/10)*position

    def move_to_pos(self, position):
        if self.current_port != position:
            self.ready = False
            stepper = self.steppers[0]
            stepper.move_to(self.pos_dict[position])
            if self.geared:
                time.sleep(0.3)
            cur_pos = stepper.get_current_position()
            if cur_pos != self.pos_dict[position]:
                self.pos_dict[position] = cur_pos
            self.current_port = position
            if position == 5 and self.he_sensors[0].analog_read() < 700:
                self.home_valve()
            self.ready = True

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
        delay = 0.3
        stepper = self.steppers[0]
        he_sens = self.he_sensors[0]
        prev_speed = self.steppers[0].running_speed
        stepper.set_running_speed(self.homing_spd)
        stepper.set_current_position(0)
        max_pos = 0
        fwd = True
        max_reading = he_sens.analog_read()
        iterations = 0
        while max_reading < 700:
            if max_reading < 600:
                reading_history = []
                for i in range(10):
                    stepper.move_steps(self.spr/10, True)
                    sensor_reading = he_sens.analog_read()
                    reading_history.append(sensor_reading)
                    if self.check_stop:
                        break
                    if sensor_reading > 550:
                        max_pos = stepper.get_current_position()
                        max_reading = sensor_reading
                        break
                if i >= 9 and max_reading < 550:
                    max_tmp = max(reading_history)
                    pos = reading_history.index(max_tmp)
                    stepper.move_to(i*pos, True)
                    stepper.move_steps(-320, True)
                    rvs_read = he_sens.analog_read()
                    stepper.move_steps(640, True)
                    fwd_read = he_sens.analog_read()
                    if rvs_read > fwd_read:
                        stepper.move_steps(-640, True)
                        max_reading = rvs_read
                    else:
                        max_reading = fwd_read
                    max_pos = stepper.get_current_position()
            elif 550 < max_reading < 700:
                prev_reading = max_reading
                steps = 320 * (iterations + 1)
                upper_limit = steps / 80
                for i in range(upper_limit):
                    steps = self.reverse_steps(steps, fwd)
                    stepper.move_steps(steps, True)
                    time.sleep(delay)
                    sensor_reading = he_sens.analog_read()
                    if sensor_reading > prev_reading:
                        max_reading = sensor_reading
                    else:
                        fwd = not fwd
                    steps = steps / 2
                    if max_reading > 700:
                        break
                if max_reading == prev_reading:
                    stepper.move_to(max_pos, True)
            if self.check_stop:
                break
        if not self.check_stop:
            stepper.move_steps(3200)
            stepper.set_current_position(0)
            self.current_port = 0
            stepper.set_running_speed(prev_speed)
        else:
            self.current_port = None
        stepper.set_running_speed(prev_speed)
        stepper.en_motor()
        self.ready = True

    def check_pos(self, increments, max_min):
        """
        :param increments: number of increments of 20 steps to move
        :param max_min: Whether to check maximum or minimum from hall sensor. False only used for 0 position
        :return:
        """
        stepper = self.steppers[0]
        he_sens = self.he_sensors[0]
        prev_speed = self.steppers[0].running_speed
        stepper.set_running_speed(self.check_spd)
        chk_pos = [[], []]
        for i in range(0, increments):
            chk_pos[0].append(stepper.get_current_position())
            chk_pos[1].append(he_sens.analog_read())
            stepper.move_steps(20)
        if max_min:
            target_pos = chk_pos[1].index(max(chk_pos[1]))
        else:
            target_pos = chk_pos[1].index(min(chk_pos[1]))
        stepper.move_to(chk_pos[0][target_pos])
        stepper.set_running_speed(prev_speed)

    def zero(self):
        self.steppers[0].set_current_position(0)
        self.current_port = 0

    def he_read(self):
        reading = self.he_sensors[0].analog_read()
        message = f'{self.name} he sensor reading is {reading}'
        self.write_to_gui(message)

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
            command_home = {'mod_type': 'valve', 'module_name': self.name, 'command': 'home', 'parameters': {'wait': True}}
            command_move_pos = {'mod_type': 'valve', 'module_name': self.name, 'command': command_dicts[0]['command'], 'parameters': {'wait': True}}
            command_dicts[0] = command_home
            command_dicts.append(command_move_pos)
            return True




