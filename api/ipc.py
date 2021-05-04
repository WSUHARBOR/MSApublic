import multiprocessing
from typing import Any
import time

from messages import SensorValue, GPSStatus, RecorderStatus

# Construct a manager server process pre-fork
_manager = multiprocessing.Manager()


class BaseInterface:
    """High level communication for performing inter-process communication"""

    def __init__(self, message_type) -> None:
        """Construct a new interface using a pre-fork message type. Messages must be imported first!"""
        self._message_type = message_type
        self._lock = _manager.Lock()  # State control lock
        self._state = _manager.Namespace()  # Dynamic object for transmitting state

        # Common communication channels used in all processes
        self._state.should_record = False
        self._state.is_recording = False
        self._state.current_state = None
        self._state.state_time = 0.0

    def signal_should_record(self, should_record: bool) -> None:
        """(from parent) Instruct the child process to start a recording session"""
        with self._lock:
            self._state.should_record = should_record

    def acknowledge_is_recording(self, is_recording: bool) -> None:
        """(from child) Acknowledge that recording has started"""
        with self._lock:
            self._state.is_recording = is_recording

    def get_recording_state(self) -> (bool, bool):
        """(from anywhere) Get the current instruction, acknowledgement of recording"""
        with self._lock:
            return self._state.should_record, self._state.is_recording

    def set_current_state(self, state_object: Any) -> None:
        """(from child) Describe the current instantaneous state"""
        with self._lock:
            self._state.current_state = state_object
            self._state.state_time = time.time()

    def get_current_state(self) -> (Any, float):
        """(from anywhere) Get the current state object and time of state"""
        with self._lock:
            current_state = self._state.current_state
            time_since_state = time.time() - self._state.state_time
        return current_state, time_since_state


# Construct IPC interfaces to each of the major child processes
sensor_interface = BaseInterface(SensorValue)
gps_interface = BaseInterface(GPSStatus)
recorder_interface = BaseInterface(RecorderStatus)
