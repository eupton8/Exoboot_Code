import numpy as np
import filters
import exoboot
from scipy import signal
from collections import deque
import time
import constants
from typing import Type
import util
import config_util
import data_util


class GaitStateEstimator():
    def __init__(self,
                 data_container: Type[exoboot.Exo.DataContainer],
                 heel_strike_detector,
                 gait_phase_estimator,
                 toe_off_detector,
                 do_print_heel_strikes: bool = False,
                 side: Type[constants.Side] = constants.Side.NONE):
        '''Looks at the exo data, applies logic to detect HS, gait phase, and TO, and adds to exo.data'''
        self.side = side
        self.data_container = data_container
        self.heel_strike_detector = heel_strike_detector
        self.gait_phase_estimator = gait_phase_estimator
        self.toe_off_detector = toe_off_detector
        self.do_print_heel_strikes = do_print_heel_strikes

    def detect(self):
        data = self.data_container  # For convenience
        data.did_heel_strike = self.heel_strike_detector.detect(data)
        data.gait_phase = self.gait_phase_estimator.estimate(data)
        data.did_toe_off = self.toe_off_detector.detect(data)
        if self.do_print_heel_strikes and data.did_heel_strike:
            print('heel strike detected on side: %-*s  at time: %s' %
                  (10, self.side, data.loop_time))

    def update_params_from_config(self, config: Type[config_util.ConfigurableConstants]):
        pass


class MLGaitStateEstimator():
    def __init__(self,
                 side: Type[constants.Side],
                 data_container: Type[exoboot.Exo.DataContainer],
                 heel_strike_detector,
                 gait_phase_estimator,
                 toe_off_detector):
        '''Looks at the exo data, applies logic to detect HS, gait phase, and TO, and adds to exo.data'''
        self.side = side
        self.data_container = data_container
        self.heel_strike_detector = heel_strike_detector
        self.gait_phase_estimator = gait_phase_estimator
        self.toe_off_detector = toe_off_detector

    def detect(self, data: Type[exoboot.Exo.DataContainer], do_print_heel_strikes=True):
        data = self.data_container  # For convenience
        data.did_heel_strike = self.heel_strike_detector.detect(data)
        data.gait_phase = self.gait_phase_estimator.estimate(data)
        data.did_toe_off = self.toe_off_detector.detect(data)
        if do_print_heel_strikes and data.did_heel_strike:
            print('heel strike detected on side: ', self.side)

    def update_params_from_config(self, config: Type[config_util.ConfigurableConstants]):
        pass


class GyroHeelStrikeDetector():
    def __init__(self, height: float, gyro_filter: Type[filters.Filter], delay=0):
        self.height = height
        self.gyro_filter = gyro_filter
        self.gyro_history = deque([0, 0, 0], maxlen=3)
        self.delay = delay
        # self.timer_active = False
        self.timer = util.DelayTimer(delay_time=self.delay)

    def detect(self, data: Type[exoboot.Exo.DataContainer]):
        self.gyro_history.appendleft(self.gyro_filter.filter(data.gyro_z))
        if (self.gyro_history[1] > self.height and
            self.gyro_history[1] > self.gyro_history[0] and
                self.gyro_history[1] > self.gyro_history[2]):
            self.timer.start()
        if self.timer.check():
            self.timer.reset()
            return True
        else:
            return False


class GaitPhaseBasedToeOffDetector():
    def __init__(self, fraction_of_gait):
        '''Uses gait phase estimated from heel strikes to estimate toe-off.'''
        self.fraction_of_gait = fraction_of_gait
        self.has_toe_off_occurred = False

    def detect(self, data: Type[exoboot.Exo.DataContainer]):
        gait_phase = data.gait_phase
        if gait_phase is None:
            did_toe_off = False
        else:
            if gait_phase < self.fraction_of_gait:
                self.has_toe_off_occurred = False
            if gait_phase > self.fraction_of_gait and self.has_toe_off_occurred is False:
                did_toe_off = True
                self.has_toe_off_occurred = True
            else:
                did_toe_off = False
        return did_toe_off


