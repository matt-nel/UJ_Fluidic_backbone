# **UJ Fluidic Backbone**

This software provides a controller for low-cost, open-source chemistry equipment. The fluidic backbone uses Commanduino Arduino-based robots using Python scripts. The software provides an object-oriented interace that correlates to the equipment, broken down into module objects with attached device objects. 

The robot can be run manually using the GUI or by loading XDL documents that describe a chemical synthesis. 

https://croningroup.gitlab.io/chemputer/xdl/standard/index.html

The robot can be run in conjuction with the MC_Labserver (https://github.com/Pajables/MC_Labserver), which allows the user to send reactions to a number of attached robots and tracks reaction data. 

## **Installation**

To use the robot, we need to set up software set up on computer and an Arduino. I'll run through all of that here.

First, get the robot's software. On the Github page, click on the green button on the top right and select "Download Zip" from the menu. Extract the contents of that zip file to somewhere on your computer. 

### **Python**

The robot has been tested extensively with Python 3.8.5 you can install Python 3.8.5 using the link that follows. It is recommended that you add Python to your Path variables (Keep an eye on the options in the installer). 

https://www.python.org/downloads/release/python-385/

### **Python packages**

The following packages should be installed. The easiest way is to use the `pip` tool in the command prompt (Windows) or terminal (Unix):

**networkx**

**pillow**

**opencv-python**

To use pip, open a terminal and type:

```pip install pillow```

The same can be used for the other packages.

### **Commanduino**

 Commanduino is a library created by the Cronin Group at the University of Glasgow for controlling Arduino microcontrollers using Python. This robot uses a modified version of the Commanduino library available at:

https://github.com/Pajables/commanduino

To install, download the zip and extract the files to a folder on your computer, I would recommend C:/Users/your_user_name/your_folder for Windows users. Open a terminal window, you'll notice that the text to the left of the cursor shows the directory you're currently working within. We need to get the directory that contains commanduino. 

`cd your_folder/commanduino-main/commanduino-main `

Now you can use Python to run the setup.py file in that directory:

`python setup.py install`

Commanduino is set up!

### **OpenCV** (optional)

OpenCV is a open-source C++ library for computer vision. Required if you will need a camera. 

Windows:

https://opencv.org/releases/

Linux:

Open a terminal and use your favourite package manager to install OpenCV:

`sudo apt install python3-opencv`

### **Arduino IDE and libraries**

To set up the firmware on the Arduino, first download the Arduino IDE at:

https://www.arduino.cc/en/software

The required libraries for the Arduino code can be found in the UJ_Fluidic_backbone repo under: 

`./fluidic_backbone_arduino/commanduino_libraries/`

Please copy the contents of that folder into your Arduino library folder. For Windows users, this is likely

`Documents/Arduino/libraries`

### **Arduino firmware**

Once the Arduino libraries are set up, use the Arduino IDE to upload the firmware within `./fluidic_backbone_arduino/`. Open the Fluidic_backbone_arduino.ino file, set the board and port settings using the tools menu, then click on Upload. This will set the Arduino up to send and receive commands using Commanduino. 

## First-time setup

To first configure the robot, please run the setup GUI. This program will allow you to configure the software for the specific hardware setup you are using.

1. Run `python setup_GUI.py` using the terminal.
2. If a button for an Arduino is available, click on that. Otherwise, write the name of the serial port you will be using in the field, and click "Accept".
3. Click on **"Configure modules"**, then enter the number of valves and syringes into the pop ups that appear.
4. The next screen will show the available valves. Each port has a dropdown where you can select the type of module that is connected to that port. For each port you have connected, select the corresponding item in the dropdown.
5. Once you have selected modules for each used port, click on the buttons for each used port to configure the module. The configuration options will change based on the module you have selected. Once configuration for the port is complete, the button will turn green.
6. Once you have configured all the ports, click **"Accept"**
7. In the main window, click **"Create config"**, then exit the or click "Run Fluidic Backbone" on the right hand side. 

Alternatively, open a terminal and use `cd` browse to the directory where you unzipped the UJ_Fluidic_backbone repo. Use the command `python main.py` to start the robot.

