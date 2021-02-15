from Modules.Module import Module
from threading import Thread


class SelectorValve(Module):
    def __init__(self, name, module_info, cmduino, manager):
        self.name = name
        module_config = module_info["mod_config"]
        self.ports = module_config["ports"]
        super(SelectorValve, self).__init__(module_info, cmduino, manager)
        # todo add ability to accommodate variable number of ports
        self.pos_dict = {0: 0, 1: 320, 2: 640, 3: 960, 4: 1280, 5: 1600, 6: 1920, 7: 2240, 8: 2560, 9: 2880}
        if self.steppers[0].steps_per_rev != 3200:
            for position in range(10):
                self.pos_dict[position] = (self.steppers[0].steps_per_rev/10)*position

    def move_to_pos(self, position):
        if position == 0:
            self.home_valve()
        else:
            stepper = self.steppers[0]
            he_sens = self.he_sensors[0]
            chk_pos = []
            # check for true position within ~14 degree window
            cur_pos = stepper.get_current_position()
            if cur_pos > self.pos_dict[position]:
                target_steps = cur_pos - self.pos_dict[position] + 60
                stepper.move_steps(-target_steps)
            else:
                target_steps = self.pos_dict[position] - cur_pos - 60
                stepper.move_steps(target_steps)
            for i in range(0, 7):
                stepper.move_steps(20)
                chk_pos.append(he_sens.analog_read())
            if position == 0:
                new_pos = stepper.get_current_position() - 120 + (chk_pos.index(min(chk_pos)) * 20)
            else:
                new_pos = stepper.get_current_position() - 120 + (chk_pos.index(max(chk_pos)) * 20)
            stepper.move_steps(-new_pos)
            self.pos_dict[position] = stepper.get_current_position()

    def home_valve(self):
        # todo add logging of information
        stepper = self.steppers[0]
        he_sens = self.he_sensors[0]
        home_positions, chk_pos = [], []
        stepper.set_current_position(0)
        spr = stepper.steps_per_rev
        # get rough positions
        for i in range(1, 41):
            stepper.move_steps(spr/40)
            home_positions.append(he_sens.analog_read())
        home_pos = home_positions.index(min(home_positions)) * (spr/40)
        # index to 100 steps away from home pos
        if home_pos > spr/2:
            target_steps = spr - home_pos + 100
            stepper.move_steps(-target_steps)
        else:
            stepper.move_steps(home_pos - 100)
        # check for true min within 11 degree window
        for i in range(0, 11):
            stepper.move_steps(spr/16)
            chk_pos.append(he_sens.analog_read())
        home_pos = stepper.get_current_position() - 100 + (chk_pos.index(min(chk_pos))*(spr/16))
        stepper.move_steps(home_pos)
        stepper.set_current_position(0)
        stepper.en_motor()

    def watch_move(self, position):
        if position == 0:
            Thread(target=self.home_valve).start()
        else:
            Thread(target=self.move_to_pos, args=(position,)).start()

