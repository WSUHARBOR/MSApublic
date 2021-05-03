# This file should be Python3 stdlib only

from pathlib import Path
import subprocess
import socket


NETWORK_ATTEMPT_TIMEOUT: float = 3.0


def _can_connect_to_internet() -> bool:
    try:
        socket.setdefaulttimeout(NETWORK_ATTEMPT_TIMEOUT)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(('8.8.8.8', 53))
        return True
    except:
        return False


def _get_application_root() -> Path:
    api_directory: Path = Path(__file__).resolve().parent
    return api_directory.parent


def check_for_dependency_update() -> None:
    """Identify if any base dependencies have changed and install them"""
    if not _can_connect_to_internet():
        # If an update isn't possible we just have to hope it's fine.
        return
    root_directory_string = str(_get_application_root())
    try:
        subprocess.check_output(['pip3', 'install', '-r', f"{root_directory_string}/requirements.txt"])
    except subprocess.CalledProcessError:
        print("WARNING: Failed to perform update")


def perform_database_migration() -> None:
    try:
        from utils import get_conn
        db_conn = get_conn()
        cur = db_conn.cursor()
        root_directory = _get_application_root()
        sql_directory = root_directory / 'sql'
        for sql_file in list(sql_directory.glob('*.sql')):
            with sql_file.open('r') as f:
                for result in cur.executescript(f.read()):
                    print(result)
    except:
        print("WARNING: Failed during database migration. Attempting to run anyway")
