from multiprocessing import Process
from typing import Optional, List, Callable
import time
import logging

import serial
from gpiozero import LED

from messages import SensorValue
from ipc import sensor_interface


def _unsigned_short_parser(byte_0: int, byte_1: int) -> int:
    return byte_0 * 256 + byte_1


def _fixed_multiplier_parser(multiplier: float) -> Callable[[int, int], float]:
    def annotated_parser(byte_0: int, byte_1: int) -> float:
        return _unsigned_short_parser(byte_0, byte_1) * multiplier

    return annotated_parser


def _celsius_parser(byte_0: int, byte_1: int) -> float:
    return float(_unsigned_short_parser(byte_0, byte_1) - 500) * 0.1


def _unsigned_char_parser(byte_0: int) -> int:
    return byte_0


class RawDataClass:
    def __init__(self, name: str, short_name: str, unit: str,
                 byte_0: int, byte_1: Optional[int] = None,
                 parser: Callable = _unsigned_short_parser) -> None:
        self.name: str = name
        self.short_name: str = short_name
        self.unit: str = unit
        self._parser: Callable = parser
        self._byte_0: int = byte_0
        self._byte_1: Optional[int] = byte_1

    def __call__(self, data_packet: bytes) -> SensorValue:
        if self._byte_1 is None:
            value = self._parser(data_packet[self._byte_0])
        else:
            value = self._parser(data_packet[self._byte_0], data_packet[self._byte_1])
        return SensorValue(self.name, self.short_name, self.unit, value)


# Winsen datasheet: https://www.winsen-sensor.com/sensors/co2-sensor/zphs01b.html
WINSEN_DEVICE: str = '/dev/ttyAMA0'
WINSEN_BAUDRATE: int = 9600
WINSEN_CONNECTION_TIMEOUT: float = 2.0
WINSEN_READ_COMMAND: bytes = b'\xff\x01\x86\x00\x00\x00\x00\x00\x79'
WINSEN_RESPONSE_SIZE: int = 26
WINSEN_DATAPACKET: List[RawDataClass] = [
    RawDataClass('PM 1.0', 'pm_1_0', 'μg/m3', 2, 3),
    RawDataClass('PM 2.5', 'pm_2_5', 'μg/m3', 4, 5),
    RawDataClass('PM 10', 'pm_10', 'μg/m3', 6, 7),
    RawDataClass('Carbon Dioxide', 'co2', 'ppm', 8, 9),
    RawDataClass('VOC', 'voc', 'grade', 10, parser=_unsigned_char_parser),
    RawDataClass('Temperature', 'temp', '°C', 11, 12, parser=_celsius_parser),
    RawDataClass('Humidity', 'humidity', '%RH', 13, 14),
    RawDataClass('Formaldehyde', 'ch2o', 'mg/m3', 15, 16, parser=_fixed_multiplier_parser(0.001)),
    RawDataClass('Carbon Monoxide', 'co', 'ppm', 17, 18, parser=_fixed_multiplier_parser(0.1)),
    RawDataClass('Ozone', 'o3', 'ppm', 19, 20, parser=_fixed_multiplier_parser(0.01)),
    RawDataClass('Nitrogen Dioxide', 'no2', 'ppm', 21, 22, parser=_fixed_multiplier_parser(0.01)),
]

DATA_POLL_RATE: float = 1.0


class ParseError(RuntimeError):
    pass


class NoSensorData(RuntimeError):
    pass


class SensorReceiver(Process):
    @staticmethod
    def get_current_status() -> (List[SensorValue], float):
        sensor_data, latency_s = sensor_interface.get_current_state()
        if not sensor_data:
            raise NoSensorData()
        return sensor_data, latency_s

    @staticmethod
    def get_recording_state() -> (bool, bool):
        return sensor_interface.get_recording_state()

    @staticmethod
    def start_collect() -> None:
        sensor_interface.signal_should_record(True)

    @staticmethod
    def stop_collect() -> None:
        sensor_interface.signal_should_record(False)

    def run(self) -> None:
        logging.info("Starting Sensor Daemon")
        winsen_connection = get_winsen_connection()
        collection_light = LED(16)
        last_read_s: float = 0.0
        logging.info("Successfully initialized Sensor Daemon")
        while True:
            should_collect, is_recording = sensor_interface.get_recording_state()
            if not should_collect:
                if is_recording:
                    sensor_interface.acknowledge_is_recording(False)
                time.sleep(0.1)
                continue
            if not is_recording:
                sensor_interface.acknowledge_is_recording(True)

            if time.time() >= (last_read_s + DATA_POLL_RATE):
                collection_light.on()
                winsen_connection.write(WINSEN_READ_COMMAND)
                data_packet = winsen_connection.read(WINSEN_RESPONSE_SIZE)
                if data_packet:
                    try:
                        sensor_values = self._parse_data_packet(data_packet)
                    except ParseError:
                        continue
                    sensor_interface.set_current_state(sensor_values)
                last_read_s = time.time()
                collection_light.off()
            time.sleep(0.01)

    @staticmethod
    def _parse_data_packet(raw_packet: bytes) -> List[SensorValue]:
        sensor_values = []
        for data_class in WINSEN_DATAPACKET:
            sensor_values.append(data_class(raw_packet))
        return sensor_values


def get_winsen_connection() -> serial.Serial:
    for _ in range(10):
        try:
            winsen_connection = serial.Serial(port=WINSEN_DEVICE,
                                              baudrate=WINSEN_BAUDRATE,
                                              timeout=WINSEN_CONNECTION_TIMEOUT,
                                              writeTimeout=WINSEN_CONNECTION_TIMEOUT)
            return winsen_connection
        except serial.serialutil.SerialException:
            time.sleep(6)
    raise RuntimeError("Could not connect to Winsen device")


sensor_receiver = SensorReceiver()
