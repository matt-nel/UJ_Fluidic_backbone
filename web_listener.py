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

    def update_url(self, new_url):
        with self.lock:
            self.url = "http://" + new_url + "/robot_query"
        self.manager.prev_run_config['url'] = self.url
        self.manager.rc_changes = True

    def check_connection(self):
        if self.url == "":
            print("No URL has been supplied")
            return False
        else:
            r = requests.get(self.url, params={"id": self.manager.id})
            response_dict = r.json()
            print(F"Received {r.status_code}")
            if r.status_code == "200":
                if response_dict['robot_found']:
                    print(F"Robot {self.manager.id} recognised.")
                    return True
        return False

    def run(self):
        while True:
            with self.lock:
                try:
                    if self.url != "":
                        r = requests.get(self.url, params={"id": self.manager.id, "cmd": "qstart"})
                        response = r.json()
                        start = response["Start"]
                        if start:
                            self.manager.start_queue()
                except requests.ConnectionError:
                    self.url = ""
                    print("Please update the url\n")
            time.sleep(10)
