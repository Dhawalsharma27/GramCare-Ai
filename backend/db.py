import sqlite3
import json
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

DB_PATH = Path(__file__).resolve().parent / "gramcare.db"

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 1. Patients Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                phone TEXT,
                village TEXT,
                age INTEGER,
                gender TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # 2. Triage Records Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS triage_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT,
                patient_name TEXT,
                age INTEGER,
                gender TEXT,
                village TEXT,
                symptoms TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                confidence REAL NOT NULL,
                condition TEXT,
                precautions TEXT,
                action_advice TEXT,
                generic_medicines TEXT,
                longitudinal_alert TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (patient_id) REFERENCES patients (patient_id)
            )
        """)

        # Migration check: Ensure new columns exist if table was already created
        cursor.execute("PRAGMA table_info(triage_records)")
        existing_cols = {col["name"] for col in cursor.fetchall()}
        if "patient_id" not in existing_cols:
            cursor.execute("ALTER TABLE triage_records ADD COLUMN patient_id TEXT")
        if "generic_medicines" not in existing_cols:
            cursor.execute("ALTER TABLE triage_records ADD COLUMN generic_medicines TEXT")
        if "longitudinal_alert" not in existing_cols:
            cursor.execute("ALTER TABLE triage_records ADD COLUMN longitudinal_alert TEXT")

        # 3. Clinician Feedback Records
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id INTEGER,
                user_name TEXT,
                rating INTEGER,
                corrected_risk TEXT,
                comments TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (record_id) REFERENCES triage_records (id)
            )
        """)
        conn.commit()

# --- Patient Management Functions ---

def get_or_create_patient(
    name: str,
    phone: Optional[str] = None,
    village: Optional[str] = None,
    age: Optional[int] = None,
    gender: Optional[str] = None
) -> Dict[str, Any]:
    """Finds an existing patient by phone or (name + village), or creates a new one with auto-generated ID."""
    clean_name = name.strip()
    clean_phone = phone.strip() if phone else None
    clean_village = village.strip() if village else None

    with get_db() as conn:
        cursor = conn.cursor()
        patient = None

        if clean_phone:
            cursor.execute("SELECT * FROM patients WHERE phone = ?", (clean_phone,))
            patient = cursor.fetchone()

        if not patient and clean_name and clean_village:
            cursor.execute(
                "SELECT * FROM patients WHERE LOWER(name) = LOWER(?) AND LOWER(village) = LOWER(?)",
                (clean_name, clean_village)
            )
            patient = cursor.fetchone()

        if patient:
            # Update fields if new details provided
            pid = patient["patient_id"]
            cursor.execute("""
                UPDATE patients 
                SET age = COALESCE(?, age), gender = COALESCE(?, gender), village = COALESCE(?, village), phone = COALESCE(?, phone)
                WHERE patient_id = ?
            """, (age, gender, clean_village, clean_phone, pid))
            conn.commit()
            cursor.execute("SELECT * FROM patients WHERE patient_id = ?", (pid,))
            return dict(cursor.fetchone())

        # Generate unique patient ID: GC-1001, GC-1002, etc.
        cursor.execute("SELECT MAX(id) as max_id FROM patients")
        max_row = cursor.fetchone()
        next_num = 1001 + (max_row["max_id"] or 0)
        patient_id = f"GC-{next_num}"

        now_str = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO patients (patient_id, name, phone, village, age, gender, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (patient_id, clean_name, clean_phone, clean_village, age, gender, now_str))
        conn.commit()

        cursor.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,))
        return dict(cursor.fetchone())

