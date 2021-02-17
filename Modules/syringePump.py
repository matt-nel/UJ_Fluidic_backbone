from Modules.Module import Module
from threading import Thread
import time


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
        # initialises devices connected to module
        self.name = name
        module_config = module_info["mod_config"]
        # volume of syringe in ul
        self.syr_vol = module_config["volume"]
        self.syr_length = self.syr_lengths[self.syr_vol]
        self.screw_pitch = module_config["screw_pitch"]
        self.position = 0
        self.syr_contents = {}
        self.contents_list = []
        self.set_contents("Empty", 5000)
        self.withdraw = True
        super(SyringePump, self).__init__(module_info, cmd_mng, manager)
        self.steps_per_rev = self.steppers[0].steps_per_rev

    def set_contents(self, substance, volume):
        # Todo set up logger with tracking of volumes dispensed and timestamps
        self.syr_contents[substance] = volume
        self.contents_list.append(substance)

    def move_syringe(self, volume, flow_rate, withdraw):
        """
        Determines the number of steps to send to the manager function for addressing stepper drivers
        :param withdraw: False - aspirate syringe. True - withdraw syringe
        :param flow_rate: flow rate in uL/min
        :param volume: micro litres required to deliver
        :return:
        """
        self.withdraw = withdraw
        speed = (flow_rate * self.steps_per_rev * self.syr_length) / (self.screw_pitch * self.syr_vol * 60)
        # calculate number of steps to send to motor
        volume *= 1000
        steps = (volume * self.syr_length * self.steps_per_rev) / (self.syr_vol * self.screw_pitch)
        travel = (steps / self.steps_per_rev) * self.screw_pitch
        move_flag = True
        if withdraw:
            travel = -travel
            if self.position + travel < 0:
                move_flag = False
        else:
            if self.position + travel > self.syr_length:
                move_flag = False
        if move_flag:
            with self.lock:
                self.steppers[0].en_motor(True)
                self.steppers[0].set_running_speed(round(speed))
                self.steppers[0].revert_direction(withdraw)
                prev_step_pos = self.steppers[0].get_current_position()
                prev_position = (prev_step_pos/self.steps_per_rev) * self.screw_pitch
                self.steppers[0].move_steps(steps)
                self.watch_move(0)
                cur_step_pos = self.steppers[0].get_current_position()
                self.position = (cur_step_pos / self.steps_per_rev) * self.screw_pitch
                travel = abs(self.position - prev_position)
                self.syr_contents[self.contents_list[-1]] += self.change_volume(travel)
            return True
        else:
            return False

    def home(self):
        self.steppers[0].en_motor(True)
        self.steppers[0].home(True)
        self.position = 0.0

    def jog(self, steps, direction):
        with self.lock:
            self.steppers[0].en_motor(True)
            self.steppers[0].revert_direction(direction)
            self.steppers[0].move_steps(steps)

    def watch_move(self, stepper_num):
        """
        Watches steppers while they move. If endstop is hit will stop motor. Updates the position of the pump after
        move or once endstop hit. Once motor finished moving, toggles enable pin LOW.
        :param stepper_num: the number of the stepper in list steppers
        :return: None.
        """

        while self.steppers[stepper_num].is_moving:
            time.sleep(0.5)
        self.steppers[stepper_num].en_motor()

    def change_volume(self, travel):
        vol_change = ((travel / self.syr_length) * self.syr_vol)
        if self.withdraw:
            vol_change = -vol_change
        return vol_change
