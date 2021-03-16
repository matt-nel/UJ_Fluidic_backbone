import os
import tkinter as tk
from Manager import Manager


class FluidicBackboneUI:
    def __init__(self, tk_root, simulation):
        """
        :param tk_root: root TK window object
        :param simulation: Bool to run the software in simulation mode
        """
        self.manager = Manager(self, simulation)
        self.primary = tk_root
        self.primary.title('Fluidic Backbone Prototype')
        self.primary.configure(background='SteelBlue2')
        self.volume_tmp, self.flow_rate_tmp = 0.0, 0.0
        self.direct_flag = True
        self.fonts = {'buttons': ('Verdana', 16), 'labels': ('Verdana', 16), 'default': ('Verdana', 16)}

        icon = tk.PhotoImage(file=os.path.join(os.path.dirname(__file__), 'Syringe.png'))
        self.primary.iconphoto(True, icon)

        self.button_frame = tk.Frame(self.primary, borderwidth=5)

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

        self.log_frame = tk.Frame(self.primary)
        self.log = tk.Text(self.log_frame, state='disabled', width=80, height=24, wrap='none', borderwidth=5)

        self.log_frame.grid(row=0, column=3, padx=5, pady=10)
        self.button_frame.grid(row=0, column=0, padx=5, pady=10)
        self.log.grid(row=14, column=0)
        self.manager.start()

    def populate_syringes(self, syringe_name):
        """
        Populates the buttons for syringe
        :param syringe_name: name of syringe from config file
        :return:
        """
        syringe_no = int(syringe_name[-1]) - 1
        syringe_print_name = "Syringe " + str(syringe_no + 1)
        self.syringe_labels.append(tk.Label(self.button_frame, text=syringe_print_name, font=self.fonts['default'],
                                                 bg='white'))
        self.syringe_labels[syringe_no].grid(row=0, column=syringe_no+1)

        home_button = tk.Button(self.button_frame, text='Home Syringe', font=self.fonts['default'], padx=5, bg='teal', fg='white', command=lambda: self.home_syringe(syringe_name, syringe_print_name))
        jog_button = tk.Button(self.button_frame, text='Jog', font=self.fonts['default'], padx=5, bg='teal', fg='white', command=lambda: self.jog_syringe(syringe_name, syringe_print_name))

        home_button.grid(row=1, column=syringe_no+1)
        jog_button.grid(row=2, column=syringe_no + 1)

        asp_button = tk.Button(self.button_frame, text='Aspirate', font=self.fonts['default'], padx=5, bg='teal', fg='white', command=lambda: self.asp_with(syringe_name, syringe_print_name, False))
        asp_button.grid(row=3, column=syringe_no+1, columnspan=1)

        with_button = tk.Button(self.button_frame, text='Withdraw', font=self.fonts['default'], padx=5, bg='teal', fg='white', command=lambda: self.asp_with(syringe_name, syringe_print_name, True))
        with_button.grid(row=4, column=syringe_no+1)

    def populate_valves(self, valve_name):
        """
        Populates the buttons for valve
        :param valve_name: number of valve
        :return:
        """
        ports = []
        valve_no = int(valve_name[-1]) - 1
        valve_print_name = "Valve " + str(valve_no+1)
        self.valves_labels.append(tk.Label(self.button_frame, text=valve_print_name, font=self.fonts['default'],
                                                bg='white'))
        self.valves_labels[valve_no].grid(row=5, column=valve_no+1, columnspan=1)

        ports.append(tk.Button(self.button_frame, text='Home', font=self.fonts['default'], padx=5, bg='green', fg='white', command=lambda: self.move_valve(valve_name, 'home')))
        ports[0].grid(row=7, column=valve_no+1)
        self.valves_buttons.append(tk.Button(self.button_frame, text='Jog', font=self.fonts['default'], padx=5, bg='green', fg='white', command=lambda: self.jog_valve(valve_name, valve_print_name)))
        self.valves_buttons[-1].grid(row=6, column=valve_no+1)

        for port_no in range(1, 11):
            ports.append(tk.Button(self.button_frame, text=str(port_no), font=self.fonts['default'], padx=5, bg='teal', fg='white', command=lambda i=port_no: self.move_valve(valve_name, i)))
            ports[port_no].grid(row=8+port_no, column=valve_no+1, columnspan=1)

        # Append list of ports corresponding to valve_no to valves_buttons
        self.valves_buttons.append(ports)

    def v_button_colour(self, command_dict):
        port_no = command_dict["command"]
        valve = int(command_dict["module_name"][-1]) - 1
        for item in self.valves_buttons:
            item[port_no].configure(bg='teal')
        self.valves_buttons[valve][port_no].configure(bg='OrangeRed2')

    def asp_with(self, syringe_name, syringe_print_name, withdraw):
        """
        Menu to control syringe pumps
        :param syringe_print_name: name to print in messages and logs
        :param syringe_name: syringe to be addressed
        :param withdraw: boolean, True if aspirating syringe, False if withdrawing syringe
        :return: None
        """

        def asp_command(syr_name, direction):
            command_dict = {'mod_type': 'syringe', 'module_name': syr_name, 'command': 'move',
                            'parameters': {'volume': self.volume_tmp*1000, 'flow_rate': self.flow_rate_tmp, 'withdraw': direction, 'wait': False, 'target': None}}
            asp_menu.destroy()
            self.send_command(command_dict)

        if withdraw:
            button_text = menu_title = "Withdraw"
            wd = True
        else:
            button_text = menu_title = "Aspirate"
            wd = False

        asp_menu = tk.Toplevel(self.primary)
        asp_menu.title(menu_title + ' ' + syringe_print_name)
        val_vol = self.primary.register(self.validate_vol)
        val_flow = self.primary.register(self.validate_flow)

        vol_label = tk.Label(asp_menu, text='Volume to ' + button_text.lower() + 'in ml:')
        vol_entry = tk.Entry(asp_menu, validate='key', validatecommand=(val_vol, '%P'), fg='black', bg='white', width=50)

        flow_label = tk.Label(asp_menu, text='Flow rate in \u03BCL/min:')
        flow_entry = tk.Entry(asp_menu, validate='key', validatecommand=(val_flow, '%P'), fg='black', bg='white', width=50)

        go_button = tk.Button(asp_menu, text=button_text, font=self.fonts['default'], bg='teal', fg='white', command=lambda: asp_command(syringe_name, wd))
        cancel_button = tk.Button(asp_menu, text='Cancel', font=self.fonts['default'], bg='tomato2', fg='white', command=asp_menu.destroy)

        vol_label.grid(row=0, column=1)
        vol_entry.grid(row=0, column=5)
        flow_label.grid(row=2, column=1)
        flow_entry.grid(row=2, column=5)
        go_button.grid(row=5, column=5)
        cancel_button.grid(row=5, column=6)

    def home_syringe(self, syringe_name, syringe_print_name):
        command_dict = {'mod_type': 'syringe', 'module_name': syringe_name, 'command': 'home',
                        "parameters": {'volume': 0.0, 'flow_rate': 9999, 'wait': False}}

        def home_command(fb_gui):
            home_popup.destroy()
            fb_gui.send_command(command_dict)

        home_popup = tk.Toplevel(self.primary)
        home_popup.title('Home ' + syringe_print_name)
        warning_label = tk.Label(home_popup, text='Homing the syringe will empty its contents, are you sure?')
        yes_button = tk.Button(home_popup, text='Home', font=self.fonts['default'], bg='teal', fg='white', command=lambda: home_command(self))
        no_button = tk.Button(home_popup, text='Cancel', font=self.fonts['default'], bg='tomato2', fg='white', command=home_popup.destroy)
        warning_label.grid(row=0, column=1, columnspan=5)
        yes_button.grid(row=2, column=1)
        no_button.grid(row=2, column=5)

    def jog_syringe(self, syringe_name, syringe_print_name):
        command_dict = {'mod_type': 'syringe', 'module_name': syringe_name, 'command': 'jog',
                        "parameters": {'volume': 0.0, 'flow_rate': 9999, 'steps': 0, 'withdraw': False, 'wait': False}}
        # todo: add jog speed setting

        def change_steps(steps):
            command_dict['parameters']['steps'] = steps

        def setpos():
            new_pos = set_pos.get()
            zero_dict = {'mod_type': 'syringe', 'module_name': syringe_name, 'command': 'setpos',
                         "parameters": {'volume': 0.0, 'flow_rate': 9999, 'pos': new_pos, 'wait': False}}
            self.send_command(zero_dict)

        def change_direction(withdraw):
            if withdraw:
                command_dict["parameters"]['withdraw'] = True
            else:
                command_dict["parameters"]['withdraw'] = False

        jog_popup = tk.Toplevel(self.primary)
        jog_popup.title('Jog' + syringe_print_name)
        fh_button = tk.Button(jog_popup, text='500 Steps', font=self.fonts['default'], bg='teal', fg='white', command=lambda: change_steps(500))
        single_rev_button = tk.Button(jog_popup, text='3200 Steps', font=self.fonts['default'], bg='teal', fg='white', command=lambda: change_steps(3200))
        db_rev_button = tk.Button(jog_popup, text='6400 Steps', font=self.fonts['default'], bg='teal', fg='white', command=lambda: change_steps(6400))
        set_pos_label = tk.Label(jog_popup, text='Set syringe position in ml')
        set_pos = tk.Entry(jog_popup)
        set_pos_butt = tk.Button(jog_popup, text='set current position', command=setpos)
        fwd_button = tk.Button(jog_popup, text='Direction: Aspirate', font=self.fonts['default'], bg='teal', fg='white', command=lambda: change_direction(False))
        rev_button = tk.Button(jog_popup, text='Direction: Withdraw', font=self.fonts['default'], bg='teal', fg='white', command=lambda: change_direction(True))
        jog_button = tk.Button(jog_popup, text='Go', font=self.fonts['default'], bg='teal', fg='white', command=lambda: self.send_command(command_dict))
        close_button = tk.Button(jog_popup, text='Close', font=self.fonts['default'], bg='tomato2', fg='white', command=jog_popup.destroy)

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
        command_dict = {'mod_type': 'valve', 'module_name': valve_name, 'command': port_no, 'parameters': {'wait': False}}
        self.send_command(command_dict)

    def jog_valve(self, valve_name, valve_print_name):
        def check_direction():
            if self.direct_flag:
                dir_str = 'cw'
            else:
                dir_str = 'cc'
            return dir_str

        def change_direction(direction):
            if direction:
                self.direct_flag = True
            else:
                self.direct_flag = False

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
                                "parameters": {'steps': nr_steps, 'direction': check_direction(), 'wait': False}}
            else:
                nr_steps = steps
                command_dict = {'mod_type': 'valve', 'module_name': valve_name, 'command': 'jog',
                                "parameters": {'steps': nr_steps, 'direction': check_direction(), 'wait': False}}
            self.send_command(command_dict)

        b_font = self.fonts['default']
        jog_popup = tk.Toplevel(self.primary)
        jog_popup.title('Jog ' + valve_print_name)
        steps_label = tk.Label(jog_popup, text='Steps to move:')
        steps_entry = tk.Entry(jog_popup)
        cust_move_butt = tk.Button(jog_popup, text='Custom move', font=b_font, bg='teal', fg='white', command= lambda: move(True, 0))
        p_butt = tk.Button(jog_popup, text='1 port', font=b_font, bg='teal', fg='white', command=lambda: move(False, 640))
        cw_butt = tk.Button(jog_popup, text='Direction: CW', font=b_font, bg='teal', fg='white', command=lambda: change_direction(True))
        cc_butt = tk.Button(jog_popup, text='Direction: CC', font=b_font, bg='teal', fg='white', command=lambda: change_direction(False))
        zero_butt = tk.Button(jog_popup, text='Set pos 0', font=b_font, bg='teal', fg='white',
                                   command=zero_command)
        he_butt = tk.Button(jog_popup, text='Read HE sensor', font=b_font, bg='teal', fg='white', command= read_sens)
        close_button = tk.Button(jog_popup, text='Close', font=b_font, bg='tomato2', fg='white', command=jog_popup.destroy)

        steps_label.grid(row=0)
        steps_entry.grid(row=1)
        cust_move_butt.grid(row=1, column=1)
        p_butt.grid(row=2)
        cw_butt.grid(row=3, column=0)
        cc_butt.grid(row=3, column=1)
        zero_butt.grid(row=4)
        he_butt.grid(row=5)
        close_button.grid(row=6, column=1)

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
            if command == 'home' or command == 'jog':
                message = f'Sent command to {name} to {command}'
            elif command == 'move':
                vol, flow = command_dict['parameters']['volume'], command_dict['parameters']['flow_rate']
                if params['withdraw']:
                    message = f'Sent command to {name} to withdraw {vol/1000}ml at {flow} \u03BCL/min'
                else:
                    message = f'Sent command to {name} to aspirate {vol/1000}ml at {flow} \u03BCL/min'
            elif command == 'setpos':
                message = f"Sent command to {name} to set position to {params['pos']}"
            else:
                message = f'Unrecognised command: {command}'
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

    def send_interrupt(self, parameters):
        command_dict = {'mod_type': 'manager', 'module_name': self.manager.name, 'command': 'interrupt',
                        'parameters': parameters}
        self.send_command(command_dict)

    def end_program(self):
        parameters = {'exit': True}
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
    primary = tk.Tk()
    fb_gui = FluidicBackboneUI(primary, sim)
    primary.protocol('WM_DELETE_WINDOW', fb_gui.end_program)
    primary.mainloop()