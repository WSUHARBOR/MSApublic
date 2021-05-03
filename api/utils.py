from pathlib import Path
import os

import pysqlite3


DATA_DIRECTORY: str = os.environ.get("DATA_DIRECTORY", ".")


def get_application_root() -> Path:
    api_directory: Path = Path(__file__).resolve().parent
    return api_directory.parent


def get_collection_filepath(collection_name: str) -> str:
    return os.path.join(DATA_DIRECTORY, f"{collection_name}.csv")


def get_conn():
    return pysqlite3.connect(f"{str(get_application_root())}/storage.db")
