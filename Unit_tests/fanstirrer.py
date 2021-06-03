import os
from dummy_manager import DummyManager
from commanduino import CommandManager
from threading import Lock
from Modules import reactor
import time


def disable_all_motors(cmduino):
    cmduino.ENY.high()
    cmduino.ENX.high()


stdout_mutex = Lock()
Reactor = reactor.Reactor
script_dir = os.path.dirname(__file__)
cm_config = os.path.join(script_dir, "cmd_config.json")
cmd_mng = CommandManager.from_configfile(cm_config, False)
disable_all_motors(cmd_mng)
manager = DummyManager(stdout_mutex)
manager.start()
module_dict = {"reactor1": {"name": "reactor1", "mod_type": "reactor", "class_type": "Reactor",
                            "mod_config": {"num_heaters": 1, "Contents": "empty", "Current volume": "0",
                                           "Maximum volume": "100"},
                            "devices": {'heater': {"name": "heater1", "cmd_id": "AW1", "device_config": {}},
                                        "mag_stirrer": {"name": "stirrer1", "cmd_id": "AW2",
                                                        "device_config": {"fan_speed": 7200}},
                                        "temp_sensor": {"name": "temp_sensor1", "cmd_id": "T1", "device_config":
                                            {"SH_C": [0.0008271125019925238, 0.0002088017729221142,
                                                      8.059262669466295e-08]}}}}}
module_info = module_dict["reactor1"]
my_reactor = Reactor("test_reactor", module_info, cmd_mng, manager)

while True:
    response = input("Write or read?")
    if response == 'w':
        temp_val = float(input("What temp value (°C) should I set?"))
        temp_secs = float(input("How long should the reactor heat for?"))
        stir_speed = int(input("What speed should the reactor stir?"))
        stir_secs = float(input("How long should the reactor stir for?"))
        my_reactor.start_reactor(False, temp_val, temp_secs, stir_speed, stir_secs)
    elif response == 'r':
        my_reactor.read_temp()
        time.sleep(0.5)
