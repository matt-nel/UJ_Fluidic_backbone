import context
import UJ_FB.manager as manager
from threading import Thread


class QueueTest(Thread):
    def __init__(self, manager):
        Thread.__init__(self)
        self.manager = manager
        self.listener = self.manager.listener
        self.quit_flag = False

    def run(self):
        while not self.quit_flag:
            self.main_menu()

    def quit(self):
        self.quit_flag = True

    def main_menu(self):
        response = input("[1]: Move\n[2]: Heat and stir\n[3]: Show pipeline\n[4]: Execute pipeline\n"
                         "[5]: Clear pipeline\n[6]: Import pipeline\n[7]: Export pipeline\n[8]: Update URL\n"
                         "[q] Quit")
        if response == "1":
            self.move_menu()
        elif response == "2":
            self.reactor_menu()
        elif response == "3":
            pipeline = self.manager.echo_queue()
            for command in pipeline:
                print(f"{command['module_name']}: {command['command']}")
        elif response == "4":
            self.manager.start_queue()
        elif response == "5":
            self.manager.pipeline.queue.clear()
        elif response == "6":
            self.manager.import_queue("Configs/Pipeline.json")
        elif response == "7":
            self.manager.export_queue()
        elif response == "8":
            print("Please enter the IP address of the server")
            response = input("IP address:")
            self.listener.update_url(response)
        elif response == 'q':
            self.quit_flag = True

    def move_menu(self):
        print("The following nodes are connected:")
        for node in self.manager.valid_nodes:
            print(node)
        source = input('What is the source?')
        destination = input('What is the destination?')
        volume = int(input('What is the volume?'))
        speed = int(input("At what speed?"))
        print(f"Move {volume}ml from {source} to {destination} at {speed} ul/min.\n")
        response = input("Is this correct? (y/n)")
        if response == 'y':
            self.manager.move_liquid(source, destination, volume, speed)

    def reactor_menu(self):
        avail_reactors = self.manager.reactors.keys()
        print("The following reactors are available:\n")
        for reactor in avail_reactors:
            print(reactor, '\n')
        reactor = input("Which reactor?")
        command = input("Heat, stir, or heat and stir?")
        speed, temp = 0, 0.0
        heat_secs, stir_secs = 0.0, 0.0
        preheat = False
        if 'heat' in command.lower():
            print("Heating parameters:")
            temp = float(input("Temperature?"))
            heat_secs = int(input("For how many seconds?"))
            preheat = input("Would you like the reactor to preheat?")
            if preheat == 'y' or preheat == 'Y':
                preheat = True
        if 'stir' in command.lower():
            print("Stirring parameters:")
            speed = float(input("What speed"))
            stir_secs = float(input("For how many seconds?"))
        self.manager.heat_stir(reactor, command, preheat, temp, heat_secs, speed, stir_secs)
        

if __name__ == "__main__":
    test = QueueTest(manager.Manager())
    test.start()
    test.manager.mainloop()

