from typing import NamedTuple, Union
import datetime


class SensorValue(NamedTuple):
    """Describes the value and metadata for a single sensor reading"""
    name: str
    short_name: str
    unit: str
    value: Union[float, int]


class GPSStatus(NamedTuple):
    """Describes the value and metadata for an aggregated GPS reading"""
    timestamp: datetime.datetime
    latitude: float
    longitude: float
    altitude: float
    dop: float


class RecorderStatus(NamedTuple):
    # Describes the current status of a recording session
    collection_id: int
    collection_local_start_s: float
    collected_points: int
