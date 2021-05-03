from typing import Iterable

from utils import get_conn, get_collection_filepath


def get_collection_name_from_id(collection_id: int) -> str:
    db_conn = get_conn()
    cur = db_conn.cursor()
    cur.execute("SELECT name FROM collections WHERE id = ?", (collection_id,))
    return cur.fetchone()[0]


def download_collection_data(collection_name: str) -> Iterable[str]:
    with open(get_collection_filepath(collection_name), 'r') as f:
        for line in f.readlines():
            yield line
