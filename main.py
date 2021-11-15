from UJ_FB.manager import Manager

manager = Manager(gui=True, simulation=False, web_enabled=True)
manager.gui_main.mainloop()
manager.gui_main.primary.destroy()