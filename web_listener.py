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
