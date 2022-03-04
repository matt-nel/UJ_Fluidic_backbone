import datetime
import logging
from UJ_FB import Manager

logfile = 'UJ_FB/logs/log' + datetime.datetime.today().strftime('%Y%m%d')
logging.basicConfig(filename=logfile, level=logging.INFO)

robot = Manager(gui=True, simulation=False, web_enabled=True)
robot.gui_main.mainloop()
robot.gui_main.primary.destroy()
