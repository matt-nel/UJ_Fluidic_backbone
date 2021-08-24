import xml.etree.ElementTree as et
import time
import logging
import requests

# IP address of PI server
DEFAULT_URL = "http://192.168.43.211/robots_api"


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

    def update_url(self, new_url):
        self.url = "http://" + new_url + "/robot_query"
        self.manager.prev_run_config['url'] = self.url
        self.manager.rc_changes = True
        self.test_connection()

    def test_connection(self):
        try:
            r = requests.get(self.url, params={"robot_id": self.id, 'robot_key': self.key, "cmd": "connect"})
            r = r.json()
            if r['conn_status'] == 'accept':
                self.manager.write_log(f'Connection established to {self.url}', level=logging.INFO)
                self.valid_connection = True
            else:
                self.manager.write_log('Connection refused. Please check robot ID and key in configuration files.',  level=logging.WARNING)
        except requests.ConnectionError:
            self.url = ""
            print("Could not connect to server, running offline. Update URL to connect\n")

    def update_status(self, ready, error=False):
        if self.valid_connection:
            if error:
                status = 'ERROR'
            elif ready:
                status = 'IDLE'
            else:
                status = 'BUSY'
            response = requests.post(self.url + '/status', params={'robot_id': self.id, 'robot_key': self.key, 'cmd': 'robot_status', 'robot_status': status})

    def request_reaction(self):
        if self.valid_connection:
            response = requests.get(self.url + '/reaction', params={'robot_id': self.id, 'robot_key': self.key, 'cmd': 'get_reaction'})
            response = response.json()
            protocol  = response.get('protocol')
            if protocol is not None:
                self.load_xdl(protocol, is_file=False)
                if response['start'] == 1:
                    self.manager.start_queue()

    def load_xdl(self, file, is_file=True):
        if file:
            try:
                with open(file) as queue_file:
                    tree = et.parse(file)
            except FileNotFoundError:
                self.manager.write_log(f"{file} not found",  level=logging.WARNING)
                return False
        else:
            tree = et.parse(file)
        self.parse_xdl(tree)

    def parse_xdl(self, tree):
        reagents = {}
        root = tree.getroot()
        req_hardware = root.findall('Hardware')
        req_reagents = root.findall('Reagents')
        procedure = root.finall('Procedure')
        for reagent in req_reagents:
            flask = self.manager.find_reagent(reagent['name'])
            reagents[reagent['name']] = flask
        for step in procedure:
            if step.tag == "Add":
                target = step['vessel']
                source = reagents[step['reagent']]
                reagent_info = step['volume']
                if reagent_info is None:
                    reagent_info = step['mass']
                    # additional steps for solid reagents
                    continue
                else:
                    reagent_info = reagent_info.split(' ')
                    volume = float(reagent_info[0])
                    unit = reagent_info[1]
                    if unit != 'ml':
                        # assume uL
                        volume = volume/1000
                flow_rate = volume/int(step['time'].split(' ')[0])
                self.manager.move_liquid(source, target, volume, flow_rate)
            elif step.tag == "Transfer":
                source = step['from_vessel']
                target = step['to_vessel']
                volume = float(step['volume'].split(' ')[0])
                flow_rate = volume/int(step['time'].split(' ')[0])
                self.manager.move_liquid(source, target, volume, flow_rate)
            elif 'Stir' in step.tag:
                reactor_name = step['vessel']
                # StopStir
                if 'Stop' in step.tag:
                    self.manager.stop_reactor(reactor_name, command='stop_stir')
                # StartStir
                elif 'Start' in step.tag:
                    self.manager.start_stir(reactor_name, command='start_stir', speed=step['stir_speed'], stir_secs=0, wait=False)
                # Stir
                else:
                    self.manager.start_stir(reactor_name, command='start_stir', speed=step['stir_speed'], stir_secs=step['time'], wait=True)
            elif "HeatChill" in step.tag:
                reactor_name = step['vessel']
                # StopHeatChill
                if 'Stop' in step.tag:
                    self.manager.stop_reactor(reactor_name, command='stop_heat')
                # StartHeatChill
                elif 'Start' in step.tag:
                    self.manager.start_heating(reactor_name, command='start_heat', temp=step['temp'], heat_secs=0, wait=False)
                # HeatChillToTemp
                elif 'To' in step.tag:
                    self.manager.start_heating(reactor_name, command='start_heat', temp=step['temp'], heat_secs=0, target=True, wait=True)
                # HeatChill
                else:
                    self.manager.start_heating(reactor_name, command='start_heat', temp=step['temp'], heat_secs=step['time'], target=True, wait=True)
