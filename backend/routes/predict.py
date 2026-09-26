import joblib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from backend.knowledge import kb
from backend.db import save_triage_record, get_or_create_patient, evaluate_longitudinal_risk
from backend.routes.telemedicine import generate_telemedicine_session

router = APIRouter(prefix="/api", tags=["Prediction"])

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MODEL_PATH = BASE_DIR / "models" / "triage_model.pkl"
VEC_PATH = BASE_DIR / "models" / "vectorizer.pkl"

# Load artifacts
model = None
vectorizer = None

def load_models():
    global model, vectorizer
    if model is None and MODEL_PATH.exists():
        model = joblib.load(MODEL_PATH)
    if vectorizer is None and VEC_PATH.exists():
        vectorizer = joblib.load(VEC_PATH)

load_models()

class PredictRequest(BaseModel):
    symptoms: str = Field(..., example="cough, high fever, breathlessness")
    patient_name: Optional[str] = Field(None, example="Ramesh Kumar")
    phone: Optional[str] = Field(None, example="9876543210")
    age: Optional[int] = Field(None, example=45)
    gender: Optional[str] = Field(None, example="Male")
    village: Optional[str] = Field(None, example="Rampur")
    is_pregnant: bool = Field(False, example=False)
    comorbidities: List[str] = Field(default_factory=list, example=["Diabetes"])
    allergies: List[str] = Field(default_factory=list, example=["NSAIDs"])
    user_id: Optional[str] = Field(None, example="USR-1082")
    family_member_id: Optional[str] = Field(None, example="FAM-1082-CHILD-001")
    family_member_name: Optional[str] = Field(None, example="Aarav Kumar")
    token_id: Optional[str] = Field(None, example="TK-RAM-84920")

class GenericMedicineItem(BaseModel):
    name: str
    type: str
    purpose: str
    jan_aushadhi: bool
    savings: str

class TopConditionItem(BaseModel):
    disease: str
    confidence_pct: int
    description: Optional[str] = None
    precautions: List[str] = []

class ReferralGuidance(BaseModel):
    urgency: str
    facility: str
    timeframe: str
    asha_action: str

class LongitudinalInfo(BaseModel):
    is_escalated: bool = False
    baseline_risk: str
    recurrence_count: int = 0
    recurring_symptoms: List[str] = []
    alert_message: Optional[str] = None
    previous_visits_count: int = 0

class TelemedicineInfo(BaseModel):
    available: bool = False
    session_id: Optional[str] = None
    room_name: Optional[str] = None
    room_url: Optional[str] = None
    doctor_name: Optional[str] = None
    doctor_role: Optional[str] = None
    specialty: Optional[str] = None
    organization: Optional[str] = None
    status: Optional[str] = None
    instructions: Optional[str] = None

class PredictResponse(BaseModel):
    record_id: int
    patient_id: Optional[str] = None
    symptoms: str
    risk_level: str
    confidence: float
    class_probabilities: Dict[str, float]
    condition: Optional[str] = None
    condition_description: Optional[str] = None
    top_conditions: List[TopConditionItem] = []
    risk_reasons: List[str] = []
    emergency_override: bool = False
    precautions: List[str] = []
    action_advice: str
    generic_medicines: List[GenericMedicineItem] = []
    referral_guidance: Optional[ReferralGuidance] = None
    longitudinal_alert: Optional[str] = None
    longitudinal_analysis: Optional[LongitudinalInfo] = None
    telemedicine: Optional[TelemedicineInfo] = None
    followup_date: Optional[str] = None
    referral_status: str = "Referral Generated"
    user_id: Optional[str] = None
    family_member_id: Optional[str] = None
    family_member_name: Optional[str] = None
    token_id: Optional[str] = None
    patient_info: Dict[str, Any]

