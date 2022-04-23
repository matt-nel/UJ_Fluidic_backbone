import os

from dummy_manager import DummyManager
from commanduino import CommandManager
from threading import Lock
import context
from UJ_FB.devices import devices, steppermotor
from UJ_FB.modules import modules, syringepump
import time

class Task:
    def __init__(self):
        self.error = None

SYRINGE_DICT = {"syringe1": {
    "name": "syringe1",
    "mod_type": "syringe",
    "class_type": "SyringePump",
    "mod_config": {
        "screw_lead": 8,
        "linear_stepper": True
    },
    "devices": {
        "stepper": {
            "name": "stepperX",
            "cmd_id": "STPX",
            "enable_pin": "ENX",
            "device_config": {
                "steps_per_rev": 3200,
                "enabled_acceleration": False,
                "speed": 1000,
                "max_speed": 10000,
                "acceleration": 1000
            }
        }
    }
}
}

MOTOR_CONFIG = {
    "name": "stepperE1",
    "cmd_id": "STPE1",
    "enable_pin": "ENE1",
    "device_config": {
        "steps_per_rev": 3200,
        "enabled_acceleration": False,
        "speed": 1000,
        "max_speed": 10000,
        "acceleration": 1000
    }
}

FLASK_CONFIG = {"Flask1": {
        "name": "Flask1",
        "mod_type": "flask",
        "class_type": "FBFlask",
        "mod_config": {
            "Contents": "water",
            "Current volume": "200",
            "Maximum volume": "400"
        },
        "devices": {}
        },
    "Flask2": {
        "name": "Flask2",
        "mod_type": "flask",
        "class_type": "FBFlask",
        "mod_config": {
            "Contents": "water",
            "Current volume": "200",
            "Maximum volume": "400"
        },
        "devices": {}
    }
}


stdout_mutex = Lock()
script_dir = os.path.dirname(__file__)
cm_config = os.path.join(script_dir, "cmd_config_simple_valve.json")
cmd_mng = CommandManager.from_configfile(cm_config, False)
# disable_all_motors(cmd_mng)
manager = DummyManager(stdout_mutex)
manager.start()
module_info = SYRINGE_DICT['syringe1']
pump = syringepump.SyringePump('syringe1', module_info, cmd_mng, manager)
pump.set_max_volume(10)
# pump.change_contents("water", 1000)
pump.set_pos(5)
valve_step = getattr(cmd_mng, "stepperE1")
valve = steppermotor.StepperMotor(valve_step, MOTOR_CONFIG["device_config"], manager.serial_lock)
flask1 = modules.FBFlask("Flask1", FLASK_CONFIG["Flask1"], cmd_mng, manager)
flask2 = modules.FBFlask("Flask2", FLASK_CONFIG["Flask2"], cmd_mng, manager)

while True:
    print("Press A to aspirate syringe", "Press D to dispense syringe", "Press V to move valve motor")
    response = input()
    response = response.capitalize()
    task = Task()
    if response == "A":
        parameters = {}
        response = input("Current target?")
        if response == "Flask1":
            target = flask1
        elif response == "Flask2":
            target = flask2
        else:
            continue
        volume = 2000
        flow_rate = 5000
        direction = "A"
        pump.move_syringe(target, volume, flow_rate, direction, task)
    elif response == "D":
        parameters = {}
        response = input("Current target?")
        if response == "Flask1":
            target = flask1
        elif response == "Flask2":
            target = flask2
        else:
            continue
        volume = 2000
        flow_rate = 5000
        direction = "D"
        pump.move_syringe(target, volume, flow_rate, direction, task)
    elif response == "V":
        response2 = input("How many steps?")
        steps = int(response2)
        valve.move_steps(steps)
    elif response == "X":
        response2 = float(input("how many ul?"))
        pump.move_syringe(None, response2, 5000, "A", task)
    elif response == "C":
        response2 = float(input("how many ul?"))
        pump.move_syringe(None, response2, 5000, "D", task)
    elif response == "H":
        pump.home()

