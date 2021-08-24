import logging
from UJ_FB.Modules import modules

direction_map = {'A': "aspirate", "D": "dispense"}

class SyringePump(modules.Module):
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
        self.min_volume = 0.0
        self.syringe_length = 0.0
        self.screw_lead = module_config["screw_lead"]
        self.position = 0
        self.cur_step_pos = 0
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

    def move_syringe(self, target, volume, flow_rate, direction):
        """
        Determines the number of steps to send to the manager function for addressing stepper drivers
        :param : parameters{volume: int, flow_rate: int, direction: string "A" for aspirate, "D" for dispense
        target: FBflask, wait: boolean}
        :return:
        """
        self.ready = False
        speed = (flow_rate * self.steps_per_rev * self.syringe_length) / (self.screw_lead * self.max_volume * 60)
        # calculate number of steps to send to motor
        steps = (volume * self.syringe_length * self.steps_per_rev) / (self.max_volume * self.screw_lead)
        # calculate distance travelled after steps
        travel = (steps / self.steps_per_rev) * self.screw_lead
        move_flag = True
        if direction == "A":
            # Aspirate: Turn CCW, syringe filling
            steps = -steps
            travel = -travel
            if self.position + travel < -self.syringe_length:
                move_flag = False
        else:
            # Dispense: Turn CW, syringe emptying
            if self.position + travel > 0:
                move_flag = False
        # None target allows systems with simple routing to function.
        if target is not None:
            if not target.check_volume(volume):
                move_flag = False
        if move_flag:
            with self.lock:
                self.cur_step_pos = self.steppers[0].get_current_position()
                self.steppers[0].set_running_speed(round(speed))
                self.steppers[0].move_steps(steps)
                # Blocked until move complete or stop command received
                new_step_pos = self.steppers[0].get_current_position()
                # if aspirating, step change is neg.
                step_change = new_step_pos + self.cur_step_pos
                actual_travel = (step_change / self.steps_per_rev) * self.screw_lead
                self.position += actual_travel
                vol_change = self.calc_volume(actual_travel)
                if direction == 'A':
                    vol_change = -vol_change
                self.current_vol += vol_change
                self.write_log(f'{self.name}: {direction_map[direction]} {abs(vol_change)}')
                self.change_volume(vol_change, target)
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

    def calc_volume(self, travel):
        vol_change = (travel / self.syringe_length) * self.max_volume
        return vol_change

    def check_volume(self, volume):
        if volume > self.max_volume:
            return False
        return True

    def change_volume(self, volume_change, target):
        self.contents[1] += volume_change
        if target is not None:
            if target.type != "SP":
                # target is not a syringe pump
                if volume_change > 0 and target.contents != self.contents[0]:
                    self.change_contents(target.contents, self.contents[1])
                target.change_volume(volume_change)
            else:
                # target is a syringe pump
                if volume_change < 0:
                    # this pump is aspirating from another pump
                    self.change_contents(target.contents, volume_change)
        if self.contents[1] == 0:
            self.change_contents('empty', 0)

    def set_pos(self, position):
        vol = float(position)*1000
        self.contents[1] = vol
        self.position = self.syringe_length - ((self.max_volume - vol)/self.max_volume)*self.syringe_length
        self.steppers[0].set_current_position((self.position/8)*3200)

    def resume(self, command_dicts):
        params = command_dicts[0]['parameters']
        # if aspirating, and there is more liquid to take up
        if params['direction'] == 'A':
            if self.current_vol != params['volume']:
                command_dicts[0]['parameters']['volume'] = params['volume'] - self.current_vol
                return True
        elif self.current_vol > 0:
            params['volume'] = self.current_vol
            return True
        return False
