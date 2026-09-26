import sqlite3
import json
import re
import hashlib
import secrets
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

import os
import shutil

ORIGINAL_DB_PATH = Path(__file__).resolve().parent / "gramcare.db"

def _resolve_db_path() -> Path:
    # On Vercel / serverless platforms, only /tmp is writable
    if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        tmp_db = Path("/tmp/gramcare.db")
        if not tmp_db.exists():
            if ORIGINAL_DB_PATH.exists():
                shutil.copy2(ORIGINAL_DB_PATH, tmp_db)
            else:
                tmp_db.touch()
        return tmp_db
    return ORIGINAL_DB_PATH

DB_PATH = _resolve_db_path()

def get_db():
    target_path = _resolve_db_path()
    conn = sqlite3.connect(str(target_path))
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password: str) -> str:
    """Secure hash for user credentials."""
    return hashlib.sha256((password + "gramcare_salt_2026").encode('utf-8')).hexdigest()

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
                is_pregnant INTEGER DEFAULT 0,
                comorbidities TEXT,
                allergies TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # Migration check for patients table
        cursor.execute("PRAGMA table_info(patients)")
        p_cols = {col["name"] for col in cursor.fetchall()}
        if "is_pregnant" not in p_cols:
            cursor.execute("ALTER TABLE patients ADD COLUMN is_pregnant INTEGER DEFAULT 0")
        if "comorbidities" not in p_cols:
            cursor.execute("ALTER TABLE patients ADD COLUMN comorbidities TEXT")
        if "allergies" not in p_cols:
            cursor.execute("ALTER TABLE patients ADD COLUMN allergies TEXT")

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
                top_conditions TEXT,
                risk_reasons TEXT,
                emergency_override INTEGER DEFAULT 0,
                precautions TEXT,
                action_advice TEXT,
                generic_medicines TEXT,
                longitudinal_alert TEXT,
                followup_date TEXT,
                referral_status TEXT DEFAULT 'Referral Generated',
                doctor_notes TEXT,
                user_id TEXT,
                family_member_id TEXT,
                family_member_name TEXT,
                token_id TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (patient_id) REFERENCES patients (patient_id)
            )
        """)

        # Migration check for triage_records table
        cursor.execute("PRAGMA table_info(triage_records)")
        existing_cols = {col["name"] for col in cursor.fetchall()}
        new_cols = {
            "patient_id": "TEXT",
            "generic_medicines": "TEXT",
            "longitudinal_alert": "TEXT",
            "top_conditions": "TEXT",
            "risk_reasons": "TEXT",
            "emergency_override": "INTEGER DEFAULT 0",
            "followup_date": "TEXT",
            "referral_status": "TEXT DEFAULT 'Referral Generated'",
            "doctor_notes": "TEXT",
            "user_id": "TEXT",
            "family_member_id": "TEXT",
            "family_member_name": "TEXT",
            "token_id": "TEXT"
        }
        for col_name, col_type in new_cols.items():
            if col_name not in existing_cols:
                cursor.execute(f"ALTER TABLE triage_records ADD COLUMN {col_name} {col_type}")

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

        # 4. Users Table (ASHA Worker & Patient Self-Service Auth)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE NOT NULL,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL,
                phone TEXT,
                village TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # 5. Family Members Table (Health & Family Vault)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS family_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                member_id TEXT UNIQUE NOT NULL,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                relation TEXT NOT NULL,
                age INTEGER,
                gender TEXT,
                is_pregnant INTEGER DEFAULT 0,
                comorbidities TEXT,
                allergies TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)

        # 6. Patient Tokens Table (ASHA Worker Intake Tokens)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS patient_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_id TEXT UNIQUE NOT NULL,
                asha_worker_id TEXT NOT NULL,
                patient_name TEXT NOT NULL,
                phone TEXT,
                village TEXT,
                age INTEGER,
                gender TEXT,
                status TEXT DEFAULT 'Active',
                created_at TEXT NOT NULL
            )
        """)

        # 7. Translation Cache Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS translation_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_lang TEXT NOT NULL,
                target_lang TEXT NOT NULL,
                source_hash TEXT NOT NULL,
                source_text TEXT NOT NULL,
                translated_text TEXT NOT NULL,
                provider TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trans_lookup ON translation_cache(source_lang, target_lang, source_hash)")

        # 8. Seed Demo Accounts for Instant Testing & Privacy Protection
        seed_default_users(cursor)

        conn.commit()

