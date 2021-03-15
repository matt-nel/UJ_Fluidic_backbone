from Modules.Module import Module


class SyringePump(Module):
    """
    Syringe pump module class for managing all equipment required for a syringe pump. 0 position corresponds to syringe
    max length
    """
    # TODO tracking of whether syringe currently contains reagents
    # todo add position update function
    # todo allow syringe to move after endstop hit if movement in withdraw direction
    cor_fact = 0.993  # correction factor for dispensed volume
    # {volume: length in mm}
    syr_lengths = {1000: 58, 2000: 2, 4000: 42, 5000: 58, 10000: 58, 20000: 20, 60000: 90}

    def __init__(self, name, module_info, cmd_mng, manager):
        """
        :param name: syringe pump name
        :param module_info: Dictionary containing IDs of attached devices and their configuration information
        :param cmd_mng: commanduino command manager object
        """
        self.name = name
        module_config = module_info["mod_config"]
        self.syr_vol = module_config["volume"]
        self.syr_length = self.syr_lengths[self.syr_vol]
        self.screw_pitch = module_config["screw_pitch"]
        self.position = 0
        self.contents = ['empty', 0]
        self.contents_history = []
        super(SyringePump, self).__init__(module_info, cmd_mng, manager)
        self.steps_per_rev = self.steppers[0].steps_per_rev

    def change_contents(self, substance, vol):
        # Todo set up logger with tracking of volumes dispensed and timestamps
        self.contents = [substance, vol]
        self.contents_history.append((substance, vol))

    def move_syringe(self, parameters):
        """
        Determines the number of steps to send to the manager function for addressing stepper drivers
        :param : parameters{volume: int, flow_rate: int, withdraw: boolean, target: FBflask, wait: boolean}
        :return:
        """
        volume, flow_rate, withdraw = parameters['volume'], parameters['flow_rate'], parameters['withdraw']
        target = parameters['target']
        self.ready = False
        speed = (flow_rate * self.steps_per_rev * self.syr_length) / (self.screw_pitch * self.syr_vol * 60)
        # calculate number of steps to send to motor
        volume *= 1000
        steps = (volume * self.syr_length * self.steps_per_rev) / (self.syr_vol * self.screw_pitch)
        travel = (steps / self.steps_per_rev) * self.screw_pitch
        move_flag = True
        if withdraw:
            travel = -travel
            steps = -steps
            if self.position + travel < 0:
                move_flag = False
        else:
            if self.position + travel > self.syr_length:
                move_flag = False
        if move_flag:
            with self.lock:
                self.steppers[0].en_motor(True)
                self.steppers[0].set_running_speed(round(speed))
                prev_step_pos = self.steppers[0].get_current_position()
                prev_position = (prev_step_pos/self.steps_per_rev) * self.screw_pitch
                self.steppers[0].move_steps(steps)
                cur_step_pos = self.steppers[0].get_current_position()
                self.position = (cur_step_pos / self.steps_per_rev) * self.screw_pitch
                travel = abs(self.position - prev_position)
                if withdraw and target.contents != self.contents:
                    self.change_contents(target.contents, self.change_volume(travel, target))
                else:
                    self.contents[1] += self.change_volume(travel, target)
                if self.contents[1] == 0:
                    self.change_contents('empty', 0)
            self.ready = True
            return True
        self.ready = True
        return False

    def home(self):
        self.ready = False
        self.steppers[0].en_motor(True)
        self.steppers[0].home()
        self.position = 0.0
        self.ready = True

    def jog(self, steps, withdraw):
        self.ready = False
        if withdraw:
            steps = -steps
        with self.lock:
            self.steppers[0].en_motor(True)
            self.steppers[0].move_steps(steps)
        self.ready = True

    def change_volume(self, travel, target):
        vol_change = ((travel / self.syr_length) * self.syr_vol)
        target.change_volume(vol_change)
        return vol_change

    def set_pos(self, position):
        # todo add conversion to mm
        vol = float(position)*1000
        self.position = self.syr_length - (vol/self.syr_vol)*self.syr_length
