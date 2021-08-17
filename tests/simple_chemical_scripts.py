from context import UJ_FB
import UJ_FB.web_listener as web_listener
import UJ_FB.manager as manager
from threading import Thread
import UJ_FB.fluidic_backbone_gui as fluidic_backbone_gui


class GraphTest(Thread):
    def __init__(self, gui_main):
        Thread.__init__(self)
        self.gui = gui_main
        self.listener = self.gui.manager.listener
        self.quit_flag = False

    def run(self):
        while not self.quit_flag:
            self.main_menu()

    def quit(self):
        self.quit_flag = True

    def main_menu(self):
        response = input("[1]: Move\n[2]: Heat and stir\n[3]: Show pipeline\n[4]: Execute pipeline\n"
                         "[5]: Clear pipeline\n[6]: Import pipeline\n[7]: Export pipeline\n[8]: Update URL\n")
        if response == "1":
            self.move_menu()
        elif response == "2":
            self.reactor_menu()
        elif response == "3":
            pipeline = self.gui.manager.echo_queue()
            for command in pipeline:
                print(f"{command['module_name']}: {command['command']}")
        elif response == "4":
            self.gui.manager.start_queue()
        elif response == "5":
            self.gui.manager.pipeline.queue.clear()
        elif response == "6":
            self.gui.manager.import_queue("Configs/Pipeline.json")
        elif response == "7":
            self.gui.manager.export_queue()
        elif response == "8":
            print("Please enter the IP address of the server")
            response = input("IP address:")
            self.listener.update_url(response)

    def move_menu(self):
        print("The following nodes are connected:")
        for node in self.gui.manager.valid_nodes:
            print(node)
        source = input('What is the source?')
        destination = input('What is the destination?')
        volume = int(input('What is the volume?'))
        speed = int(input("At what speed?"))
        print(f"Move {volume}ml from {source} to {destination} at {speed} ul/min.\n")
        response = input("Is this correct? (y/n)")
        if response == 'y':
            self.gui.manager.move_liquid(source, destination, volume, speed)

    def reactor_menu(self):
        avail_reactors = self.gui.manager.reactors.keys()
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
        self.gui.manager.heat_stir(reactor, command, preheat, temp, heat_secs, speed, stir_secs)
        

gui = fluidic_backbone_gui.FluidicBackboneUI(False)
listener = web_listener.WebListener(gui.manager)
test = GraphTest(gui)
test.start()
listener.start()
gui.primary.mainloop()