# --- Patient Management Functions ---

def get_or_create_patient(
    name: str,
    phone: Optional[str] = None,
    village: Optional[str] = None,
    age: Optional[int] = None,
    gender: Optional[str] = None,
    is_pregnant: bool = False,
    comorbidities: Optional[List[str]] = None,
    allergies: Optional[List[str]] = None
) -> Dict[str, Any]:
    clean_name = name.strip()
    clean_phone = phone.strip() if phone else None
    clean_village = village.strip() if village else None
    comorb_str = json.dumps(comorbidities or [])
    allergies_str = json.dumps(allergies or [])

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
            pid = patient["patient_id"]
            cursor.execute("""
                UPDATE patients 
                SET age = COALESCE(?, age), 
                    gender = COALESCE(?, gender), 
                    village = COALESCE(?, village), 
                    phone = COALESCE(?, phone),
                    is_pregnant = COALESCE(?, is_pregnant),
                    comorbidities = CASE WHEN ? != '[]' THEN ? ELSE comorbidities END,
                    allergies = CASE WHEN ? != '[]' THEN ? ELSE allergies END
                WHERE patient_id = ?
            """, (age, gender, clean_village, clean_phone, 1 if is_pregnant else 0, comorb_str, comorb_str, allergies_str, allergies_str, pid))
            conn.commit()
            cursor.execute("SELECT * FROM patients WHERE patient_id = ?", (pid,))
            row = dict(cursor.fetchone())
            try:
                row["comorbidities"] = json.loads(row["comorbidities"]) if row.get("comorbidities") else []
                row["allergies"] = json.loads(row["allergies"]) if row.get("allergies") else []
            except Exception:
                row["comorbidities"], row["allergies"] = [], []
            return row

        cursor.execute("SELECT MAX(id) as max_id FROM patients")
        max_row = cursor.fetchone()
        next_num = 1001 + (max_row["max_id"] or 0)
        patient_id = f"GC-{next_num}"

        now_str = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO patients (patient_id, name, phone, village, age, gender, is_pregnant, comorbidities, allergies, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (patient_id, clean_name, clean_phone, clean_village, age, gender, 1 if is_pregnant else 0, comorb_str, allergies_str, now_str))
        conn.commit()

        cursor.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,))
        row = dict(cursor.fetchone())
        try:
            row["comorbidities"] = json.loads(row["comorbidities"]) if row.get("comorbidities") else []
            row["allergies"] = json.loads(row["allergies"]) if row.get("allergies") else []
        except Exception:
            row["comorbidities"], row["allergies"] = [], []
        return row

def list_patients(search: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
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
        res = []
        for r in cursor.fetchall():
            row = dict(r)
            try:
                row["comorbidities"] = json.loads(row["comorbidities"]) if row.get("comorbidities") else []
                row["allergies"] = json.loads(row["allergies"]) if row.get("allergies") else []
            except Exception:
                row["comorbidities"], row["allergies"] = [], []
            res.append(row)
        return res

def get_patient_by_id(patient_id: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,))
        row = cursor.fetchone()
        if not row:
            return None
        res = dict(row)
        try:
            res["comorbidities"] = json.loads(res["comorbidities"]) if res.get("comorbidities") else []
            res["allergies"] = json.loads(res["allergies"]) if res.get("allergies") else []
        except Exception:
            res["comorbidities"], res["allergies"] = [], []
        return res

