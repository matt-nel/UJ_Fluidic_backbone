from Modules.Module import Module


class SelectorValve(Module):
    def __init__(self, name, module_info, cmduino, manager):
        self.name = name
        module_config = module_info["mod_config"]
        self.ports = module_config["ports"]
        super(SelectorValve, self).__init__(module_info, cmduino, manager)
        # todo add ability to accommodate variable number of ports
        self.pos_dict = {0: 0, 1: 320, 2: 640, 3: 960, 4: 1280, 5: 1600, 6: 1920, 7: 2240, 8: 2560, 9: 2880}
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
            stepper = self.steppers[0]
            he_sens = self.he_sensors[0]
            # check for true position within ~14 degree window
            cur_pos = stepper.get_current_position()
            stepper.move_to(self.positions[position])
            self.check_pos(5, True)
            cur_pos = stepper.get_current_position()
            if cur_pos != self.pos_dict[position]:
                self.pos_dict[position] = cur_pos
            self.pos_dict[position] = stepper.get_current_position()

    def home_valve(self):
        # todo add logging of information
        stepper = self.steppers[0]
        he_sens = self.he_sensors[0]
        home_positions, chk_pos = [[], []], [[], []]
        home_positions[0].append(stepper.get_current_position())
        home_positions[1].append(he_sens.analog_read())
        spr = stepper.steps_per_rev
        # get rough positions
        for i in range(0, 20):
            stepper.move_steps(spr/20)
            home_positions[0].append(stepper.get_current_position())
            home_positions[1].append(he_sens.analog_read())
        min_pos = min(home_positions[1])
        # index to 60 steps away from min pos
        stepper.move_to(home_positions[0][min_pos] - 60)
        # check for true min within 13.5 degree window
        self.check_pos(8, False)
        stepper.set_current_position(0)
        stepper.en_motor()

    def check_pos(self, increments, max_min):
        """
        :param increments: number of increments of 20 steps to move
        :param max_min: Whether to check maximum or minimum from hall sensor. False only used for 0 position
        :return:
        """
        stepper = self.steppers[0]
        he_sens = self.he_sensors[0]
        chk_pos = [[], []]
        for i in range(0, increments):
            chk_pos[0].append(stepper.get_current_position())
            chk_pos[1].append(he_sens.analog_read())
            stepper.move_steps(20)
        if max_min:
            target_pos = max(chk_pos[1])
        else:
            target_pos = min(chk_pos[1])
        stepper.move_to(chk_pos[0][target_pos])
