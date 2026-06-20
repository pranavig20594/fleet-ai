CREATE TABLE IF NOT EXISTS trucks (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    number  TEXT UNIQUE NOT NULL,
    vin     TEXT,
    plate   TEXT,
    make    TEXT,
    model   TEXT,
    year    INTEGER,
    status  TEXT DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS drivers (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    license_number TEXT,
    truck_id       INTEGER REFERENCES trucks(id)
);

CREATE TABLE IF NOT EXISTS trailers (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    number   TEXT UNIQUE,
    plate    TEXT,
    truck_id INTEGER REFERENCES trucks(id)
);

CREATE TABLE IF NOT EXISTS documents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    type        TEXT NOT NULL,  -- fuel_receipt | title | tax_form | maintenance_receipt | registration | insurance | inspection | other
    truck_id    INTEGER REFERENCES trucks(id),
    driver_id   INTEGER REFERENCES drivers(id),
    trailer_id  INTEGER REFERENCES trailers(id),
    date        TEXT,           -- YYYY-MM-DD
    amount      REAL,
    vendor      TEXT,
    description TEXT,
    file_path   TEXT,
    raw_text    TEXT,
    file_hash   TEXT UNIQUE,
    ingested_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_docs_truck ON documents(truck_id);
CREATE INDEX IF NOT EXISTS idx_docs_type  ON documents(type);
CREATE INDEX IF NOT EXISTS idx_docs_date  ON documents(date);
