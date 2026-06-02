# fybot
Automation and accessory handling for the Fuck Yeah machine.

## To use
On a Raspberry Pi with a screen and input device, run ./launcher.sh to bring up the program selector and configurer. Make sure you have the equipment and connections installed for the program of your choice.

## To add your own programs
In the programs/ directory, add a new class that inherits from program_elements.program.Program. Fill out the PARAMETERS variable with configurable inputs, and implement the run() method, using the handlers, program_elements, and outputs as building blocks. Your program should look for self.main_stop_event as a shutdown signal, or override stop() to provide a different signal. Look at risky_mercy.pl as an example program that uses all of the building blocks so far.

## To add support for additional devices
Any pump or tens unit that you can code to implement pump_protocol or tens_protocol should be easy to swap into any existing program. Many stepper drivers come with manufacturer provided code, and some tens units (like other ErosTek devices) have existing third-party drivers.
For other types of devices, try to create a reasonable protocol for the device type and code your scenarios against that, so that others can reuse them.
