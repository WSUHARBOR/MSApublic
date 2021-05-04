from multiprocessing import Process
import time
from datetime import datetime
from typing import Optional
import logging

import pynmea2
import smbus2

from ipc import gps_interface
from messages import GPSStatus

# I2C bus can be found by running `ls /dev/i2c*` on the pi
GPS_I2C_BUS: int = 1
# I2C address can be found by running `sudo i2cdetect -y 1` on the pi
GPS_I2C_ADDRESS: int = 0x42

# Registers described in https://www.u-blox.com/en/docs/UBX-16012619
AVAILABLE_BYTES_REGISTER: int = 0xFD
DATA_STREAM_REGISTER: int = 0xFF


class NoGPSData(RuntimeError):
    """Non-critical error for missing GPS data"""


class GPSReceiver(Process):
    """Process for receiving and parsing data from the GPS sensor"""

    @staticmethod
    def get_current_status() -> (GPSStatus, float):
        """Describe the current state of the GPS, including last datapoint"""
        current_state, latency_s = gps_interface.get_current_state()
        if not current_state or current_state.latitude == 0.0:
            raise NoGPSData()
        return current_state, latency_s

    def run(self) -> None:
        """Main loop in forked process"""
        logging.info("Starting GPS Daemon")

        # Aggregated state storage for parsed GPS data:
        timestamp: datetime = datetime.utcnow()
        latitude: float = 0.0
        longitude: float = 0.0
        altitude: float = 0.0
        dop: float = 0.0

        bus: Optional[smbus2.SMBus] = None
        try:
            # Connect to the I2C bus
            bus = get_gps_bus()
            logging.info("Successfully initialized GPS Daemon")
            buffer = ''
            while True:
                # Get new GPS data
                try:
                    # Ask the GPS for how much data we can read from it
                    available_bytes = bus.read_byte_data(GPS_I2C_ADDRESS, AVAILABLE_BYTES_REGISTER)
                except OSError:
                    # Restart the read operation
                    continue
                if not available_bytes:
                    continue
                # Read the next block of data
                while available_bytes > 0:
                    # Read data in blocks of maximum 32 bytes
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
                        # Buffer up characters into a string until a whole sentence is formed
                        buffer += next_character
                        # Sentences are separated by a newline character
                        if next_character == '\n':
                            try:
                                # Attempt to parse the string
                                sentence = pynmea2.parse(buffer)

                                # Each sentence contains a different selection of fields, check that we care about
                                timestamp = getattr(sentence, 'datetime', timestamp)
                                # Attempt to cast the floating point values to check for parsing errors
                                latitude = float(getattr(sentence, 'latitude', latitude))
                                longitude = float(getattr(sentence, 'longitude', longitude))
                                altitude = float(getattr(sentence, 'altitude', altitude))
                                dop = float(getattr(sentence, 'pdop', dop))

                                # Update the current state with the aggregated values from this and previous sessions
                                gps_interface.set_current_state(GPSStatus(
                                    timestamp=timestamp,
                                    latitude=latitude,
                                    longitude=longitude,
                                    altitude=altitude,
                                    dop=dop
                                ))
                            except (pynmea2.ChecksumError, pynmea2.ParseError, TypeError, ValueError):
                                # Ignore transport errors
                                pass
                            buffer = ''
                # Don't totally consume the GIL
                time.sleep(0.001)
        finally:
            if bus is not None:
                bus.close()


def get_gps_bus() -> smbus2.SMBus:
    """Get a connection to the local I2C bus with provided GPS sensor"""
    for _ in range(10):
        try:
            return smbus2.SMBus(GPS_I2C_BUS)
        except PermissionError:
            # Attempt 10 times over 60 seconds
            time.sleep(6)
    raise RuntimeError("Could not connect to GPS bus")


# Construct a GPS object for later command and control
gps_receiver = GPSReceiver()
