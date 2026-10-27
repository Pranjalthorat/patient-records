"""SQLite storage for patient records."""
import sqlite3
from contextlib import closing
from pathlib import Path

DB_PATH = Path(__file__).parent / "patients.db"

# Dates are stored as YYYY-MM-DD so they sort correctly; the UI shows dd/mm/yyyy.
# remarks stays NULL until the AI service has produced a prediction.
SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name     TEXT NOT NULL,
    date_of_birth TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    glucose       REAL NOT NULL,
    haemoglobin   REAL NOT NULL,
    cholesterol   REAL NOT NULL,
    remarks       TEXT,
    UNIQUE (full_name COLLATE NOCASE, date_of_birth)
);
"""


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with closing(_connect()) as conn:
        conn.executescript(SCHEMA)


def list_patients(search=""):
    sql = "SELECT * FROM patients"
    params = ()
    if search:
        sql += " WHERE full_name LIKE ? OR email LIKE ?"
        params = (f"%{search}%", f"%{search}%")
    sql += " ORDER BY id"
    with closing(_connect()) as conn:
        return conn.execute(sql, params).fetchall()


def get_patient(patient_id):
    with closing(_connect()) as conn:
        return conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()


def email_exists(email, exclude_id=None):
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT 1 FROM patients WHERE email = ? AND id IS NOT ?", (email, exclude_id)
        ).fetchone()
    return row is not None


def person_exists(full_name, date_of_birth, exclude_id=None):
    """Same name (ignoring case) and date of birth is treated as the same person."""
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT 1 FROM patients WHERE full_name = ? COLLATE NOCASE "
            "AND date_of_birth = ? AND id IS NOT ?",
            (full_name, date_of_birth, exclude_id),
        ).fetchone()
    return row is not None


def insert_patient(data):
    with closing(_connect()) as conn:
        cur = conn.execute(
            "INSERT INTO patients (full_name, date_of_birth, email, glucose, haemoglobin, cholesterol) "
            "VALUES (:full_name, :date_of_birth, :email, :glucose, :haemoglobin, :cholesterol)",
            data,
        )
        conn.commit()
        return cur.lastrowid


def update_patient(patient_id, data):
    with closing(_connect()) as conn:
        conn.execute(
            "UPDATE patients SET full_name = :full_name, date_of_birth = :date_of_birth, "
            "email = :email, glucose = :glucose, haemoglobin = :haemoglobin, "
            "cholesterol = :cholesterol WHERE id = :id",
            {**data, "id": patient_id},
        )
        conn.commit()


def set_remarks(patient_id, remarks):
    with closing(_connect()) as conn:
        conn.execute("UPDATE patients SET remarks = ? WHERE id = ?", (remarks, patient_id))
        conn.commit()


def delete_patient(patient_id):
    with closing(_connect()) as conn:
        conn.execute("DELETE FROM patients WHERE id = ?", (patient_id,))
        conn.commit()