@router.post("/predict", response_model=PredictResponse)
def predict_triage(req: PredictRequest):
    load_models()
    if not model or not vectorizer:
        raise HTTPException(status_code=503, detail="Triage ML models are not available or still loading.")

    clean_symptoms = req.symptoms.strip()
    if not clean_symptoms:
        raise HTTPException(status_code=400, detail="Symptoms text cannot be empty.")

    # 1. Patient Profile Auto-Registration / Lookup
    patient_record = None
    patient_id = None
    if req.patient_name:
        patient_record = get_or_create_patient(
            name=req.patient_name,
            phone=req.phone,
            village=req.village,
            age=req.age,
            gender=req.gender,
            is_pregnant=req.is_pregnant,
            comorbidities=req.comorbidities,
            allergies=req.allergies
        )
        patient_id = patient_record.get("patient_id")

    # 2. Emergency Red-Flag Symptom Override Safety Check
    emergency_match = kb.check_emergency_override(clean_symptoms)
    is_emergency = emergency_match is not None

    # 3. Vectorize and ML Prediction
    x_vec = vectorizer.transform([clean_symptoms])
    predicted_risk = model.predict(x_vec)[0]
    
    # Probabilities
    probs = {}
    confidence = 1.0
    if hasattr(model, "predict_proba"):
        prob_values = model.predict_proba(x_vec)[0]
        for cls_name, p in zip(model.classes_, prob_values):
            probs[str(cls_name)] = round(float(p), 4)
        confidence = probs.get(predicted_risk, 1.0)

    # 4. Longitudinal Risk Assessment (Patient History over last 30-60 days)
    long_eval = evaluate_longitudinal_risk(
        patient_id=patient_id,
        current_symptoms=clean_symptoms,
        baseline_risk=predicted_risk
    )
    final_risk = long_eval["escalated_risk"]

    # 5. Explainability Reasoning Collection
    reasons: List[str] = []

    # If Emergency Red-Flag Triggered -> Override risk to High unconditionally
    if is_emergency:
        final_risk = "High"
        confidence = 1.0
        reasons.append(f"🚨 Clinical Emergency Override: {emergency_match['description']} detected ({emergency_match['matched_symptom']}). Immediate life-safety intervention required.")
    else:
        reasons.append(f"✓ ML Triage Classification: Evaluated symptom feature patterns as {predicted_risk} risk with {int(confidence * 100)}% model certainty.")

    if long_eval["is_escalated"]:
        reasons.append(f"✓ Longitudinal Progression: Key recurring symptoms ({', '.join(long_eval['recurring_symptoms'])}) detected across {long_eval['previous_visits_count'] + 1} consultations in the last 60 days.")
    elif long_eval["recurrence_count"] > 0:
        reasons.append(f"✓ Patient History Context: Prior consultation documented on patient profile.")

    # Vulnerability Factors
    if req.is_pregnant:
        reasons.append("✓ Vulnerability Flag: Maternal / Pregnancy Care protocol active (requires careful clinical monitoring).")
        if final_risk == "Low":
            final_risk = "Medium"
    if req.age and req.age >= 60:
        reasons.append(f"✓ Vulnerability Flag: Senior Citizen patient (Age {req.age}) with increased clinical vulnerability.")
    if req.age and req.age <= 5:
        reasons.append(f"✓ Vulnerability Flag: Pediatric patient (Age {req.age}) requiring urgent ASHA follow-up.")
    if req.comorbidities:
        reasons.append(f"✓ Comorbidity Impact: Patient has active condition(s): {', '.join(req.comorbidities)}.")
    if req.token_id:
        reasons.append(f"✓ ASHA Intake Token: Registered under Patient Token ID {req.token_id} for rural fieldwork tracking.")
    if req.family_member_name and req.family_member_name != req.patient_name:
        reasons.append(f"✓ Family Vault Profile: Consultation recorded for {req.family_member_name} under authenticated patient vault.")

    # 6. Condition, Top-3 Differential Diagnoses & Generic Medicines
    top_matches = kb.match_top_conditions(clean_symptoms, top_k=3)
    primary_condition = top_matches[0] if top_matches else None
    condition_name = primary_condition["disease"] if primary_condition else None
    condition_desc = primary_condition["description"] if primary_condition else None
    precautions = primary_condition["precautions"] if primary_condition else []

    action_advice = kb.get_action_advice(final_risk)
    generic_meds = kb.get_generic_medicines(condition_name, final_risk, allergies=req.allergies)
    referral_guide = kb.get_referral_guidance(final_risk, condition_name)

    # 7. Follow-up Date Calculation
    if is_emergency or final_risk == "High":
        followup_delta = 1  # 24 hours
    elif final_risk == "Medium":
        followup_delta = 3  # 3 days
    else:
        followup_delta = 7  # 7 days
    followup_date_str = (datetime.now() + timedelta(days=followup_delta)).date().isoformat()

    # 8. Persist to Database with Auth & Family Privacy Mapping
    record_id = save_triage_record(
        symptoms=clean_symptoms,
        risk_level=final_risk,
        confidence=confidence,
        condition=condition_name,
        top_conditions=top_matches,
        risk_reasons=reasons,
        emergency_override=is_emergency,
        precautions=precautions,
        action_advice=action_advice,
        generic_medicines=generic_meds,
        longitudinal_alert=long_eval["alert_message"],
        followup_date=followup_date_str,
        referral_status="Referral Generated",
        patient_id=patient_id,
        patient_name=req.patient_name,
        age=req.age,
        gender=req.gender,
        village=req.village,
        user_id=req.user_id,
        family_member_id=req.family_member_id,
        family_member_name=req.family_member_name,
        token_id=req.token_id
    )

    # 9. Telemedicine Online Doctor Video Call Backend (Mandatory for Medium Risk)
    telemedicine_data = None
    if final_risk == "Medium":
        reasons.append("✓ Telemedicine Video Call: Medium Risk requires clinical doctor evaluation. Online consultation session activated (self-cure not advised).")
        telemed_dict = generate_telemedicine_session(
            record_id=record_id,
            patient_name=req.patient_name,
            condition=condition_name,
            risk_level=final_risk
        )
        telemedicine_data = TelemedicineInfo(**telemed_dict)

    top_items = [
        TopConditionItem(
            disease=item["disease"],
            confidence_pct=item.get("confidence_pct", 50),
            description=item.get("description"),
            precautions=item.get("precautions", [])
        )
        for item in top_matches
    ]

    return PredictResponse(
        record_id=record_id,
        patient_id=patient_id,
        symptoms=clean_symptoms,
        risk_level=final_risk,
        confidence=confidence,
        class_probabilities=probs,
        condition=condition_name,
        condition_description=condition_desc,
        top_conditions=top_items,
        risk_reasons=reasons,
        emergency_override=is_emergency,
        precautions=precautions,
        action_advice=action_advice,
        generic_medicines=[GenericMedicineItem(**m) for m in generic_meds],
        referral_guidance=ReferralGuidance(**referral_guide),
        longitudinal_alert=long_eval["alert_message"],
        longitudinal_analysis=LongitudinalInfo(
            is_escalated=long_eval["is_escalated"],
            baseline_risk=predicted_risk,
            recurrence_count=long_eval["recurrence_count"],
            recurring_symptoms=long_eval["recurring_symptoms"],
            alert_message=long_eval["alert_message"],
            previous_visits_count=long_eval["previous_visits_count"]
        ),
        telemedicine=telemedicine_data,
        followup_date=followup_date_str,
        referral_status="Referral Generated",
        user_id=req.user_id,
        family_member_id=req.family_member_id,
        family_member_name=req.family_member_name,
        token_id=req.token_id,
        patient_info={
            "patient_id": patient_id,
            "patient_name": req.patient_name,
            "phone": req.phone,
            "age": req.age,
            "gender": req.gender,
            "village": req.village,
            "is_pregnant": req.is_pregnant,
            "comorbidities": req.comorbidities,
            "allergies": req.allergies
        }
    )
