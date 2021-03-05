from Modules.Module import Module


class SelectorValve(Module):
    def __init__(self, name, module_info, cmduino, manager):
        self.name = name
        module_config = module_info["mod_config"]
        self.ports = module_config["ports"]
        super(SelectorValve, self).__init__(module_info, cmduino, manager)
        # todo add ability to accommodate variable number of ports
        self.pos_dict = {0: 0, 1: 320, 2: 640, 3: 960, 4: 1280, 5: 1600, 6: 1920, 7: 2240, 8: 2560, 9: 2880}
        self.homing_spd = 5000
        self.check_spd = 3000
        self.pos_threshold = 0
        self.neg_threshold = 0
        self.pos_he = []
        self.spr = self.steppers[0].steps_per_rev
        if self.spr != 3200:
            for position in range(10):
                self.pos_dict[position] = (self.spr/10)*position

    def move_to_pos(self, position):
        if position == 0:
            self.home_valve()
        else:
            self.ready = False
            stepper = self.steppers[0]
            he_sens = self.he_sensors[0]
            # check for true position within ~14 degree window
            stepper.move_to(self.pos_dict[position])
            # self.check_pos(5, True)
            cur_pos = stepper.get_current_position()
            if cur_pos != self.pos_dict[position]:
                self.pos_dict[position] = cur_pos
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
        stepper = self.steppers[0]
        he_sens = self.he_sensors[0]
        prev_speed = self.steppers[0].running_speed
        stepper.set_running_speed(self.homing_spd)
        home_positions, chk_pos = [[], []], [[], []]
        home_positions[0].append(stepper.get_current_position())
        home_positions[1].append(he_sens.analog_read())
        spr = stepper.steps_per_rev
        # get rough positions
        for i in range(0, 20):
            stepper.move_steps(spr/20)
            home_positions[0].append(stepper.get_current_position())
            home_positions[1].append(he_sens.analog_read())
        min_pos = home_positions[1].index(min(home_positions[1]))
        # index to 60 steps away from min pos
        stepper.move_to(home_positions[0][min_pos] - 60)
        # check for true min within 13.5 degree window
        self.check_pos(8, False)
        stepper.set_current_position(0)
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

    def zero(self):
        self.steppers[0].set_current_position(0)