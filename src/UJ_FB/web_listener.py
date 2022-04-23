import xml.etree.ElementTree as et
from threading import Lock
import time
import logging
import requests
import socket
import json

# IP address of PI server
DEFAULT_URL = "http://127.0.0.1:5000/robots_api"


class WebListener:
    """This class is used for all the web related tasks for the robot, and also to parse XDL for
    execution on the robots.
    """
    def __init__(self, robot_manager, robot_id,  robot_key):
        """
        Args:
            robot_manager (UJ_FB.Manager): the manager for this robot
            robot_id (str): the robot's ID
            robot_key (str): the robot's key (password)
        """
        self.manager = robot_manager
        self.id = robot_id
        self.key = robot_key
        self.url_lock = Lock()
        self.url = self.manager.prev_run_config["url"]
        if "http" in self.url:
            self.ip = self.url.split("/")[2]
        if self.url == "":
            self.url = DEFAULT_URL
        self.manager.prev_run_config["url"] = self.url
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
        """Tests whether a connection can be successfully established with a server. 
        """
        retry = False
        with self.url_lock:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect((self.ip, 80))
                ip_address = s.getsockname()[0]
                r = requests.get(self.url + "/", json={"robot_id": self.id, "robot_key": self.key,
                                                       "cmd": "connect", "ip": ip_address}, timeout=10)
                r = r.json()
                self.manager.prev_run_config["url"] = self.url
                self.manager.rc_changes = True
                if r["conn_status"] == "accepted":
                    self.manager.write_log(f"Connection established to {self.url}", level=logging.INFO)
                    self.valid_connection = True
                else:
                    self.manager.write_log("Connection refused. Please check robot ID and key in configuration files.",
                                           level=logging.WARNING)
            except (requests.ConnectionError, json.decoder.JSONDecodeError, socket.gaierror) as e:
                if self.url != DEFAULT_URL:
                    self.url = DEFAULT_URL
                    retry = True
                else:
                    self.valid_connection = False
                    self.manager.write_log("Could not connect to server, running offline. ", level=logging.WARNING)
        if retry:
            self.test_connection()

    def update_status(self, ready, error=False, reaction_complete=False):
        """Updates the robot's status on the server

        Args:
            ready (bool): True if ready to run a reaction, False otherwise
            error (bool, optional): True if robot has encountered an error. Defaults to False.
            reaction_complete (bool, optional): True if reaction is complete. Defaults to False.
        """
        time_elapsed = time.time() - self.last_error_update
        with self.url_lock:
            if self.valid_connection:
                if error:
                    status = "ERROR"
                elif ready:
                    status = "IDLE"
                else:
                    status = "BUSY"
                if status != self.last_set_status or reaction_complete:
                    json_data = {"robot_id": self.id, "robot_key": self.key, "cmd": "robot_status",
                                 "robot_status": status}
                    if reaction_complete:
                        json_data.update({"reaction_complete": True, "reaction_id": self.manager.reaction_id})
                    requests.post(self.url + "/status", json=json_data)
                    self.last_set_status = status
                elif error and time_elapsed > self.polling_time:
                    response = requests.get(self.url + "/status", json={"robot_id": self.id, "robot_key": self.key,
                                                                        "cmd": "error_state"})
                    json_args = response.json()
                    error_state = int(json_args.get("error_state"))
                    self.last_error_update = time.time()
                    if not error_state:
                        self.manager.error = False
                        self.manager.resume()

    def update_execution(self):
        """Queries whether the robot should continue to execute the queue

        Returns:
            bool/None: Returns True/False if response received from server. Otherwise returns None.
        """
        time_elapsed = time.time() - self.last_execution_update
        with self.url_lock:
            if self.valid_connection and time_elapsed > self.polling_time:
                try:
                    response = requests.get(self.url + "/status", json={"robot_id": self.id, "robot_key": self.key,
                                                                        "cmd": "robot_execute"})
                    response = response.json()
                    execute = response.get("action")
                    self.last_execution_update = time.time()
                    return execute
                except (requests.ConnectionError, json.JSONDecodeError) as e:
                    self.valid_connection = False
                    return None
            return None

    def send_image(self, image_metadata, img_data):
        """Sends an image to the server. Images are sent in two post requests. The first request holds the images 
        metadata, and the second holds the image encoded as bytes

        Args:
            image_metadata (dict): the metadata for the image, like the date, name etc
            img_data (bytes): the image encoded in bytes

        Returns:
            requests.Response/bool: returns the response if one received, otherwise returns False
        """
        if not self.valid_connection:
            self.test_connection()
        with self.url_lock:
            try:
                r = requests.post(self.url + "/send_image", json=image_metadata)
                if r.ok:
                    request_id = r.json().get("request_id")
            except requests.ConnectionError:
                self.manager.write_log(f"A connection to {self.url} could not be established, trying again.",
                                       level=logging.WARNING)
                self.valid_connection = False
                time.sleep(20)
                return False
            else:
                r = requests.post(self.url + "/send_image", data=img_data.tobytes(), params={"request_id": request_id})
                return r

    def request_reaction(self):
        """Requests a reaction from the server

        Returns:
            bool: True if reaction received, False if nothing received or no valid connection
        """
        time_elapsed = time.time() - self.last_reaction_update
        with self.url_lock:
            if self.valid_connection and time_elapsed > self.polling_time:
                try:
                    response = requests.get(self.url + "/reaction", json={"robot_id": self.id, "robot_key": self.key,
                                                                          "cmd": "get_reaction"})
                    response = response.json()
                    # get the xdl string
                    protocol = response.get("protocol")
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
        """Loads an XDL file or string

        Args:
            xdl (str, file-like object): the XDL data
            is_file (bool, optional): Whether the XDL data is a file or a string. Defaults to True.
            clean_step (bool, optional): True if a cleaning step is required at the end of the reaction. Defaults to False.

        Returns:
            bool: True if XDL loaded and parsed correctly. Otherwise False.
        """
        if is_file:
            try:
                tree = et.parse(xdl)
                tree = tree.getroot()
            except (FileNotFoundError, et.ParseError):
                if xdl != "":
                    self.manager.write_log(f"{xdl} not found",  level=logging.WARNING)
                return False
        else:
            try:
                tree = et.fromstring(xdl)
            except et.ParseError as e:
                self.manager.write_log(f"The XDL provided is not formatted correctly, {str(e)}", level=logging.ERROR)
                return False
        return self.parse_xdl(tree, clean_step=clean_step)

    def parse_xdl(self, tree, clean_step=False):
        """Parse the XDL and determine what steps need to be carried out. Put the steps into the Manager's queue.

        Args:
            tree (Element): an Element object representing the XML tree
            clean_step (bool, optional): True if cleaning step required after reaction. Defaults to False.

        Returns:
            bool: True if XDL parsed successfully. False otherwise.
        """
        self.manager.pipeline.queue.clear()
        reagents = {}
        modules = {}
        if tree.find("Synthesis"):
            tree = tree.find("Synthesis")
        metadata = tree.find("Metadata")
        reaction_name = metadata.get("name")
        req_hardware = tree.find("Hardware")
        req_reagents = tree.find("Reagents")
        procedure = tree.find("Procedure")
        for reagent in req_reagents:
            reagent_name = reagent.get("id")
            flask = self.manager.find_reagent(reagent_name)
            reagents[reagent_name] = flask
            if flask is None:
                self.manager.write_log(f"Could not find {reagent_name} on {self.manager.id}")
                return False
        for module in req_hardware:
            module_id = module.get("id")
            reagent = self.manager.find_target(module_id)
            modules[module_id] = reagent.name
            if modules[module_id] is None:
                self.manager.write_log(f"Could not find {module_id} on {self.manager.id}")
                return False
        parse_success = True
        for step in procedure:
            if step.tag == "Add":
                if not self.process_xdl_add(reagents, step):
                    parse_success = False
            elif step.tag == "Transfer":
                if not self.process_xdl_transfer(step):
                    parse_success = False
            elif "Stir" in step.tag:
                if not self.process_xdl_stir(step):
                    parse_success = False
            elif "HeatChill" in step.tag:
                if not self.process_xdl_heatchill(step):
                    parse_success = False
            elif "Wait" in step.tag:
                if not self.process_xdl_wait(step, metadata):
                    parse_success = False
        if clean_step:
            self.manager.wait(0, {"wait_user": True, "wait_reason": "cleaning"})
        if not parse_success:
            self.manager.pipeline.queue.clear()
            return False
        else:
            with self.manager.interrupt_lock:
                self.manager.reaction_ready = True
                if not self.manager.reaction_name:
                    self.manager.reaction_name = reaction_name
                self.manager.write_log("XDL loaded successfully")
                return True

    def process_xdl_add(self, reagents, add_info):
        """Process reagent addition step

        Args:
            reagents (dict): dictionary of reagents and their corresponding flask
            add_info (dict): additional information for the addition

        Returns:
            bool: True if successful processed and queued. False otherwise
        """
        vessel = add_info.get("vessel")
        target = self.manager.find_target(vessel.lower())
        if target is None:
            return False
        target = target.name
        source = reagents[add_info.get("reagent")]
        reagent_info = add_info.get("volume")
        if reagent_info is None:
            reagent_info = add_info.get("mass")
            # additional steps for solid reagents
            self.manager.write_log(f"No volume given for addition of {add_info['reagent']} from {source} to {target}")
            return False
        else:
            reagent_info = reagent_info.split(" ")
            volume = float(reagent_info[0])
            if volume == 0:
                return True
            unit = reagent_info[1]
            if unit != "ml":
                # assume uL
                # todo: update this to check a mapping
                volume = volume/1000
        a_time = add_info.get("time")
        if a_time is not None:
            # flow should be in uL/min
            a_time = a_time.split(" ")
            if a_time[1] == "s":
                flow_rate = (volume*1000)/(float(a_time[0])/60)
            else:
                flow_rate = (volume*1000)/float(a_time[0])
        else:
            flow_rate = 0
        return self.manager.move_fluid(source, target, volume, flow_rate)

    def process_xdl_transfer(self, transfer_info):
        """Process a fluid transfer between modules

        Args:
            transfer_info (dict): information about the transfer

        Returns:
            bool: True if successfully processed and queued, False otherwise.
        """
        source = transfer_info.get("from_vessel")
        target = transfer_info.get("to_vessel")
        source = self.manager.find_target(source).name
        target = self.manager.find_target(target).name
        if target is None or source is None:
            return False
        reagent_info = transfer_info.get("volume")
        if reagent_info is None:
            reagent_info = transfer_info.get("mass")
            self.manager.write_log(f"No volume given for transfer from {source} to {target}")
            return False
        else:
            reagent_info = reagent_info.split(" ")
            volume = float(reagent_info[0])
            if volume == 0:
                return True
            unit = reagent_info[1]
            if unit != "ml":
                volume = volume/1000
        t_time = transfer_info.get("time")
        if t_time is not None:
            # uL/min
            t_time = t_time.split(" ")
            if t_time[1] == "s":
                flow_rate = (volume * 1000) / (float(t_time[0]) / 60)
            else:
                flow_rate = (volume * 1000) / float(t_time[0])
        else:
            flow_rate = 0
        return self.manager.move_fluid(source, target, volume, flow_rate, adjust_dead_vol=True, transfer=True)

    def process_xdl_stir(self, stir_info):
        """Process a stir step

        Args:
            stir_info (dict): information about the stir step

        Returns:
            bool: True if successfully parsed and queued. False otherwise.
        """
        reactor_name = stir_info.get("vessel")
        reactor = self.manager.find_target(reactor_name.lower())
        if reactor is None:
            return False
        reactor_name = reactor.name
        # StopStir
        if "Stop" in stir_info.tag:
            self.manager.stop_reactor(reactor_name, command="stop_stir")
            return True
        else:
            speed = stir_info.get("stir_speed")
            speed = speed.split(" ")[0]
            stir_secs = stir_info.get("time")
            if stir_secs is None:
                stir_secs = 0
            else:
                stir_secs = stir_secs.split(" ")[0]
            # StartStir
            if "Start" in stir_info.tag:
                self.manager.start_stirring(reactor_name, command="start_stir", speed=float(speed),
                                            stir_secs=stir_secs, wait=False)
            # Stir
            else:
                self.manager.start_stirring(reactor_name, command="start_stir", speed=float(speed),
                                            stir_secs=int(stir_secs), wait=True)
            return True
    
    def process_xdl_heatchill(self, heatchill_info):
        """Process a heating/chilling step

        Args:
            heatchill_info (dict): information about the heating/chilling step

        Returns:
            bool: True if successfully processed and queued. False otherwise.
        """
        reactor_name = heatchill_info.get("vessel")
        reactor = self.manager.find_target(reactor_name.lower())
        if reactor is None:
            return False
        reactor_name = reactor.name
        temp = heatchill_info.get("temp")
        heat_secs = heatchill_info.get("time")
        # StopHeatChill
        if "Stop" in heatchill_info.tag:
            self.manager.stop_reactor(reactor_name, command="stop_heat")
        # StartHeatChill
        # Reactor will heat to specified temperature and stay on until end of reaction, or told to stop.
        elif "Start" in heatchill_info.tag:
            temp = float(temp.split(" ")[0])
            self.manager.start_heating(reactor_name, command="start_heat", temp=temp, heat_secs=0, wait=False)
        # HeatChillToTemp
        # reactor will heat to required temperature and then turn off. 
        elif "To" in heatchill_info.tag:
            temp = float(temp.split(" ")[0])
            self.manager.start_heating(reactor_name, command="start_heat", temp=temp, heat_secs=1, target=True,
                                       wait=True)
        # HeatChill
        # Reactor will heat to specified temperature for specified time.
        else:
            temp = float(temp.split(" ")[0])
            heat_secs = int(heat_secs.split(" ")[0])
            self.manager.start_heating(reactor_name, command="start_heat", temp=temp, heat_secs=heat_secs,
                                       target=True, wait=True)
        return True

    def process_xdl_wait(self, wait_info, metadata):
        """Process a wait step. Used to either allow reaction to complete or to settle solids

        Args:
            wait_info (dict): information about the wait step
            metadata (dict): metadata for this XDL reaction

        Returns:
            bool: True if successfully processed and queued. False otherwise. 
        """
        wait_time = wait_info.get("time")
        img_processing = metadata.get("img_processing")
        if wait_time is None:
            self.manager.wait(wait_time=30, actions={})
        else:
            wait_time = wait_time.split(" ")
            unit = wait_time[1]
            if unit == "s" or unit == "seconds":
                wait_time = int(wait_time[0])
            elif unit == "min" or unit == "minutes":
                wait_time = float(wait_time[0]) * 60
            # comments: "Picture<picture_no>, wait_user, wait_reason(reason)"
            comments = wait_info.get("comments")
            if comments is None:
                self.manager.wait(wait_time, {})
            else:
                add_actions = {}
                comments = comments.lower()
                comments = comments.split(",")
                for comment in comments:
                    if "picture" in comment:
                        pic_no = comment.split("picture")[1]
                        add_actions["picture"] = int(pic_no)
                        if img_processing is not None:
                            add_actions["img_processing"] = img_processing
                        else:
                            add_actions["img_processing"] = ""
                    elif "wait_user" in comment:
                        add_actions["wait_user"] = True
                    if "wait_reason" in comment:
                        reason = comment[comment.index("(")+1:-1]
                        add_actions["wait_reason"] = reason
                self.manager.wait(wait_time=wait_time, actions=add_actions)
        return True
