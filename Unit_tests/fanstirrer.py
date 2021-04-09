import os
import time
from commanduino import CommandManager

script_dir = os.path.dirname(__file__)
cm_config = os.path.join(script_dir, "cmd_config.json")
cmd_mng = CommandManager.from_configfile(cm_config, False)

# for i in range(1):
#     print("Setting capsule to 2.3V")
#     cmd_mng.HCAP.set_pwm_value(200)
#     time.sleep(20)
#     print("Setting capsule to 9.1V")
#     cmd_mng.HCAP.set_pwm_value(800)
#     time.sleep(20)
#     print("Setting capsule to 12V")
#     cmd_mng.HCAP.set_pwm_value(1024)
#     time.sleep(20)
#     print("Setting to 0")
#     cmd_mng.HCAP.set_pwm_value(0)

# for i in range(2):
#     print("fan speed 20%")
#     cmd_mng.STIR.set_pwm_value(200)
#     time.sleep(5)
#     print("fan speed 80%")
#     cmd_mng.STIR.set_pwm_value(800)
#     time.sleep(5)
#     print("fan speed 100%")
#     cmd_mng.STIR.set_pwm_value(1024)
#     time.sleep(5)
#     print("fan speed o%")
#     cmd_mng.STIR.set_pwm_value(0)
#     time.sleep(5)

while True:
    pwm_val = int(input("What value should I set?"))
    cmd_mng.STIR.set_pwm_value(pwm_val)