import os
import tkinter as tk
import UJ_FB.manager as manager


class FluidicBackboneUI:
    def __init__(self, manager):
        """
        :param simulation: Bool to run the software in simulation mode
        """
        self.primary = tk.Tk()
        self.primary.protocol('WM_DELETE_WINDOW', self.end_program)
        self.manager = manager
        self.fonts = {'buttons': ('Calibri', 12), 'labels': ('Calibri', 14), 'default': ('Calibri', 16),
                      'heading': ('Calibri', 16), 'text': ('Calibri', 10)}
        self.colours = {'form-background': "#9ab5d9", 'accept-button': '#4de60b', 'cancel-button': '#e6250b',
         'heading': '#e65525',  "other-button": "#45296e", "other-button-text": "#FFFFFF", 'form-bg': '#b5d5ff'}
        self.primary.title('Fluidic Backbone Prototype')
        self.primary.configure(background=self.colours['form-background'])
        self.volume_tmp, self.flow_rate_tmp = 0.0, 0.0


        icon = tk.PhotoImage(file=os.path.join(os.path.dirname(__file__), 'Syringe.png'))
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
        self.log = tk.Text(self.log_frame, state='disabled', width=60, height=24, wrap='none', borderwidth=5)

        self.override_frame = tk.Frame(self.primary, bg=self.colours['form-background'])
        self.clean_butt = tk.Button(self.override_frame, text="Clean step complete?", font=self.fonts['buttons'], bg=self.colours['other-button'],
                                                fg='white', command=self.clean_done)
        self.pause_butt = tk.Button(self.override_frame, text='Pause', font=self.fonts['buttons'], bg=self.colours['other-button'],
                                    fg='white', command=self.pause)
        self.stop_butt = tk.Button(self.override_frame, text='Stop', font=self.fonts['buttons'], bg=self.colours['cancel-button'], fg='white',
                                   command=self.stop)
        
        self.web_frame = tk.Frame(self.primary, bg=self.colours['form-background'])
        self.url_label = tk.Label(self.web_frame, text="Current server URL: " + self.manager.listener.url, font=self.fonts['labels'], background=self.colours['form-background'])
        self.url_butt = tk.Button(self.web_frame, text="Update URL", font=self.fonts['buttons'], fg='white', bg=self.colours['other-button'], 
                                                command=self.update_url)
        
        self.reactor_frame = tk.Frame(self.primary, bg=self.colours['form-background'])
        for reactor in self.manager.reactors.keys():
            self.populate_reactors(reactor)

        self.valve_pump_frame.grid(row=0, column=0, padx=5, pady=10)
        self.reactor_frame.grid(row=1, column=0, padx=5, pady=5)
        self.log_frame.grid(row=0, column=1, padx=5, pady=5)
        self.override_frame.grid(row=1, column=1, padx=5, pady=5)
        self.web_frame.grid(row=3, column=1, padx=5, pady=5)
        self.url_label.grid(row=0, column=1)
        self.url_butt.grid(row=0, column=2)
        self.clean_butt.grid(row=0, sticky="E")
        self.pause_butt.grid(row=0, column=2, sticky="W")
        self.stop_butt.grid(row=0, column=3, sticky="W")
        self.log.grid(row=14, column=0)

    def populate_syringes(self, syringe_name):
        """
        Populates the buttons for syringe
        :param syringe_name: name of syringe from config file
        :return:
        """
        syringe_no = int(syringe_name[-1]) - 1
        col = syringe_no * 2
        syringe_print_name = "Syringe " + str(syringe_no + 1)
        self.syringe_labels.append(tk.Label(self.valve_pump_frame, text=syringe_print_name, font=self.fonts['labels'],
                                            bg='white'))
        self.syringe_labels[syringe_no].grid(row=0, column=col, columnspan=2)

        home_button = tk.Button(self.valve_pump_frame, text='Home', font=self.fonts['buttons'], width=5, padx=5, bg=self.colours['other-button'],
                                fg='white', command=lambda: self.home_syringe(syringe_name, syringe_print_name))
        jog_button = tk.Button(self.valve_pump_frame, text='Jog', font=self.fonts['buttons'], padx=5, bg=self.colours['other-button'], fg='white',
                               command=lambda: self.jog_syringe(syringe_name, syringe_print_name))

        home_button.grid(row=1, column=col)
        jog_button.grid(row=2, column=col)

        dispense_button = tk.Button(self.valve_pump_frame, text='Dispense', font=self.fonts['buttons'], padx=5, bg=self.colours['other-button'],
                                    fg='white',
                                    command=lambda: self.move_syringe(syringe_name, syringe_print_name, "D"))
        dispense_button.grid(row=1, column=col + 1, columnspan=1)

        aspirate_button = tk.Button(self.valve_pump_frame, text='Aspirate', font=self.fonts['buttons'], padx=5, bg=self.colours['other-button'],
                                fg='white', command=lambda: self.move_syringe(syringe_name, syringe_print_name, "A"))
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
        valve_label = tk.Label(self.valve_pump_frame, text=valve_print_name, font=self.fonts['labels'],
                                           bg='white')
        valve_label.grid(row=4, column=col, columnspan=2)

        home_button = tk.Button(self.valve_pump_frame, text='Home', font=self.fonts['buttons'], padx=5, bg=self.colours['accept-button'],
                                fg='white',
                      command=lambda: self.move_valve(valve_name, 'home'))
        home_button.grid(row=5, column=col)
        jog_button = tk.Button(self.valve_pump_frame, text='Jog', font=self.fonts['buttons'], padx=5, bg=self.colours['accept-button'],
                               fg='white',
                      command=lambda: self.jog_valve(valve_name, valve_print_name))
        jog_button.grid(row=5, column=col + 1)

        for port_no in range(0, 5):
            ports.append(tk.Button(self.valve_pump_frame, text=str(port_no + 1), font=self.fonts['buttons'], width=5, padx=5, bg=self.colours['other-button'],
                                   fg='white', command=lambda i=port_no + 1: self.move_valve(valve_name, i)))
            ports[port_no].grid(row=6 + port_no, column=col)

        for port_no in range(5, 10):
            ports.append(tk.Button(self.valve_pump_frame, text=str(port_no + 1), font=self.fonts['buttons'], width=5, padx=5, bg=self.colours['other-button'],
                                   fg='white', command=lambda i=port_no + 1: self.move_valve(valve_name, i)))
            ports[port_no].grid(row=1 + port_no, column=col + 1)

        # Append list of ports corresponding to valve_no to valves_buttons
        self.valves_buttons[valve_name] = ports

    def populate_reactors(self, reactor_name):
        reactor_no = int(reactor_name[-1])
        reactor_print_name = "Reactor " + str(reactor_no)
        row = reactor_no
        self.syringe_labels.append(tk.Label(self.reactor_frame, text=reactor_print_name, font=self.fonts['labels'],
                                            bg=self.colours['form-background']))
        self.syringe_labels[reactor_no].grid(row=row, column=0)

        heat_button = tk.Button(self.reactor_frame, text='Heating', font=self.fonts['buttons'], padx=5, bg=self.colours['other-button'],
                                fg='white', command=lambda: self.heat_reactor(reactor_name, reactor_print_name))
        stir_button = tk.Button(self.reactor_frame, text='Stirring', font=self.fonts['buttons'], padx=5, bg=self.colours['other-button'], fg='white',
                               command=lambda: self.stir_reactor(reactor_name, reactor_print_name))

        heat_button.grid(row=row, column=1)
        stir_button.grid(row=row, column=2)

    def v_button_colour(self, command_dict):
        command = command_dict["command"]
        if command == "home":
            port_no = 0
        else:
            port_no = command_dict["command"] - 1
        valve = command_dict["module_name"]
        for item in self.valves_buttons[valve]:
            item.configure(bg=self.colours['other-button'])
        self.valves_buttons[valve][port_no].configure(bg=self.colours['heading'])
    
    def update_url(self):
        def accept_url():
            new_url = url_entry.get()
            self.manager.update_url(new_url)
            cur_url = self.manager.listener.url
            self.url_label.configure(text="Current server URL: " + cur_url, font=self.fonts['labels'])
            url_window.destroy()

        url_window = tk.Toplevel(self.primary)
        url_window.title="Configure server URL"
        url_label = tk.Label(url_window, text='Please enter the new IP address for the server: ', font=self.fonts['labels'])
        url_entry = tk.Entry(url_window, width=30)
        url_buttonA = tk.Button(url_window, text='Accept', font=self.fonts['buttons'], bg=self.colours['accept-button'], command=accept_url)
        url_buttonC = tk.Button(url_window, text='Cancel', font=self.fonts['buttons'], bg=self.colours['cancel-button'], command=url_window.destroy)

        url_label.grid(row=0, column=0)
        url_entry.grid(row=0, column=1)
        url_buttonA.grid(row=1, column = 0)
        url_buttonC.grid(row=1, column=1)


    def move_syringe(self, syringe_name, syringe_print_name, direction):
        """
        Menu to control syringe pumps
        :param syringe_print_name: name to print in messages and logs
        :param syringe_name: syringe to be addressed
        :param direction: boolean, True if aspirating syringe, False if dispensing syringe
        :return: None
        """

        def dispense(syr_name):
            command_dict = {'mod_type': 'syringe', 'module_name': syr_name, 'command': 'move',
                            'parameters': {'volume': self.volume_tmp * 1000, 'flow_rate': self.flow_rate_tmp,
                                           'direction': direction, 'wait': False, 'target': None}}
            sp_move_menu.destroy()
            self.send_command(command_dict)

        if direction == "A":
            button_text = menu_title = "Aspirate"
        else:
            button_text = menu_title = "Dispense"

        sp_move_menu = tk.Toplevel(self.primary)
        sp_move_menu.title(menu_title + ' ' + syringe_print_name)
        sp_move_menu.configure(bg=self.colours['form-background'])
        val_vol = self.primary.register(self.validate_vol)
        val_flow = self.primary.register(self.validate_flow)

        vol_label = tk.Label(sp_move_menu, text='Volume to ' + button_text.lower() + 'in ml:')
        vol_entry = tk.Entry(sp_move_menu, validate='key', validatecommand=(val_vol, '%P'), fg='black', bg='white',
                             width=50)

        flow_label = tk.Label(sp_move_menu, text='Flow rate in \u03BCL/min:')
        flow_entry = tk.Entry(sp_move_menu, validate='key', validatecommand=(val_flow, '%P'), fg='black', bg='white',
                              width=50)

        go_button = tk.Button(sp_move_menu, text=button_text, font=self.fonts['buttons'], bg=self.colours['accept-button'], fg='white',
                              command=lambda: dispense(syringe_name))
        cancel_button = tk.Button(sp_move_menu, text='Cancel', font=self.fonts['buttons'], bg=self.colours['cancel-button'], fg='white',
                                  command=sp_move_menu.destroy)

        vol_label.grid(row=0, column=1)
        vol_entry.grid(row=0, column=5)
        flow_label.grid(row=2, column=1)
        flow_entry.grid(row=2, column=5)
        go_button.grid(row=5, column=5)
        cancel_button.grid(row=5, column=6)

    def home_syringe(self, syringe_name, syringe_print_name):
        command_dict = {'mod_type': 'syringe', 'module_name': syringe_name, 'command': 'home',
                        "parameters": {'volume': 0.0, 'flow_rate': 9999, 'wait': False}}

        def home_command():
            home_popup.destroy()
            self.send_command(command_dict)

        home_popup = tk.Toplevel(self.primary)
        home_popup.title('Home ' + syringe_print_name)
        warning_label = tk.Label(home_popup, text='Homing the syringe will empty its contents, are you sure?')
        yes_button = tk.Button(home_popup, text='Home', font=self.fonts['buttons'], bg=self.colours['other-button'], fg='white',
                               command=home_command)
        no_button = tk.Button(home_popup, text='Cancel', font=self.fonts['buttons'], bg=self.colours['other-button'], fg='white',
                              command=home_popup.destroy)
        warning_label.grid(row=0, column=1, columnspan=5)
        yes_button.grid(row=2, column=1)
        no_button.grid(row=2, column=5)

    def jog_syringe(self, syringe_name, syringe_print_name):
        command_dict = {'mod_type': 'syringe', 'module_name': syringe_name, 'command': 'jog',
                        "parameters": {'volume': 0.0, 'flow_rate': 9999, 'steps': 0, 'direction': "D", 'wait': False}}

        # todo: add jog speed setting

        def change_steps(steps):
            command_dict['parameters']['steps'] = steps

        def setpos():
            new_pos = set_pos.get()
            zero_dict = {'mod_type': 'syringe', 'module_name': syringe_name, 'command': 'setpos',
                         "parameters": {'volume': 0.0, 'flow_rate': 9999, 'pos': new_pos, 'wait': False}}
            self.send_command(zero_dict)

        def change_direction(direction):
            if direction == "A":
                command_dict["parameters"]['direction'] = "A"
            else:
                command_dict["parameters"]['direction'] = "D"

        jog_popup = tk.Toplevel(self.primary)
        jog_popup.title('Jog' + syringe_print_name)
        fh_button = tk.Button(jog_popup, text='500 Steps', font=self.fonts['buttons'], bg=self.colours['other-button'], fg='white',
                              command=lambda: change_steps(500))
        single_rev_button = tk.Button(jog_popup, text='3200 Steps', font=self.fonts['buttons'], bg=self.colours['other-button'], fg='white',
                                      command=lambda: change_steps(3200))
        db_rev_button = tk.Button(jog_popup, text='6400 Steps', font=self.fonts['buttons'], bg=self.colours['other-button'], fg='white',
                                  command=lambda: change_steps(6400))
        set_pos_label = tk.Label(jog_popup, text='Set syringe position in ml')
        set_pos = tk.Entry(jog_popup)
        set_pos_butt = tk.Button(jog_popup, text='set current position', command=setpos)
        fwd_button = tk.Button(jog_popup, text='Direction: Dispense', font=self.fonts['buttons'], bg=self.colours['other-button'], fg='white',
                               command=lambda: change_direction("D"))
        rev_button = tk.Button(jog_popup, text='Direction: Aspirate', font=self.fonts['buttons'], bg=self.colours['other-button'], fg='white',
                               command=lambda: change_direction("A"))
        jog_button = tk.Button(jog_popup, text='Go', font=self.fonts['buttons'], bg=self.colours['other-button'], fg='white',
                               command=lambda: self.send_command(command_dict))
        close_button = tk.Button(jog_popup, text='Close', font=self.fonts['buttons'], bg=self.colours['other-button'], fg='white',
                                 command=jog_popup.destroy)

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
        command_dict = {'mod_type': 'valve', 'module_name': valve_name, 'command': port_no,
                        'parameters': {'wait': False}}
        self.send_command(command_dict)
        self.v_button_colour(command_dict)

    def jog_valve(self, valve_name, valve_print_name):
        def change_direction(invert_direction):
            if invert_direction:
                self.invert_valve  = True
            else:
                self.invert_valve = False

        def zero_command():
            zero_dict = {'mod_type': 'valve', 'module_name': valve_name, 'command': 'zero',
                         "parameters": {'wait': False}}
            self.send_command(zero_dict)

        def read_sens():
            read_dict = {'mod_type': 'valve', 'module_name': valve_name, 'command': 'he_sens',
                         "parameters": {'wait': False}}
            self.send_command(read_dict)

        def move(custom, steps):
            if custom:
                nr_steps = int(steps_entry.get())
                command_dict = {'mod_type': 'valve', 'module_name': valve_name, 'command': 'jog',
                                "parameters": {'steps': nr_steps, 'invert_direction' : self.invert_valve, 'wait': False}}
            else:
                nr_steps = steps
                command_dict = {'mod_type': 'valve', 'module_name': valve_name, 'command': 'jog',
                                "parameters": {'steps': nr_steps, 'invert_direction':  self.invert_valve, 'wait': False}}
            self.send_command(command_dict)

        self.invert_valve = False
        jog_popup = tk.Toplevel(self.primary)
        jog_popup.title('Jog ' + valve_print_name)
        steps_label = tk.Label(jog_popup, text='Steps to move:')
        steps_entry = tk.Entry(jog_popup)
        cust_move_butt = tk.Button(jog_popup, text='Custom move', font=self.fonts['buttons'], bg=self.colours['other-button'], fg='white',
                                   command=lambda: move(True, 0))
        p_butt = tk.Button(jog_popup, text='1 port', font=self.fonts['buttons'], bg=self.colours['other-button'], fg='white',
                           command=lambda: move(False, 640))
        cw_butt = tk.Button(jog_popup, text='Direction: CW', font=self.fonts['buttons'], bg=self.colours['other-button'], fg='white',
                            command=lambda: change_direction(True))
        cc_butt = tk.Button(jog_popup, text='Direction: CC', font=self.fonts['buttons'], bg=self.colours['other-button'], fg='white',
                            command=lambda: change_direction(False))
        zero_butt = tk.Button(jog_popup, text='Set pos 0', font=self.fonts['buttons'], bg=self.colours['other-button'], fg='white',
                              command=zero_command)
        he_butt = tk.Button(jog_popup, text='Read HE sensor', font=self.fonts['buttons'], bg=self.colours['other-button'], fg='white', command=read_sens)
        close_button = tk.Button(jog_popup, text='Close', font=self.fonts['buttons'], bg='tomato2', fg='white',
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
        def start_heat():
            temp = float(reactor_entry.get())
            command_dict = {"mod_type": "reactor", "module_name": reactor_name, 'command': 'start_heat', 
                                        'parameters': {'temp': temp, "heat_secs": 0, 'wait': False, 'target': True}}
            self.send_command(command_dict)

        def stop_heat():
            command_dict = {"mod_type": "reactor", "module_name": reactor_name, "command": "stop_heat",
                                        "parameters": {}}
            self.send_command(command_dict)

        heat_popup = tk.Toplevel(self.primary)
        heat_popup.title = reactor_print_name + " heating"
        heat_popup.configure(bg=self.colours['form-background'])
        reactor_label = tk.Label(heat_popup, text=f'Heating options for {reactor_print_name}', font=self.fonts['heading'], fg=self.colours['heading'], bg=self.colours['form-background'])
        temp_label = tk.Label(heat_popup, text="Temperature (°C):", font=self.fonts['labels'], bg=self.colours['form-background'])
        reactor_entry = tk.Entry(heat_popup)
        start_butt = tk.Button(heat_popup, text="Start heating", font=self.fonts['buttons'], bg=self.colours['accept-button'], command=start_heat)
        stop_butt = tk.Button(heat_popup, text='Stop heating', font=self.fonts['buttons'], bg=self.colours['cancel-button'], command=stop_heat)
        cancel_butt = tk.Button(heat_popup, text="Close", font=self.fonts['buttons'], bg=self.colours['cancel-button'], command=heat_popup.destroy)

        reactor_label.grid(row=0, columnspan=2)
        temp_label.grid(row=1, column=0)
        reactor_entry.grid(row=1, column=1)
        start_butt.grid(row=2, column=0)
        stop_butt.grid(row=2, column=1)
        cancel_butt.grid(row=3, columnspan=2, pady=5)

    def stir_reactor(self, reactor_name, reactor_print_name):
        def start_stir():
            speed = int(reactor_entry.get())
            command_dict = {"mod_type": "reactor", "module_name": reactor_name, 'command': 'start_stir', 
                                        'parameters': {'speed': speed, "stir_secs": 0, 'wait': False, 'target': True}}
            self.send_command(command_dict)

        def stop_stir():
            command_dict = {"mod_type": "reactor", "module_name": reactor_name, "command": "stop_stir",
                                        "parameters": {}}
            self.send_command(command_dict)

        stir_popup = tk.Toplevel(self.primary)
        stir_popup.title = reactor_print_name + " stirring"
        stir_popup.configure(bg=self.colours['form-background'])
        reactor_label = tk.Label(stir_popup, text=f'Heating options for {reactor_print_name}', font=self.fonts['heading'], fg=self.colours['heading'], bg=self.colours['form-background'])
        temp_label = tk.Label(stir_popup, text="Temperature (°C):", font=self.fonts['labels'], bg=self.colours['form-background'])
        reactor_entry = tk.Entry(stir_popup)
        start_butt = tk.Button(stir_popup, text="Start heating", font=self.fonts['buttons'], bg=self.colours['accept-button'], command=start_stir)
        stop_butt = tk.Button(stir_popup, text='Stop heating', font=self.fonts['buttons'], bg=self.colours['cancel-button'], command=stop_stir)
        cancel_butt = tk.Button(stir_popup, text="Close", font=self.fonts['buttons'], bg=self.colours['cancel-button'], command=stir_popup.destroy)

        reactor_label.grid(row=0, columnspan=2)
        temp_label.grid(row=1, column=0)
        reactor_entry.grid(row=1, column=1)
        start_butt.grid(row=2, column=0)
        stop_butt.grid(row=2, column=1)
        cancel_butt.grid(row=3, columnspan=2, pady=5)

    def wait_user(self):
        def done():
            self.manager.user_wait_flag = True
            window.destroy()

        window = tk.Toplevel(self.primary, bg=self.colours['form-bg'])
        label = tk.Label(window, text='Click done when ready to resume', font=self.fonts['heading'], fg=self.colours['heading'], bg=self.colours['form-bg'])
        done_butt = tk.Button(window, text="Done", bg=self.colours['accept-button'], command=done)
        label.grid()
        done_butt.grid()

    def send_command(self, command_dict):
        self.manager.q.put(command_dict)
        name, command = command_dict['module_name'], command_dict['command']
        params = command_dict['parameters']
        if command_dict['mod_type'] == 'valve':
            if command == 'zero':
                self.write_message(f'Sent command to zero {name}')
            elif command == 'home':
                self.write_message(f'Sent command to home {name}')
        elif command_dict['mod_type'] == 'syringe':
            if command == 'home':
                message = f"Sent command to home {name}"
            elif command == "jog":
                message = f'Sent command to jog {name} by {params["steps"]}'
            elif command == 'move':
                vol, flow = command_dict['parameters']['volume'], command_dict['parameters']['flow_rate']
                if params['direction']:
                    message = f'Sent command to {name} to aspirate {vol / 1000}ml at {flow} \u03BCL/min'
                else:
                    message = f'Sent command to {name} to dispense {vol / 1000}ml at {flow} \u03BCL/min'
            elif command == 'setpos':
                message = f"Sent command to {name} to set position to {params['pos']}"
            else:
                message = f'Unrecognised command: {command}'
            self.write_message(message)
        elif command_dict['mod_type']=='reactor':
            if command == "start_heat":
                self.write_message(f"Started heating {name} to {params['temp']}")
            elif command == "stop_heat":
                self.write_message(f"Stopped heating {name}")
            elif command == "start_stir":
                self.write_message(f'Started stirring {name} at {params["speed"]}')

    def write_message(self, message):
        numlines = int(self.log.index('end - 1 line').split('.')[0])
        self.log['state'] = 'normal'
        if numlines == 24:
            self.log.delete(1.0, 2.0)
        if self.log.index('end-1c') != '1.0':
            self.log.insert('end', '\n')
        self.log.insert('end', message)
        self.log['state'] = 'disabled'

    def send_message(self, parameters):
        pass

    def stop(self):
        self.stop_butt.configure(state='disabled')
        self.send_interrupt({'pause': True, 'stop': True, 'resume': False, 'exit': True})

    def pause(self):
        self.pause_butt.configure(text='Resume', bg='lawn green', command=self.resume)
        self.send_interrupt({'pause': True, 'stop': False, 'resume': False, 'exit': True})

    def resume(self):
        self.pause_butt.configure(text='pause', bg='sky blue', command=self.pause)
        self.send_interrupt({'pause': False, 'stop': False, 'resume': True, 'exit': True})

    def clean_done(self):
        self.manager.clean_step = False

    def send_interrupt(self, parameters):
        if parameters['stop']:
            with self.manager.interrupt_lock:
                self.manager.pause_flag = True
                self.manager.stop_flag = True
                self.manager.interrupt = True
            self.write_message('Stopping all operations')
        elif parameters['pause']:
            with self.manager.interrupt_lock:
                self.manager.pause_flag = True
                self.manager.interrupt = True
            self.write_message('Pausing all operations')
        elif parameters['resume']:
            with self.manager.interrupt_lock:
                self.manager.pause_flag = False
                self.manager.interrupt = True
            self.write_message('Resuming operations')
        elif parameters['exit']:
            with self.manager.interrupt_lock:
                self.manager.exit_flag = True
                self.manager.interrupt = True

    def end_program(self):
        parameters = {'pause': False, 'stop': False, 'resume': False, 'exit': True}
        self.send_interrupt(parameters)
        self.primary.destroy()

    def validate_vol(self, new_num):
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
        if not new_num:
            self.flow_rate_tmp = 0.0
            return True
        try:
            self.flow_rate_tmp = float(new_num)
            return True
        except ValueError:
            self.write_message("Incorrect value for flow rate")
            return False


if __name__ == '__main__':
    sim = False
    man = manager.Manager()
    fb_gui = FluidicBackboneUI(sim, man)
