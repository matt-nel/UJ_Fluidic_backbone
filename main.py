import datetime
import logging
import os
from UJ_FB import Manager


script_dir = os.path.dirname(__file__)
if not os.path.exists(os.path.join(script_dir, "logs")):
    os.chdir(script_dir)
    os.mkdir("logs")
logfile = 'logs/log' + datetime.datetime.today().strftime('%Y%m%d')
logfile = os.path.join(script_dir, logfile)
logging.basicConfig(filename=logfile, level=logging.INFO)

robot = Manager(gui=True, simulation=False, web_enabled=True)
robot.gui_main.mainloop()
