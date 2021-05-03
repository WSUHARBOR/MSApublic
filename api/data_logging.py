from typing import Optional, List, Dict, Any, NamedTuple
from multiprocessing import Process
import time
from datetime import datetime
import os
import logging
import platform

from utils import get_conn, get_collection_filepath
from gps import gps_receiver, NoGPSData
from sensors import sensor_receiver, NoSensorData, WINSEN_DATAPACKET
from ipc import recorder_interface
from messages import RecorderStatus


class StoredDataType(NamedTuple):
    name: str
    short_name: str
    unit: str


DATAPOINT_COLLECTION_INTERVAL_S: float = 7.0
KNOWN_DATA_COLUMNS = [StoredDataType(x.name, x.short_name, x.unit) for x in WINSEN_DATAPACKET] + [
    StoredDataType('Timestamp', 'timestamp', 'ISO 8601'),
    StoredDataType('Mission Elapsed Time', 'met', 's'),
    StoredDataType('Latitude', 'lat', 'degrees'),
    StoredDataType('Longitude', 'lon', 'degrees'),
    StoredDataType('Altitude', 'alt', 'm'),
    StoredDataType('Position Dilution of Precision', 'dop', ''),
]


def start_collection(description: Optional[str] = None) -> int:
    recorder.start_collection()
    # Wait 60 seconds for recording to start
    for _ in range(600):
        should_record, is_recording = recorder.get_recording_state()
        if not should_record:
            logging.warning("Recording signal has been cancelled during start wait")
            return -1

        if is_recording:
            collection_id = recorder.get_current_collection_id()
            if description:
                db_conn = get_conn()
                cur = db_conn.cursor()
                cur.execute("""
                    UPDATE collections
                    SET description = ?
                    WHERE id = ?
                """, (description, collection_id))
                db_conn.commit()
                db_conn.close()
            return collection_id
        time.sleep(0.1)
    raise RuntimeError("Recorder could not start")


def stop_collection() -> int:
    recorder.stop_collection()
    # Wait 60 seconds for recording to stop
    for _ in range(600):
        should_record, is_recording = recorder.get_recording_state()
        if should_record:
            logging.warning("Recording signal has been cancelled during stop wait")
            return -1

        if not is_recording:
            collection_id = recorder.get_current_collection_id()
            return collection_id
        time.sleep(0.1)
    raise RuntimeError("Recorder could not stop")


def get_collection_list() -> List[Dict[str, Any]]:
    db_conn = get_conn()
    cur = db_conn.cursor()
    cur.execute("""
        SELECT id, name, start_s, end_s, description, uploaded
        FROM collections
        ORDER BY start_s DESC
    """)
    collections_raw = cur.fetchall()
    collection_response = []
    for collection in collections_raw:
        collection_id, name, start_s, end_s, description, uploaded = collection
        collection_response.append({
            'id': collection_id,
            'name': name,
            'start_s': start_s,
            'end_s': end_s,
            'description': description,
            'uploaded': uploaded,
        })
    db_conn.close()
    return collection_response


def get_collection_details(collection_id: int) -> Dict[str, Any]:
    db_conn = get_conn()
    cur = db_conn.cursor()
    cur.execute("""
        SELECT name, start_s, end_s, uploaded, description
        FROM collections
        WHERE id = ?
    """, (collection_id,))
    collection = cur.fetchone()
    name, start_s, end_s, uploaded, description = collection
    db_conn.close()
    collection_filename = get_collection_filepath(name)
    if not os.path.exists(collection_filename):
        data = []
    else:
        with open(collection_filename, 'r') as f:
            all_data = f.readlines()
        if not all_data:
            data = []
        else:
            data_map = {}
            column_short_names = all_data[0].strip().split(',')
            date_idx = column_short_names.index('timestamp')
            met_idx = column_short_names.index('met')
            for column in KNOWN_DATA_COLUMNS:
                data_map[column.short_name] = {
                    'name': column.name,
                    'short_name': column.short_name,
                    'unit': column.unit,
                    'points': []
                }
            for row in all_data[1:]:
                entries = row.strip().split(',')
                raw_timestamp = entries[date_idx]
                for idx, value in enumerate(entries):
                    if idx in [date_idx, met_idx]:
                        continue
                    try:
                        typed_value = float(value)
                    except:
                        typed_value = value
                    data_map[column_short_names[idx]]['points'].append({
                        'ts': raw_timestamp,
                        'value': typed_value
                    })
            data = [x for x in data_map.values() if x['points']]
    return {
        'id': collection_id,
        'name': name,
        'start_s': start_s,
        'end_s': end_s,
        'uploaded': uploaded,
        'description': description,
        'data': data,
    }


