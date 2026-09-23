import joblib
from pathlib import Path
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from backend.knowledge import kb
from backend.db import save_triage_record, get_or_create_patient, evaluate_longitudinal_risk

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

class GenericMedicineItem(BaseModel):
    name: str
    type: str
    purpose: str
    jan_aushadhi: bool
    savings: str

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

class PredictResponse(BaseModel):
    record_id: int
    patient_id: Optional[str] = None
    symptoms: str
    risk_level: str
    confidence: float
    class_probabilities: Dict[str, float]
    condition: Optional[str] = None
    condition_description: Optional[str] = None
    precautions: List[str] = []
    action_advice: str
    generic_medicines: List[GenericMedicineItem] = []
    referral_guidance: Optional[ReferralGuidance] = None
    longitudinal_analysis: Optional[LongitudinalInfo] = None
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
            gender=req.gender
        )
        patient_id = patient_record.get("patient_id")

    # 2. Vectorize and ML Prediction
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

    # 3. Longitudinal Risk Assessment (Patient History over last 30-60 days)
    long_eval = evaluate_longitudinal_risk(
        patient_id=patient_id,
        current_symptoms=clean_symptoms,
        baseline_risk=predicted_risk
    )
    final_risk = long_eval["escalated_risk"]

    # 4. Condition, Precautions, Generic Medicines & Referral Lookup
    condition_match = kb.match_condition(clean_symptoms)
    condition_name = condition_match["disease"] if condition_match else None
    condition_desc = condition_match["description"] if condition_match else None
    precautions = condition_match["precautions"] if condition_match else []

    action_advice = kb.get_action_advice(final_risk)
    generic_meds = kb.get_generic_medicines(condition_name, final_risk)
    referral_guide = kb.get_referral_guidance(final_risk, condition_name)

    # 5. Persist to SQLite Database
    record_id = save_triage_record(
        symptoms=clean_symptoms,
        risk_level=final_risk,
        confidence=confidence,
        condition=condition_name,
        precautions=precautions,
        action_advice=action_advice,
        generic_medicines=generic_meds,
        longitudinal_alert=long_eval["alert_message"],
        patient_id=patient_id,
        patient_name=req.patient_name,
        age=req.age,
        gender=req.gender,
        village=req.village
    )

    return PredictResponse(
        record_id=record_id,
        patient_id=patient_id,
        symptoms=clean_symptoms,
        risk_level=final_risk,
        confidence=confidence,
        class_probabilities=probs,
        condition=condition_name,
        condition_description=condition_desc,
        precautions=precautions,
        action_advice=action_advice,
        generic_medicines=[GenericMedicineItem(**m) for m in generic_meds],
        referral_guidance=ReferralGuidance(**referral_guide),
        longitudinal_analysis=LongitudinalInfo(
            is_escalated=long_eval["is_escalated"],
            baseline_risk=predicted_risk,
            recurrence_count=long_eval["recurrence_count"],
            recurring_symptoms=long_eval["recurring_symptoms"],
            alert_message=long_eval["alert_message"],
            previous_visits_count=long_eval["previous_visits_count"]
        ),
        patient_info={
            "patient_id": patient_id,
            "patient_name": req.patient_name,
            "phone": req.phone,
            "age": req.age,
            "gender": req.gender,
            "village": req.village
        }
    )