class StrideAverageGaitPhaseEstimator():
    '''Calculates gait phase based on average of recent stride durations.'''

    def __init__(self,
                 num_strides_required: int = 2,
                 num_strides_to_average: int = 2,
                 min_allowable_stride_duration: float = 0.6,
                 max_allowable_stride_duration: float = 2):
        ''' Returns gait phase, which is either None or in [0, 1]
        Arguments:
        num_strides_required: int, number of acceptable strides in a row before gait is deemed steady
        num_strides_to_average: int, number of strides to average
        min_allowable_stride_duration: minimum allowable duration of a stride
        max_allowable_stride_duration: maximum allowable duration of a stride
        Returns: gait_phase, which is either None or in [0, 1].'''
        if num_strides_required < 1:
            raise ValueError('num_strides_required must be >= 1')
        if num_strides_to_average > num_strides_required:
            raise ValueError(
                'num_strides_to_average must be >= num_strides_required')
        self.num_strides_required = num_strides_required
        self.min_allowable_stride_duration = min_allowable_stride_duration
        self.max_allowable_stride_duration = max_allowable_stride_duration
        self.time_of_last_heel_strike = 0  # something a long time ago
        self.last_stride_durations = deque(
            [1000] * self.num_strides_required, maxlen=self.num_strides_required)
        self.stride_duration_filter = filters.MovingAverage(
            window_size=num_strides_to_average)

    def estimate(self, data: Type[exoboot.Exo.DataContainer]):
        time_now = time.perf_counter()
        if data.did_heel_strike:
            stride_duration = time_now - self.time_of_last_heel_strike
            self.last_stride_durations.append(stride_duration)
            self.time_of_last_heel_strike = time_now
            self.mean_stride_duration = self.stride_duration_filter.filter(
                stride_duration)

        time_since_last_heel_strike = time_now - self.time_of_last_heel_strike
        if all(self.min_allowable_stride_duration < last_stride_duration
                < self.max_allowable_stride_duration for last_stride_duration
                in self.last_stride_durations) and (time_since_last_heel_strike
                                                    < 1.2 * self.max_allowable_stride_duration):
            gait_phase = min(1, time_since_last_heel_strike /
                             self.mean_stride_duration)
        else:
            gait_phase = None
        return gait_phase


class BilateralSlipDetectorParent():
    def __init__(self,
                 exo_1: Type[exoboot.Exo],
                 exo_2: Type[exoboot.Exo],
                 delay_ms: int = 0,
                 time_out: float = 5):
        self.exo_list = [exo_1, exo_2]
        self.slip_detect_active = False
        print('slip_detect_active: ', self.slip_detect_active)
        self.update_delay(delay_ms=delay_ms)
        self.refractory_timer = util.DelayTimer(time_out, true_until=True)

    def detect(self):
        slip_detected = self.detect_slip()
        if self.slip_detect_active and slip_detected:
            print('slip detected!')
            self.delay_timer.start()
        if self.delay_timer.check():
            self.delay_timer.reset()
            for exo in self.exo_list:
                exo.data.did_slip = True
        elif self.slip_detect_active and not slip_detected:
            for exo in self.exo_list:
                exo.data.did_slip = False
        elif not self.slip_detect_active:
            if slip_detected:
                print('slip detected, but detector inactive')
            for exo in self.exo_list:
                exo.data.did_slip = False

    def detect_slip(self) -> bool:
        raise ValueError(
            'Child class does not have a detect_slip function implemented yet')

    def update_delay(self, delay_ms):
        self.delay_timer = util.DelayTimer(delay_ms)

    def update_params_from_config(self, config: Type[config_util.ConfigurableConstants]):
        print('slip detection_active: ', config.SLIP_DETECT_ACTIVE)
        self.slip_detect_active = config.SLIP_DETECT_ACTIVE


class BilateralSlipDetectorFromSync(BilateralSlipDetectorParent):
    def __init__(self,
                 exo_1: Type[exoboot.Exo],
                 exo_2: Type[exoboot.Exo],
                 delay_ms=500,
                 time_out=5):
        super().__init__(exo_1=exo_1, exo_2=exo_2, delay_ms=delay_ms, time_out=time_out)

    def detect_slip(self):
        if self.refractory_timer.check():  # if recent slip
            slip_detected = False
        else:
            for exo in self.exo_list:
                if self.last_sync and not exo.data.sync:  # falling edge
                    slip_detected = True
                    self.refractory_timer.start()
                    break
                else:
                    slip_detected = False
        self.last_sync = exo.data.sync
        return slip_detected


