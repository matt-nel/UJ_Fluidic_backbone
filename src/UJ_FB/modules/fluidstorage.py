from UJ_FB.modules import modules
import logging
import datetime


class FluidStorage(modules.Module):
    """
    Fluid storage based on the Cronin group's clusterbot
    """
    def __init__(self, name, module_info, cmduino, manager):
        """Initialise the storage unit

        Args:
            name (str): name of the storage unit
            module_info (dict): configuration information
            cmduino (CommandManager): Commanduino CommandManager for controlling the Arduino
            manager (UJ_FB.Manager): Manager for this robot
        """
        super(FluidStorage, self).__init__(name, module_info, cmduino, manager)
        self.mod_type = "storage"
        module_config = module_info["mod_config"]
        self.max_samples = module_config["max_samples"]
        self.current_position = 1
        self.current_sample = 0
        self.contents = {}
        for i in range(1, self.max_samples + 1):
            self.contents[i] = {"sample_id": "", "volume": 0.0, "time_created": ""}
        # convert to uL
        self.max_volume = module_config["max_volume"] * 1000
        self.stepper = self.steppers[0]

    def turn_wheel(self, n_turns, direction):
        """Turns the wheel n times in the forward (CW) or reverse (CCW) direction

        Args:
            n_turns (int): the number of turns requried
            direction (str): "F" for CW, "R" for CCW. 
        """
        steps = 3200
        if direction.upper() == "R":
            steps *= -1
            self.current_position -= n_turns
        else:
            self.current_position += n_turns
        if self.current_position < 1:
            self.current_position += self.max_samples
        elif self.current_position > self.max_samples:
            self.current_position -= self.max_samples
        self.write_log(f"{self.name} moving to {self.current_position}")
        for i in range(n_turns):
            self.stepper.move_steps(steps)

    def move_to_position(self, position):
        """Moves the storage module to a specific position

        Args:
            position (int): the position number to move to
        """
        if position == self.current_position:
            return
        self.write_log(f"{self.name} moving to {position}")
        if position > self.current_position:
            diff_fwd = abs(position - self.current_position)
            diff_rev = abs(self.current_position - self.max_samples - position)
        else:
            diff_fwd = abs(self.current_position - self.max_samples - position)
            diff_rev = abs(position - self.current_position)
        if diff_rev > diff_fwd:
            direction = "F"
            diff = diff_fwd
        else:
            direction = "R"
            diff = diff_rev
        self.turn_wheel(diff, direction)

    def add_sample(self, id_override, volume):
        """Adds a sample to the storage, writing a record to the log and the running config.

        Args:
            id_override (str): if no information is given for the reaction, this string is used instead.
            volume (float): the volume to be added
        """
        pos = self.find_empty()
        if pos is not None:
            self.move_to_position(pos)
            if self.manager.reaction_id is None:
                sample_name = f"sample{self.current_sample} {id_override}"
            else:
                sample_name = f"Reaction id: {self.manager.reaction_id}"
            self.contents[self.current_position]["sample_id"] = sample_name
            self.contents[self.current_position]["volume"] += volume
            self.contents[self.current_position]["time_created"] = datetime.datetime.today().strftime("%Y-%m-%dT%H:%M")
            self.write_log(f"Stored {sample_name} in vessel {self.current_position}")

    def find_empty(self):
        found_empty = False
        i = None
        for i in range(self.current_position, self.max_samples + 1):
            if not self.contents[i]["sample_id"]:
                found_empty = True
                break
        if not found_empty:
            for i in range(1, self.current_position):
                if not self.contents[i]["sample_id"]:
                    found_empty = True
                    break
        if found_empty:
            return i
        else:
            return None

    def remove_sample(self):
        """Removes a sample from the storage record.
        """
        self.write_log(f"Removed {self.contents[self.current_position]}")
        self.contents[self.current_position]["sample_id"] = ""
        self.contents[self.current_position]["time_created"] = ""
        self.contents[self.current_position]["volume"] = 0.0

    def print_contents(self):
        self.write_log(f"Samples currently stored in {self.name}:")
        for item in self.contents.keys():
            if self.contents[item]["sample_id"]:
                self.write_log(f"{self.contents[item]['sample_id']} in vessel {item}")

    def change_volume(self, new_contents, vol):
        if vol < 0:
            pos = self.current_position
            if self.contents[pos]["volume"] <= 0:
                self.remove_sample()
            else:
                self.contents[pos]["volume"] += vol
        else:
            self.add_sample(new_contents, vol)

    def check_volume(self, vol):
        if vol < 0:
            pos = self.current_position
            if self.contents[pos]["volume"] + vol < 0:
                self.manager.write_log(f"Insufficient {self.contents[pos]['sample_id']} in {self.name}",
                                       level=logging.WARNING)
        else:
            pos = self.find_empty()
            if self.contents[pos]["volume"] + vol > self.max_volume:
                self.write_log(f"Max volume of vessel at position {pos} on {self.name} would be exceeded",
                               level=logging.WARNING)
                return False
        return True


class FluidStorageExt:
    """
    More complicated fluid storage implemented in external robot
    """
    pass
