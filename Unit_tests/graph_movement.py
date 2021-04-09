from Manager import Manager
from threading import Thread
from Fluidic_backbone_GUI import FluidicBackboneUI


class GraphTest(Thread):
    def __init__(self, gui):
        Thread.__init__(self)
        self.gui = gui

    def run(self):
        while True:
            print('Test1: Move 20ml of liquid from flask1 to flask2\n')
            print('Test2: Move 5ml of liquid from flask1 to syringe1\n')

            response = input('Move, heat, or stir?')
            if response == 'move':
                source = input('What is the source?')
                destination = input('What is the destination?')
                volume = int(input('What is the volume?'))
                speed = int(input("At what speed?"))
                print(f"Move {volume}ml from {source} to {destination} at {speed}.\n")
                response = input("Is this correct? (y/n)")
                if response == 'y':
                    self.gui.manager.move_liquid(source, destination, volume, speed)
            elif 'heat' or 'stir' in response:
                print("The following reactors are available:\n", self.gui.manager.flasks.keys(), '\n')
                reactor = input("Which reactor?")
                if 'heat' in response:
                    temp = float(input("Temperature?"))
                    heat_secs = int(input("For how many seconds?"))
                if 'stir' in response:
                    print("Stirring:\n")
                    speed = float(input("What speed"))
                    stir_secs = float(input("For how many seconds?"))
                self.gui.manager.move_liquid('flask1', 'syringe1', 5, 10000)
            elif response == 'q':
                break
        self.gui.destroy()


gui = FluidicBackboneUI(False)
test = GraphTest(gui)
test.start()
gui.primary.mainloop()
