import threading
from typing import Type
import config_util


class ParameterPasser(threading.Thread):
    def __init__(self,
                 lock: Type[threading.Lock],
                 config: Type[config_util.ConfigurableConstants],
                 quit_event: Type[threading.Event],
                 new_params_event: Type[threading.Event],
                 name='keyboard-input-thread'):
        '''This class passes parameters via user input and a parallel thread.

        The general idea is that this thread waits for an input, then grabs a lock (to stop the main thread),
        checks if the message follows the "code" (starts with 'v', ends with '!'), and then updates config
        params, depending on which params your child class wants updated. Then it sets the new_param_event flag
        to signal to the main loop to update the controllers'''
        super().__init__(name=name)
        self.daemon = True  # Thread property
        self.lock = lock
        self.config = config
        self.quit_event = quit_event
        self.new_params_event = new_params_event
        self.start()  # Starts the run() function

    # This run function overrides the run() function in threading.Thread
    def run(self):
        while True:
            msg = input()
            if msg == 'a':
                self.lock.acquire()
                self.config.SLIP_DETECT_ACTIVE = not self.config.SLIP_DETECT_ACTIVE
                self.config.SWING_ONLY = not self.config.SWING_ONLY
                print('swing only: ', self.config.SWING_ONLY,
                      'slip detect active: ', self.config.SWING_ONLY)
                self.new_params_event.set()
                self.lock.release()

            elif len(msg) < 3:
                print('Message must be either "quit" or a string of parameters'
                      ' starting with a letter (v for splines, k for stiffness,'
                      ' s for setpoint) and ending with an exclamation point)')

            elif msg.lower() == 'quit':
                print('Quitting')
                self.lock.acquire()
                self.quit_event.set()
                self.lock.release()
                break

            elif msg[-1] == '!':
                self.lock.acquire()
                first_letter = msg[0]
                msg_content = msg[1:-1]

                if first_letter == 'v':
                    param_list = [float(x) for x in msg_content.split(',')]
                    if len(param_list) != 5:
                        print('Must send five spline points with v<>! message')
                    else:
                        self.config.RISE_FRACTION = param_list[0]
                        self.config.LEFT_PEAK_TORQUE = param_list[1]
                        self.config.RIGHT_PEAK_TORQUE = param_list[1]
                        self.config.PEAK_FRACTION = param_list[2]
                        self.config.FALL_FRACTION = param_list[3]
                elif first_letter == 'k':
                    if msg_content.isdigit():
                        self.config.K_VAL = int(msg_content)
                        self.config.B_VAL = self.config.B_RATIO * \
                            self.config.K_VAL  # 2.5ish = critically damped
                        print('k_val updated to: ', msg_content)
                    else:
                        print('Must provide single positive integer to update k_val')
                elif first_letter == 's':
                    if msg_content.lstrip('-').isdigit():
                        self.config.SET_POINT = int(msg_content)
                        print('SET_POINT updated to: ', msg_content)
                    else:
                        print('Must provide single integer to update SET_POINT')
                elif first_letter == 'r':
                    if msg_content.isdigit():
                        if 0 <= int(msg_content) <= 40:
                            self.config.RIGHT_PEAK_TORQUE = int(msg_content)
                            print('RIGHT Peak torque set to: ',
                                  self.config.RIGHT_PEAK_TORQUE)
                    else:
                        print('Must provide single integer to update RIGHT_PEAK_TORQUE')
                elif first_letter == 'l':
                    if msg_content.isdigit():
                        if 0 <= int(msg_content) <= 40:
                            self.config.LEFT_PEAK_TORQUE = int(msg_content)
                            print('LEFT Peak torque set to: ',
                                  self.config.LEFT_PEAK_TORQUE)
                    else:
                        print('Must provide single integer to update LEFT_PEAK_TORQUE')
                elif first_letter == 't':
                    #print(msg_content)
                    if float(msg_content)<1:
                        if 0 <= float(msg_content) <= 1:
                            self.config.LEFT_PEAK_FRACTION = float(msg_content)
                            print('LEFT PEAK FRACTION set to : ',
                                  self.config.LEFT_PEAK_FRACTION)
                    else:
                        print('Must provide decimal to update LEFT_PEAK_FRACTION')
                elif first_letter=="y":
                    if float(msg_content)<1:
                       if 0<= float(msg_content)<=1:
                            self.config.RIGHT_PEAK_FRACTION =float(msg_content)
                            print("RIGHT PEAK FRACTION set to : ",self.config.RIGHT_PEAK_FRACTION)
                    else:
                       print('Must provide decimal to update RIGHT_PEAK_FRACTION')
                elif first_letter == 'u':
                    #print(msg_content)
                    if float(msg_content)<1:
                        if 0 <= float(msg_content) <= 1:
                            self.config.LEFT_TOE_OFF_FRACTION = float(msg_content)
                            print('LEFT TOE OFF FRACTION set to : ',
                                  self.config.LEFT_TOE_OFF_FRACTION)
                    else:
                        print('Must provide decimal to update LEFT_PEAK_FRACTION')
                elif first_letter=="i":
                    if float(msg_content)<1:
                       if 0<= float(msg_content)<=1:
                            self.config.RIGHT_TOE_OFF_FRACTION =float(msg_content)
                            print("RIGHT TOE OFF FRACTION set to : ",self.config.RIGHT_TOE_OFF_FRACTION)
                    else:
                       print('Must provide decimal to update RIGHT_PEAK_FRACTION')
                elif first_letter == 'o':
                    #print(msg_content)
                    if float(msg_content)<1:
                        if 0 <= float(msg_content) <= 1:
                            self.config.LEFT_FALL_FRACTION = float(msg_content)
                            print('LEFT FALL FRACTION set to : ',
                                  self.config.LEFT_FALL_FRACTION)
                    else:
                        print('Must provide decimal to update LEFT_FALL_FRACTION')
                elif first_letter=="p":
                    if float(msg_content)<1:
                       if 0<= float(msg_content)<=1:
                            self.config.RIGHT_FALL_FRACTION =float(msg_content)
                            print("RIGHT FALL FRACTION set to : ",self.config.RIGHT_FALL_FRACTION)
                    else:
                       print('Must provide decimal to update RIGHT_FALL_FRACTION')
                elif first_letter == 'd':
                    # Delay for slip detectors
                    self.config.SLIP_DETECT_DELAY = int(msg_content)
                elif first_letter == '-':
                    self.config.EXPERIMENTER_NOTES = msg_content
                    print('Added that message to the config.')
                self.new_params_event.set()
                self.lock.release()

            else:
                print('IDK how to interpret your message')
