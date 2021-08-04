import os

from dummy_manager import DummyManager
from commanduino import CommandManager
from threading import Lock
from Devices import stepperMotor
from Modules import syringePump
from Modules import modules
import time

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
            "Current volume": "80",
            "Maximum volume": "100"
        },
        "devices": {}},
    "Flask2": {
        "name": "Flask2",
        "mod_type": "flask",
        "class_type": "FBFlask",
        "mod_config": {
            "Contents": "water",
            "Current volume": "0",
            "Maximum volume": "100"
        },
        "devices": {}
    }
}


def disable_all_motors(cmduino):
    cmduino.ENX.high()
    cmduino.ENY.high()
    cmduino.ENZ.high()
    cmduino.ENE0.high()
    cmduino.ENE1.high()


stdout_mutex = Lock()
script_dir = os.path.dirname(__file__)
cm_config = os.path.join(script_dir, "cmd_config_simple_valve.json")
cmd_mng = CommandManager.from_configfile(cm_config, False)
# disable_all_motors(cmd_mng)
manager = DummyManager(stdout_mutex)
manager.start()
module_info = SYRINGE_DICT['syringe1']
pump = syringePump.SyringePump('syringe1', module_info, cmd_mng, manager)
pump.set_max_volume(10)
pump.change_contents("water", 1000)
pump.set_pos(1)
valve_step = getattr(cmd_mng, "stepperE1")
valve_en = getattr(cmd_mng, "ENE1")
valve = stepperMotor.StepperMotor(valve_step, valve_en, MOTOR_CONFIG["device_config"], manager.serial_lock)
flask1 = modules.FBFlask("Flask1", FLASK_CONFIG["Flask1"], cmd_mng, manager)
flask2 = modules.FBFlask("Flask2", FLASK_CONFIG["Flask2"], cmd_mng, manager)

while True:
    print("Press A to aspirate syringe", "Press D to dispense syringe", "Press V to move valve motor")
    response = input()
    response = response.capitalize()
    if response == "A":
        parameters = {}
        response = input("Current target?")
        if response == "Flask1":
            parameters["target"] = flask1
        elif response == "Flask2":
            parameters["target"] = flask2
        else:
            continue
        parameters["volume"] = 2000
        parameters["flow_rate"] = 5000
        parameters["direction"] = "A"
        pump.move_syringe(parameters)
    elif response == "D":
        parameters = {}
        response = input("Current target?")
        if response == "Flask1":
            parameters["target"] = flask1
        elif response == "Flask2":
            parameters["target"] = flask2
        else:
            continue
        parameters["volume"] = 2000
        parameters["flow_rate"] = 5000
        parameters["direction"] = "D"
        pump.move_syringe(parameters)
    elif response == "V":
        response2 = input("How many steps?")
        steps = int(response2)
        valve.move_steps(steps)