def get_patient_consultations(patient_id: str, limit: int = 20) -> List[Dict[str, Any]]:
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
            try:
                rec["top_conditions"] = json.loads(rec["top_conditions"]) if rec.get("top_conditions") else []
            except Exception:
                rec["top_conditions"] = []
            try:
                rec["risk_reasons"] = json.loads(rec["risk_reasons"]) if rec.get("risk_reasons") else []
            except Exception:
                rec["risk_reasons"] = []
            records.append(rec)
        return records

# --- Longitudinal Risk Engine ---

def evaluate_longitudinal_risk(
    patient_id: Optional[str],
    current_symptoms: str,
    baseline_risk: str
) -> Dict[str, Any]:
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

    stop_words = {"have", "with", "from", "days", "week", "mild", "pain", "feel", "also", "some", "time"}
    current_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', current_symptoms.lower())) - stop_words

    recurring_found = set()
    relevant_visits = 0

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
        elif baseline_risk == "Medium":
            escalated_risk = "High"
            is_escalated = True
            alert_message = (
                f"Longitudinal Alert: Persistent symptoms ({sym_list_str}) detected across {relevant_visits + 1} consultations in the last 60 days. "
                "Indicates a potentially progressing or chronic illness. Risk escalated to High. Immediate PHC evaluation advised."
            )
        else:
            alert_message = (
                f"Longitudinal Alert: Recurring symptoms ({sym_list_str}) previously reported on {past_records[0]['created_at'][:10]}. "
                "High emergency risk with documented recurring symptom history."
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
    top_conditions: Optional[List[Dict[str, Any]]] = None,
    risk_reasons: Optional[List[str]] = None,
    emergency_override: bool = False,
    precautions: Optional[List[str]] = None,
    action_advice: Optional[str] = None,
    generic_medicines: Optional[List[Dict[str, Any]]] = None,
    longitudinal_alert: Optional[str] = None,
    followup_date: Optional[str] = None,
    referral_status: str = "Referral Generated",
    patient_id: Optional[str] = None,
    patient_name: Optional[str] = None,
    age: Optional[int] = None,
    gender: Optional[str] = None,
    village: Optional[str] = None,
    user_id: Optional[str] = None,
    family_member_id: Optional[str] = None,
    family_member_name: Optional[str] = None,
    token_id: Optional[str] = None
) -> int:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO triage_records (
                patient_id, patient_name, age, gender, village, symptoms, risk_level,
                confidence, condition, top_conditions, risk_reasons, emergency_override,
                precautions, action_advice, generic_medicines, longitudinal_alert,
                followup_date, referral_status, user_id, family_member_id, family_member_name, token_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            json.dumps(top_conditions or []),
            json.dumps(risk_reasons or []),
            1 if emergency_override else 0,
            json.dumps(precautions or []),
            action_advice,
            json.dumps(generic_medicines or []),
            longitudinal_alert,
            followup_date,
            referral_status,
            user_id,
            family_member_id,
            family_member_name,
            token_id,
            datetime.now().isoformat()
        ))
        conn.commit()
        return cursor.lastrowid