class Recorder(Process):
    def __init__(self):
        # Used only in fork
        self._collection_name: str = 'UNKNOWN'
        self._true_start_s: float = 0.0

        super(Recorder, self).__init__()

    @staticmethod
    def start_collection() -> None:
        recorder_interface.signal_should_record(True)

    @staticmethod
    def stop_collection() -> None:
        recorder_interface.signal_should_record(False)

    @staticmethod
    def get_recording_state() -> bool:
        return recorder_interface.get_recording_state()

    @staticmethod
    def get_current_collection_id() -> int:
        return recorder_interface.get_current_state()[0].collection_id

    @staticmethod
    def get_elapsed_s() -> float:
        return time.time() - recorder_interface.get_current_state()[0].collection_local_start_s

    @staticmethod
    def get_datapoints() -> int:
        return recorder_interface.get_current_state()[0].collected_points

    def run(self) -> None:
        logging.info("Starting Recorder Daemon")
        last_datapoint_s: float = 0.0
        current_collection_id: int = -1
        current_datapoints: int = 0
        current_local_start_s: float = 0.0
        failed_start_cycles: int = 0
        db_conn = get_conn()
        while True:
            should_be_recording, currently_recording = recorder_interface.get_recording_state()
            if not currently_recording:
                if not should_be_recording:
                    # Nothing to do
                    time.sleep(0.5)
                    continue

                if failed_start_cycles > 20:
                    logging.error("Failed to start collecting")
                    recorder_interface.signal_should_record(False)
                    continue

                # Start sensor collection
                if not sensor_receiver.get_recording_state()[0]:
                    sensor_receiver.start_collect()
                    time.sleep(1.0)

                # Check for sensor and gps data
                try:
                    collection_datetime = self._current_time_from_gps()
                except NoGPSData:
                    logging.warning("No GPS lock, skipping collection start cycle")
                    failed_start_cycles += 1
                    time.sleep(0.5)
                    continue
                try:
                    sensor_receiver.get_current_status()
                except NoSensorData:
                    logging.warning("No sensor data, skipping collection start cycle")
                    failed_start_cycles += 1
                    time.sleep(0.5)
                    continue

                # Start a new recording session
                failed_start_cycles = 0
                self._true_start_s = collection_datetime.timestamp()
                self._collection_name: str = collection_datetime.strftime("%Y_%m_%d-%H_%M_%S") + f"-{platform.node()}"
                cur = db_conn.cursor()
                cur.execute("""
                    INSERT INTO collections(name, start_s)
                    VALUES (?, ?)
                """, (self._collection_name, self._true_start_s))
                current_collection_id: int = cur.lastrowid
                db_conn.commit()
                current_local_start_s = time.time()
                current_datapoints = 0
                recorder_interface.set_current_state(RecorderStatus(current_collection_id,
                                                                    current_local_start_s,
                                                                    current_datapoints))
                recorder_interface.acknowledge_is_recording(True)

            if not should_be_recording:
                # Close out existing collection
                cur = db_conn.cursor()
                try:
                    end_s = self._current_time_from_gps().timestamp()
                except NoGPSData:
                    logging.warning("No GPS lock, skipping cycle")
                    time.sleep(0.5)
                    continue
                cur.execute("""
                    UPDATE collections
                    SET end_s = ?
                    WHERE id = ?
                """, (end_s, current_collection_id))
                db_conn.commit()
                sensor_receiver.stop_collect()
                recorder_interface.acknowledge_is_recording(False)
                continue

            if time.time() >= (last_datapoint_s + DATAPOINT_COLLECTION_INTERVAL_S):
                self._record_new_datapoint()
                current_datapoints += 1
                recorder_interface.set_current_state(RecorderStatus(current_collection_id,
                                                                    current_local_start_s,
                                                                    current_datapoints))
                last_datapoint_s = time.time()

    @staticmethod
    def _current_time_from_gps() -> datetime:
        return gps_receiver.get_current_status()[0].timestamp

    def _record_new_datapoint(self) -> None:

        # Get Winsen sensor data
        try:
            sensor_data, sensor_latency_s = sensor_receiver.get_current_status()
        except NoSensorData:
            logging.warning("No sensor data, skipping recording point")
            return
        if sensor_latency_s > 10.0:
            logging.warning(f"Sensor latency currently at {sensor_latency_s} seconds")

        # Get GPS data
        try:
            gps_data, gps_latency_s = gps_receiver.get_current_status()
        except NoGPSData:
            logging.warning("No GPS data, skipping recording point")
            return
        if gps_latency_s > 10.0:
            logging.warning(f"GPS latency currently at {gps_latency_s} seconds")

        # Write data to file
        collection_filename = get_collection_filepath(self._collection_name)
        mission_time: float = gps_data.timestamp.timestamp() - self._true_start_s

        if not os.path.exists(collection_filename):
            column_names = ['timestamp', 'met', 'lat', 'lon', 'alt', 'dop'] + [x.short_name for x in sensor_data]
            with open(collection_filename, 'w') as f:
                f.write(f"{','.join(column_names)}\n")

        columns = [gps_data.timestamp.isoformat(), mission_time, gps_data.latitude, gps_data.longitude,
                   gps_data.altitude, gps_data.dop] + [x.value for x in sensor_data]
        with open(collection_filename, 'a') as f:
            f.writelines(f"{','.join(str(x) for x in columns)}\n")


recorder = Recorder()
