import xml.etree.ElementTree as et
from threading import Lock
import time
import logging
import requests
import socket
import json

# IP address of PI server
DEFAULT_URL = "http://127.0.0.1:5000/robots_api"
DEFAULT_FLOW = 5000


class WebListener:
    def __init__(self, robot_manager, robot_id,  robot_key):
        self.manager = robot_manager
        self.id = robot_id
        self.key = robot_key
        self.url_lock = Lock()
        self.url = self.manager.prev_run_config['url']
        if "http" in self.url:
            self.ip = self.url.split("/")[2]
        if self.url == "":
            self.url = DEFAULT_URL
        self.manager.prev_run_config['url'] = self.url
        self.valid_connection = False
        self.polling_time = 20
        self.last_set_status = ""
        self.last_execution_update = 0
        self.last_reaction_update = 0
        self.last_error_update = 0

    def update_url(self, ip):
        self.ip = ip
        self.url = "http://" + ip + "/robots_api"
        self.test_connection()

    def test_connection(self):
        with self.url_lock:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect((self.ip, 80))
                ip_address = s.getsockname()[0]
                r = requests.get(self.url + "/", json={"robot_id": self.id, 'robot_key': self.key, "cmd": "connect", "ip": ip_address})
                r = r.json()
                self.manager.prev_run_config['url'] = self.url
                self.manager.rc_changes = True
                if r['conn_status'] == 'accepted':
                    self.manager.write_log(f'Connection established to {self.url}', level=logging.INFO)
                    self.valid_connection = True
                else:
                    self.manager.write_log('Connection refused. Please check robot ID and key in configuration files.',  level=logging.WARNING)
            except (requests.ConnectionError, json.decoder.JSONDecodeError, socket.gaierror) as e:
                if self.url != DEFAULT_URL:
                    self.url = DEFAULT_URL
                    self.test_connection()
                else:
                    self.valid_connection = False
                    self.manager.write_log("Could not connect to server, running offline. ", level=logging.WARNING)

    def update_status(self, ready, error=False, reaction_complete=False):
        time_elapsed = time.time() - self.last_error_update
        with self.url_lock:
            if self.valid_connection:
                if error:
                    status = 'ERROR'
                elif ready:
                    status = 'IDLE'
                else:
                    status = 'BUSY'
                if status != self.last_set_status or reaction_complete:
                    json_data = {'robot_id': self.id, 'robot_key': self.key, 'cmd': 'robot_status', 'robot_status': status}
                    if reaction_complete:
                        json_data.update({'reaction_complete': True, 'reaction_id': self.manager.reaction_id})
                    response = requests.post(self.url + '/status', json=json_data)
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
        with self.url_lock:
            if self.valid_connection and time_elapsed > self.polling_time:
                try:
                    response = requests.get(self.url + "/status", json={'robot_id': self.id, 'robot_key': self.key, 'cmd': 'robot_execute'})
                    response = response.json()
                    execute = response.get("action")
                    self.last_execution_update = time.time()
                    return execute
                except (requests.ConnectionError, json.JSONDecodeError) as e:
                    self.valid_connection = False
                    return None
            return None

    def send_image(self, image_metadata, img_data, task, num_retries):
        if not self.valid_connection:
            self.test_connection()
        with self.url_lock:
            try:
                r = requests.post(self.url + '/send_image', json=image_metadata)
                if r.ok:
                    request_id = r.json().get('request_id')
            except requests.ConnectionError:
                self.manager.write_log(f"A connection to {self.url} could not be established, trying again.", level=logging.WARNING)
                num_retries += 1
                self.valid_connection = False
                time.sleep(20)
                return False, num_retries
            else:
                r = requests.post(self.url + '/send_image', data=img_data.tobytes(), params={'request_id': request_id})
                if not r.ok:
                    num_retries += 1
                return r, num_retries

    def request_reaction(self):
        time_elapsed = time.time() - self.last_reaction_update
        with self.url_lock:
            if self.valid_connection and time_elapsed > self.polling_time:
                try:
                    response = requests.get(self.url + '/reaction', json={'robot_id': self.id, 'robot_key': self.key, 'cmd': 'get_reaction'})
                    response = response.json()
                    # get the xdl string
                    protocol = response.get('protocol')
                    if protocol is not None:
                        self.manager.write_log(f"Received reaction {response.get('name')}", level=logging.INFO)
                        self.manager.reaction_name = response.get("name")
                        self.manager.reaction_id = response.get("reaction_id")
                        clean_step = response.get("clean_step")
                        self.load_xdl(protocol, is_file=False, clean_step=clean_step)
                        return True
                except requests.exceptions.ConnectionError as e:
                    self.manager.write_log(f"Connection failed, {e}", level=logging.INFO)
            return False

    def load_xdl(self, xdl, is_file=True, clean_step=False):
        if is_file:
            try:
                tree = et.parse(xdl)
                tree = tree.getroot()
            except (FileNotFoundError, et.ParseError):
                self.manager.write_log(f"{xdl} not found",  level=logging.WARNING)
                return False
        else:
            try:
                tree = et.fromstring(xdl)
            except et.ParseError as e:
                self.manager.write_log(f"The XDL provided is not formatted correctly, {str(e)}", level=logging.ERROR)
                return False
        self.parse_xdl(tree, clean_step=clean_step)

    def parse_xdl(self, tree, clean_step=False):
        reagents = {}
        modules = {}
        if tree.find('Synthesis'):
            tree = tree.find('Synthesis')
        metadata = tree.find("Metadata")
        reaction_name = metadata.get('name')
        req_hardware = tree.find('Hardware')
        req_reagents = tree.find('Reagents')
        procedure = tree.find('Procedure')
        for reagent in req_reagents:
            reagent_name = reagent.get('id')
            flask = self.manager.find_reagent(reagent_name)
            reagents[reagent_name] = flask
        for module in req_hardware:
            module_id = module.get('id')
            modules[module_id] = self.manager.find_target(module_id).name
        parse_success = True
        for step in procedure:
            if step.tag == "Add":
                if not self.process_xdl_add(modules, reagents, step):
                    parse_success = False
            elif step.tag == "Transfer":
                if not self.process_xdl_transfer(step):
                    parse_success = False
            elif 'Stir' in step.tag:
                if not self.process_xdl_stir(step):
                    parse_success = False
            elif "HeatChill" in step.tag:
                if not self.process_xdl_heatchill(step):
                    parse_success = False
            elif "Wait" in step.tag:
                if not self.process_xdl_wait(step, metadata):
                    parse_success = False
        if clean_step:
            self.manager.wait(0, {'wait_user': True, "wait_reason": "cleaning"})
        if not parse_success:
            self.manager.pipeline.queue.clear()
        else:
            with self.manager.interrupt_lock:
                self.manager.reaction_ready = True
                if not self.manager.reaction_name:
                    self.manager.reaction_name = reaction_name

    def process_xdl_add(self, modules, reagents, add_info):
        vessel = add_info.get('vessel')
        target = self.manager.find_target(vessel.lower())
        if target is None:
            return False
        target = target.name
        source = reagents[add_info.get('reagent')]
        reagent_info = add_info.get('volume')
        if reagent_info is None:
            reagent_info = add_info.get('mass')
            # additional steps for solid reagents
            return
        else:
            reagent_info = reagent_info.split(' ')
            volume = float(reagent_info[0])
            if volume == 0:
                return True
            unit = reagent_info[1]
            if unit != 'ml':
                # assume uL
                # todo: update this to check a mapping
                volume = volume/1000
        a_time = add_info.get('time')
        if a_time is not None:
            # flow should be in uL/min
            a_time = a_time.split(' ')
            if a_time[1] == 's':
                flow_rate = (volume*1000)/(float(a_time[0])/60)
            else:
                flow_rate = (volume*1000)/float(a_time[0])
        else:
            flow_rate = DEFAULT_FLOW
        self.manager.move_fluid(source, target, volume, flow_rate)
        return True
    
    def process_xdl_transfer(self, transfer_info):
        source = transfer_info.get('from_vessel')
        target = transfer_info.get('to_vessel')
        source = self.manager.find_target(source).name
        target = self.manager.find_target(target).name
        if target is None or source is None:
            return False
        reagent_info = transfer_info.get('volume')
        if reagent_info is None:
            reagent_info = transfer_info.get('mass')
            return
        else:
            reagent_info = reagent_info.split(' ')
            volume = float(reagent_info[0])
            if volume == 0:
                return True
            unit = reagent_info[1]
            if unit != 'ml':
                volume = volume/1000
        t_time = transfer_info.get('time')
        if t_time is not None:
            # uL/min
            t_time = t_time.split(' ')
            if t_time[1] == 's':
                flow_rate = (volume * 1000) / (float(t_time[0]) / 60)
            else:
                flow_rate = (volume * 1000) / float(t_time[0])
        else:
            flow_rate = DEFAULT_FLOW
        self.manager.move_fluid(source, target, volume, flow_rate, transfer=True)
        return True

    def process_xdl_stir(self, stir_info):
        reactor_name = stir_info.get('vessel')
        reactor = self.manager.find_target(reactor_name.lower())
        if reactor is None:
            return False
        reactor_name = reactor.name
        # StopStir
        if 'Stop' in stir_info.tag:
            self.manager.stop_reactor(reactor_name, command='stop_stir')
            return True
        else:
            speed = stir_info.get('stir_speed')
            speed = speed.split(' ')[0]
            stir_secs = stir_info.get('time')
            if stir_secs is None:
                stir_secs = 0
            else:
                stir_secs = stir_secs.split(' ')[0]
            # StartStir
            if 'Start' in stir_info.tag:
                self.manager.start_stirring(reactor_name, command='start_stir', speed=float(speed), stir_secs=stir_secs, wait=False)
            # Stir
            else:
                self.manager.start_stirring(reactor_name, command='start_stir', speed=float(speed), stir_secs=int(stir_secs), wait=True)
            return True
    
    def process_xdl_heatchill(self, heatchill_info):
        reactor_name = heatchill_info.get('vessel')
        reactor = self.manager.find_target(reactor_name.lower())
        if reactor is None:
            return False
        reactor_name = reactor.name
        temp = heatchill_info.get('temp')
        heat_secs = heatchill_info.get('time')
        # StopHeatChill
        if 'Stop' in heatchill_info.tag:
            self.manager.stop_reactor(reactor_name, command='stop_heat')
        # StartHeatChill
        # Reactor will heat to specified temperature and stay on until end of reaction, or told to stop.
        elif 'Start' in heatchill_info.tag:
            temp = float(temp.split(' ')[0])
            self.manager.start_heating(reactor_name, command='start_heat', temp=temp, heat_secs=0, wait=False)
        # HeatChillToTemp
        # reactor will heat to required temperature and then turn off. 
        elif 'To' in heatchill_info.tag:
            temp = float(temp.split(' ')[0])
            self.manager.start_heating(reactor_name, command='start_heat', temp=temp, heat_secs=1, target=True, wait=True)
        # HeatChill
        # Reactor will heat to specified temperature for specified time.
        else:
            temp = float(temp.split(' ')[0])
            heat_secs = int(heat_secs.split(' ')[0])
            self.manager.start_heating(reactor_name, command='start_heat', temp=temp, heat_secs=heat_secs, target= True, wait=True)
        return True

    def process_xdl_wait(self, wait_info, metadata):
        wait_time = wait_info.get('time')
        img_processing = metadata.get("img_processing")
        if wait_time is None:
            self.manager.wait(wait_time=30, actions={})
        else:
            wait_time = wait_time.split(' ')
            unit = wait_time[1]
            if unit == 's' or unit == 'seconds':
                wait_time = int(wait_time[0])
            elif unit == 'min' or unit == 'minutes':
                wait_time = float(wait_time[0]) * 60
            # comments: "Picture<picture_no>, wait_user, wait_reason(reason)"
            comments = wait_info.get('comments')
            if comments is None:
                self.manager.wait(wait_time, {})
            else:
                add_actions = {}
                comments = comments.lower()
                comments = comments.split(',')
                for comment in comments:
                    if "picture" in comment:
                        pic_no = comment.split('picture')[1]
                        add_actions["picture"] = int(pic_no)
                        if img_processing is not None:
                            add_actions['img_processing'] = img_processing
                        else:
                            add_actions['img_processing'] = ''
                    elif "wait_user" in comment:
                        add_actions['wait_user'] =True
                    if "wait_reason" in comment:
                        reason = comment[comment.index('(')+1:-1]
                        add_actions['wait_reason'] = reason
                self.manager.wait(wait_time=wait_time, actions=add_actions)
        return True
