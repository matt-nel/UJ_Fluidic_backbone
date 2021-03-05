import tkinter
from threading import Thread
from Fluidic_backbone_GUI import FluidicBackboneUI


class GraphTest(Thread):
    def __init__(self):
        Thread.__init__(self)

    def run(self):
        while True:
            print('Test1: Move 20ml of liquid from flask1 to flask2\n')
            print('Test2: Move 20ml of liquid from flask1 to syringe1\n')

            response = input('Test 1 or test 2?')
            if response == '1':
                gui.manager.move_liquid('flask1', 'flask2', 20, 1000)
            elif response == '2':
                gui.manager.move_liquid('flask')
            elif response == 'q':
                break


root = tkinter.Tk()
gui = FluidicBackboneUI(root, False)
test = GraphTest()
test.start()
root.mainloop()
