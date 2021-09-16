import os
import sys

#file_path = os.path.abspath(os.path.dirname(__file__))
#sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from UJ_FB.manager import Manager

manager = Manager(gui=True, simulation=False, web_enabled=True)
manager.mainloop()