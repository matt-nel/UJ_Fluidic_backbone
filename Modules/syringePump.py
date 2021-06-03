from Modules.modules import Module


class SyringePump(Module):
    """
    Syringe pump module class for managing all equipment required for a syringe pump. 0 position corresponds to syringe
    max length
    """
    def __init__(self, name, module_info, cmduino, manager):
        """
        :param name: syringe pump name
        :param module_info: Dictionary containing IDs of attached devices and their configuration information
        :param cmduino: commanduino command manager object
        """
        super(SyringePump, self).__init__(name, module_info, cmduino, manager)
        self.type = "SP"
        module_config = module_info["mod_config"]
        # todo update this in Manager.check_connections
        self.cor_fact = 0.993  # correction factor for dispensed volume
        # {volume: length in mm}
        self.syringe_lengths = {1000.0: 58, 2000.0: 2, 4000.0: 42, 5000.0: 58, 10000.0: 58, 20000.0: 20, 60000.0: 90}
        self.max_volume = 0.0
        self.min_volume = 1.0
        self.syringe_length = 0.0
        self.screw_lead = module_config["screw_lead"]
        self.position = 0
        self.current_vol = 0.0
        self.contents = ['empty', 0.0]
        self.contents_history = []
        self.steps_per_rev = self.steppers[0].steps_per_rev

    def init_syringe(self):
        if not self.steppers[0].check_endstop():
            self.home()

    def set_max_volume(self, volume):
        self.max_volume = float(volume) * 1000.0
        self.syringe_length = self.syringe_lengths[self.max_volume]

    def change_contents(self, substance, vol):
        # Todo set up logger with tracking of volumes dispensed and timestamps
        self.contents = [substance, float(vol)]
        self.contents_history.append((substance, vol))

    def move_syringe(self, parameters):
        """
        Determines the number of steps to send to the manager function for addressing stepper drivers
        :param : parameters{volume: int, flow_rate: int, direction: string "A" for aspirate, "D" for dispense
        target: FBflask, wait: boolean}
        :return:
        """
        self.ready = False
        volume, flow_rate, direction = parameters['volume'], parameters['flow_rate'], parameters['direction']
        target = parameters['target']
        speed = (flow_rate * self.steps_per_rev * self.syringe_length) / (self.screw_lead * self.max_volume * 60)
        # calculate number of steps to send to motor
        steps = (volume * self.syringe_length * self.steps_per_rev) / (self.max_volume * self.screw_lead)
        travel = (steps / self.steps_per_rev) * self.screw_lead
        move_flag = True
        if direction == "A":
            # Turn CCW
            steps = -steps
            if self.position + travel > self.syringe_length:
                move_flag = False
        else:
            # Volume within syringe reducing
            travel = -travel
            if self.position + travel < 0:
                move_flag = False
        vol_to_move = self.check_volume(travel)
        if not target.check_volume(vol_to_move):
            move_flag = False
        if move_flag:
            with self.lock:
                cur_step_pos = self.steppers[0].get_current_position()
                self.steppers[0].set_running_speed(round(speed))
                self.steppers[0].move_steps(steps)
                new_step_pos = self.steppers[0].get_current_position()
                self.position += ((cur_step_pos - new_step_pos) / self.steps_per_rev) * self.screw_lead
                step_change = new_step_pos - cur_step_pos
                if step_change != steps:
                    actual_travel = (step_change / self.steps_per_rev) * self.screw_lead
                    if direction == "D":
                        actual_travel = -actual_travel
                    self.current_vol = ((travel - actual_travel) / self.syringe_length) * self.max_volume
                    travel = (step_change / self.steps_per_rev) * self.screw_lead
                else:
                    self.current_vol += vol_to_move
                self.change_volume(travel, target)
            self.ready = True
            return True
        self.ready = True
        return False

    def home(self):
        with self.lock:
            self.ready = False
            self.steppers[0].home()
            self.position = 0.0
            self.ready = True

    def jog(self, steps, direction):
        self.ready = False
        if direction == "A":
            steps = -steps
        with self.lock:
            self.steppers[0].move_steps(steps)
        self.ready = True

    def stop(self):
        with self.steppers[0].stop_lock:
            self.steppers[0].stop_cmd = True
        self.steppers[0].stop()

    def check_volume(self, travel):
        vol_change = (travel / self.syringe_length) * self.max_volume
        return vol_change

    def change_volume(self, travel, target):
        vol_change = self.check_volume(travel)
        if target.type != "SP":
            if travel < 0 and target.contents != self.contents[0]:
                self.contents[1] += vol_change
                self.change_contents(target.contents, self.contents[1])
            else:
                self.contents[1] += vol_change
            if self.contents[1] == 0:
                self.change_contents('empty', 0)
            target.change_volume(vol_change)
        else:
            if travel < 0:
                self.change_contents(target.contents, vol_change)
            else:
                self.change_contents('empty', 0)

    def set_pos(self, position):
        vol = float(position)*1000
        self.contents[1] = vol
        self.position = self.syringe_length - ((self.max_volume - vol)/self.max_volume)*self.syringe_length
        self.steppers[0].set_current_position((self.position/8)*3200)

    def resume(self, command_dicts):
        if self.current_vol > 0:
            return False
        else:
            command_dicts[0]['volume'] = self.current_vol
        return True
