import logging
import time
from UJ_FB.Modules import modules


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
        self.remaining_volume = 0.0
        self.error_count = 0
        self.last_dir = "D"
        self.backlash = module_config["backlash"]
        self.contents = (['air', 0.0], ['', 0.0])
        self.stepper = self.steppers[0]
        self.steps_per_rev = self.stepper.steps_per_rev
        self.valve = None

    def set_max_volume(self, volume):
        self.max_volume = float(volume) * 1000.0
        self.syringe_length = self.syringe_lengths[self.max_volume]

    def move_syringe(self, target, volume, flow_rate, direction, air, task=None):
        """Moves the syringe to aspirate (take in) or dispense fluid. Updates the target volume (if target is not None)
        Args:
            target (Module Object): Object representing the target module. Can be a SyringePump, Flask, or Reactor
            volume (float): Volume in uL to be aspirated or dispensed
            flow_rate (float): Flow rate in uL/min for pump
            direction (str): 'A' - aspirate syringe, motor moves CCW. 'D' - dispense syringe, motor moves CW
            air (bool): True if syringe is pumping air
            task (Task Object): Object used to track task completion
        """
        self.ready = False
        self.stepper.encoder_error = False
        # speed in steps/sec
        speed = (flow_rate * self.steps_per_rev * self.syringe_length) / (self.screw_lead * self.max_volume * 60)
        # calculate number of steps to send to motor
        steps = (volume * self.syringe_length * self.steps_per_rev) / (self.max_volume * self.screw_lead)
        adj_steps = False
        actual_steps = steps
        if direction != self.last_dir:
            adj_steps = True
            actual_steps += self.backlash
        # calculate distance travelled after steps
        travel = (steps / self.steps_per_rev) * self.screw_lead
        move_flag = True
        if direction == "A":
            # Aspirate: Turn CCW, syringe filling
            actual_steps = -actual_steps
            travel = -travel
            volume = -volume
            if self.position + travel < -self.syringe_length:
                self.write_log(f"The syringe cannot travel {travel} mm", level=logging.ERROR)
                move_flag = False
        else:
            # Dispense: Turn CW, syringe emptying
            if self.position + travel > 2:
                self.write_log(f"The syringe cannot travel {travel} mm", level=logging.ERROR)
                move_flag = False
        # None target allows systems with simple routing to function.
        if target is not None:
            if not target.check_volume(volume):
                move_flag = False
            elif direction == 'A':
                self.write_log(f'{self.name}: start aspirate {abs(round(volume,2))} ul from {target.name}')
            else:
                self.write_log(f'{self.name}: start dispense {abs(round(volume,2))} ul to {target.name}')
        elif air and direction == 'A':
            self.write_log(f'{self.name}: start aspirate {abs(round(volume,2))} air')
        if move_flag:
            with self.lock:
                self.cur_step_pos = self.stepper.get_current_position()
                self.stepper.set_running_speed(round(speed))
                self.stepper.move_steps(actual_steps)
                # Blocked until move complete or stop command received
                if self.stepper.encoder_error:
                    new_step_pos = self.correct_error(actual_steps)
                    if self.stepper.encoder_error:
                        if task is not None:
                            task.error = True
                        self.write_log(f'{self.name}: Unable to move, check for obstructions', level=logging.ERROR)
                else:
                    new_step_pos = self.stepper.get_current_position()
                # if aspirating, step change is neg.
                step_change = new_step_pos - self.cur_step_pos
                if adj_steps:
                    if direction == 'A':
                        step_change += self.backlash
                    else:
                        step_change -= self.backlash
                actual_travel = (step_change / self.steps_per_rev) * self.screw_lead
                self.position += actual_travel
                vol_change = self.calc_volume(actual_travel)
                self.remaining_volume = abs(abs(volume) - abs(vol_change))
                # syringe volume change is inverted relative to stepper direction - ie clockwise (+) when emptying (-)
                vol_change = -vol_change
                self.current_vol += vol_change
                self.change_volume(vol_change, target, air)
                self.last_dir = direction
            self.ready = True
            time.sleep(flow_rate/5000)
            self.error_count = 0
            return
        self.remaining_volume = abs(volume)
        self.ready = True
        if task is not None:
            task.error = True

    def home(self, task):
        """Moves the pump until the limit switch is triggered
        Args:
            task (Task): Task object that is associated with this function call
        """
        with self.lock:
            self.ready = False
            self.stepper.home()
            self.position = 0.0
            self.last_dir = 'D'
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
            self.stepper.move_steps(steps)
            if self.stepper.encoder_error and task is not None:
                task.error = True
        self.last_dir = direction
        self.ready = True

    def stop(self):
        """Stops the pump movement
        """
        with self.stepper.stop_lock:
            self.stepper.stop_cmd = True
        self.stepper.stop()

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

    def change_volume(self, volume_change, target, air):
        """Changes the volume of the syringe to reflect change from movement

        Args:
            volume_change (float): Volume that has been aspirated(+)/dispensed(-)
            target (Module object): The module that is receiving/supplying the fluid
            air (bool): whether the pump is moving air

        """
        # contents: (['air', air_volume], [other contents, other_contents_volume])
        volume_change = round(volume_change, 2)
        message = f'{self.name}: '
        if target is not None:
            # we are aspirating
            if volume_change > 0:
                message += f'aspirate {round(abs(volume_change),2)} ul of '
                if not air:
                    if target.type != "SP":
                        target.change_volume(self.contents[1][0], -volume_change)
                        message += f'{target.contents[0]} '
                        self.contents[1][0] = target.contents[0]
                    else:
                        message += f'{target.contents[0][0]}'
                        self.contents[1][0] = target.contents[1][0]
                    self.contents[1][1] += volume_change
                else:
                    message += 'air '
                    self.contents[0][1] += volume_change
                message += f'from {target.name}'
            # we are dispensing
            else:
                message += f'dispense {int(abs(volume_change))} ul of '
                if not air:
                    message += f'{self.contents[1][0]} '
                    self.contents[1][1] += volume_change
                    if target.type != "SP":
                        target.change_volume(self.contents[1][0], -volume_change)
                else:
                    message += 'air '
                    self.contents[0][1] += volume_change
                message += f'to {target.name}'
            self.write_log(message)
            self.contents[1][1] = max(self.contents[1][1], 0)
            self.contents[0][1] = max(self.contents[0][1], 0)
        elif air and volume_change < 0:
            message += f" aspirate {int(abs(volume_change))} ul of air"
            self.write_log(message)

    def set_pos(self, position):
        """Sets the syringe pump position in mm

        Args:
            position (float): Position of the pump relative to the limit switch
        """
        vol = float(position)*1000
        self.contents[1][1] = vol
        self.position = self.syringe_length - ((self.max_volume - vol)/self.max_volume)*self.syringe_length
        self.stepper.set_current_position((self.position/8)*3200)

    def correct_error(self, steps):
        self.write_log(f"{self.name} can't move. Moving back:")
        self.stepper.encoder_error = False
        self.stepper.move_to(self.cur_step_pos)
        self.manager.correct_position_error(self)
        self.stepper.move(steps)
        return self.stepper.get_current_position()

    def resume(self, command_dicts):
        """Resumes a paused move

        Args:
            command_dicts (dictionary): dictionary containing the command and parameters

        Returns:
            bool: True if resuming, False otherwise
        """
        params = command_dicts[0]['parameters']
        # if aspirating, and there is more liquid to take up
        if self.remaining_volume > 0:
            command_dicts[0]['parameters']['volume'] = self.remaining_volume
            return True
        return False
