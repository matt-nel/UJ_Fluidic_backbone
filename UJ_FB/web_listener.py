import xml.etree.ElementTree as et
from threading import Thread, Lock
import time
import requests

# IP address of PI server
DEFAULT_URL = "http://192.168.43.211/robot_query"


class WebListener(Thread):
    def __init__(self, robot_manager):
        Thread.__init__(self)
        self.manager = robot_manager
        self.url = self.manager.prev_run_config['url']
        if self.url == "":
            self.url = DEFAULT_URL
        self.lock = Lock()
        self.manager.prev_run_config['url'] = self.url
        self.valid_connection = False
        self.response_buffer = []

    def update_url(self, new_url):
        with self.lock:
            self.url = "http://" + new_url + "/robot_query"
        self.manager.prev_run_config['url'] = self.url
        self.manager.rc_changes = True
        self.test_connection()

    def check_connection(self):
        r = requests.get(self.url, params={"id": self.manager.id})
        response_dict = r.json()
        print(F"Received {r.status_code}")
        if r.status_code == "200":
            if response_dict['robot_found']:
                print(F"Robot {self.manager.id} recognised.")
                return True
        return False

    def test_connection(self):
        try:
            r = requests.get(self.url, params={"id": self.manager.id, "cmd": "qstart"})
            self.response_buffer.append(r)
            self.valid_connection = True
        except requests.ConnectionError:
            self.url = ""
            print("Could not connect to server, running offline. Update URL to connect\n")

    def load_xdl(self, file):
        try:
            with open(file) as queue_file:
                tree = et.parse(file)
        except FileNotFoundError:
            self.manager.gui_main.write_message(f"{file} not found")
            return False
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
                volume = float(step['volume'].split(' ')[0])
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
                #StartStir
                if 'Start' in step.tag:
                    self.manager.start_stir(reactor_name, command='start_stir', speed=step['stir_speed'], stir_secs=0, wait=False)
                #StopStir
                elif 'Stop' in step.tag:
                    self.manager.stop_reactor(reactor_name, command='stop_stir')
                #Stir
                else:
                    self.manager.start_stir(reactor_name, command='start_stir', speed=step['stir_speed'], stir_secs=step['time'], wait=True)
            elif "HeatChill" in step.tag:
                reactor_name = step['vessel']
                #StartHeatChill
                if 'Start' in step.tag:
                    self.manager.start_heating(reactor_name, command='start_heat', temp=step['temp'], heat_secs=0, wait=False)
                #StopHeatChill
                elif 'Stop' in step.tag:
                    self.manager.stop_reactor(reactor_name, command='stop_heat')
                #HeatChillToTemp
                elif 'To' in step.tag:
                    self.manager.start_heating(reactor_name, command='start_heat', temp=step['temp'], heat_secs=0, target=True, wait=True)
                #HeatChill
                else:
                    self.manager.start_heating(reactor_name, command='start_heat', temp=step['temp'], heat_secs=step['time'], target=True, wait=True)

    def run(self):
        while True:
            if self.valid_connection:
                with self.lock:
                    try:
                        if self.url != "":
                            r = requests.get(self.url, params={"id": self.manager.id, "cmd": "qstart"})
                            response = r.json()
                            start = response["Start"]
                            if start:
                                self.manager.start_queue()
                        elif self.response_buffer:
                            response = self.response_buffer[0].json()
                            # todo run functions etc?
                    except requests.ConnectionError:
                        print("Could not connect to server, running offline. Update URL to attempt to connect\n")
                        self.valid_connection = False
            time.sleep(10)