def list_patients(search: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Lists patients with recent visit count and latest risk status."""
    with get_db() as conn:
        cursor = conn.cursor()
        query = """
            SELECT p.*, 
                   COUNT(t.id) as visit_count,
                   MAX(t.created_at) as last_visit,
                   (SELECT t2.risk_level FROM triage_records t2 WHERE t2.patient_id = p.patient_id ORDER BY t2.id DESC LIMIT 1) as latest_risk,
                   (SELECT t2.condition FROM triage_records t2 WHERE t2.patient_id = p.patient_id ORDER BY t2.id DESC LIMIT 1) as latest_condition
            FROM patients p
            LEFT JOIN triage_records t ON p.patient_id = t.patient_id
        """
        params = []
        if search:
            query += " WHERE LOWER(p.name) LIKE ? OR LOWER(p.village) LIKE ? OR p.patient_id LIKE ? OR p.phone LIKE ?"
            term = f"%{search.lower().strip()}%"
            params.extend([term, term, term, term])

        query += " GROUP BY p.patient_id ORDER BY p.id DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

def get_patient_by_id(patient_id: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_patient_consultations(patient_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Returns all past triage consultations for a patient."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM triage_records 
            WHERE patient_id = ? 
            ORDER BY id DESC LIMIT ?
        """, (patient_id, limit))
        records = []
        for r in cursor.fetchall():
            rec = dict(r)
            try:
                rec["precautions"] = json.loads(rec["precautions"]) if rec["precautions"] else []
            except Exception:
                rec["precautions"] = []
            try:
                rec["generic_medicines"] = json.loads(rec["generic_medicines"]) if rec["generic_medicines"] else []
            except Exception:
                rec["generic_medicines"] = []
            records.append(rec)
        return records

# --- Longitudinal Risk Engine ---

def evaluate_longitudinal_risk(
    patient_id: Optional[str],
    current_symptoms: str,
    baseline_risk: str
) -> Dict[str, Any]:
    """
    Checks previous consultations within the last 30-60 days.
    If key symptoms recur or worsen across multiple visits, the system escalates
    the risk level and alerts the healthcare worker of a potential progressing or chronic condition.
    """
    if not patient_id:
        return {
            "escalated_risk": baseline_risk,
            "is_escalated": False,
            "recurrence_count": 0,
            "recurring_symptoms": [],
            "alert_message": None,
            "previous_visits_count": 0
        }

    past_records = get_patient_consultations(patient_id, limit=10)
    if not past_records:
        return {
            "escalated_risk": baseline_risk,
            "is_escalated": False,
            "recurrence_count": 0,
            "recurring_symptoms": [],
            "alert_message": None,
            "previous_visits_count": 0
        }

    # Extract non-trivial symptom words (>3 chars)
    stop_words = {"have", "with", "from", "days", "week", "mild", "pain", "feel", "also", "some", "time"}
    current_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', current_symptoms.lower())) - stop_words

    recurring_found = set()
    relevant_visits = 0

    # Look back over recent visits (last 60 days)
    cutoff = datetime.now() - timedelta(days=60)
    for rec in past_records:
        try:
            visit_date = datetime.fromisoformat(rec["created_at"])
            if visit_date < cutoff:
                continue
        except Exception:
            pass

        past_sym_text = rec["symptoms"].lower()
        past_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', past_sym_text)) - stop_words
        overlap = current_words.intersection(past_words)
        if overlap:
            recurring_found.update(overlap)
            relevant_visits += 1

    escalated_risk = baseline_risk
    is_escalated = False
    alert_message = None

    if relevant_visits >= 1 and recurring_found:
        sym_list_str = ", ".join(f"'{s}'" for s in sorted(recurring_found)[:3])
        if baseline_risk == "Low":
            escalated_risk = "Medium"
            is_escalated = True
            alert_message = (
                f"Longitudinal Alert: Key symptoms ({sym_list_str}) have recurred across {relevant_visits + 1} visits in the last 60 days. "
                "Risk escalated from Low to Medium. Recommend healthcare worker or clinical consultation."
            )
        elif baseline_risk == "Medium" and relevant_visits >= 2:
            escalated_risk = "High"
            is_escalated = True
            alert_message = (
                f"Longitudinal Alert: Persistent symptoms ({sym_list_str}) detected across {relevant_visits + 1} consultations. "
                "Indicates a potentially progressing or chronic illness. Risk escalated to High. Immediate PHC evaluation advised."
            )
        else:
            alert_message = (
                f"Patient History Note: Symptoms ({sym_list_str}) previously reported on {past_records[0]['created_at'][:10]}. "
                "Monitor for progressive deterioration."
            )

    return {
        "escalated_risk": escalated_risk,
        "is_escalated": is_escalated,
        "recurrence_count": len(recurring_found),
        "recurring_symptoms": list(recurring_found),
        "alert_message": alert_message,
        "previous_visits_count": len(past_records)
    }

