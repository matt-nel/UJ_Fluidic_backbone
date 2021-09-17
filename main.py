import os
import sys

from UJ_FB.manager import Manager

manager = Manager(gui=True, simulation=False, web_enabled=True)
manager.mainloop()