def update_referral_status(record_id: int, referral_status: str, doctor_notes: Optional[str] = None) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE triage_records 
            SET referral_status = ?, doctor_notes = COALESCE(?, doctor_notes)
            WHERE id = ?
        """, (referral_status, doctor_notes, record_id))
        conn.commit()
        return cursor.rowcount > 0

def get_triage_records(
    limit: int = 50,
    offset: int = 0,
    risk_level: Optional[str] = None,
    user_id: Optional[str] = None,
    family_member_id: Optional[str] = None,
    token_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        clauses = []
        params = []
        if risk_level:
            clauses.append("LOWER(risk_level) = LOWER(?)")
            params.append(risk_level)
        if user_id:
            clauses.append("user_id = ?")
            params.append(user_id)
        if family_member_id:
            clauses.append("family_member_id = ?")
            params.append(family_member_id)
        if token_id:
            clauses.append("token_id = ?")
            params.append(token_id)

        where_stmt = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        query = f"SELECT * FROM triage_records {where_stmt} ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, tuple(params))
        
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
            try:
                record["top_conditions"] = json.loads(record["top_conditions"]) if record.get("top_conditions") else []
            except Exception:
                record["top_conditions"] = []
            try:
                record["risk_reasons"] = json.loads(record["risk_reasons"]) if record.get("risk_reasons") else []
            except Exception:
                record["risk_reasons"] = []
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
        try:
            record["top_conditions"] = json.loads(record["top_conditions"]) if record.get("top_conditions") else []
        except Exception:
            record["top_conditions"] = []
        try:
            record["risk_reasons"] = json.loads(record["risk_reasons"]) if record.get("risk_reasons") else []
        except Exception:
            record["risk_reasons"] = []
        return record

# --- Health Analytics & Village Surveillance Summary ---

def get_analytics_summary() -> Dict[str, Any]:
    """Generates rural health analytics, risk breakdown, village outbreak heatmap, and follow-ups."""
    with get_db() as conn:
        cursor = conn.cursor()

        # Total Patients & Consultations
        cursor.execute("SELECT COUNT(*) as count FROM patients")
        total_patients = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM triage_records")
        total_consultations = cursor.fetchone()["count"]

        # Risk Breakdown
        cursor.execute("""
            SELECT risk_level, COUNT(*) as count 
            FROM triage_records 
            GROUP BY risk_level
        """)
        risk_breakdown = {"High": 0, "Medium": 0, "Low": 0}
        for row in cursor.fetchall():
            risk_breakdown[row["risk_level"]] = row["count"]

        # Village Outbreak Heatmap (Village-wise count of recent consultations)
        cursor.execute("""
            SELECT village, COUNT(*) as count, 
                   SUM(CASE WHEN risk_level = 'High' THEN 1 ELSE 0 END) as high_risk_count,
                   MAX(condition) as primary_condition
            FROM triage_records 
            WHERE village IS NOT NULL AND TRIM(village) != ''
            GROUP BY village 
            ORDER BY count DESC 
            LIMIT 10
        """)
        village_stats = [dict(row) for row in cursor.fetchall()]

        # Top Reported Conditions
        cursor.execute("""
            SELECT condition, COUNT(*) as count 
            FROM triage_records 
            WHERE condition IS NOT NULL 
            GROUP BY condition 
            ORDER BY count DESC 
            LIMIT 6
        """)
        top_conditions = [dict(row) for row in cursor.fetchall()]

        # Follow-ups Due (today or overdue)
        today_str = datetime.now().date().isoformat()
        cursor.execute("""
            SELECT id, patient_name, village, condition, risk_level, followup_date, referral_status
            FROM triage_records 
            WHERE followup_date IS NOT NULL AND followup_date <= ? AND referral_status != 'Recovered'
            ORDER BY followup_date ASC LIMIT 10
        """, (today_str,))
        followups_due = [dict(row) for row in cursor.fetchall()]

        # Emergency Overrides Count
        cursor.execute("SELECT COUNT(*) as count FROM triage_records WHERE emergency_override = 1")
        emergency_count = cursor.fetchone()["count"]

        return {
            "total_patients": total_patients,
            "total_consultations": total_consultations,
            "risk_breakdown": risk_breakdown,
            "emergency_overrides": emergency_count,
            "village_stats": village_stats,
            "top_conditions": top_conditions,
            "followups_due": followups_due,
            "followups_due_count": len(followups_due)
        }

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

# ==========================================================================
# Authentication, Role-Based Access, & Patient Token Generator Functions
# ==========================================================================

def seed_default_users(cursor):
    """Seeds default demo accounts for instant evaluation and data privacy testing."""
    # 1. ASHA Worker Account
    cursor.execute("SELECT id FROM users WHERE username = 'asha@gramcare.gov.in'")
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO users (user_id, username, password_hash, full_name, role, phone, village, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "ASHA-782",
            "asha@gramcare.gov.in",
            hash_password("asha123"),
            "Sunita Devi (ASHA Worker #782)",
            "asha",
            "9876543210",
            "Rampur",
            datetime.now().isoformat()
        ))
        # Initial sample patient token
        cursor.execute("""
            INSERT INTO patient_tokens (token_id, asha_worker_id, patient_name, phone, village, age, gender, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "TK-RAM-84920",
            "ASHA-782",
            "Meena Bai",
            "9899011223",
            "Rampur",
            34,
            "Female",
            "Active",
            datetime.now().isoformat()
        ))

    # 2. Self Patient Account
    cursor.execute("SELECT id FROM users WHERE username = 'patient@gramcare.in'")
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO users (user_id, username, password_hash, full_name, role, phone, village, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "USR-1082",
            "patient@gramcare.in",
            hash_password("patient123"),
            "Ramesh Kumar",
            "patient",
            "9812345678",
            "Shivpur",
            datetime.now().isoformat()
        ))

        # Seed Family Vault Members for Ramesh Kumar
        demo_family = [
            ("FAM-1082-SELF", "USR-1082", "Ramesh Kumar", "Self", 42, "Male", 0, '["Hypertension"]', '[]'),
            ("FAM-1082-SPOUSE", "USR-1082", "Sita Devi", "Spouse", 38, "Female", 0, '[]', '["NSAIDs"]'),
            ("FAM-1082-CHILD", "USR-1082", "Aarav Kumar", "Child", 9, "Male", 0, '[]', '[]'),
            ("FAM-1082-PARENT", "USR-1082", "Kailash Chand", "Parent", 68, "Male", 0, '["Diabetes", "Arthritis"]', '[]')
        ]
        for m in demo_family:
            cursor.execute("""
                INSERT INTO family_members (member_id, user_id, name, relation, age, gender, is_pregnant, comorbidities, allergies, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (*m, datetime.now().isoformat()))

def create_user(
    username: str,
    password: str,
    full_name: str,
    role: str = "patient",
    phone: Optional[str] = None,
    village: Optional[str] = None
) -> Dict[str, Any]:
    """Registers a new user (ASHA worker or Self Patient)."""
    clean_username = username.strip().lower()
    clean_phone = phone.strip() if phone else None
    clean_village = village.strip() if village else None
    pwd_hash = hash_password(password)

    with get_db() as conn:
        cursor = conn.cursor()
        # Verify uniqueness
        cursor.execute("SELECT id FROM users WHERE username = ? OR (phone IS NOT NULL AND phone = ?)", (clean_username, clean_phone))
        if cursor.fetchone():
            raise ValueError(f"User with username/phone '{clean_username}' already exists.")

        # Generate User ID
        ts = int(datetime.now().timestamp() % 100000)
        prefix = "ASHA" if role.lower() == "asha" else "USR"
        user_id = f"{prefix}-{ts:04d}"

        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO users (user_id, username, password_hash, full_name, role, phone, village, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, clean_username, pwd_hash, full_name.strip(), role.lower(), clean_phone, clean_village, now))

        # If patient, automatically create 'Self' profile in family vault
        if role.lower() == "patient":
            member_id = f"FAM-{user_id}-SELF"
            cursor.execute("""
                INSERT INTO family_members (member_id, user_id, name, relation, age, gender, is_pregnant, comorbidities, allergies, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (member_id, user_id, full_name.strip(), "Self", None, None, 0, json.dumps([]), json.dumps([]), now))

        conn.commit()

        return {
            "user_id": user_id,
            "username": clean_username,
            "full_name": full_name.strip(),
            "role": role.lower(),
            "phone": clean_phone,
            "village": clean_village,
            "created_at": now
        }

def authenticate_user(username_or_phone: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticates credentials against the users table."""
    clean_ident = username_or_phone.strip().lower()
    pwd_hash = hash_password(password)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id, username, password_hash, full_name, role, phone, village, created_at 
            FROM users 
            WHERE (username = ? OR phone = ?)
        """, (clean_ident, clean_ident))
        row = cursor.fetchone()
        if not row:
            return None

        user = dict(row)
        if user["password_hash"] != pwd_hash:
            return None

        # Redact password hash
        del user["password_hash"]
        return user

def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id, username, full_name, role, phone, village, created_at 
            FROM users 
            WHERE user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_user_by_username_or_phone(ident: str) -> Optional[Dict[str, Any]]:
    clean_ident = ident.strip().lower()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id, username, full_name, role, phone, village, created_at 
            FROM users 
            WHERE username = ? OR phone = ?
        """, (clean_ident, clean_ident))
        row = cursor.fetchone()
        return dict(row) if row else None

# --- Family Vault Functions ---

def get_family_members(user_id: str) -> List[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM family_members 
            WHERE user_id = ? 
            ORDER BY CASE WHEN relation = 'Self' THEN 0 ELSE 1 END, id ASC
        """, (user_id,))
        members = []
        for r in cursor.fetchall():
            m = dict(r)
            try:
                m["comorbidities"] = json.loads(m["comorbidities"]) if m.get("comorbidities") else []
                m["allergies"] = json.loads(m["allergies"]) if m.get("allergies") else []
            except Exception:
                m["comorbidities"], m["allergies"] = [], []
            members.append(m)
        return members

