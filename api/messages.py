from typing import NamedTuple, Union
import datetime


class SensorValue(NamedTuple):
    name: str
    short_name: str
    unit: str
    value: Union[float, int]


class GPSStatus(NamedTuple):
    timestamp: datetime.datetime
    latitude: float
    longitude: float
    altitude: float
    dop: float


class RecorderStatus(NamedTuple):
    collection_id: int
    collection_local_start_s: float
    collected_points: int
