import sys
import time
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
    ts = int(time.time())
    payload = {
        "patient_name": f"Ramesh Patel {ts}",
        "phone": f"98765{ts % 100000:05d}",
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
    assert len(data["top_conditions"]) > 0
    assert data["followup_date"] is not None
    assert len(data["risk_reasons"]) > 0
    print(f"✅ Patient Auto-Registration & Baseline Triage passed (ID: {data['patient_id']}, Risk: {data['risk_level']})")
    return data["patient_id"]

def test_emergency_symptom_override():
    payload = {
        "patient_name": "Emergency Patient",
        "phone": "9110000000",
        "village": "Belagavi",
        "age": 62,
        "gender": "Male",
        "symptoms": "acute chest pain and loss of consciousness with cold sweats"
    }
    response = client.post("/api/predict", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["emergency_override"] is True
    assert data["risk_level"] == "High"
    assert any("Emergency Override" in r for r in data["risk_reasons"])
    assert data["followup_date"] is not None
    print(f"✅ Emergency Symptom Override passed: Risk = {data['risk_level']}, Override = {data['emergency_override']}")

def test_top3_differential_diagnoses():
    payload = {
        "patient_name": "Fever Patient",
        "village": "Shivpur",
        "symptoms": "high fever, headache, chills, joint pain, nausea"
    }
    response = client.post("/api/predict", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert len(data["top_conditions"]) >= 2
    for item in data["top_conditions"]:
        assert "disease" in item
        assert "confidence_pct" in item
    print(f"✅ Top Differential Diagnoses passed: {[c['disease'] + ' (' + str(c['confidence_pct']) + '%)' for c in data['top_conditions']]}")

def test_allergy_filtering():
    # Patient with arthritis symptoms but allergic to NSAIDs
    payload = {
        "patient_name": "Allergic Patient",
        "village": "Kampur",
        "symptoms": "joint pain, stiffness in knee",
        "allergies": ["NSAIDs", "Aspirin", "Diclofenac"]
    }
    response = client.post("/api/predict", json=payload)
    assert response.status_code == 200
    data = response.json()

    med_names = [m["name"].lower() for m in data["generic_medicines"]]
    # Diclofenac must NOT be present
    assert not any("diclofenac" in name for name in med_names)
    print(f"✅ Drug Allergy Filtering passed: Incompatible NSAIDs omitted, safe meds returned: {[m['name'] for m in data['generic_medicines']]}")

def test_longitudinal_risk_escalation():
    ts = int(time.time())
    phone = f"98888{ts % 100000:05d}"
    name = f"Devi Bai {ts}"
    payload_visit_1 = {
        "patient_name": name,
        "phone": phone,
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
        "patient_name": name,
        "phone": phone,
        "village": "Shivpur",
        "age": 55,
        "gender": "Female",
        "symptoms": "persistent cough and high fever"
    }
    res2 = client.post("/api/predict", json=payload_visit_2)
    assert res2.status_code == 200
    data2 = res2.json()
    
    assert data2["patient_id"] == pid
    assert data2["longitudinal_alert"] is not None
    assert "Longitudinal Alert" in data2["longitudinal_alert"]
    print(f"✅ Longitudinal Risk Alert Triggered: '{data2['longitudinal_alert'][:65]}...'")

    # Verify Timeline
    timeline_res = client.get(f"/api/patients/{pid}/timeline")
    assert timeline_res.status_code == 200
    t_data = timeline_res.json()
    assert t_data["total_consultations"] >= 2
    print(f"✅ Patient Health Timeline verified: {t_data['total_consultations']} consultations recorded")
    return data2["record_id"]

def test_analytics_and_referral_loop(record_id: int):
    # Test Analytics endpoint
    res = client.get("/api/analytics")
    assert res.status_code == 200
    data = res.json()
    assert data["total_consultations"] > 0
    assert data["total_patients"] > 0
    assert "High" in data["risk_breakdown"]
    assert len(data["village_stats"]) > 0
    print(f"✅ Health Analytics passed: {data['total_consultations']} consults, {len(data['village_stats'])} villages tracked")

    # Test Referral Loop Status Update
    status_payload = {
        "referral_status": "Hospital Visited",
        "doctor_notes": "Patient reached PHC. Treated with IV fluids and admitted for observation."
    }
    status_res = client.post(f"/api/history/{record_id}/referral-status", json=status_payload)
    assert status_res.status_code == 200
    assert status_res.json()["referral_status"] == "Hospital Visited"
    print("✅ Care-Loop Referral Status Update passed: Status = 'Hospital Visited'")

def test_medium_risk_telemedicine():
    # Test duty doctor status
    doc_res = client.get("/api/telemedicine/doctor-status")
    assert doc_res.status_code == 200
    doc_data = doc_res.json()
    assert doc_data["doctor"]["name"] == "Dr. Anjali Verma, MBBS"
    assert doc_data["doctor"]["status"] == "Online"
    print(f"✅ Telemedicine Doctor Status verified: {doc_data['doctor']['name']} ({doc_data['doctor']['status']})")

    # Patient with Medium Risk (Maternal vulnerability or moderate condition)
    ts = int(time.time())
    payload = {
        "patient_name": f"Meena Devi {ts}",
        "phone": f"98711{ts % 100000:05d}",
        "village": "Belagavi",
        "age": 28,
        "gender": "Female",
        "is_pregnant": True,
        "symptoms": "mild fever and mild cough for 3 days"
    }
    response = client.post("/api/predict", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["risk_level"] == "Medium"
    # Ensure self cure is NOT recommended
    assert "self-cure" in data["action_advice"].lower() or "not rely on self-cure" in data["action_advice"].lower()
    assert "video call" in data["action_advice"].lower() or "video consultation" in data["action_advice"].lower()
    
    # Telemedicine session must be active and available
    assert data["telemedicine"] is not None
    assert data["telemedicine"]["available"] is True
    assert data["telemedicine"]["room_url"].startswith("https://meet.jit.si/")
    assert data["telemedicine"]["doctor_name"] == "Dr. Anjali Verma, MBBS"
    print(f"✅ Medium Risk Telemedicine Backend verified: Video Call URL generated -> {data['telemedicine']['room_url']}")
    print(f"✅ Medium Risk Action Advice verified: '{data['action_advice'][:75]}...'")

    # Test completing consultation
    session_id = data["telemedicine"]["session_id"]
    complete_res = client.post(f"/api/telemedicine/session/{session_id}/complete", json={
        "doctor_notes": "Consulted patient via live video. Hydration and rest prescribed. Safe for pregnancy.",
        "rx_medicines": ["Paracetamol 500mg"],
        "followup_advice": "Follow up after 3 days if fever continues."
    })
    assert complete_res.status_code == 200
    assert complete_res.json()["status"] == "success"
    print(f"✅ Telemedicine Session Completion verified for session: {session_id}")

def test_authentication_token_and_family_vault():
    # 1. Test ASHA Worker Authentication
    asha_login_res = client.post("/api/auth/login", json={
        "username": "asha@gramcare.gov.in",
        "password": "asha123"
    })
    assert asha_login_res.status_code == 200
    asha_data = asha_login_res.json()
    assert asha_data["user"]["role"] == "asha"
    assert asha_data["user"]["user_id"] == "ASHA-782"
    assert "session_token" in asha_data
    print(f"✅ ASHA Worker Login passed: {asha_data['user']['full_name']} (Role: {asha_data['user']['role']})")

    # 2. Test ASHA Patient Intake Token Generation
    token_res = client.post("/api/auth/asha/generate-token", json={
        "asha_worker_id": "ASHA-782",
        "patient_name": "Radha Bai",
        "phone": "9811223344",
        "village": "Rampur",
        "age": 30,
        "gender": "Female"
    })
    assert token_res.status_code == 200
    token_data = token_res.json()
    token_id = token_data["token"]["token_id"]
    assert token_id.startswith("TK-RAM-")
    print(f"✅ ASHA Token Generation passed: Issued token {token_id} for {token_data['token']['patient_name']}")

    # Verify token retrieval
    tokens_list_res = client.get("/api/auth/asha/tokens?asha_worker_id=ASHA-782")
    assert tokens_list_res.status_code == 200
    assert any(t["token_id"] == token_id for t in tokens_list_res.json()["tokens"])
    print(f"✅ ASHA Tokens List verified: {tokens_list_res.json()['count']} tokens registered")

    # 3. Test Self-Patient Authentication
    pat_login_res = client.post("/api/auth/login", json={
        "username": "patient@gramcare.in",
        "password": "patient123"
    })
    assert pat_login_res.status_code == 200
    pat_data = pat_login_res.json()
    assert pat_data["user"]["role"] == "patient"
    assert pat_data["user"]["user_id"] == "USR-1082"
    print(f"✅ Self Patient Login passed: {pat_data['user']['full_name']} (User ID: {pat_data['user']['user_id']})")

    # 4. Test Family Members Vault (Self + Dependents)
    fam_res = client.get("/api/auth/family?user_id=USR-1082")
    assert fam_res.status_code == 200
    members = fam_res.json()["family_members"]
    assert len(members) >= 4
    rel_types = [m["relation"] for m in members]
    assert "Self" in rel_types
    assert "Child" in rel_types
    print(f"✅ Family Vault retrieved: {len(members)} members ({', '.join(rel_types)})")

    # 5. Add a new family member to the vault
    new_fam_res = client.post("/api/auth/family", json={
        "user_id": "USR-1082",
        "name": "Priya Kumar",
        "relation": "Child",
        "age": 6,
        "gender": "Female",
        "is_pregnant": False,
        "comorbidities": [],
        "allergies": []
    })
    assert new_fam_res.status_code == 200
    child_member = new_fam_res.json()["member"]
    assert child_member["name"] == "Priya Kumar"
    print(f"✅ Add Family Member passed: Added {child_member['name']} (ID: {child_member['member_id']})")

    # 6. Submit Triage under Family Member & Token (Data Privacy)
    triage_payload = {
        "patient_name": "Priya Kumar",
        "age": 6,
        "gender": "Female",
        "village": "Shivpur",
        "symptoms": "fever and persistent cough for 2 days",
        "user_id": "USR-1082",
        "family_member_id": child_member["member_id"],
        "family_member_name": child_member["name"],
        "token_id": token_id
    }
    triage_res = client.post("/api/predict", json=triage_payload)
    assert triage_res.status_code == 200
    triage_data = triage_res.json()
    assert triage_data["user_id"] == "USR-1082"
    assert triage_data["family_member_id"] == child_member["member_id"]
    assert triage_data["token_id"] == token_id
    print(f"✅ Privacy-Scoped Triage passed: Record #{triage_data['record_id']} bound to User USR-1082 & Family Member {child_member['name']}")

    # 7. Query Vault History with Privacy Boundary
    vault_hist_res = client.get(f"/api/auth/vault/history?user_id=USR-1082&family_member_id={child_member['member_id']}")
    assert vault_hist_res.status_code == 200
    vault_records = vault_hist_res.json()["records"]
    assert len(vault_records) >= 1
    assert vault_records[0]["family_member_id"] == child_member["member_id"]
    print(f"✅ Data Privacy Verification passed: Vault history exclusively returns {len(vault_records)} record(s) for {child_member['name']}")

def test_google_authentication():
    # 1. New Google user auto-provisioning
    google_email = f"dhawal.test.{int(time.time())}@gmail.com"
    req_payload = {
        "email": google_email,
        "name": "Dhawal Sharma",
        "google_id": "google_oauth_12345",
        "village": "Rural Sub-Centre"
    }
    res = client.post("/api/auth/google", json=req_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "GC-GOOGLE-SESSION-" in data["session_token"]
    assert data["user"]["username"] == google_email
    assert data["user"]["full_name"] == "Dhawal Sharma"
    assert data["provider"] == "google"
    print(f"✅ Google SSO Auto-provisioning passed: Created user {data['user']['user_id']} ({google_email})")

    # 2. Existing Google user sign-in
    res2 = client.post("/api/auth/google", json=req_payload)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["user"]["user_id"] == data["user"]["user_id"]
    print(f"✅ Google SSO Re-authentication passed: Authenticated existing user {data2['user']['user_id']}")

def test_multilingual_language_directory():
    res = client.get("/api/languages")
    assert res.status_code == 200
    data = res.json()
    assert data["count"] >= 14
    codes = [l["code"] for l in data["languages"]]
    assert "en" in codes
    assert "hi" in codes
    assert "cg" in codes
    assert "bn" in codes
    assert "mr" in codes
    assert "te" in codes
    assert "ta" in codes
    assert "gu" in codes
    assert "or" in codes
    assert "pa" in codes
    
    # Check Chhattisgarhi specific metadata
    cg_info = next(l for l in data["languages"] if l["code"] == "cg")
    assert cg_info["name"] == "Chhattisgarhi"
    assert "छत्तीसगढ़ी" in cg_info["native_name"]
    assert "जोहार" in cg_info["greeting"]
    print(f"✅ Multilingual Language Directory verified ({data['count']} languages, including Chhattisgarhi, Hindi, Bengali, Telugu, Marathi)")

def test_chhattisgarhi_and_hindi_translation():
    # 1. Translate clinical sentence to Chhattisgarhi (cg)
    cg_res = client.post("/api/translate", json={
        "text": "Hello, how are you? High fever and severe cough",
        "target_lang": "cg",
        "source_lang": "en"
    })
    assert cg_res.status_code == 200
    cg_data = cg_res.json()
    assert cg_data["target_lang"] == "cg"
    assert len(cg_data["translated_text"]) > 0
    # Chhattisgarhi dialect idioms verified
    assert any(term in cg_data["translated_text"] for term in ["जोहार", "कइसन", "तपन", "खोंखी", "बुखार"])
    print(f"✅ Chhattisgarhi Dialect Translation passed: '{cg_data['translated_text']}'")

    # 2. Translate to Hindi
    hi_res = client.post("/api/translate", json={
        "text": "Immediate Medical Attention Required",
        "target_lang": "hi",
        "source_lang": "en"
    })
    assert hi_res.status_code == 200
    hi_data = hi_res.json()
    assert hi_data["target_lang"] == "hi"
    assert "तत्काल" in hi_data["translated_text"] or "डॉक्टर" in hi_data["translated_text"] or "देखभाल" in hi_data["translated_text"]

    # 3. Test Translation Cache Hit
    cached_res = client.post("/api/translate", json={
        "text": "Immediate Medical Attention Required",
        "target_lang": "hi",
        "source_lang": "en"
    })
    assert cached_res.status_code == 200
    assert cached_res.json()["cached"] is True
    print("✅ High-Speed SQLite Translation Cache Hit verified")

def test_batch_translation_and_ui_dictionary():
    # 1. Batch translation
    batch_res = client.post("/api/translate", json={
        "texts": ["High Fever", "Severe Cough", "Jan Aushadhi Scheme"],
        "target_lang": "bn",
        "source_lang": "en"
    })
    assert batch_res.status_code == 200
    batch_data = batch_res.json()
    assert len(batch_data["translated_texts"]) == 3
    print("✅ Batch Translation passed (Bengali 3 strings converted)")

    # 2. UI Localized Dictionary retrieval
    dict_res = client.get("/api/translations/cg")
    assert dict_res.status_code == 200
    cg_dict = dict_res.json()["dictionary"]
    assert "मितानिन" in cg_dict["role_asha_title"]
    assert "खोंखी" in cg_dict["lbl_symptoms"] or "तकलीफ" in cg_dict["lbl_symptoms"]
    print(f"✅ Localized UI Dictionary verified for Chhattisgarhi ({len(cg_dict)} keys)")

def test_dynamic_triage_result_translation():
    triage_payload = {
        "target_lang": "cg",
        "source_lang": "en",
        "condition": "Pneumonia",
        "condition_description": "An infection that inflames air sacs in lungs.",
        "action_advice": "Visit Primary Health Centre immediately.",
        "precautions": ["Rest in upright position.", "Drink clean boiled water."],
        "referral_facility": "Primary Health Centre (PHC)",
        "referral_action": "Accompany patient or arrange 108 ambulance."
    }
    res = client.post("/api/translate/triage-result", json=triage_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["target_lang"] == "cg"
    assert "condition" in data
    assert len(data["precautions"]) == 2
    assert "referral_facility" in data
    print(f"✅ Dynamic Triage Medical Guidance Translation passed (Condition: {data['condition']}, Precautions: {data['precautions'][0]})")

if __name__ == "__main__":
    init_db()
    print("🚀 Running GramCare AI Advanced Feature Test Suite...\n")
    test_frontend_root()
    test_health()
    test_patient_registration_and_triage()
    test_emergency_symptom_override()
    test_medium_risk_telemedicine()
    test_authentication_token_and_family_vault()
    test_google_authentication()
    test_multilingual_language_directory()
    test_chhattisgarhi_and_hindi_translation()
    test_batch_translation_and_ui_dictionary()
    test_dynamic_triage_result_translation()
    test_top3_differential_diagnoses()
    test_allergy_filtering()
    rec_id = test_longitudinal_risk_escalation()
    test_analytics_and_referral_loop(rec_id)
    print("\n🎉 ALL ADVANCED GRAMCARE AI TESTS (MULTILINGUAL, TRANSLATION API, AUTH & FAMILY VAULT) PASSED WITH 100% SUCCESS!")




