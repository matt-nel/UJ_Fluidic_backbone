import tkinter
import os
import json


class SetupGUI:
    def __init__(self, primary):
        # todo add check for existing config
        # todo select connections from graph file
        # todo add means to change syringe start position
        self.script_dir = os.path.dirname(__file__)
        self.primary = primary
        self.primary.title("FLuidic backbone setup")
        self.primary.configure(background='DarkOliveGreen1')
        self.fonts = {'buttons': ('Verdana', 12), 'labels': ('Verdana', 16), 'default': ('Verdana', 16), 'headings': ('Verdana', 16), 'text': ('Verdana', 10)}

        self.setup_frame = tkinter.Frame(self.primary, bg='grey', borderwidth=5)
        self.utilities_frame = tkinter.Frame(self.primary, bg='grey', borderwidth=2)
        self.log_frame = tkinter.Frame(self.primary)
        self.log = tkinter.Text(self.log_frame, state='disable', width=80, height=24, wrap='none', borderwidth=5)

        self.setup_label = tkinter.Label(self.primary, text='Fluidic backbone setup:', font=self.fonts['default'],
                                         padx=2, bg='white')
        self.utilities_label = tkinter.Label(self.primary, text='Utilities', font=self.fonts['default'], padx=2,
                                             bg='white')

        self.log_frame.grid(row=4, column=2, padx=5, pady=10)
        self.log.grid(row=0, column=0)
        self.setup_label.grid(row=2, column=2)
        self.utilities_label.grid(row=2, column=10)
        self.setup_frame.grid(row=3, column=2)
        self.utilities_frame.grid(row=3, column=10)

        self.text_temp = ''
        self.int_temp = 0
        self.com_ports = []
        self.devices = {}
        self.modules = {}
        self.module_connections = {}
        self.num_syringes = 0
        self.num_valves = 0
        self.num_he_sens = 0
        self.valves = []
        self.es_options = {'X min': 3, 'X max': 2, 'Y min': 14, 'Y max': 15, 'Z min': 18, 'Z max': 19}
        self.motor_configs = {"default": {"steps_per_rev": 3200, "enabled_acceleration": False, "speed": 1000, "max_speed": 10000, "acceleration": 1000 },
                             "cmd_default": {"enabled_acceleration": False, "speed": 1000, "max_speed": 10000, "acceleration": 1000 }}
        self.motor_options = {'X': {'stepperX': {'cmd_id': 'STPX', 'enable_pin': 'ENX', 'device_config': self.motor_configs['default']}},
                              'Y': {'stepperY': {'cmd_id': 'STPY', 'enable_pin': 'ENY', 'device_config': self.motor_configs['default']}},
                              'Z': {'stepperZ': {'cmd_id': 'STPZ', 'enable_pin': 'ENZ', 'device_config': self.motor_configs['default']}},
                              'E0': {'stepperE0': {'cmd_id': 'STPE0', 'enable_pin': 'ENE0', 'device_config': self.motor_configs['default']}},
                              'E1': {'stepperE1': {'cmd_id': 'STPE1', 'enable_pin': 'ENE1', 'device_config': self.motor_configs['default']}}}
        self.syringe_volumes = [1, 2, 4, 5, 10, 20]
        self.test_connections = {'inlet': 'syringe1', '0': 'no_conn', '1': 'no_conn', '2': 'no_conn',
                                          '3': 'no_conn', '4': 'no_conn', '5': 'no_conn', '6': 'no_conn',
                                          '7': 'no_conn', '8': 'no_conn', '9': 'no_conn'}
        self.pins = {'Analog Read 1 (A3)': 'AR1', 'Analog Read 2 (A4)': 'AR2'}
        self.used_motor_connectors = {}
        self.used_endstop_connectors = {}
        self.used_he_pins = []
        self.simulation = False
        self.exit_flag = False
        self.init_setup_panel()
        self.init_utilities_panel()

    def init_setup_panel(self):
        def add_com_port():
            port = self.text_temp
            self.com_ports.append({"port": port})
            self.write_message(f"Port {port} added")
            com_port_entry.delete(0, 'end')
        heading_font = self.fonts['default']
        button_font = self.fonts['buttons']
        top_label = tkinter.Label(self.setup_frame, text='Setup', font=heading_font, bg='white')
        com_port_label = tkinter.Label(self.setup_frame, text="Enter the communication port or TCP/IP address",
                                       font=heading_font, bg='white')
        val_text = self.primary.register(self.validate_text)
        com_port_entry = tkinter.Entry(self.setup_frame, validate='key', validatecommand=(val_text, '%P'), bg='white', fg='black', width=25)
        com_port_button = tkinter.Button(self.setup_frame, text='Accept', font=button_font, bg='lawn green', fg='black', command=add_com_port)

        modules_label = tkinter.Label(self.setup_frame, text='Add modules to the backbone:', font=heading_font, bg='white')

        syringe_button = tkinter.Button(self.setup_frame, text='Syringe', font=button_font, bg='LemonChiffon2', fg='black',
                                        command=self.setup_syringe)
        valve_button = tkinter.Button(self.setup_frame, text='Valve', font=button_font, bg='LemonChiffon2', fg='black', command=self.setup_valve)
        reactor_button = tkinter.Button(self.setup_frame, text='Reactor', font=button_font, bg='LemonChiffon2', fg='black', command=self.setup_reactor)
        generate_button = tkinter.Button(self.setup_frame, text='Create config', font=button_font, bg='lawn green', fg='black', command=self.generate_config)

        top_label.grid(row=0, column=1)
        com_port_label.grid(row=1, column=1)
        com_port_entry.grid(row=2, column=1)
        com_port_button.grid(row=2, column=2)
        modules_label.grid(row=3, column=1)
        syringe_button.grid(row=4, column=1)
        valve_button.grid(row=5, column=1)
        reactor_button.grid(row=6, column=1)
        generate_button.grid(row=7, column=1)

    def init_utilities_panel(self):
        run_fb_button = tkinter.Button(self.utilities_frame, text='Run Fluidic Backbone', font=self.fonts['buttons'], bg='DeepSkyBlue', fg='black', command=self.run_fb_menu)
        run_fb_button.grid(row=1, column=0)

    def setup_syringe(self):
        def accept():
            motor = motor_connector.get()
            endstop = endstop_connector.get()
            cur_volume = syringe_volume.get()*1000
            select_new = False
            if motor and endstop:
                if motor in self.used_motor_connectors.keys():
                    select_new = True
                    self.write_message(f"That motor connector is already used by {self.used_motor_connectors[motor]}")
                if endstop in self.used_endstop_connectors.keys():
                    select_new = True
                    self.write_message(f'That endstop connector is already used by {self.used_endstop_connectors[endstop]}')
                if not select_new:
                    self.num_syringes += 1
                    syringe_name = f'syringe{self.num_syringes}'
                    stepper_name = f'stepper{motor}'
                    self.used_motor_connectors[motor] = syringe_name
                    self.used_endstop_connectors[endstop] = syringe_name
                    mod_config = {'volume': cur_volume, 'screw_pitch': 8, 'linear_stepper': True}
                    self.setup_motor(syringe_name, stepper_name, motor, mod_config)
                    syringe_setup.destroy()
            else:
                if not motor:
                    self.write_message('Please select a motor connector')
                if not endstop:
                    self.write_message('Please select an endstop connector')

        syringe_setup = tkinter.Toplevel(self.primary)
        syringe_setup.title('Syringe setup')
        font = self.fonts['default']
        motor_connector = tkinter.StringVar()
        endstop_connector = tkinter.StringVar()
        syringe_volume = tkinter.IntVar()
        motor_connection_label = tkinter.Label(syringe_setup, text='Which motor connector is used for this syringe', font=font)
        motor_connection_label.grid(row=0, column=0)
        i = 1
        options = self.motor_options.keys()
        selected = self.used_motor_connectors.keys()
        for motor in options:
            tkinter.Radiobutton(syringe_setup, text=motor, variable=motor_connector, value=motor).grid(row=i, column=0)
            i += 1
        motor_connector.set(self.find_unselected(options, selected))
        endstop_label = tkinter.Label(syringe_setup, text='Which endstop connection is used for this syringe?', font=font)
        endstop_label.grid(row=7, column=0)
        i = 8
        options = self.es_options.keys()
        selected = self.used_endstop_connectors.keys()
        for option in options:
            tkinter.Radiobutton(syringe_setup, text=option, variable=endstop_connector, value=option).grid(row=i, column=0)
            i += 1
        endstop_connector.set(self.find_unselected(options, selected))
        volume_label = tkinter.Label(syringe_setup, text='What volume of syringe is currently used? (select 0 for empty)', font=font)
        volume_label.grid(row=i, column=0)
        i += 1
        for volume in self.syringe_volumes:
            tkinter.Radiobutton(syringe_setup, text=str(volume), variable=syringe_volume, value=volume).grid(row=i, column=0)
            i += 1
        syringe_volume.set('5')
        accept_button = tkinter.Button(syringe_setup, text='Accept', fg='black', bg='lawn green', command=accept)
        cancel_button = tkinter.Button(syringe_setup, text='Cancel', fg='black', bg='tomato2', command=syringe_setup.destroy)
        accept_button.grid(row=i, column=0)
        cancel_button.grid(row=i, column=1)

    def setup_valve(self):
        def accept():
            motor = motor_connector.get()
            try:
                pin = hall_connector.get()
                hall_sensor = self.pins[pin]
            except KeyError:
                self.write_message('Please select a pin for the hall-effect sensor')
            else:
                if motor:
                    if motor in self.used_motor_connectors.keys():
                        self.write_message(f"That motor connector is already used by {self.used_motor_connectors[motor]}")
                    else:
                        self.num_valves += 1
                        self.num_he_sens += 1
                        valve_name = f'valve{self.num_valves}'
                        stepper_name = f'stepper{motor}'
                        he_sens_name = f'he_sens{self.num_he_sens}'
                        self.used_motor_connectors[motor] = valve_name
                        self.used_he_pins.append(pin)
                        mod_config = {'ports': 10, "linear_stepper": False}
                        self.setup_motor(valve_name, stepper_name, motor, mod_config)
                        self.modules[valve_name]['devices']['he_sens'] = {'name': he_sens_name, 'cmd_id': hall_sensor, 'device_config': {}}
                        self.devices[hall_sensor] = {'command_id': hall_sensor}
                        self.valves.append(valve_name)
                        valve_setup.destroy()

        valve_setup = tkinter.Toplevel(self.primary)
        valve_setup.title('Valve setup')
        font = self.fonts['default']
        motor_connector = tkinter.StringVar()
        hall_connector = tkinter.StringVar()
        motor_text = 'Which motor connector is used for this valve?'
        motor_connection_label = tkinter.Label(valve_setup, text=motor_text, font=font)
        i = 1
        options = self.motor_options.keys()
        selected = self.used_motor_connectors.keys()
        for motor in options:
            tkinter.Radiobutton(valve_setup, text=motor, variable=motor_connector, value=motor).grid(row=i, column=0)
            i += 1
        motor_connector.set(self.find_unselected(options, selected))
        hall_sensor_label = tkinter.Label(valve_setup, text='Which pin is the hall sensor plugged into?', font=font)
        hall_options = list(self.pins.keys())
        pin_to_remove = None
        for j in range(0, len(hall_options)):
            if hall_options[j] in self.used_he_pins:
                pin_to_remove = j
        if pin_to_remove is not None:
            hall_options.pop(pin_to_remove)
        hall_sensor_selector = tkinter.OptionMenu(valve_setup, hall_connector, *hall_options)
        accept_button = tkinter.Button(valve_setup, text='Accept', fg='black', bg='lawn green',
                                       command=accept)
        cancel_button = tkinter.Button(valve_setup, text='Cancel', fg='black', bg='tomato2',
                                       command=valve_setup.destroy)
        motor_connection_label.grid(row=0, column=0)
        hall_sensor_label.grid(row=7, column=0)
        hall_sensor_selector.grid(row=8, column=0)
        accept_button.grid(row=16, column=0)
        cancel_button.grid(row=16, column=1)

    def setup_motor(self, name, stepper_name, motor, mod_config):
        motor_config = self.motor_options[motor][stepper_name]
        motor_config['name'] = stepper_name
        mod_info_device = {'stepper': motor_config}
        self.modules[name] = {'mod_config': mod_config, 'devices': mod_info_device}
        self.devices[stepper_name] = {'command_id': motor_config['cmd_id'], 'config': self.motor_configs['default']}
        enable_pin = motor_config['enable_pin']
        self.devices[enable_pin] = {'command_id': enable_pin}

    def setup_reactor(self):
        pass

    def validate_text(self, new_text):
        if not new_text:
            self.text_temp = ''
            return True
        try:
            self.text_temp = str(new_text)
            return True
        except ValueError:
            return False

    def validate_int(self, new_int):
        if not new_int:
            self.int_temp = 0
            return True
        try:
            self.int_temp = int(new_int)
            return True
        except ValueError:
            return False

    @staticmethod
    def find_unselected(possible_options, selected_options):
        options = list(possible_options)
        selected = list(selected_options)
        for option in options:
            if option not in selected:
                return option

    def run_fb_menu(self):
        run_popup = tkinter.Toplevel(self.primary)
        run_popup.title('Run Fluidic Backbone')
        warning_label = tkinter.Label(run_popup, text='Have you finished configuring the system? Selecting yes will use configuration stored in configs folder.', font=self.fonts['text'])
        yes_button = tkinter.Button(run_popup, text='Yes', font=self.fonts['buttons'], bg='teal', fg='white',
                                    command=self.start_fb)
        no_button = tkinter.Button(run_popup, text='Cancel', font=self.fonts['buttons'], bg='tomato2', fg='white',
                                   command=run_popup.destroy)
        warning_label.grid(row=0, column=0)
        yes_button.grid(row=1, column=1)
        no_button.grid(row=1, column=2)

    def generate_config(self):
        encoder = json.JSONEncoder()
        configs_dir = os.path.join(self.script_dir, 'Configs')
        config_filenames = ['cmd_config.json', 'module_connections.json', 'module_info.json']
        config_files = []
        for filename in config_filenames:
            filename = os.path.join(configs_dir, filename)
            config_files.append(open(filename, 'w'))
        cmd_config_dict = {"ios": self.com_ports, "devices": self.devices}
        cmd_config = encoder.encode(cmd_config_dict)
        config_files[0].write(cmd_config)
        for valve in self.valves:
            self.module_connections[valve] = self.test_connections
        module_connections = encoder.encode(self.module_connections)
        config_files[1].write(module_connections)
        module_config = encoder.encode(self.modules)
        config_files[2].write(module_config)
        for file in config_files:
            file.close()
        self.write_message("Config files written")

    def generate_graph(self):
        pass

    def write_message(self, message):
        numlines = int(self.log.index('end - 1 line').split('.')[0])
        self.log['state'] = 'normal'
        if numlines == 24:
            self.log.delete(1.0, 2.0)
        if self.log.index('end-1c') != '1.0':
            self.log.insert('end', '\n')
        self.log.insert('end', message)
        self.log['state'] = 'disabled'

    def start_fb(self):
        self.primary.destroy()
        os.system('python Fluidic_backbone_GUI.py')


if __name__ == '__main__':
    primary = tkinter.Tk()
    program = SetupGUI(primary)
    primary.mainloop()
