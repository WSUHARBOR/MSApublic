import multiprocessing
from typing import Any
import time

from messages import SensorValue, GPSStatus, RecorderStatus


_manager = multiprocessing.Manager()


class BaseInterface:
    def __init__(self, message_type) -> None:
        self._message_type = message_type
        self._lock = _manager.Lock()
        self._state = _manager.Namespace()
        self._state.should_record = False
        self._state.is_recording = False
        self._state.current_state = None
        self._state.state_time = 0.0

    def signal_should_record(self, should_record: bool) -> None:
        with self._lock:
            self._state.should_record = should_record

    def acknowledge_is_recording(self, is_recording: bool) -> None:
        with self._lock:
            self._state.is_recording = is_recording

    def get_recording_state(self) -> (bool, bool):
        with self._lock:
            return self._state.should_record, self._state.is_recording

    def set_current_state(self, state_object: Any) -> None:
        with self._lock:
            self._state.current_state = state_object
            self._state.state_time = time.time()

    def get_current_state(self) -> (Any, float):
        with self._lock:
            current_state = self._state.current_state
            time_since_state = time.time() - self._state.state_time
        return current_state, time_since_state


sensor_interface = BaseInterface(SensorValue)
gps_interface = BaseInterface(GPSStatus)
recorder_interface = BaseInterface(RecorderStatus)