# --- Triage Record Persistence ---

def save_triage_record(
    symptoms: str,
    risk_level: str,
    confidence: float,
    condition: Optional[str] = None,
    precautions: Optional[List[str]] = None,
    action_advice: Optional[str] = None,
    generic_medicines: Optional[List[Dict[str, Any]]] = None,
    longitudinal_alert: Optional[str] = None,
    patient_id: Optional[str] = None,
    patient_name: Optional[str] = None,
    age: Optional[int] = None,
    gender: Optional[str] = None,
    village: Optional[str] = None
) -> int:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO triage_records (
                patient_id, patient_name, age, gender, village, symptoms, risk_level,
                confidence, condition, precautions, action_advice, generic_medicines,
                longitudinal_alert, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            patient_id,
            patient_name,
            age,
            gender,
            village,
            symptoms,
            risk_level,
            confidence,
            condition,
            json.dumps(precautions or []),
            action_advice,
            json.dumps(generic_medicines or []),
            longitudinal_alert,
            datetime.now().isoformat()
        ))
        conn.commit()
        return cursor.lastrowid

def get_triage_records(limit: int = 50, offset: int = 0, risk_level: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        if risk_level:
            cursor.execute("""
                SELECT * FROM triage_records 
                WHERE LOWER(risk_level) = LOWER(?)
                ORDER BY id DESC LIMIT ? OFFSET ?
            """, (risk_level, limit, offset))
        else:
            cursor.execute("""
                SELECT * FROM triage_records 
                ORDER BY id DESC LIMIT ? OFFSET ?
            """, (limit, offset))
        
        rows = cursor.fetchall()
        results = []
        for r in rows:
            record = dict(r)
            try:
                record["precautions"] = json.loads(record["precautions"]) if record["precautions"] else []
            except Exception:
                record["precautions"] = []
            try:
                record["generic_medicines"] = json.loads(record["generic_medicines"]) if record["generic_medicines"] else []
            except Exception:
                record["generic_medicines"] = []
            results.append(record)
        return results

def get_triage_record_by_id(record_id: int) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM triage_records WHERE id = ?", (record_id,))
        row = cursor.fetchone()
        if not row:
            return None
        record = dict(row)
        try:
            record["precautions"] = json.loads(record["precautions"]) if record["precautions"] else []
        except Exception:
            record["precautions"] = []
        try:
            record["generic_medicines"] = json.loads(record["generic_medicines"]) if record["generic_medicines"] else []
        except Exception:
            record["generic_medicines"] = []
        return record

def save_feedback(
    record_id: Optional[int],
    user_name: Optional[str],
    rating: int,
    corrected_risk: Optional[str],
    comments: Optional[str]
) -> int:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO feedback_records (
                record_id, user_name, rating, corrected_risk, comments, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            record_id,
            user_name,
            rating,
            corrected_risk,
            comments,
            datetime.now().isoformat()
        ))
        conn.commit()
        return cursor.lastrowid

def get_feedbacks(limit: int = 50) -> List[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT f.*, t.symptoms, t.risk_level as predicted_risk 
            FROM feedback_records f
            LEFT JOIN triage_records t ON f.record_id = t.id
            ORDER BY f.id DESC LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
