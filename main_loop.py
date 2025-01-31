'''
This is the main GT program for running the Dephy exos. Read the Readme.
'''
import exoboot
import threading
import controllers
import state_machines
import gait_state_estimators
import constants
import filters
import time
import util
import config_util
import parameter_passers
import control_muxer
import plotters
import ml_util
import traceback
import socket
import os
import re
from numpy import diff
#from Exo.DataContainer import gyro_z

global pastDataBuf, peakData, valleyData
pastDataBuf=[0]*8
valleyData=peakData=[]
'''
s = socket.socket()  # Create a socket object
port = 50000  # Reserve a port for your service every new transfer wants a new port or you must wait.  
s.connect(('localhost', port))
x = 0  
st = str(x)
byt = st.encode()
s.send(byt)
'''
def determineMinMaxData(anyData,exo):
    global pastDataBuf
    global peakData
    global valleyData
    global pastData

    dataDiff=diff(pastDataBuf)
    if (dataDiff[0]>0 and dataDiff[1]<=0 and dataDiff[2]<=0 and dataDiff[3]<=0 and pastDataBuf[1]>1):
        peakData.append(pastDataBuf[1])
        #maxTLA=
        if exo.side==constants.Side.LEFT:
             print("LEFT PEAK VALUE REACHED: "+str(pastDataBuf[1]))
        else:
             print("RIGHT PEAK VALUE REACHED: " +str(pastDataBuf[1]))
        #st = str(pastDataBuf[1])
        #byt = st.encode()
        #s.send(byt)
        lastPlotTime=time.perf_counter()        
        pastData=pastDataBuf[1]
    else:
        maxData=0
        minData=0
        peakDataMean=0

    pastDataBuf.pop(0)
    pastDataBuf.append(anyData)
    return peakData

config = config_util.load_config_from_args()  # loads config from passed args
file_ID = input(
    'Other than the date, what would you like added to the filename?')

'''if sync signal is used, this will be gpiozero object shared between exos.'''
sync_detector = config_util.get_sync_detector(config)

'''Connect to Exos, instantiate Exo objects.'''
exo_list = exoboot.connect_to_exos(
    file_ID=file_ID, config=config, sync_detector=sync_detector)
print('Battery Voltage: ', 0.001*exo_list[0].get_batt_voltage(), 'V')

config_saver = config_util.ConfigSaver(
    file_ID=file_ID, config=config)  # Saves config updates

'''Instantiate gait_state_estimator and state_machine objects, store in lists.'''
gait_state_estimator_list, state_machine_list = control_muxer.get_gse_and_sm_lists(
    exo_list=exo_list, config=config)

'''Prep parameter passing.'''
lock = threading.Lock()
quit_event = threading.Event()
new_params_event = threading.Event()
# v0.2,15,0.56,0.6!

'''Perform standing calibration.'''
if not config.READ_ONLY:
    for exo in exo_list:
        standing_angle = exo.standing_calibration()
        if exo.side == constants.Side.LEFT:
            config.LEFT_STANDING_ANGLE = standing_angle
        else:
            config.RIGHT_STANDING_ANGLE = standing_angle
else:
    print('Not calibrating... READ_ONLY = True in config')

input('Press any key to begin')
print('Start!')



'''Main Loop: Check param updates, Read data, calculate gait state, apply control, write data.'''
timer = util.FlexibleTimer(
    target_freq=config.TARGET_FREQ)  # attempts constants freq
t0 = time.perf_counter()
keyboard_thread = parameter_passers.ParameterPasser(
    lock=lock, config=config, quit_event=quit_event,
    new_params_event=new_params_event)
config_saver.write_data(loop_time=0)  # Write first row on config
only_write_if_new = not config.READ_ONLY and config.ONLY_LOG_IF_NEW

lastPlotTime=0
gyro_z=exo.data.gyro_z
appliedTorque=exo.data.ankle_torque_from_current
while True:
    try:
        timer.pause()
        loop_time = time.perf_counter() - t0

        lock.acquire()
        if new_params_event.is_set():
            config_saver.write_data(loop_time=loop_time)  # Update config file
            for state_machine in state_machine_list:  # Make sure up to date
                state_machine.update_ctrl_params_from_config(config=config)
            for gait_state_estimator in gait_state_estimator_list:  # Make sure up to date
                gait_state_estimator.update_params_from_config(config=config)
            new_params_event.clear()
        if quit_event.is_set():  # If user enters "quit"
            break
        lock.release()

        for exo in exo_list:
            exo.read_data(loop_time=loop_time)
            #maxValue=determineMinMaxData(exo.data.ankle_torque_from_current,exo)
        for gait_state_estimator in gait_state_estimator_list:
            gait_state_estimator.detect()
        if not config.READ_ONLY:
            for state_machine in state_machine_list:
                state_machine.step(read_only=config.READ_ONLY)
        for exo in exo_list:
            exo.write_data(only_write_if_new=only_write_if_new)
            #maxValue=determineMinMaxData(exo.data.ankle_torque_from_current)
        #print(exo.data.ankle_torque_from_current)
        #maxValue=determineMinMaxData(exo.data.ankle_torque_from_current)
        '''
        if time.perf_counter()-lastPlotTime>0.5:
            st = str(exo.data.gyro_z)
            byt = st.encode()
            s.send(byt)
            lastPlotTime=time.perf_counter()
        '''

    except KeyboardInterrupt:
        print('Ctrl-C detected, Exiting Gracefully')
        break
    except Exception as err:
        print(traceback.print_exc())
        print("Unexpected error:", err)
        break

'''Safely close files, stop streaming, optionally saves plots'''
config_saver.close_file()
for exo in exo_list:
    exo.close()
if config.VARS_TO_PLOT:
    plotters.save_plot(filename=exo_list[0].filename.replace(
        '_LEFT.csv', '').replace('_RIGHT.csv', ''), vars_to_plot=config.VARS_TO_PLOT)

print('Done!!!')
