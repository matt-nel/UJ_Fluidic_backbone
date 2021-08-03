# Fluidic Backbone prototype code
This software is intended to provide a controller for low-cost, open-source chemistry equipment. The fluidic backbone can use commanduino or Firmata to control Arduino-based robots using Python scripts. The software provides an object-oriented interace that correlates to the equipment, broken down into module objects with attached device objects. 

The Manager script coordinates the modules, which in turn control their attached devices. Commands are sent to the Manager thread where they reside in a queue to be dispatched to the required modules. To perform a given task, the Manager will read and interpret the task command dictionary, and then create a new Thread object to run the required module method. The module method will then make calls to its attached devices, which use the commanduino or Firmata library to send strings to the Arduino. The Manager keeps track of running tasks using a Task object, which is also used to pause and resume tasks. 

## Installation

### Python packages

Please first install the following packages using the command prompt (Windows) or terminal (Unix):

**Networkx**

```pip install networkx```

**Pillow**

```pip install pillow```

It is also required that the commanduino library be installed. Commanduino is a library created by the Cronin Group at the University of Glasgow for controlling Arduino microcontrollers using Python. This robot uses a modified version of the Commanduino library. Commanduino is available at:

https://github.com/Pajables/commanduino

### Arduino IDE and libraries

To set up the firmware on the Arduino, please first download the Arduino IDE at:

https://www.arduino.cc/en/software

The required libraries for the software can be found in the repo under: 

`./fluidic_backbone_arduino/commanduino_libraries/`

Please copy the contents into your Arduino library folder. For Windows users, this is likely 

`Documents/Arduino/libraries`

## #Arduino firmware

Once the Arduino libraries are set up, use the Arduino IDE to upload the firmware within `./fluidic_backbone_arduino/`. This will set the Arduino up to send and receive commands using Commanduino. 

## First-time setup

To first configure the robot, please run the setup GUI. This program will allow you to configure the software for the specific hardware setup you are using.

1. Run `python setup_GUI.py` using the terminal.
2. If a button for an Arduino is available, click on that. Otherwise, write the name of the serial port you will be using in the field, and click "Accept".
3. Click on **"Configure modules"**, then enter the number of valves and syringes into the pop ups that appear.
4. The next screen will show the available valves. Each port has a dropdown where you can select the type of module that is connected to that port. For each port you have connected, select the corresponding item in the dropdown.
5. Once you have selected modules for each used port, then click on the buttons for each used port to configure the module. The configuration options will change based on the module you have selected. Once configuration for the port is complete, the button will turn green.
6. Once you have configured all the ports, click **"Accept"**
7. In the main window, click **"Create config"**, then exit the program.

Now you can run **Fluidic_backbone_GUI.py** to control the robot manually, or run **simple_chemical_scripts** to access a simple console app for scheduling commands.