def add_family_member(
    user_id: str,
    name: str,
    relation: str,
    age: Optional[int] = None,
    gender: Optional[str] = None,
    is_pregnant: bool = False,
    comorbidities: Optional[List[str]] = None,
    allergies: Optional[List[str]] = None
) -> Dict[str, Any]:
    clean_name = name.strip()
    clean_rel = relation.strip().capitalize()
    ts = int(datetime.now().timestamp() % 100000)
    member_id = f"FAM-{user_id[-4:]}-{clean_rel[:3].upper()}-{ts:03d}"
    now = datetime.now().isoformat()

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO family_members (
                member_id, user_id, name, relation, age, gender, is_pregnant, comorbidities, allergies, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            member_id,
            user_id,
            clean_name,
            clean_rel,
            age,
            gender,
            1 if is_pregnant else 0,
            json.dumps(comorbidities or []),
            json.dumps(allergies or []),
            now
        ))
        conn.commit()

        return {
            "member_id": member_id,
            "user_id": user_id,
            "name": clean_name,
            "relation": clean_rel,
            "age": age,
            "gender": gender,
            "is_pregnant": is_pregnant,
            "comorbidities": comorbidities or [],
            "allergies": allergies or [],
            "created_at": now
        }

def delete_family_member(user_id: str, member_id: str) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        # Protect default 'Self' profile from deletion
        cursor.execute("SELECT relation FROM family_members WHERE user_id = ? AND member_id = ?", (user_id, member_id))
        row = cursor.fetchone()
        if not row:
            return False
        if row["relation"] == "Self":
            raise ValueError("The primary 'Self' profile cannot be deleted.")

        cursor.execute("DELETE FROM family_members WHERE user_id = ? AND member_id = ?", (user_id, member_id))
        conn.commit()
        return cursor.rowcount > 0

