import xml.etree.ElementTree as et
import time
import logging
import requests
import socket

# IP address of PI server
DEFAULT_URL = "http://127.0.0.1:5000/robots_api"

class WebListener():
    def __init__(self, robot_manager, robot_id,  robot_key):
        self.manager = robot_manager
        self.id = robot_id
        self.key = robot_key
        self.url = self.manager.prev_run_config['url']
        if self.url == "":
            self.url = DEFAULT_URL
        self.manager.prev_run_config['url'] = self.url
        self.valid_connection = False
        self.polling_time = 20
        self.last_set_status = ""
        self.last_execution_update = 0
        self.last_reaction_update = 0
        self.last_error_update = 0

    def update_url(self, new_url):
        self.url = "http://" + new_url + "/robots_api"
        self.manager.prev_run_config['url'] = self.url
        self.manager.rc_changes = True
        self.test_connection()

    def test_connection(self):
        try:
            ip_address = socket.gethostbyname(socket.gethostname())
            r = requests.get(self.url + "/", json={"robot_id": self.id, 'robot_key': self.key, "cmd": "connect", "ip": ip_address})
            r = r.json()
            if r['conn_status'] == 'accepted':
                self.manager.write_log(f'Connection established to {self.url}', level=logging.INFO)
                self.valid_connection = True
                self.manager.prev_run_config['url'] = self.url
                self.manager.rc_changes = True
            else:
                self.manager.write_log('Connection refused. Please check robot ID and key in configuration files.',  level=logging.WARNING)
        except requests.ConnectionError:
            if self.url != DEFAULT_URL:
                self.url = DEFAULT_URL
                self.test_connection()
            else:
                self.url = ""
                print("Could not connect to server, running offline. Update URL to connect\n")

    def update_status(self, ready, error=False):
        time_elapsed = time.time() - self.last_error_update
        if self.valid_connection:
            if error:
                status = 'ERROR'
            elif ready:
                status = 'IDLE'
            else:
                status = 'BUSY'
            if status != self.last_set_status:
                response = requests.post(self.url + '/status', json={'robot_id': self.id, 'robot_key': self.key, 'cmd': 'robot_state', 'robot_status': status})
                self.last_set_status = status
            elif error and time_elapsed > self.polling_time:
                response = requests.get(self.url + '/status', json={'robot_id': self.id, 'robot_key': self.key, 'cmd': 'error_state'})
                json_args = response.json()
                error_state = int(json_args.get('error_state'))
                self.last_error_update = time.time()
                if not error_state:
                    self.manager.error = False 
                    self.manager.resume()          

    def update_execution(self):
        time_elapsed = time.time() - self.last_execution_update
        if self.valid_connection and time_elapsed > self.polling_time:
            response = requests.get(self.url + "/status", json={'robot_id': self.id, 'robot_key': self.key, 'cmd': 'robot_execute'})
            response = response.json()
            execute = response.get("action")
            self.last_execution_update = time.time()
            return execute
        return None

    def request_reaction(self):
        time_elapsed = time.time() - self.last_reaction_update
        if self.valid_connection and time_elapsed > self.polling_time:
            response = requests.get(self.url + '/reaction', json={'robot_id': self.id, 'robot_key': self.key, 'cmd': 'get_reaction'})
            response = response.json()
            # get the xdl string
            protocol  = response.get('protocol')
            if protocol is not None:
                self.load_xdl(protocol, is_file=False)
                return True
        return False

    def load_xdl(self, xdl, is_file=True):
        if is_file:
            try:
                tree = et.parse(xdl)
                tree = tree.getroot()
            except FileNotFoundError:
                self.manager.write_log(f"{xdl} not found",  level=logging.WARNING)
                return False
        else:
            try:
                tree = et.fromstring(xdl)
            except et.ParseError:
                self.manager.write_log(f"The XDL provided is not formatted correctly", level=logging.ERROR)
        self.parse_xdl(tree)

    def parse_xdl(self, tree):
        reagents = {}
        modules = {}
        req_hardware = tree.find('Hardware')
        req_reagents = tree.find('Reagents')
        procedure = tree.find('Procedure')
        for reagent in req_reagents:
            reagent_name = reagent.get('name')
            flask = self.manager.find_reagent(reagent_name)
            reagents[reagent_name]= flask
        for module in req_hardware:
            module_id = module.get('id')
            modules[module_id] = self.manager.find_target(module_id).name
        for step in procedure:
            if step.tag == "Add":
                vessel = step.get('vessel')
                target = modules[vessel]
                source = reagents[step.get('reagent')]
                reagent_info = step.get('volume')
                if reagent_info is None:
                    reagent_info = step.get('mass')
                    # additional steps for solid reagents
                    continue
                else:
                    reagent_info = reagent_info.split(' ')
                    volume = float(reagent_info[0])
                    unit = reagent_info[1]
                    if unit != 'ml':
                        # assume uL
                        # todo: update this to check a mapping
                        volume = volume/1000
                time = step.get('time')
                if time is not None:
                    # uL/min
                    flow_rate = (volume*1000)/int(time.split(' ')[0]) * 60
                else:
                    flow_rate = 1000
                self.manager.move_liquid(source, target, volume, flow_rate)
            elif step.tag == "Transfer":
                source = step.get('from_vessel')
                target = step.get('to_vessel')
                volume = float(step.get('volume').split(' ')[0])
                time = step.get('time')
                if time is not None:
                    #uL/min
                    flow_rate = volume/int(time.split(' ')[0]) * 60
                else:
                    flow_rate = 1000
                self.manager.move_liquid(source, target, volume, flow_rate)
            elif 'Stir' in step.tag:
                reactor_name = step.get('vessel')
                speed = step.get('stir_speed')
                speed = speed.split(' ')[0]
                stir_secs = step.get('time')
                stir_secs = stir_secs.split(' ')[0]
                # StopStir
                if 'Stop' in step.tag:
                    self.manager.stop_reactor(reactor_name, command='stop_stir')
                # StartStir
                elif 'Start' in step.tag:
                    self.manager.start_stir(reactor_name, command='start_stir', speed=float(speed), stir_secs=0, wait=False)
                # Stir
                else:
                    self.manager.start_stirring(reactor_name, command='start_stir', speed=float(speed), stir_secs=int(stir_secs), wait=True)
            elif "HeatChill" in step.tag:
                reactor_name = step.get('vessel')
                temp = step.get('temp')
                heat_secs = step.get('time')
                # StopHeatChill
                if 'Stop' in step.tag:
                    self.manager.stop_reactor(reactor_name, command='stop_heat')
                # StartHeatChill
                elif 'Start' in step.tag:
                    temp = temp.split(' ')[0]
                    self.manager.start_heating(reactor_name, command='start_heat', temp=float(temp), heat_secs=0, wait=False)
                # HeatChillToTemp
                elif 'To' in step.tag:
                    temp = temp.split(' ')[0]
                    self.manager.start_heating(reactor_name, command='start_heat', temp=float(temp), heat_secs=0, target=True, wait=True)
                # HeatChill
                else:
                    temp = temp.split(' ')[0]
                    self.manager.start_heating(reactor_name, command='start_heat', temp=float(temp), heat_secs=heat_secs, target=True, wait=True)
