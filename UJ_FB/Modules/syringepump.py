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

    def move_syringe(self, target, volume, flow_rate, direction, task):
        """Moves the syringe to aspirate (take in) or dispense fluid. Updates the target volume (if target is not None)
        Args:
            target (Module Object): Object representing the target module. Can be a SyringePump, Flask, or Reactor
            volume (float): Volume in uL to be aspirated or dispensed
            flow_rate (float): Flow rate in uL/min for pump
            direction (str): 'A' - aspirate syringe, motor moves CCW. 'D' - dispense syringe, motor moves CW
            task (Task Object): Object used to track task completion
        """
        self.ready = False
        #speed in steps/sec
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
            volume = -volume
            if self.position + travel < -self.syringe_length:
                move_flag = False
        else:
            # Dispense: Turn CW, syringe emptying
            if self.position + travel > 2:
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
                if self.steppers[0].encoder_error:
                    self.write_log(f'{self.name}: Unable to move, check for obstructions', level=logging.ERROR)
                    task.error = True
                    # will have skipped steps, for at least two gap intervals. 
                    new_step_pos = self.steppers[0].get_current_position() - 400
                else:
                    new_step_pos = self.steppers[0].get_current_position()
                # if aspirating, step change is neg.
                step_change = new_step_pos - self.cur_step_pos
                actual_travel = (step_change / self.steps_per_rev) * self.screw_lead
                self.position += actual_travel
                vol_change = self.calc_volume(actual_travel)
                if direction == 'A':
                    vol_change = -vol_change
                self.current_vol += vol_change
                self.write_log(f'{self.name}: {direction_map[direction]} {int(abs(vol_change))}ul', level=logging.INFO)
                self.change_volume(vol_change, target)
            self.ready = True
            return
        self.ready = True
        task.error = True

    def home(self):
        """Moves the pump until the limit switch is triggered
        Args:
            task (Task): Task object that is associated with this function call
        """
        with self.lock:
            self.ready = False
            self.steppers[0].home()
            self.position = 0.0
            self.ready = True

    def jog(self, steps, direction, task):
        """Moves the pump manually 

        Args:
            steps (int): number of steps to move
            direction (string): 'A' - aspirate the syringe, 'D' - Dispense the syringe
            task (Task): Task object associated with this function call.
        """
        self.ready = False
        if direction == "A":
            steps = -steps
        with self.lock:
            self.steppers[0].move_steps(steps)
            if self.steppers[0].encoder_error:
                task.error = True
        self.ready = True

    def stop(self):
        """Stops the pump movement
        """
        with self.steppers[0].stop_lock:
            self.steppers[0].stop_cmd = True
        self.steppers[0].stop()

    def calc_volume(self, travel):
        """Calculates the volume change from the travel distance

        Args:
            travel ([float]): mm that the pump has moved

        Returns:
            [float ]: volume change for the syringe pump from this movement
        """
        vol_change = (travel / self.syringe_length) * self.max_volume
        return vol_change

    def check_volume(self, volume):
        """Checks whether the pump can aspirate/dispense the volume required

        Args:
            volume (float): Volume to be aspirated/dispensed

        Returns:
            bool: True if possible to aspirate/dispense. False otherwise
        """
        if volume > self.max_volume:
            return False
        return True

    def change_volume(self, volume_change, target):
        """Changes the volume of the syringe to reflect change from movement

        Args:
            volume_change (float): Volume that has been aspirated/dispensed
            target (Module object): The module that is receiving/supplying the fluid
        """
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
        """Sets the syringe pump position in mm

        Args:
            position (float): Position of the pump relative to the limit switch
        """
        vol = float(position)*1000
        self.contents[1] = vol
        self.position = self.syringe_length - ((self.max_volume - vol)/self.max_volume)*self.syringe_length
        self.steppers[0].set_current_position((self.position/8)*3200)

    def resume(self, command_dicts):
        """Resumes a paused move

        Args:
            command_dicts (dictionary): dictionary containing the command and parameters

        Returns:
            bool: True if resuming, False otherwise
        """
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
