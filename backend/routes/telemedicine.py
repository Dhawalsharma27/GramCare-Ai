import time
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/telemedicine", tags=["Telemedicine"])

# Simulated Active Telemedicine Registry
ACTIVE_SESSIONS: Dict[str, Dict[str, Any]] = {}

DUTY_DOCTOR = {
    "doctor_id": "DOC-9082",
    "name": "Dr. Anjali Verma, MBBS",
    "role": "Medical Officer (Telemedicine On-Duty)",
    "specialty": "General Medicine & Rural Primary Healthcare",
    "organization": "e-Sanjeevani / National Rural Telehealth Hub",
    "status": "Online",
    "available": True,
    "rating": 4.9,
    "experience_years": 8,
    "languages": ["Hindi", "English", "Bhojpuri"]
}

class TelemedicineInitRequest(BaseModel):
    record_id: Optional[int] = None
    patient_id: Optional[str] = None
    patient_name: Optional[str] = "Patient"
    risk_level: str = "Medium"
    condition: Optional[str] = "Primary Evaluation"
    symptoms: Optional[str] = None

class TelemedicineSessionModel(BaseModel):
    available: bool = True
    session_id: str
    room_name: str
    room_url: str
    doctor_name: str
    doctor_role: str
    specialty: str
    organization: str
    status: str
    created_at: str
    instructions: str

class CompleteConsultationRequest(BaseModel):
    doctor_notes: str
    rx_medicines: Optional[List[str]] = []
    followup_advice: Optional[str] = None

def generate_telemedicine_session(
    record_id: Optional[int] = None,
    patient_name: Optional[str] = None,
    condition: Optional[str] = None,
    risk_level: str = "Medium"
) -> Dict[str, Any]:
    """Generates an instant WebRTC Telemedicine consultation room."""
    rec_num = record_id if record_id else int(time.time() % 100000)
    ts = int(time.time())
    session_id = f"GC-TELE-{rec_num}-{ts}"
    room_name = f"GramCare-Telemed-Room-{rec_num}-{ts % 1000}"
    # Standard WebRTC Jitsi Meet room (no software installation required)
    room_url = f"https://meet.jit.si/{room_name}#config.startWithAudioMuted=false&config.startWithVideoMuted=false"

    session_data = {
        "available": True,
        "session_id": session_id,
        "room_name": room_name,
        "room_url": room_url,
        "doctor_name": DUTY_DOCTOR["name"],
        "doctor_role": DUTY_DOCTOR["role"],
        "specialty": DUTY_DOCTOR["specialty"],
        "organization": DUTY_DOCTOR["organization"],
        "status": "Ready to Connect",
        "created_at": datetime.now().isoformat(),
        "instructions": (
            "Telemedicine video call initiated. Self-cure is not advised for Medium Risk. "
            "Please click 'Connect to Doctor Online' to launch the face-to-face video consultation."
        )
    }

    ACTIVE_SESSIONS[session_id] = {
        **session_data,
        "record_id": record_id,
        "patient_name": patient_name,
        "risk_level": risk_level,
        "condition": condition
    }

    return session_data

@router.get("/doctor-status")
def get_doctor_status():
    """Returns duty medical officer availability for rural video calls."""
    return {
        "status": "ok",
        "doctor": DUTY_DOCTOR,
        "active_telemedicine_sessions": len(ACTIVE_SESSIONS),
        "server_time": datetime.now().isoformat()
    }

@router.post("/session", response_model=TelemedicineSessionModel)
def create_session(req: TelemedicineInitRequest):
    """Initializes a new real-time video consultation session for Medium Risk cases."""
    session = generate_telemedicine_session(
        record_id=req.record_id,
        patient_name=req.patient_name,
        condition=req.condition,
        risk_level=req.risk_level
    )
    return TelemedicineSessionModel(**session)

@router.post("/session/{session_id}/complete")
def complete_consultation(session_id: str, req: CompleteConsultationRequest):
    """Doctor completes consultation and attaches clinical notes."""
    if session_id not in ACTIVE_SESSIONS:
        # Gracefully handle dynamic session completion
        ACTIVE_SESSIONS[session_id] = {
            "session_id": session_id,
            "created_at": datetime.now().isoformat()
        }

    session = ACTIVE_SESSIONS[session_id]
    session["status"] = "Completed"
    session["completed_at"] = datetime.now().isoformat()
    session["doctor_notes"] = req.doctor_notes
    session["rx_medicines"] = req.rx_medicines
    session["followup_advice"] = req.followup_advice

    return {
        "status": "success",
        "message": "Video consultation completed and recorded.",
        "session": session
    }
