-- Timestamps are local-time ISO 8601 strings (YYYY-MM-DDTHH:MM[:SS]) so they sort and compare as text.

CREATE TABLE contacts (
    id INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL CHECK (trim(first_name) <> ''),
    last_name TEXT NOT NULL DEFAULT '',
    phone TEXT,
    email TEXT,
    company TEXT,
    source TEXT,
    status TEXT NOT NULL DEFAULT 'lead' CHECK (status IN ('lead', 'prospect', 'client', 'inactive')),
    product_interest TEXT,
    client_flag INTEGER NOT NULL DEFAULT 0 CHECK (client_flag IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_contacts_status ON contacts (status);

CREATE TABLE activities (
    id INTEGER PRIMARY KEY,
    contact_id INTEGER NOT NULL REFERENCES contacts (id) ON DELETE CASCADE,
    activity_type TEXT NOT NULL CHECK (activity_type IN ('call', 'meeting', 'email', 'message', 'note')),
    timestamp TEXT NOT NULL,
    outcome TEXT,
    notes TEXT,
    product TEXT,
    next_action TEXT,
    followup_date TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_activities_contact ON activities (contact_id, timestamp);
CREATE INDEX idx_activities_timestamp ON activities (timestamp);

CREATE TABLE follow_ups (
    id INTEGER PRIMARY KEY,
    contact_id INTEGER NOT NULL REFERENCES contacts (id) ON DELETE CASCADE,
    due_at TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high')),
    reason TEXT,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'done', 'cancelled')),
    completed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_follow_ups_status_due ON follow_ups (status, due_at);

CREATE TABLE appointments (
    id INTEGER PRIMARY KEY,
    contact_id INTEGER REFERENCES contacts (id) ON DELETE SET NULL,
    start_at TEXT NOT NULL,
    end_at TEXT,
    location TEXT,
    purpose TEXT,
    status TEXT NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'completed', 'cancelled', 'no_show')),
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (end_at IS NULL OR end_at >= start_at)
);
CREATE INDEX idx_appointments_start ON appointments (start_at);

CREATE TABLE goals (
    id INTEGER PRIMARY KEY,
    metric TEXT NOT NULL CHECK (metric IN (
        'calls', 'contacts', 'first_meetings', 'second_meetings', 'third_meetings', 'contracts', 'production'
    )),
    period_type TEXT NOT NULL CHECK (period_type IN ('year', 'month', 'week', 'day')),
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    target_value REAL NOT NULL CHECK (target_value >= 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (period_end >= period_start),
    UNIQUE (metric, period_type, period_start)
);

-- Production is a financial record: deleting a contact that has production is refused.
CREATE TABLE production (
    id INTEGER PRIMARY KEY,
    contact_id INTEGER NOT NULL REFERENCES contacts (id) ON DELETE RESTRICT,
    product TEXT NOT NULL,
    date TEXT NOT NULL,
    value REAL NOT NULL CHECK (value >= 0),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'issued', 'cancelled')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_production_date ON production (date);
