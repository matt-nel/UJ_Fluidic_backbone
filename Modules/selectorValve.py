from Modules.Module import Module
import time


class SelectorValve(Module):
    def __init__(self, name, module_info, cmduino, manager):
        self.name = name
        module_config = module_info["mod_config"]
        self.ports = module_config["ports"]
        super(SelectorValve, self).__init__(module_info, cmduino, manager)
        # todo add ability to accommodate variable number of ports
        self.pos_dict = {0: 0, 1: 320, 2: 640, 3: 960, 4: 1280, 5: 1600, 6: 1920, 7: 2240, 8: 2560, 9: 2880}
        self.port_names = {-1: '', 0: '', 1: '', 2: '', 3: '', 4: '', 5: '', 6: '', 7: '', 8: '', 9: ''}
        self.used_ports = []
        self.port_objects = {-1: None, 0: None, 1: None, 2: None, 3: None, 4: None, 5: None, 6: None, 7: None, 8: None, 9: None}
        self.current_port = None
        self.homing_spd = 5000
        self.check_spd = 3000
        self.pos_threshold = 0
        self.neg_threshold = 0
        self.pos_he = []
        geared = module_config['gear']
        self.spr = self.steppers[0].steps_per_rev
        if geared[1] != 'D':
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
            # check for true position within ~14 degree window
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
        self.steppers[0].en_motor()
        self.ready = True

    def home_valve(self):
        # todo add logging of information
        self.ready = False
        delay = 0.3
        stepper = self.steppers[0]
        he_sens = self.he_sensors[0]
        prev_speed = self.steppers[0].running_speed
        stepper.set_running_speed(self.homing_spd)
        stepper.set_current_position(0)
        max_pos = 0
        direction = True
        fwd = True
        max_reading = he_sens.analog_read()
        while max_reading < 700:
            if max_reading < 600:
                cnt = 0
                for i in range(10):
                    stepper.move_steps(self.spr/10)
                    sensor_reading = he_sens.analog_read()
                    time.sleep(delay)
                    if sensor_reading > 550:
                        max_pos = stepper.get_current_position()
                        max_reading = sensor_reading
                        break
                    cnt += 1
                if cnt > 9 and max_reading < 550:
                    stepper.move_steps(320)
            elif 600 < max_reading < 700:
                prev_reading = max_reading
                steps = 320
                for i in range(3):
                    steps = self.reverse_steps(steps, fwd)
                    stepper.move_steps(steps)
                    time.sleep(delay)
                    sensor_reading = he_sens.analog_read()
                    if sensor_reading > prev_reading:
                        max_reading = sensor_reading
                    else:
                        fwd = not fwd
                    steps = steps / 2
                if max_reading == prev_reading:
                    stepper.move_to(max_pos)
                    max_reading = he_sens.analog_read()
                    direction = not direction
        stepper.move_steps(3200)
        stepper.set_current_position(0)
        self.current_port = 0
        stepper.en_motor()
        stepper.set_running_speed(prev_speed)
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
        stepper.en_motor(False)

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