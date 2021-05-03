CREATE TABLE IF NOT EXISTS collections (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    start_s INTEGER,
    end_s INTEGER,
    description TEXT,
    uploaded BOOLEAN DEFAULT FALSE
)