# --- ASHA Worker Patient Token Generator ---

def generate_patient_token(
    asha_worker_id: str,
    patient_name: str,
    phone: Optional[str] = None,
    village: Optional[str] = None,
    age: Optional[int] = None,
    gender: Optional[str] = None
) -> Dict[str, Any]:
    """Generates an encrypted, distinct patient intake token for ASHA workers."""
    clean_name = patient_name.strip()
    clean_vil = (village or "VIL").strip().upper()[:3]
    rand_suffix = secrets.token_hex(2).upper()
    ts_sec = int(datetime.now().timestamp() % 10000)
    token_id = f"TK-{clean_vil}-{ts_sec:04d}-{rand_suffix}"
    now = datetime.now().isoformat()

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO patient_tokens (
                token_id, asha_worker_id, patient_name, phone, village, age, gender, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            token_id,
            asha_worker_id,
            clean_name,
            phone.strip() if phone else None,
            village.strip() if village else None,
            age,
            gender,
            "Active",
            now
        ))
        conn.commit()

        return {
            "token_id": token_id,
            "asha_worker_id": asha_worker_id,
            "patient_name": clean_name,
            "phone": phone,
            "village": village,
            "age": age,
            "gender": gender,
            "status": "Active",
            "created_at": now
        }

def get_patient_tokens_by_asha(asha_worker_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM patient_tokens 
            WHERE asha_worker_id = ? 
            ORDER BY id DESC LIMIT ?
        """, (asha_worker_id, limit))
        return [dict(row) for row in cursor.fetchall()]

def get_token_by_id(token_id: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM patient_tokens WHERE token_id = ?", (token_id.strip(),))
        row = cursor.fetchone()
        return dict(row) if row else None

# --- Privacy Scoped Triage History ---

def get_vault_records_for_user(
    user_id: str,
    family_member_id: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Fetches triage consultations strictly bound to user's credentials and family vault."""
    with get_db() as conn:
        cursor = conn.cursor()
        if family_member_id:
            cursor.execute("""
                SELECT * FROM triage_records 
                WHERE user_id = ? AND family_member_id = ?
                ORDER BY id DESC LIMIT ?
            """, (user_id, family_member_id, limit))
        else:
            cursor.execute("""
                SELECT * FROM triage_records 
                WHERE user_id = ?
                ORDER BY id DESC LIMIT ?
            """, (user_id, limit))

        rows = cursor.fetchall()
        records = []
        for r in rows:
            rec = dict(r)
            try:
                rec["precautions"] = json.loads(rec["precautions"]) if rec.get("precautions") else []
                rec["generic_medicines"] = json.loads(rec["generic_medicines"]) if rec.get("generic_medicines") else []
                rec["top_conditions"] = json.loads(rec["top_conditions"]) if rec.get("top_conditions") else []
                rec["risk_reasons"] = json.loads(rec["risk_reasons"]) if rec.get("risk_reasons") else []
            except Exception:
                pass
            records.append(rec)
        return records


# --- Translation Cache Functions ---

def _hash_text(text: str) -> str:
    return hashlib.sha256(text.strip().encode('utf-8')).hexdigest()

def _ensure_translation_cache_table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS translation_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_lang TEXT NOT NULL,
            target_lang TEXT NOT NULL,
            source_hash TEXT NOT NULL,
            source_text TEXT NOT NULL,
            translated_text TEXT NOT NULL,
            provider TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trans_lookup ON translation_cache(source_lang, target_lang, source_hash)")

def get_cached_translation(source_text: str, source_lang: str, target_lang: str) -> Optional[str]:
    """Retrieve cached translation if previously translated."""
    if not source_text or not source_text.strip():
        return source_text
    shash = _hash_text(source_text)
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            _ensure_translation_cache_table(cursor)
            cursor.execute("""
                SELECT translated_text FROM translation_cache 
                WHERE source_lang = ? AND target_lang = ? AND source_hash = ?
                ORDER BY id DESC LIMIT 1
            """, (source_lang.lower(), target_lang.lower(), shash))
            row = cursor.fetchone()
            return row["translated_text"] if row else None
    except Exception:
        return None

def set_cached_translation(
    source_text: str,
    source_lang: str,
    target_lang: str,
    translated_text: str,
    provider: str = "auto"
):
    """Store translation result in cache for high-speed offline-first reuse."""
    if not source_text or not translated_text:
        return
    shash = _hash_text(source_text)
    now = datetime.now().isoformat()
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            _ensure_translation_cache_table(cursor)
            cursor.execute("""
                INSERT INTO translation_cache (source_lang, target_lang, source_hash, source_text, translated_text, provider, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (source_lang.lower(), target_lang.lower(), shash, source_text.strip(), translated_text.strip(), provider, now))
            conn.commit()
    except Exception:
        pass



