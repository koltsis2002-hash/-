-- Business Advisor. Preparation, client answers, internal notes and the final summary live in separate
-- tables so the client presentation can be served from answers + explicitly shared fields only.

CREATE TABLE advisor_presentations (
    id INTEGER PRIMARY KEY,
    contact_id INTEGER REFERENCES contacts (id) ON DELETE SET NULL,
    previous_id INTEGER REFERENCES advisor_presentations (id) ON DELETE SET NULL,
    meeting_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'in_progress', 'completed')),
    current_screen INTEGER NOT NULL DEFAULT 0 CHECK (current_screen BETWEEN 0 AND 9),
    current_question TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_advisor_presentations_updated ON advisor_presentations (updated_at);

CREATE TABLE advisor_preparations (
    presentation_id INTEGER PRIMARY KEY REFERENCES advisor_presentations (id) ON DELETE CASCADE,
    business_name TEXT,
    owner_name TEXT,
    industry TEXT,
    legal_form TEXT,
    employees INTEGER CHECK (employees IS NULL OR employees >= 0),
    partners INTEGER CHECK (partners IS NULL OR partners >= 0),
    facilities TEXT,
    existing_coverage TEXT,
    financial_obligations TEXT,
    interests TEXT NOT NULL DEFAULT '[]',
    shared_fields TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL
);

CREATE TABLE advisor_internal_notes (
    presentation_id INTEGER PRIMARY KEY REFERENCES advisor_presentations (id) ON DELETE CASCADE,
    notes TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE advisor_answers (
    presentation_id INTEGER NOT NULL REFERENCES advisor_presentations (id) ON DELETE CASCADE,
    question_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('answered', 'unknown', 'skipped')),
    value TEXT,
    note TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (presentation_id, question_id)
);

CREATE TABLE advisor_summaries (
    presentation_id INTEGER PRIMARY KEY REFERENCES advisor_presentations (id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    edited INTEGER NOT NULL DEFAULT 0 CHECK (edited IN (0, 1)),
    approved_at TEXT,
    updated_at TEXT NOT NULL
);

-- Local document index (official product PDFs in knowledge/products/), one row per page.
CREATE TABLE documents (
    id INTEGER PRIMARY KEY,
    filename TEXT NOT NULL UNIQUE,
    sha256 TEXT NOT NULL,
    page_count INTEGER NOT NULL CHECK (page_count >= 0),
    indexed_at TEXT NOT NULL
);

CREATE TABLE document_pages (
    document_id INTEGER NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    page INTEGER NOT NULL CHECK (page >= 1),
    text TEXT NOT NULL,
    folded TEXT NOT NULL,
    PRIMARY KEY (document_id, page)
);
