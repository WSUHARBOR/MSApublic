from multiprocessing import Process
import time
from datetime import datetime
from typing import Optional
import logging

import pynmea2
import smbus2

from ipc import gps_interface
from messages import GPSStatus

GPS_I2C_BUS: int = 1
GPS_I2C_ADDRESS: int = 0x42
AVAILABLE_BYTES_REGISTER: int = 0xFD
DATA_STREAM_REGISTER: int = 0xFF


class NoGPSData(RuntimeError):
    pass


class GPSReceiver(Process):
    @staticmethod
    def get_current_status() -> (GPSStatus, float):
        current_state, latency_s = gps_interface.get_current_state()
        if not current_state or current_state.latitude == 0.0:
            raise NoGPSData()
        return current_state, latency_s

    def run(self) -> None:
        logging.info("Starting GPS Daemon")
        timestamp: datetime = datetime.utcnow()
        latitude: float = 0.0
        longitude: float = 0.0
        altitude: float = 0.0
        dop: float = 0.0

        bus: Optional[smbus2.SMBus] = None
        try:
            bus = get_gps_bus()
            logging.info("Successfully initialized GPS Daemon")
            buffer = ''
            while True:
                # Get new GPS data
                try:
                    available_bytes = bus.read_byte_data(GPS_I2C_ADDRESS, AVAILABLE_BYTES_REGISTER)
                except OSError:
                    # Restart the read operation
                    continue
                if not available_bytes:
                    continue
                # Read the next block of data
                while available_bytes > 0:
                    bytes_read = min(available_bytes, 32)
                    try:
                        block = bus.read_i2c_block_data(GPS_I2C_ADDRESS, DATA_STREAM_REGISTER, bytes_read)
                    except OSError:
                        # Restart the read operation
                        continue
                    available_bytes -= available_bytes
                    for b in block:
                        if b == 0xFF:
                            # Skip non-value bytes
                            continue
                        next_character = chr(b)
                        buffer += next_character
                        if next_character == '\n':
                            try:
                                sentence = pynmea2.parse(buffer)
                                timestamp = getattr(sentence, 'datetime', timestamp)
                                latitude = float(getattr(sentence, 'latitude', latitude))
                                longitude = float(getattr(sentence, 'longitude', longitude))
                                altitude = float(getattr(sentence, 'altitude', altitude))
                                dop = float(getattr(sentence, 'pdop', dop))

                                gps_interface.set_current_state(GPSStatus(
                                    timestamp=timestamp,
                                    latitude=latitude,
                                    longitude=longitude,
                                    altitude=altitude,
                                    dop=dop
                                ))
                            except (pynmea2.ChecksumError, pynmea2.ParseError, TypeError):
                                # Ignore transport errors
                                pass
                            buffer = ''
                # Don't totally consume the GIL
                time.sleep(0.001)
        finally:
            if bus is not None:
                bus.close()


def get_gps_bus() -> smbus2.SMBus:
    for _ in range(10):
        try:
            return smbus2.SMBus(GPS_I2C_BUS)
        except PermissionError:
            time.sleep(6)
    raise RuntimeError("Could not connect to GPS bus")


gps_receiver = GPSReceiver()
