from UJ_FB.modules import modules
import logging
import datetime


class FluidStorage(modules.Module):
    """
    Fluid storage based on the clusterbot
    """
    def __init__(self, name, module_info, cmduino, manager):
        super(FluidStorage, self).__init__(name, module_info, cmduino, manager)
        self.mod_type = "storage"
        module_config = module_info["mod_config"]
        self.max_samples = module_config["max_samples"]
        self.current_position = 1
        self.current_sample = 0
        self.contents = {}
        for i in range(1, self.max_samples + 1):
            self.contents[i] = {"sample_id": "", "time_created": ""}
        self.max_volume = module_config["max_volume"]
        self.stepper = self.steppers[0]

    def turn_wheel(self, n_turns, direction):
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

    def add_sample(self, id_override, task):
        found_empty = False
        pos = 0
        for i in range(self.current_position, self.max_samples + 1):
            if not self.contents[i]["sample_id"]:
                found_empty = True
        if not found_empty:
            for i in range(1, self.current_position):
                if not self.contents[i]["sample_id"]:
                    found_empty = True
        if found_empty:
            self.move_to_position(pos)
            if self.manager.reaction_id is None:
                sample_name = f"sample{self.current_sample} {id_override}"
            else:
                sample_name = f"Reaction id: {self.manager.reaction_id}"
            self.contents[self.current_position]["sample_id"] = sample_name
            self.contents[self.current_position]["time_created"] = datetime.datetime.today().strftime("%Y-%m-%dT%H:%M")
            self.write_log(f"Stored {sample_name} in vessel {self.current_position}")
        else:
            self.write_log(f"No more empty slots on {self.name}")
            task.error_flag = True

    def remove_sample(self):
        self.write_log(f"Removed {self.contents[self.current_position]}")
        self.contents[self.current_position]["sample_id"] = ""
        self.contents[self.current_position]["time_created"] = ""

    def print_contents(self):
        self.write_log(f"Samples currently stored in {self.name}:")
        for item in self.contents.keys():
            if self.contents[item]["sample_id"]:
                self.write_log(f"{self.contents[item]['sample_id']} in vessel {item}")


class FluidStorageExt:
    """
    More complicated fluid storage implemented in external robot
    """
    pass
