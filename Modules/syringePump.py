from Modules.Module import Module
from threading import Thread
import time


class SyringePump(Module):
    """
    Syringe pump module class for managing all equipment required for a syringe pump. 0 position corresponds to syringe
    """
    # TODO tracking of whether syringe currently contains reagents
    cor_fact = 0.993  # correction factor for dispensed volume
    # {volume: length in mm}
    syr_lengths = {58: 1000, 2000: 2, 4000: 42, 5000: 5, 10000: 58, 20000: 20, 60000: 90}

    def __init__(self, name, module_info, manager_obj):
        """
        :param name: syringe pump name
        :param module_info: Dictionary containing IDs of attached devices and their configuration information
        :param manager_obj: commanduino command manager object
        """
        # initialises devices connected to module
        self.name = name
        super(SyringePump, self).__init__(module_info, manager_obj)
        module_config = module_info["mod_config"]
        # volume of syringe in ul
        self.syr_vol = module_config["volume"] * 1000
        self.syr_length = self.syr_lengths[self.syr_vol]
        # TODO list of syringe lengths given volume? - find standard syringe sizes
        self.steps_per_rev = self.steppers[0].steps_per_rev
        self.screw_pitch = module_config["screw_pitch"]
        self.syr_contents = {}
        self.contents_list = []
        self.set_contents("Empty", 0.0)
        self.position = 0.0
        self.aspirate = True

    def set_contents(self, substance, volume):
        # Todo set up logger with tracking of volumes dispensed and timestamps
        self.syr_contents[substance] = volume
        self.contents_list.append(substance)

    def move_syringe(self, volume, flow_rate, aspirate):
        """
        Determines the number of steps to send to the manager function for addressing stepper drivers
        :param aspirate: True - aspirate syringe. False - withdraw syringe
        :param flow_rate: flow rate in uL/min
        :param volume: micro litres required to deliver
        :return:
        """
        self.aspirate = aspirate
        speed = (flow_rate * self.steps_per_rev * self.syr_length) / (self.screw_pitch * self.syr_vol)
        self.steppers[0].set_running_speed(speed)
        self.steppers[0].revert_direction(aspirate)
        # calculate number of steps to send to motor
        steps = (volume * self.syr_length * self.steps_per_rev) / (self.syr_vol * self.screw_pitch)
        travel = (steps / self.steps_per_rev) * self.screw_pitch
        current_vol = self.syr_contents[self.contents_list[-1]]
        new_vol = self.change_volume(travel)
        if 0.0 < current_vol - new_vol < self.syr_vol:
            self.steppers[0].move_steps(steps)
            Thread(target=self.watch_move, args=(0, 0)).start()
            return True
        else:
            return False

    def home(self):
        # move until endstop hit
        self.steppers[0].move_steps(64000)
        Thread(target=self.watch_move, args=(0, 0)).start()
        while not self.steppers[0].stopped:
            time.sleep(0.1)
        self.position = 0.0

    def watch_move(self, stepper_num, endstop_num=None):
        """
        Watches steppers while they move. If endstop is hit will stop motor. Updates the position of the pump after
        move or once endstop hit. Once motor finished moving, toggles enable pin LOW.
        :param stepper_num: the number of the stepper in list steppers
        :param endstop_num: Optional. The number of the endstop in list endstops
        :return: None.
        """
        prev_position = (self.steppers[stepper_num].get_current_pos()/self.steps_per_rev) * self.screw_pitch
        if self.aspirate:
            while self.steppers[stepper_num].is_moving:
                if self.endstops[endstop_num].digital_read() != 1:
                    self.steppers[stepper_num].stop()
        else:
            while self.steppers[stepper_num].is_moving:
                time.sleep(0.1)
        self.steppers[stepper_num].en_motor()
        self.position = (self.steppers[stepper_num].get_current_pos()/self.steps_per_rev)*self.screw_pitch
        travel = abs(self.position - prev_position)
        self.syr_contents[self.contents_list[-1]] += self.change_volume(travel)

    def change_volume(self, travel):
        vol_change = ((travel / self.syr_length) * self.syr_vol)
        if self.aspirate:
            vol_change = -vol_change
        return vol_change
