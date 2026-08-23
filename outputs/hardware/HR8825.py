import time

import gpiozero as GPIO

from loguru import logger

MotorDir = [
    'forward',
    'backward',
]

ControlMode = [
    'hardware',
    'software',
]

class HR8825:
    """
    Low-level GPIO stepper driver for the HR8825 motor controller.
    Lightly modified from the code from https://www.waveshare.com/wiki/Stepper_Motor_HAT_(B).
    """

    def __init__(self, dir_pin, step_pin, enable_pin, mode_pins):
        self.dir_pin = dir_pin
        self.step_pin = step_pin        
        self.enable_pin = enable_pin
        self.mode_pins = mode_pins
        
        self.dir = GPIO.LED(self.dir_pin)
        self.step = GPIO.LED(self.step_pin)        
        self.enable = GPIO.LED(self.enable_pin)
        self.mode_1 = GPIO.LED(self.mode_pins[0])
        self.mode_2 = GPIO.LED(self.mode_pins[1])
        self.mode_3 = GPIO.LED(self.mode_pins[2])

        self.control_pin = {
          dir_pin: self.dir,
          enable_pin: self.enable,
          step_pin: self.step,
          mode_pins[0]: self.mode_1,
          mode_pins[1]: self.mode_2,
          mode_pins[2]: self.mode_3
        }
        self._closed = False
        
    def digital_write(self, pin, value):
        if self._closed:
            return
        if value:
          self.control_pin[pin].on()
        else:
          self.control_pin[pin].off()
        
    def Stop(self):
        self.digital_write(self.enable_pin, 0)

    def close(self) -> None:
        if self._closed:
            return
        self.Stop()
        # Mark closed before tearing down pins so concurrent digital_write is a no-op.
        self._closed = True
        devices = list(self.control_pin.values())
        self.control_pin.clear()
        for device in devices:
            device.close()

    def Configure_mode(self, microstep):
        j = 0
        for i in microstep:
          self.digital_write(self.mode_pins[j], i)
          j = j+1
    
    def SetMicroStep(self, mode, stepformat):
        """
        (1) mode
            'hardware' :    Use the switch on the module to control the microstep
            'software' :    Use software to control microstep pin levels
                You must set all the DIP switches to 0 to use software control
        (2) stepformat
            ('fullstep', 'halfstep', '1/4step', '1/8step', '1/16step', '1/32step')
        """
        microstep = {'fullstep': (0, 0, 0),
                     'halfstep': (1, 0, 0),
                     '1/4step': (0, 1, 0),
                     '1/8step': (1, 1, 0),
                     '1/16step': (0, 0, 1),
                     '1/32step': (1, 0, 1)}

        if (mode == ControlMode[1]):
            self.Configure_mode(microstep[stepformat])
        
    def TurnStep(self, Dir, steps, stepdelay=0.005):
        if (Dir == MotorDir[0]):
            self.digital_write(self.enable_pin, 1)
            self.digital_write(self.dir_pin, 0)
        elif (Dir == MotorDir[1]):
            self.digital_write(self.enable_pin, 1)
            self.digital_write(self.dir_pin, 1)
        else:
            logger.error("The dir must be : 'forward' or 'backward'")
            self.digital_write(self.enable_pin, 0)
            return

        if (steps == 0):
            return
            
        for i in range(steps):
            self.digital_write(self.step_pin, True)
            time.sleep(stepdelay)
            self.digital_write(self.step_pin, False)
            time.sleep(stepdelay)

