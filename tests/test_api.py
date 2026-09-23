import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from backend.app import app
from backend.db import init_db

sys.stdout.reconfigure(encoding='utf-8')

client = TestClient(app)

def test_frontend_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "GramCare AI" in response.text
    assert "Triage Studio" in response.text
    print("✅ Frontend static mount passed (Serves HTML5 Web App)")

def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["model_loaded"] is True
    assert data["vectorizer_loaded"] is True
    print("✅ Health check passed: Triage ML Model & Vectorizer loaded")

def test_patient_registration_and_triage():
    payload = {
        "patient_name": "Ramesh Patel",
        "phone": "9876500001",
        "village": "Rampur",
        "age": 48,
        "gender": "Male",
        "symptoms": "itching, skin rash"
    }
    response = client.post("/api/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    assert data["patient_id"] is not None
    assert data["patient_id"].startswith("GC-")
    assert data["risk_level"] == "Low"
    assert len(data["generic_medicines"]) > 0
    assert data["generic_medicines"][0]["jan_aushadhi"] is True
    print(f"✅ Patient Auto-Registration & Baseline Triage passed (ID: {data['patient_id']}, Risk: {data['risk_level']})")
    return data["patient_id"]

def test_longitudinal_risk_escalation(patient_id: str):
    # Patient returns with recurring symptom (cough/fever) across multiple visits
    payload_visit_1 = {
        "patient_name": "Devi Bai",
        "phone": "9876500002",
        "village": "Shivpur",
        "age": 55,
        "gender": "Female",
        "symptoms": "sneezing, runny nose, cough"
    }
    res1 = client.post("/api/predict", json=payload_visit_1)
    assert res1.status_code == 200
    data1 = res1.json()
    pid = data1["patient_id"]
    assert data1["risk_level"] == "Low"
    print(f"✅ Longitudinal Visit 1 passed: Risk = {data1['risk_level']} (Patient ID: {pid})")

    # Visit 2: Same patient returns with recurring persistent cough and fever
    payload_visit_2 = {
        "patient_name": "Devi Bai",
        "phone": "9876500002",
        "village": "Shivpur",
        "age": 55,
        "gender": "Female",
        "symptoms": "persistent cough and high fever"
    }
    res2 = client.post("/api/predict", json=payload_visit_2)
    assert res2.status_code == 200
    data2 = res2.json()
    
    assert data2["patient_id"] == pid
    assert data2["longitudinal_analysis"]["alert_message"] is not None
    assert "Longitudinal Alert" in data2["longitudinal_alert"]
    print(f"✅ Longitudinal Risk Alert Triggered: '{data2['longitudinal_alert'][:65]}...'")

    # Verify Timeline
    timeline_res = client.get(f"/api/patients/{pid}/timeline")
    assert timeline_res.status_code == 200
    t_data = timeline_res.json()
    assert t_data["total_consultations"] >= 2
    print(f"✅ Patient Health Timeline verified: {t_data['total_consultations']} consultations recorded")

def test_patient_registry():
    response = client.get("/api/patients")
    assert response.status_code == 200
    patients = response.json()
    assert len(patients) > 0
    print(f"✅ Patient Registry passed ({len(patients)} patients found)")

def test_history_and_feedback():
    history_res = client.get("/api/history")
    assert history_res.status_code == 200
    records = history_res.json()
    assert len(records) > 0
    rec_id = records[0]["id"]

    feedback_payload = {
        "record_id": rec_id,
        "user_name": "Sunita Devi (ASHA)",
        "rating": 5,
        "corrected_risk": None,
        "comments": "Accurate triage guidance and generic medicine alternatives."
    }
    fb_res = client.post("/api/feedback", json=feedback_payload)
    assert fb_res.status_code == 200
    print("✅ Feedback submission & retrieval passed")

if __name__ == "__main__":
    init_db()
    print("🚀 Running GramCare AI End-to-End Test Suite...\n")
    test_frontend_root()
    test_health()
    pid = test_patient_registration_and_triage()
    test_longitudinal_risk_escalation(pid)
    test_patient_registry()
    test_history_and_feedback()
    print("\n🎉 ALL GRAMCARE AI TESTS PASSED WITH 100% SUCCESS!")
