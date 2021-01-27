import os
import tkinter
from Manager import Manager


class GUI:
    def __init__(self, primary, simulation, nr_valves, nr_syringes):
        """
        :param primary: root TK window object
        :param simulation: Bool to run the software in simulation mode
        :param nr_valves: number of attached valves
        :param nr_syringes: number of attached syringes
        """
        self.manager = Manager(simulation)
        self.primary = primary
        self.primary.title('Fluidic Backbone Prototype')
        self.primary.configure(background='SteelBlue2')
        self.volume, self.flow_rate = {}, {}
        self.volume_tmp, self.flow_rate_tmp = 0.0, 0.0
        self.fonts = {'default': ('Verdana', 16)}

        icon = tkinter.PhotoImage(file=os.path.join(os.path.dirname(__file__), 'Syringe.png'))
        self.primary.tk.call('wm', 'iconphoto', self.primary._w, icon)

        self.button_frame = tkinter.Frame(self.primary, borderwidth=5)

        self.nr_syringes = nr_syringes
        self.syringe_labels = []
        self.syringe_buttons = []
        # list of syringe buttons, eg: syringe_buttons[0][0] is aspirate button for syringe 1
        # syringe_buttons[0][1] is withdraw button for syringe 1
        for syringe_no in range(0, self.nr_syringes):
            self.populate_syringes(syringe_no)

        self.nr_valves = nr_valves
        self.valves_labels = []
        self.valves_buttons = []
        # valves_buttons[valve_no][port_no]
        # list valves_buttons contains buttons corresponding to each valve port starting from 1, with zero corresponding
        # to homing button. valves_buttons[0][0] is home button of valve 1, valves_buttons[3][2] is port 2 of valve 4
        for valve_no in range(0, self.nr_valves):
            self.populate_valves(valve_no)

        self.log_frame = tkinter.Frame(self.primary)
        self.log = tkinter.Text(self.log_frame, state='disabled', width=80, height=24, wrap='none', borderwidth=5)

        self.log_frame.grid(row=0, column=3, padx=5, pady=10)
        self.button_frame.grid(row=0, column=0, padx=5, pady=10)
        self.log.grid(row=14, column=0)
        self.fonts = {'buttons': ('Verdana', 16), 'labels': ('Verdana', 16), 'default': ('Verdana', 16)}

    def populate_syringes(self, syringe_no):
        """
        Populates the buttons for syringe
        :param syringe_no: number of syringe
        :return:
        """
        buttons = []
        syringe_print_name = "Syringe " + str(syringe_no+1)
        syringe_name = 'syringe' + str(syringe_no+1)
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

    def populate_valves(self, valve_no):
        """
        Populates the buttons for valve
        :param valve_no: number of valve
        :return:
        """
        ports = []
        valve_print_name = "Valve " + str(valve_no+1)
        valve_name = "valve" + str(valve_no + 1)
        self.valves_labels.append(tkinter.Label(self.button_frame, text=valve_print_name, font=self.fonts['default'],
                                                bg='white'))
        self.valves_labels[valve_no].grid(row=4, column=valve_no+1, columnspan=1)

        ports.append(tkinter.Button(self.button_frame, text='Home', font=self.fonts['default'], padx=5, bg='green',
                                    fg='white', command=lambda: self.move_valve(valve_name, valve_print_name, 0)))
        ports[0].grid(row=5, column=valve_no+1, columnspan=1)

        for port_no in range(1, 10):
            ports.append(tkinter.Button(self.button_frame, text=str(port_no), font=self.fonts['default'], padx=5,
                                        bg='teal', fg='white',
                                        command=lambda i=port_no: self.move_valve(valve_name, valve_print_name, i)))
            ports[port_no].grid(row=6+port_no, column=valve_no+1, columnspan=1)

        # Append list of ports corresponding to valve_no to valves_buttons
        self.valves_buttons.append(ports)

    def asp_with(self, syringe_name, syringe_print_name, direction):
        """
        Menu to control syringe pumps
        :param syringe_print_name: name to print in messages and logs
        :param syringe_name: syringe to be addressed
        :param direction: boolean, True if aspirating syringe, False if withdrawing syringe
        :return: None
        """

        def asp_command(gui_obj, syr_name):
            gui_obj.volume[syr_name] = self.volume_tmp
            gui_obj.flow_rate[syr_name] = self.flow_rate_tmp
            command_dict = {'module_type': 'syringe', 'module_name': syr_name, 'print_name': syringe_print_name,
                            'command': command, 'volume': gui_obj.volume[syr_name],
                            'flow_rate': gui_obj.flow_rate[syr_name]}
            asp_menu.destroy()
            self.send_command(command_dict)

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
        command_dict = {'module_type': 'syringe', 'module_name': syringe_name, 'print_name': syringe_print_name,
                        'command': 'home'}
        self.send_command(command_dict)

    def move_valve(self, valve_name, valve_print_name, port_no):
        command_dict = {'module_type': 'valve', 'module_name': valve_name, 'print_name': valve_print_name,
                        'command': port_no}
        self.send_command(command_dict)

    def write_message(self, message):
        numlines = int(self.log.index('end - 1 line').split('.')[0])
        self.log['state'] = 'normal'
        if numlines == 24:
            self.log.delete(1.0, 2.0)
        if self.log.index('end-1c') != '1.0':
            self.log.insert('end', '\n')
        self.log.insert('end', message)
        self.log['state'] = 'disabled'

    def send_command(self, command_dict):
        if command_dict['module_type'] == 'valve':
            if self.manager.command_module(self, command_dict):
                message = command_dict['print_name'] + ' is indexing to position ' + str(command_dict['command'])
            else:
                message = command_dict['print_name'] + ' failed to index to position ' + str(command_dict['command'])
            self.write_message(message)
        elif command_dict['module_type'] == 'syringe':
            message1 = command_dict['command'].capitalize() + ' ' + command_dict['print_name'] + ':'
            self.write_message(message1)
            if command_dict['command'] == 'home':
                if self.manager.command_module(self, command_dict):
                    self.write_message("Homing")
                else:
                    self.write_message("Failed")
            else:
                if self.manager.command_module(self, command_dict):
                    message2 = str(command_dict['volume']) + 'ml at flow rate: ' + str(command_dict['flow_rate']) + '\u03BCL/min'
                    self.write_message(message2)
                else:
                    self.write_message("Failed.")

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
