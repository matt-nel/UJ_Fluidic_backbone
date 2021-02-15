import os
import tkinter
import time
from Manager import Manager


class FLuidicBackboneUI:
    def __init__(self, primary, simulation):
        """
        :param primary: root TK window object
        :param simulation: Bool to run the software in simulation mode
        """
        self.manager = Manager(self, simulation)
        self.primary = primary
        self.primary.title('Fluidic Backbone Prototype')
        self.primary.configure(background='SteelBlue2')
        self.volume_tmp, self.flow_rate_tmp = 0.0, 0.0
        self.fonts = {'default': ('Verdana', 16)}

        icon = tkinter.PhotoImage(file=os.path.join(os.path.dirname(__file__), 'Syringe.png'))
        self.primary.tk.call('wm', 'iconphoto', self.primary._w, icon)

        self.button_frame = tkinter.Frame(self.primary, borderwidth=5)

        self.syringe_labels = []
        self.syringe_buttons = []
        # list of syringe buttons, eg: syringe_buttons[0][0] is aspirate button for syringe 1
        # syringe_buttons[0][1] is withdraw button for syringe 1
        for syringe in self.manager.syringes.keys():
            self.populate_syringes(syringe)

        self.valves_labels = []
        self.valves_buttons = []
        # valves_buttons[valve_no][port_no]
        # list valves_buttons contains buttons corresponding to each valve port starting from 1, with zero corresponding
        # to homing button. valves_buttons[0][0] is home button of valve 1, valves_buttons[3][2] is port 2 of valve 4
        for valve in self.manager.valves.keys():
            self.populate_valves(valve)

        self.log_frame = tkinter.Frame(self.primary)
        self.log = tkinter.Text(self.log_frame, state='disabled', width=80, height=24, wrap='none', borderwidth=5)

        self.log_frame.grid(row=0, column=3, padx=5, pady=10)
        self.button_frame.grid(row=0, column=0, padx=5, pady=10)
        self.log.grid(row=14, column=0)
        self.fonts = {'buttons': ('Verdana', 16), 'labels': ('Verdana', 16), 'default': ('Verdana', 16)}
        self.manager.start()

    def populate_syringes(self, syringe_name):
        """
        Populates the buttons for syringe
        :param syringe_name: name of syringe from config file
        :return:
        """
        buttons = []
        syringe_no = int(syringe_name[-1]) - 1
        syringe_print_name = "Syringe " + str(syringe_no + 1)
        self.syringe_labels.append(tkinter.Label(self.button_frame, text=syringe_print_name, font=self.fonts['default'],
                                                 bg='white'))
        self.syringe_labels[syringe_no].grid(row=0, column=syringe_no+1, columnspan=1)

        buttons.append(tkinter.Button(self.button_frame, text='Home Syringe', font=self.fonts['default'], padx=5,
                                      bg='teal', fg='white',
                                      command=lambda: self.home_syringe(syringe_name, syringe_print_name)))
        buttons[0].grid(row=1, column=syringe_no+1, columnspan=1)

        buttons.append(tkinter.Button(self.button_frame, text='Aspirate', font=self.fonts['default'], padx=5, bg='teal',
                                      fg='white', command=lambda: self.asp_with(syringe_name, syringe_print_name, True)))
        buttons[1].grid(row=2, column=syringe_no+1, columnspan=1)

        buttons.append(tkinter.Button(self.button_frame, text='Withdraw', font=self.fonts['default'], padx=5, bg='teal',
                                      fg='white', command=lambda: self.asp_with(syringe_name, syringe_print_name, False)
                                      ))
        buttons[2].grid(row=3, column=syringe_no+1, columnspan=1)

        self.syringe_buttons.append(buttons)

    def populate_valves(self, valve_name):
        """
        Populates the buttons for valve
        :param valve_name: number of valve
        :return:
        """
        ports = []
        valve_no = int(valve_name[-1]) - 1
        valve_print_name = "Valve " + str(valve_no+1)
        self.valves_labels.append(tkinter.Label(self.button_frame, text=valve_print_name, font=self.fonts['default'],
                                                bg='white'))
        self.valves_labels[valve_no].grid(row=4, column=valve_no+1, columnspan=1)

        ports.append(tkinter.Button(self.button_frame, text='Home', font=self.fonts['default'], padx=5, bg='green',
                                    fg='white', command=lambda: self.move_valve(valve_name, 0)))
        ports[0].grid(row=5, column=valve_no+1, columnspan=1)

        for port_no in range(1, 10):
            ports.append(tkinter.Button(self.button_frame, text=str(port_no), font=self.fonts['default'], padx=5,
                                        bg='teal', fg='white',
                                        command=lambda i=port_no: self.move_valve(valve_name, i)))
            ports[port_no].grid(row=6+port_no, column=valve_no+1, columnspan=1)

        # Append list of ports corresponding to valve_no to valves_buttons
        self.valves_buttons.append(ports)

    def v_button_colour(self, command_dict):
        port_no = command_dict["command"]
        valve = int(command_dict["module_name"][-1]) - 1
        for item in self.valves_buttons:
            item[port_no].configure(bg='teal')
        self.valves_buttons[valve][port_no].configure(bg='OrangeRed2')

    def asp_with(self, syringe_name, syringe_print_name, direction):
        """
        Menu to control syringe pumps
        :param syringe_print_name: name to print in messages and logs
        :param syringe_name: syringe to be addressed
        :param direction: boolean, True if aspirating syringe, False if withdrawing syringe
        :return: None
        """

        def asp_command(fb_gui, syr_name):
            command_dict = {'module_type': 'syringe', 'module_name': syr_name, 'command': command,
                            'parameters': {'volume': self.volume_tmp, 'flow_rate': self.flow_rate_tmp}}
            asp_menu.destroy()
            fb_gui.send_command(command_dict)

        if direction:
            button_text = menu_title = "Aspirate"
            command = "aspirate"
        else:
            button_text = menu_title = "Withdraw"
            command = "withdraw"
        asp_menu = tkinter.Toplevel(self.primary)
        asp_menu.title(menu_title + ' ' + syringe_print_name)
        val_vol = self.primary.register(self.validate_vol)
        val_flow = self.primary.register(self.validate_flow)

        vol_label = tkinter.Label(asp_menu, text='Volume to ' + command + ':')
        vol_entry = tkinter.Entry(asp_menu, validate='key', validatecommand=(val_vol, '%P'), fg='black', bg='white',
                                  width=50)

        flow_label = tkinter.Label(asp_menu, text='Flow rate in \u03BCL/min:')
        flow_entry = tkinter.Entry(asp_menu, validate='key', validatecommand=(val_flow, '%P'), fg='black', bg='white',
                                   width=50)

        go_button = tkinter.Button(asp_menu, text=button_text, font=self.fonts['default'], bg='teal', fg='white',
                                   command=lambda: asp_command(self, syringe_name))
        cancel_button = tkinter.Button(asp_menu, text='Cancel', font=self.fonts['default'], bg='tomato2',
                                       fg='white', command=asp_menu.destroy)

        vol_label.grid(row=0, column=1)
        vol_entry.grid(row=0, column=5)
        flow_label.grid(row=2, column=1)
        flow_entry.grid(row=2, column=5)
        go_button.grid(row=5, column=5)
        cancel_button.grid(row=5, column=6)

    def home_syringe(self, syringe_name, syringe_print_name):
        command_dict = {'module_type': 'syringe', 'module_name': syringe_name, 'command': 'home',
                        "parameters": {'volume': 0.0, 'flow_rate': 4500}}

        def home_command(fb_gui):
            home_popup.destroy()
            fb_gui.send_command(command_dict)

        home_popup = tkinter.Toplevel(self.primary)
        home_popup.title('Home ' + syringe_print_name)
        warning_label = tkinter.Label(home_popup, text='Homing the syringe will empty its contents, are you sure?')
        yes_button = tkinter.Button(home_popup, text='Home', font=self.fonts['default'], bg='teal', fg='white',
                                    command=lambda: home_command(self))
        no_button = tkinter.Button(home_popup, text='Cancel', font=self.fonts['default'], bg='tomato2', fg='white',
                                   command= home_popup.destroy)
        warning_label.grid(row=0, column=1, columnspan=5)
        yes_button.grid(row=2, column=1)
        no_button.grid(row=2, column=5)

    def move_valve(self, valve_name, port_no):
        command_dict = {'module_type': 'valve', 'module_name': valve_name, 'command': port_no, 'parameters': {}}
        self.send_command(command_dict)

    def send_command(self, command_dict):
        while not self.manager.write_input_buffer(command_dict):
            self.write_message("Busy")
            time.sleep(0.2)
        message_list = []
        for v in command_dict.values():
            message_list.append(v)
        if message_list[0] == 'valve':
            self.write_message(f'Sent command to move {message_list[1]} to port {message_list[2]}')
        elif message_list[0] == 'syringe':
            if message_list[2] == 'home':
                message = f'Sent command to {message_list[1]} to {message_list[2]}'
            else:
                vol, flow = message_list[3].values()
                message = f'Sent command to {message_list[1]} to {message_list[2]} {vol}ml at {flow} \u03BCL/min'
            self.write_message(message)

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
