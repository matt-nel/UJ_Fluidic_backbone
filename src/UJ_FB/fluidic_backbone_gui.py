"""
This class is used to set up a GUI for the fluidic backbone robot. Using the GUI,
users can control the syringe pumps, valves, and reactors (stirrer hotplates). 
The GUI can also start and stop the robots, and load reactions in the form of XDL documents.  
"""


import os
import queue
import time
import tkinter as tk
import tkinter.filedialog as fd


class FluidicBackboneUI:
    """
    Class used to control the GUI. The GUI communicates with the Manager via a Queue. The manager
    places messages, control signals, and other information into the queue, which the GUI will 
    retrieve every 0.3 s. Tkinter is not thread safe, so any information has to be passed to
    the GUI via this queue.     
    """
    def __init__(self, manager):
        """Initialise the GUI

        Args:
            manager (UJ_FB.Manager): the Manager object for this robot
        """
        self.primary = tk.Tk()
        self.queue = queue.Queue()
        self.quit_flag = False
        self.safe_quit_flag = False
        self.primary.protocol("WM_DELETE_WINDOW", self.end_program)
        self.manager = manager
        self.fonts = {"buttons": ("Calibri", 12), "labels": ("Calibri", 14), "default": ("Calibri", 16),
                      "heading": ("Calibri", 16), "text": ("Calibri", 10)}
        self.colours = {"form-background": "#9ab5d9", "accept-button": "#4de60b", "cancel-button": "#e6250b",
                        "heading": "#e65525",  "other-button": "#45296e", "other-button-text": "#FFFFFF",
                        "form-bg": "#b5d5ff"}
        self.primary.title("Fluidic Backbone Prototype")
        self.primary.configure(background=self.colours["form-background"])
        self.volume_tmp, self.flow_rate_tmp = 0.0, 0.0

        icon = tk.PhotoImage(file=os.path.join(os.path.dirname(__file__), "Syringe.png"))
        self.primary.iconphoto(True, icon)

        self.valve_pump_frame = tk.Frame(self.primary, borderwidth=5)

        self.syringe_labels = []
        self.syringe_buttons = []
        # list of syringe buttons, eg: syringe_buttons[0][0] is aspirate button for syringe 1
        # syringe_buttons[0][1] is aspirate button for syringe 1
        for syringe in self.manager.syringes.keys():
            self.populate_syringes(syringe)

        self.invert_valve = False
        self.valves_labels = []
        self.valves_buttons = {}
        # valves_buttons[valve_no][port_no]
        # list valves_buttons contains buttons corresponding to each valve port starting from 1, with zero corresponding
        # to homing button. valves_buttons[0][0] is home button of valve 1, valves_buttons[3][2] is port 2 of valve 4
        for valve in self.manager.valves.keys():
            self.populate_valves(valve)

        self.log_frame = tk.Frame(self.primary)
        self.log = tk.Text(self.log_frame, state="disabled", width=60, height=24, wrap="word", borderwidth=5)

        self.override_frame = tk.Frame(self.primary, bg=self.colours["form-background"])
        self.pause_butt = tk.Button(self.override_frame, text="Pause", font=self.fonts["buttons"],
                                    bg=self.colours["other-button"], fg="white", command=self.pause)
        self.stop_butt = tk.Button(self.override_frame, text="Stop", font=self.fonts["buttons"],
                                   bg=self.colours["cancel-button"], fg="white", command=self.stop)
        self.load_xdl_butt = tk.Button(self.override_frame, text="Load XDL", font=self.fonts["buttons"],
                                       bg=self.colours["other-button"], fg="white", command=self.load_xdl)
        self.execute_butt = tk.Button(self.override_frame, text="Start auto execution", font=self.fonts["buttons"],
                                      bg=self.colours["other-button"], fg="white",
                                      command=lambda: self.send_interrupt({"pause": False, "stop": False,
                                                                           "resume": False, "exit": False,
                                                                           "execute": True}))
        
        self.web_frame = tk.Frame(self.primary, bg=self.colours["form-background"])
        self.url_label = tk.Label(self.web_frame, text="Current server URL: " + self.manager.listener.url,
                                  font=self.fonts["labels"], background=self.colours["form-background"])
        self.url_butt = tk.Button(self.web_frame, text="Update URL", font=self.fonts["buttons"],
                                  fg="white", bg=self.colours["other-button"], command=self.update_url)

        self.reactor_labels = {}
        self.reactor_frame = tk.Frame(self.primary, bg=self.colours["form-background"])
        num_reactors = 0
        for reactor in self.manager.reactors.keys():
            self.populate_reactors(reactor, num_reactors)

        self.valve_pump_frame.grid(row=0, column=0, padx=5, pady=10)
        self.reactor_frame.grid(row=1, column=0, padx=5, pady=5)
        self.log_frame.grid(row=0, column=1, padx=5, pady=5)
        self.override_frame.grid(row=1, column=1, padx=5, pady=5)
        self.web_frame.grid(row=3, column=1, padx=5, pady=5)
        self.url_label.grid(row=0, column=1)
        self.url_butt.grid(row=0, column=2)
        self.pause_butt.grid(row=0, column=2, sticky="W")
        self.stop_butt.grid(row=0, column=3, sticky="W")
        self.execute_butt.grid(row=0, column=5, sticky="E")
        self.load_xdl_butt.grid(row=0, column=6, sticky="E")
        self.log.grid(row=14, column=0)
        self.primary.after(0, self.read_queue)

    def read_queue(self):
        """
        Reads the queue and sets up another event to read the queue again in 0.3 s, unless the user has exited the 
        program. 
        """
        try:
            item = self.queue.get_nowait()
            if item[0] == "log":
                self.write_message(item[1])
            elif item[0] == "logclear":
                self.clear_messages()
            elif item[0] == "temp":
                self.update_temps(item[1][0], item[1][1])
            elif item[0] == "execution":
                self.update_execution(item[1])
        except queue.Empty:
            pass
        finally:
            if not self.quit_flag:
                self.primary.after(300, self.read_queue)
            else:
                self.safe_quit_flag = True

    def populate_syringes(self, syringe_name):
        """
        Populates the buttons for syringes
        :param syringe_name: name of syringe from config file
        :return:
        """
        syringe_no = int(syringe_name[-1]) - 1
        col = syringe_no * 2
        syringe_print_name = "Syringe " + str(syringe_no + 1)
        self.syringe_labels.append(tk.Label(self.valve_pump_frame, text=syringe_print_name, font=self.fonts["labels"],
                                            bg="white"))
        self.syringe_labels[syringe_no].grid(row=0, column=col, columnspan=2)

        home_button = tk.Button(self.valve_pump_frame, text="Home", font=self.fonts["buttons"], width=5, padx=5,
                                bg=self.colours["other-button"],
                                fg="white", command=lambda: self.home_syringe(syringe_name, syringe_print_name))
        jog_button = tk.Button(self.valve_pump_frame, text="Jog", font=self.fonts["buttons"], padx=5,
                               bg=self.colours["other-button"], fg="white",
                               command=lambda: self.jog_syringe(syringe_name, syringe_print_name))

        home_button.grid(row=1, column=col)
        jog_button.grid(row=2, column=col)

        dispense_button = tk.Button(self.valve_pump_frame, text="Dispense", font=self.fonts["buttons"],
                                    padx=5, bg=self.colours["other-button"], fg="white",
                                    command=lambda: self.move_syringe(syringe_name, syringe_print_name, "D"))
        dispense_button.grid(row=1, column=col + 1, columnspan=1)

        aspirate_button = tk.Button(self.valve_pump_frame, text="Aspirate", font=self.fonts["buttons"], padx=5,
                                    bg=self.colours["other-button"], fg="white",
                                    command=lambda: self.move_syringe(syringe_name, syringe_print_name, "A"))
        aspirate_button.grid(row=2, column=col + 1)

    def populate_valves(self, valve_name):
        """
        Populates the buttons for valve
        :param valve_name: number of valve
        :return:
        """
        ports = []
        valve_no = int(valve_name[-1])
        col = (valve_no - 1)*2
        valve_print_name = "Valve " + str(valve_no)
        valve_label = tk.Label(self.valve_pump_frame, text=valve_print_name, font=self.fonts["labels"],
                               bg="white")
        valve_label.grid(row=4, column=col, columnspan=2)

        home_button = tk.Button(self.valve_pump_frame, text="Home", font=self.fonts["buttons"], padx=5,
                                bg=self.colours["accept-button"], fg="white",
                                command=lambda: self.move_valve(valve_name, "home"))
        home_button.grid(row=5, column=col)
        jog_button = tk.Button(self.valve_pump_frame, text="Jog", font=self.fonts["buttons"], padx=5,
                               bg=self.colours["accept-button"], fg="white",
                               command=lambda: self.jog_valve(valve_name, valve_print_name))
        jog_button.grid(row=5, column=col + 1)

        for port_no in range(0, 5):
            ports.append(tk.Button(self.valve_pump_frame, text=str(port_no + 1), font=self.fonts["buttons"], width=5,
                                   padx=5, bg=self.colours["other-button"], fg="white",
                                   command=lambda i=port_no + 1: self.move_valve(valve_name, i)))
            ports[port_no].grid(row=6 + port_no, column=col)

        for port_no in range(5, 10):
            ports.append(tk.Button(self.valve_pump_frame, text=str(port_no + 1), font=self.fonts["buttons"], width=5,
                                   padx=5, bg=self.colours["other-button"], fg="white",
                                   command=lambda i=port_no + 1: self.move_valve(valve_name, i)))
            ports[port_no].grid(row=1 + port_no, column=col + 1)

        # Append list of ports corresponding to valve_no to valves_buttons
        self.valves_buttons[valve_name] = ports

    def populate_reactors(self, reactor_name, reactor_num):
        """ Populates the buttons for the reactors.

        Args:
            reactor_name (str): The name of the reactor 
        """
        reactor_no = reactor_num
        reactor_print_name = "Reactor " + str(reactor_no)
        row = reactor_no
        reactor_label = tk.Label(self.reactor_frame, text=reactor_print_name, font=self.fonts["labels"],
                                 bg=self.colours["form-background"])
        reactor_label.grid(row=row, column=0)

        heat_button = tk.Button(self.reactor_frame, text="Heating", font=self.fonts["buttons"], padx=5,
                                bg=self.colours["other-button"], fg="white",
                                command=lambda: self.heat_reactor(reactor_name, reactor_print_name))
        stir_button = tk.Button(self.reactor_frame, text="Stirring", font=self.fonts["buttons"], padx=5,
                                bg=self.colours["other-button"], fg="white",
                                command=lambda: self.stir_reactor(reactor_name, reactor_print_name))

        self.reactor_labels[reactor_name] = tk.Label(self.reactor_frame, text="- °C", font=self.fonts["labels"],
                                                     padx=5, width=4, bg=self.colours["form-background"])
        self.reactor_labels[reactor_name].grid(row=row, column=3)

        heat_button.grid(row=row, column=1)
        stir_button.grid(row=row, column=2)

    def v_button_colour(self, command_dict):
        """Changes the colour of valve position buttons on the UI to indicate which port 
        is currently being used

        Args:
            command_dict (dict): The dictionary containing the command parameters
        """
        command = command_dict["command"]
        if command == "home":
            port_no = 0
        else:
            port_no = command_dict["command"] - 1
        valve = command_dict["module_name"]
        for item in self.valves_buttons[valve]:
            item.configure(bg=self.colours["other-button"])
        self.valves_buttons[valve][port_no].configure(bg=self.colours["heading"])
    
    def update_url(self):
        """Updates the server URL for the robot to connect to.
        """
        def accept_url():
            new_url = url_entry.get()
            self.manager.update_url(new_url)
            cur_url = self.manager.listener.url
            self.url_label.configure(text="Current server URL: " + cur_url, font=self.fonts["labels"])
            url_window.destroy()

        url_window = tk.Toplevel(self.primary)
        url_window.title = "Configure server URL"
        url_label = tk.Label(url_window, text="Please enter the new IP address for the server: ",
                             font=self.fonts["labels"])
        url_entry = tk.Entry(url_window, width=30)
        url_button_a = tk.Button(url_window, text="Accept", font=self.fonts["buttons"],
                                 bg=self.colours["accept-button"], command=accept_url)
        url_button_c = tk.Button(url_window, text="Cancel", font=self.fonts["buttons"],
                                 bg=self.colours["cancel-button"], command=url_window.destroy)

        url_label.grid(row=0, column=0)
        url_entry.grid(row=0, column=1)
        url_button_a.grid(row=1, column=0)
        url_button_c.grid(row=1, column=1)

    def move_syringe(self, syringe_name, syringe_print_name, direction):
        """Allows the user to move the syringe to aspirate (take up) or dispense fluid.

        Args:
            syringe_name (str): The name of the syringe to be moved.
            syringe_print_name (str): The name of the syringe, formatted for display
            direction (str): "A" for aspirate, "D" for dispense.
        """

        def dispense(syr_name):
            command_dict = {"mod_type": "syringe_pump", "module_name": syr_name, "command": "move",
                            "parameters": {"volume": self.volume_tmp * 1000, "flow_rate": self.flow_rate_tmp,
                                           "direction": direction, "wait": False, "target": None,
                                           "track_volume": False}}
            sp_move_menu.destroy()
            self.send_command(command_dict)

        if direction == "A":
            button_text = menu_title = "Aspirate"
        else:
            button_text = menu_title = "Dispense"

        sp_move_menu = tk.Toplevel(self.primary)
        sp_move_menu.title(menu_title + " " + syringe_print_name)
        sp_move_menu.configure(bg=self.colours["form-background"])
        val_vol = self.primary.register(self.validate_vol)
        val_flow = self.primary.register(self.validate_flow)

        vol_label = tk.Label(sp_move_menu, text="Volume to " + button_text.lower() + "in ml:")
        vol_entry = tk.Entry(sp_move_menu, validate="key", validatecommand=(val_vol, "%P"), fg="black", bg="white",
                             width=50)

        flow_label = tk.Label(sp_move_menu, text="Flow rate in \u03BCL/min:")
        flow_entry = tk.Entry(sp_move_menu, validate="key", validatecommand=(val_flow, "%P"), fg="black", bg="white",
                              width=50)

        go_button = tk.Button(sp_move_menu, text=button_text, font=self.fonts["buttons"],
                              bg=self.colours["accept-button"], fg="white", command=lambda: dispense(syringe_name))
        cancel_button = tk.Button(sp_move_menu, text="Cancel", font=self.fonts["buttons"],
                                  bg=self.colours["cancel-button"], fg="white", command=sp_move_menu.destroy)

        vol_label.grid(row=0, column=1)
        vol_entry.grid(row=0, column=5)
        flow_label.grid(row=2, column=1)
        flow_entry.grid(row=2, column=5)
        go_button.grid(row=5, column=5)
        cancel_button.grid(row=5, column=6)

    def home_syringe(self, syringe_name, syringe_print_name):
        """Commands the robot to home the syringe; moving it until the limit switch is triggered. 

        Args:
            syringe_name (str): The name of the syringe to be homed
            syringe_print_name (str): the name of the syringe, formatted for display
        """
        command_dict = {"mod_type": "syringe_pump", "module_name": syringe_name, "command": "home",
                        "parameters": {"volume": 0.0, "flow_rate": 9999, "wait": False}}

        def home_command():
            home_popup.destroy()
            self.send_command(command_dict)

        home_popup = tk.Toplevel(self.primary)
        home_popup.title("Home " + syringe_print_name)
        warning_label = tk.Label(home_popup, text="Homing the syringe will empty its contents, are you sure?")
        yes_button = tk.Button(home_popup, text="Home", font=self.fonts["buttons"], bg=self.colours["other-button"],
                               fg="white", command=home_command)
        no_button = tk.Button(home_popup, text="Cancel", font=self.fonts["buttons"], bg=self.colours["other-button"],
                              fg="white", command=home_popup.destroy)
        warning_label.grid(row=0, column=1, columnspan=5)
        yes_button.grid(row=2, column=1)
        no_button.grid(row=2, column=5)

    def jog_syringe(self, syringe_name, syringe_print_name):
        """This window allows the user to jog the syringe in either direction. 

        Args:
            syringe_name (str): the name of the syringe
            syringe_print_name (str): the name of the syringe, formatted for display.
        """
        command_dict = {"mod_type": "syringe_pump", "module_name": syringe_name, "command": "jog",
                        "parameters": {"volume": 0.0, "flow_rate": 9999, "steps": 0, "direction": "D", "wait": False}}

        # todo: add jog speed setting

        def change_steps(steps):
            command_dict["parameters"]["steps"] = steps

        def setpos():
            new_pos = set_pos.get()
            zero_dict = {"mod_type": "syringe_pump", "module_name": syringe_name, "command": "setpos",
                         "parameters": {"volume": 0.0, "flow_rate": 9999, "pos": new_pos, "wait": False}}
            self.send_command(zero_dict)

        def change_direction(direction):
            if direction == "A":
                command_dict["parameters"]["direction"] = "A"
            else:
                command_dict["parameters"]["direction"] = "D"

        jog_popup = tk.Toplevel(self.primary)
        jog_popup.title("Jog" + syringe_print_name)
        fh_button = tk.Button(jog_popup, text="500 Steps", font=self.fonts["buttons"], bg=self.colours["other-button"],
                              fg="white", command=lambda: change_steps(500))
        single_rev_button = tk.Button(jog_popup, text="3200 Steps", font=self.fonts["buttons"],
                                      bg=self.colours["other-button"], fg="white", command=lambda: change_steps(3200))
        db_rev_button = tk.Button(jog_popup, text="6400 Steps", font=self.fonts["buttons"],
                                  bg=self.colours["other-button"], fg="white", command=lambda: change_steps(6400))
        set_pos_label = tk.Label(jog_popup, text="Set syringe position in ml")
        set_pos = tk.Entry(jog_popup)
        set_pos_butt = tk.Button(jog_popup, text="set current position", command=setpos)
        fwd_button = tk.Button(jog_popup, text="Direction: Dispense", font=self.fonts["buttons"],
                               bg=self.colours["other-button"], fg="white", command=lambda: change_direction("D"))
        rev_button = tk.Button(jog_popup, text="Direction: Aspirate", font=self.fonts["buttons"],
                               bg=self.colours["other-button"], fg="white", command=lambda: change_direction("A"))
        jog_button = tk.Button(jog_popup, text="Go", font=self.fonts["buttons"], bg=self.colours["other-button"],
                               fg="white", command=lambda: self.send_command(command_dict))
        close_button = tk.Button(jog_popup, text="Close", font=self.fonts["buttons"], bg=self.colours["other-button"],
                                 fg="white", command=jog_popup.destroy)

        fh_button.grid(row=0, column=0)
        single_rev_button.grid(row=1, column=0)
        db_rev_button.grid(row=2, column=0)
        fwd_button.grid(row=3, column=0)
        rev_button.grid(row=4, column=0)
        set_pos_label.grid(row=5, column=0)
        set_pos.grid(row=5, column=1)
        set_pos_butt.grid(row=6)
        jog_button.grid(row=7, column=1)
        close_button.grid(row=7, column=2)

    def move_valve(self, valve_name, port_no):
        """This function is called when one of the port buttons on the main GUI window is clicked.
        Sends a command

        Args:
            valve_name (str): the name of the valve
            port_no (int): the number of the target port. Ranges from 1-10.
        """
        command_dict = {"mod_type": "selector_valve", "module_name": valve_name, "command": port_no,
                        "parameters": {"wait": False}}
        self.send_command(command_dict)
        self.v_button_colour(command_dict)

    def jog_valve(self, valve_name, valve_print_name):
        """This window allows the user to jog the valve by a number of steps or a number of ports.
        The child functions allow the user to change the movement direction, zero the valve position,
        read the Hall-effect sensor, and move the valve.

        Args:
            valve_name (str): the name of the valve to be moved
            valve_print_name (str): the name of the valve, formatted for display.
        """
        def change_direction(invert_direction):
            if invert_direction:
                self.invert_valve = True
            else:
                self.invert_valve = False

        def zero_command():
            zero_dict = {"mod_type": "selector_valve", "module_name": valve_name, "command": "zero",
                         "parameters": {"wait": False}}
            self.send_command(zero_dict)

        def read_sens():
            read_dict = {"mod_type": "selector_valve", "module_name": valve_name, "command": "he_sens",
                         "parameters": {"wait": False}}
            self.send_command(read_dict)

        def move(custom, steps):
            if custom:
                nr_steps = int(steps_entry.get())
                command_dict = {"mod_type": "selector_valve", "module_name": valve_name, "command": "jog",
                                "parameters": {"steps": nr_steps, "invert_direction": self.invert_valve,
                                               "wait": False}}
            else:
                nr_steps = steps
                command_dict = {"mod_type": "selector_valve", "module_name": valve_name, "command": "jog",
                                "parameters": {"steps": nr_steps, "invert_direction":  self.invert_valve,
                                               "wait": False}}
            self.send_command(command_dict)

        self.invert_valve = False
        jog_popup = tk.Toplevel(self.primary)
        jog_popup.title("Jog " + valve_print_name)
        steps_label = tk.Label(jog_popup, text="Steps to move:")
        steps_entry = tk.Entry(jog_popup)
        cust_move_butt = tk.Button(jog_popup, text="Custom move", font=self.fonts["buttons"],
                                   bg=self.colours["other-button"], fg="white", command=lambda: move(True, 0))
        p_butt = tk.Button(jog_popup, text="1 port", font=self.fonts["buttons"], bg=self.colours["other-button"],
                           fg="white", command=lambda: move(False, 640))
        cw_butt = tk.Button(jog_popup, text="Direction: CW", font=self.fonts["buttons"],
                            bg=self.colours["other-button"], fg="white", command=lambda: change_direction(True))
        cc_butt = tk.Button(jog_popup, text="Direction: CC", font=self.fonts["buttons"],
                            bg=self.colours["other-button"], fg="white", command=lambda: change_direction(False))
        zero_butt = tk.Button(jog_popup, text="Set pos 0", font=self.fonts["buttons"], bg=self.colours["other-button"],
                              fg="white", command=zero_command)
        he_butt = tk.Button(jog_popup, text="Read HE sensor", font=self.fonts["buttons"],
                            bg=self.colours["other-button"], fg="white", command=read_sens)
        close_button = tk.Button(jog_popup, text="Close", font=self.fonts["buttons"], bg="tomato2", fg="white",
                                 command=jog_popup.destroy)

        steps_label.grid(row=0)
        steps_entry.grid(row=1)
        cust_move_butt.grid(row=1, column=1)
        p_butt.grid(row=2)
        cw_butt.grid(row=3, column=0)
        cc_butt.grid(row=3, column=1)
        zero_butt.grid(row=4)
        he_butt.grid(row=5)
        close_button.grid(row=6, column=1)

    def heat_reactor(self, reactor_name, reactor_print_name):
        """This window allows the user to start and stop the reactor's heating element. The user
        can set the target temperature in °C using a text field. 

        Args:
            reactor_name (str): the name of the reactor 
            reactor_print_name (str): the name of the reactor, formatted for display
        """
        def start_heat():
            temp = float(reactor_entry.get())
            command_dict = {"mod_type": "reactor", "module_name": reactor_name, "command": "start_heat", 
                                        "parameters": {"temp": temp, "heat_secs": 0, "wait": False, "target": True}}
            self.send_command(command_dict)

        def stop_heat():
            command_dict = {"mod_type": "reactor", "module_name": reactor_name, "command": "stop_heat",
                                        "parameters": {"wait": False}}
            self.send_command(command_dict)

        heat_popup = tk.Toplevel(self.primary)
        heat_popup.title = reactor_print_name + " heating"
        heat_popup.configure(bg=self.colours["form-background"])
        reactor_label = tk.Label(heat_popup, text=f"Heating options for {reactor_print_name}",
                                 font=self.fonts["heading"], fg=self.colours["heading"],
                                 bg=self.colours["form-background"])
        temp_label = tk.Label(heat_popup, text="Temperature (°C):", font=self.fonts["labels"],
                              bg=self.colours["form-background"])
        reactor_entry = tk.Entry(heat_popup)
        start_butt = tk.Button(heat_popup, text="Start heating", font=self.fonts["buttons"],
                               bg=self.colours["accept-button"], command=start_heat)
        stop_butt = tk.Button(heat_popup, text="Stop heating", font=self.fonts["buttons"],
                              bg=self.colours["cancel-button"], command=stop_heat)
        cancel_butt = tk.Button(heat_popup, text="Close", font=self.fonts["buttons"], bg=self.colours["cancel-button"],
                                command=heat_popup.destroy)

        reactor_label.grid(row=0, columnspan=2)
        temp_label.grid(row=1, column=0)
        reactor_entry.grid(row=1, column=1)
        start_butt.grid(row=2, column=0)
        stop_butt.grid(row=2, column=1)
        cancel_butt.grid(row=3, columnspan=2, pady=5)

    def stir_reactor(self, reactor_name, reactor_print_name):
        """This window allows the user to start and stop the stirring 

        Args:
            reactor_name (str): the name of the reactor
            reactor_print_name (str): the name of the reactor, formatted for display
        """
        def start_stir():
            speed = int(reactor_entry.get())
            command_dict = {"mod_type": "reactor", "module_name": reactor_name, "command": "start_stir", 
                                        "parameters": {"speed": speed, "stir_secs": 0, "wait": False, "target": True}}
            self.send_command(command_dict)

        def stop_stir():
            command_dict = {"mod_type": "reactor", "module_name": reactor_name, "command": "stop_stir",
                                        "parameters": {"wait": False}}
            self.send_command(command_dict)

        stir_popup = tk.Toplevel(self.primary)
        stir_popup.title = reactor_print_name + " stirring"
        stir_popup.configure(bg=self.colours["form-background"])
        reactor_label = tk.Label(stir_popup, text=f"Stirring options for {reactor_print_name}",
                                 font=self.fonts["heading"], fg=self.colours["heading"],
                                 bg=self.colours["form-background"])
        temp_label = tk.Label(stir_popup, text="Speed (RPM):", font=self.fonts["labels"],
                              bg=self.colours["form-background"])
        reactor_entry = tk.Entry(stir_popup)
        start_butt = tk.Button(stir_popup, text="Start stirring", font=self.fonts["buttons"],
                               bg=self.colours["accept-button"], command=start_stir)
        stop_butt = tk.Button(stir_popup, text="Stop stirring", font=self.fonts["buttons"],
                              bg=self.colours["cancel-button"], command=stop_stir)
        cancel_butt = tk.Button(stir_popup, text="Close", font=self.fonts["buttons"], bg=self.colours["cancel-button"],
                                command=stir_popup.destroy)

        reactor_label.grid(row=0, columnspan=2)
        temp_label.grid(row=1, column=0)
        reactor_entry.grid(row=1, column=1)
        start_butt.grid(row=2, column=0)
        stop_butt.grid(row=2, column=1)
        cancel_butt.grid(row=3, columnspan=2, pady=5)

    def update_temps(self, reactor_name, reactor_temp):
        """Updates the temperature display, using data retrieved from the queue.

        Args:
            reactor_name (str): the name of the reactor
            reactor_temp (float): the current temperature of the reactor in °C, updated every 5 s.
        """
        self.reactor_labels[reactor_name].configure(text=f"{reactor_temp} °C")

    def wait_user(self):
        def done():
            self.manager.user_wait_flag = True
            window.destroy()

        window = tk.Toplevel(self.primary, bg=self.colours["form-bg"])
        label = tk.Label(window, text="Click done when ready to resume", font=self.fonts["heading"],
                         fg=self.colours["heading"], bg=self.colours["form-bg"])
        done_butt = tk.Button(window, text="Done", bg=self.colours["accept-button"], command=done)
        label.grid()
        done_butt.grid()

    def send_command(self, command_dict):
        """Sends commands to the robot in the form of dictionaries. These dictionaries are placed into the 
        Manager's queue to be retrieved and performed. Should a command fail to execute, the Manager will
        display error messages within the log window.

        Args:
            command_dict (dict): dictionary containing the command information: module name, module type, and parameters for the command.
        """
        if self.manager.error:
            self.manager.error_queue.put(command_dict)
        else:
            self.manager.q.put(command_dict)
        name, command = command_dict["module_name"], command_dict["command"]
        params = command_dict["parameters"]
        if command_dict["mod_type"] == "selector_valve":
            if command == "zero":
                self.write_message(f"Sent command to zero {name}")
            elif command == "home":
                self.write_message(f"Sent command to home {name}")
        elif command_dict["mod_type"] == "syringe_pump":
            if command == "home":
                message = f"Sent command to home {name}"
            elif command == "jog":
                message = f"Sent command to jog {name} by {params['steps']}"
            elif command == "move":
                vol, flow = command_dict["parameters"]["volume"], command_dict["parameters"]["flow_rate"]
                if params["direction"] == "D":
                    message = f"Sent command to {name} to dispense {vol / 1000}ml at {flow} \u03BCL/min"
                else:
                    message = f"Sent command to {name} to aspirate {vol / 1000}ml at {flow} \u03BCL/min"
            elif command == "setpos":
                message = f"Sent command to {name} to set position to {params['pos']}"
            else:
                message = f"Unrecognised command: {command}"
            self.write_message(message)
        elif command_dict["mod_type"] == "reactor":
            if command == "start_heat":
                self.write_message(f"Started heating {name} to {params['temp']}")
            elif command == "stop_heat":
                self.write_message(f"Stopped heating {name}")
            elif command == "start_stir":
                self.write_message(f"Started stirring {name} at {params['speed']}")

    def write_message(self, message):
        """Writes a message to the log window. Messages will wrap when they exceed the width of the window.

        Args:
            message (str): the message to be output
        """
        numlines = int(self.log.index("end - 1 line").split(".")[0])
        self.log["state"] = "normal"
        if numlines == 24:
            self.log.delete(1.0, 2.0)
        if self.log.index("end-1c") != "1.0":
            self.log.insert("end", "\n")
        self.log.insert("end", message)
        self.log["state"] = "disabled"

    def clear_messages(self):
        self.log["state"] = "normal"
        self.log.delete("1.0", tk.END)
        self.log["state"] = "disabled"

    def update_execution(self, execute):
        """Updates the start/stop execution button

        Args:
            execute (bool): True if currently configured to execute queue, False otherwise.
        """
        if execute:
            self.execute_butt.configure(text="Stop auto execution",
                                        command=lambda: self.send_interrupt({"pause": False, "stop": False,
                                                                             "resume": False, "exit": False,
                                                                             "execute": False}))
        else:
            self.execute_butt.configure(text="Start auto execution",
                                        command=lambda: self.send_interrupt({"pause": False, "stop": False,
                                                                             "resume": False, "exit": False,
                                                                             "execute": True}))

    def load_xdl(self):
        """Loads an XDL file to be parsed for execution. The XDL file is parsed by the WebListener class.
        """
        filename = fd.askopenfilename(title="Open XDL file", initialdir="/", filetypes=(("All files", "*.*"), ))
        self.manager.listener.load_xdl(filename, is_file=True)

    def stop(self):
        """Commands the robot to pause all ongoing actions and clear the execution queue. 
        """
        self.pause_butt.configure(text="pause", bg=self.colours["other-button"], command=self.pause)
        self.send_interrupt({"pause": True, "stop": True, "resume": False, "exit": False})

    def pause(self):
        """Commands the robot to pause all ongoing actions and changes the pause button.
        Does not clear the queue, so actions can be resumed from their last state by pressing resume.
        """
        self.pause_butt.configure(text="Resume", bg="lawn green", command=self.resume)
        self.send_interrupt({"pause": True, "stop": False, "resume": False, "exit": False})

    def resume(self):
        """Commands the robot to resume execution of the queue, starting from the last known state of the 
        last executed action. 
        """
        self.pause_butt.configure(text="Pause", bg=self.colours["other-button"], command=self.pause)
        self.send_interrupt({"pause": False, "stop": False, "resume": True, "exit": False})

    def send_interrupt(self, parameters):
        """Used to send start, stop, pause, resume, execute, and exit commands to the robot. The Manager thread runs continously,
        so Lock objects are used to ensure thread safety. 

        Args:
            parameters (dict): the parameters for the interrupt (whether to pause, stop, exit, or resume) 
        """
        execute = parameters.get("execute")
        if parameters["stop"]:
            with self.manager.interrupt_lock:
                self.manager.pause_flag = True
                self.manager.stop_flag = True
                self.manager.interrupt = True
            self.write_message("Stopping all operations")
        elif parameters["pause"]:
            with self.manager.interrupt_lock:
                self.manager.pause_flag = True
                self.manager.interrupt = True
            self.write_message("Pausing all operations")
        elif parameters["resume"]:
            with self.manager.interrupt_lock:
                self.manager.pause_flag = False
                self.manager.interrupt = True
            self.write_message("Resuming operations")
        elif execute is not None:
            with self.manager.interrupt_lock:
                self.manager.execute = execute
        elif parameters["exit"]:
            with self.manager.interrupt_lock:
                self.manager.exit_flag = True
                self.manager.interrupt = True

    def start_gui(self):
        self.primary.mainloop()

    def end_program(self):
        """Waits for the manager to exit, then reads queue to remove the "after" event.
        """
        parameters = {"pause": False, "stop": False, "resume": False, "exit": True}
        self.send_interrupt(parameters)
        self.quit_flag = True
        while not self.manager.quit_safe:
            time.sleep(0.1)
        self.read_queue()
        self.primary.destroy()

    def validate_vol(self, new_num):
        """validates whether the typed value can be converted into a float for a volume.

        Args:
            new_num (str): input to the text field

        Returns:
            bool: True if value can be converted to float or field is being cleared. False otherwise.
        """
        if not new_num:  # field is being cleared
            self.volume_tmp = 0.0
            return True
        try:
            self.volume_tmp = float(new_num)
            return True
        except ValueError:
            self.write_message("Incorrect value for volume")
            return False

    def validate_flow(self, new_num):
        """validates whether the typed value can be converted into a float for a flow rate.

        Args:
            new_num (str): input to the text field

        Returns:
            bool: True if value can be converted to float or field is being cleared. False otherwise.
        """
        if not new_num:
            self.flow_rate_tmp = 0.0
            return True
        try:
            self.flow_rate_tmp = float(new_num)
            return True
        except ValueError:
            self.write_message("Incorrect value for flow rate")
            return False


if __name__ == "__main__":
    fb_gui = FluidicBackboneUI(simulation=False, web_enabled=False)
