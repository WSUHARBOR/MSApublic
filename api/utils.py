from pathlib import Path
import os

import pysqlite3


# Get the location to store collection files from the environment variable $DATA_DIRECTORY
DATA_DIRECTORY: str = os.environ.get("DATA_DIRECTORY", ".")


def get_application_root() -> Path:
    """Get the root directory of the MSAv2 application"""
    api_directory: Path = Path(__file__).resolve().parent
    return api_directory.parent


def get_collection_filepath(collection_name: str) -> str:
    """Resolve a collection file based on collection name"""
    return os.path.join(DATA_DIRECTORY, f"{collection_name}.csv")


def get_conn():
    """Connect to the local database and return a connection object"""
    return pysqlite3.connect(f"{str(get_application_root())}/storage.db")
