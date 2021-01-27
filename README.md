# Fluidic Backbone prototype code
This program is intended to provide a software agnostic interface for constructing low-cost, open-source chemistry 
equipment. This program, run from GUI.py, is intended to interface with commanduino, firmata, or marlin. The program
provides software objects that correlate to equipment, broken down into module objects with attached device objects. 
The software coordinates the modules and their devices, sending the commands to the device driver program for execution.
## Naming conventions:
#### Module names:
syringe1, valve1, reactor2
#### Device names:
motor_en1, he_sens2, stepper3, analog5, digital6
#### Reagents and intermediates and waste
reagent1, intermediate2, waste3
#### Connections dictionary:
Contains information about the valve connections
- no connection: "no_conn"
- { "valve1": {"inlet": "syringe1", 1: "reagent1", 2: "no_conn", 3: "intermediate1", 4: "waste1" ...}
#### Device association dictionary
Contains information about devices attached to particular modules

{"module_name": {"device1_name": "commanduino_device1_name", "device2_name": "commanduino_device2_name" ...}