class BilateralSlipDetectorIMU(BilateralSlipDetectorParent):
    def __init__(self,
                 exo_1: Type[exoboot.Exo],
                 exo_2: Type[exoboot.Exo],
                 acc_threshold_x: float = 0.2,  # 0.2
                 time_out: float = 5,
                 max_acc_y: float = 0.1,  # 0.1
                 max_acc_z: float = 0.1,  # 0.1
                 do_filter_accels=True,
                 required_seconds_of_stillness=0):
        super().__init__(exo_1, exo_2, delay_ms=0, time_out=time_out)
        self.acc_threshold_x = acc_threshold_x
        self.max_acc_y = max_acc_y
        self.max_acc_z = max_acc_z
        self.do_filter_accels = do_filter_accels
        self.filter_list = [[
            filters.Butterworth(N=2, Wn=0.01, btype='high'),
            filters.Butterworth(N=2, Wn=0.01, btype='high'),
            filters.Butterworth(N=2, Wn=0.01, btype='high')],
            [filters.Butterworth(N=2, Wn=0.01, btype='high'),
             filters.Butterworth(N=2, Wn=0.01, btype='high'),
             filters.Butterworth(N=2, Wn=0.01, btype='high')]]
        self.shuffling_timer = util.DelayTimer(
            delay_time=required_seconds_of_stillness,
            true_until=True)

    def detect_slip(self):
        for exo, filt in zip(self.exo_list, self.filter_list):
            data = exo.data
            accel_x = filt[0].filter(data.accel_x)
            accel_y = filt[1].filter(data.accel_y-1)
            accel_z = filt[2].filter(data.accel_z)
            data.gen_var1 = accel_x
            data.gen_var2 = accel_y
            data.gen_var3 = accel_z

            stillness_accel_limit = 10
            if abs(accel_x) > stillness_accel_limit or abs(accel_y-1) > stillness_accel_limit or abs(accel_z) > stillness_accel_limit:
                print('stop moving homie')
                self.shuffling_timer.start()  # restart the shuffling_timer if not still
            if not self.shuffling_timer.check():  # If not shuffling (if still)
                if (accel_x < -1*self.acc_threshold_x and
                    abs(accel_y) < self.max_acc_y and
                    abs(accel_z) < self.max_acc_z and
                        not self.refractory_timer.check()):
                    self.refractory_timer.start()
                    slip_detected = True
                    break
                else:
                    slip_detected = False
            else:
                slip_detected = False
        return slip_detected


'''Deprecated===================================
class SlipDetectorAP():
    def __init__(self,
                 data_container: Type[exoboot.Exo.DataContainer],
                 acc_threshold_x: float = 0.2,
                 time_out: float = 5,
                 max_acc_y: float = 0.1,
                 max_acc_z: float = 0.1,
                 do_filter_accels=True,
                 required_seconds_of_stillness=0,
                 return_did_slip=False,
                 start_active=False):
        self.data_container = data_container
        self.acc_threshold_x = acc_threshold_x
        self.max_acc_y = max_acc_y
        self.max_acc_z = max_acc_z
        self.refractory_timer = util.DelayTimer(time_out, true_until=True)
        self.do_filter_accels = do_filter_accels
        self.return_did_slip = return_did_slip
        self.accel_x_filter = filters.Butterworth(
            N=2, Wn=0.01, btype='high')
        self.accel_y_filter = filters.Butterworth(
            N=2, Wn=0.01, btype='high')
        self.accel_z_filter = filters.Butterworth(
            N=2, Wn=0.01, btype='high')
        self.slip_detect_active = start_active
        print('slip_detect_active: ', self.slip_detect_active)
        self.shuffling_timer = util.DelayTimer(
            delay_time=required_seconds_of_stillness)

    def detect(self, did_slip_overwrite=False):
        accel_x = self.data_container.accel_x
        accel_y = self.data_container.accel_y-1  # Remove effect of gravity
        accel_z = self.data_container.accel_z
        if self.do_filter_accels:
            accel_x = self.accel_x_filter.filter(accel_x)
            accel_y = self.accel_y_filter.filter(accel_y)
            accel_z = self.accel_z_filter.filter(accel_z)
            self.data_container.gen_var1 = accel_x
            self.data_container.gen_var2 = accel_y
            self.data_container.gen_var3 = accel_z

        stillness_accel_limit = 10

        if abs(accel_x) > stillness_accel_limit or abs(accel_y) > stillness_accel_limit or abs(accel_z) > stillness_accel_limit:
            self.shuffling_timer.start()  # restart the shuffling_timer if not still
        if did_slip_overwrite or (self.slip_detect_active and
                                  accel_x < -1*self.acc_threshold_x and
                                  abs(accel_y) < + self.max_acc_y and
                                  abs(accel_z) < self.max_acc_z and
                                  not self.refractory_timer.check()):
            self.refractory_timer.start()
            did_slip = True
        else:
            did_slip = False

        if self.return_did_slip:
            return did_slip
        else:
            self.data_container.did_slip = did_slip

    def update_params_from_config(self, config: Type[config_util.ConfigurableConstants]):
        print('slip detection_active: ', config.SLIP_DETECT_ACTIVE)
        self.slip_detect_active = config.SLIP_DETECT_ACTIVE'''
