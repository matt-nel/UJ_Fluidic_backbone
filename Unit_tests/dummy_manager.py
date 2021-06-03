import threading
from queue import Queue
import json


class DummyManager(threading.Thread):
    def __init__(self, stdout_mutex):
        threading.Thread.__init__(self)
        self.stdout_mutex = stdout_mutex
        self.serial_lock = threading.Lock()
        self.lock = threading.Lock()
        self.q = Queue()
        self.exit = False

    def run(self):
        exit_flag = self.exit
        while not exit_flag:
            command_dict = self.q.get()
            self.command_module(command_dict)
            with self.lock:
                exit_flag = self.exit

    def command_module(self, command_dict):
        try:
            mod_type, name = command_dict['mod_type'], command_dict['module_name']
            command, parameters = command_dict["command"], command_dict["parameters"]
        except KeyError:
            print("Missing parameters")
        if mod_type == 'gui':
            with self.stdout_mutex:
                print(command_dict['message'])

    @staticmethod
    def json_loader(fp):
        with open(fp) as file:
            return json.load(file)