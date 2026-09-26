from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from backend.db import get_analytics_summary, update_referral_status, get_triage_record_by_id

router = APIRouter(prefix="/api", tags=["Analytics & Referral Tracking"])

class ReferralStatusUpdate(BaseModel):
    referral_status: str = Field(..., example="Hospital Visited")
    doctor_notes: Optional[str] = Field(None, example="Doctor confirmed diagnosis at PHC. Prescribed oral antibiotics. Advised review in 7 days.")

@router.get("/analytics")
def get_health_analytics():
    """
    Returns rural healthcare analytics: consultation metrics, risk ratios,
    village outbreak signals, top conditions, and follow-ups due.
    """
    return get_analytics_summary()

@router.post("/history/{record_id}/referral-status")
def update_consultation_referral_status(record_id: int, req: ReferralStatusUpdate):
    """
    Closes the care loop by tracking referral progression:
    'Referral Generated' -> 'Hospital Visited' -> 'Doctor Consulted' -> 'Recovered'.
    """
    existing = get_triage_record_by_id(record_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Consultation record not found.")

    success = update_referral_status(
        record_id=record_id,
        referral_status=req.referral_status,
        doctor_notes=req.doctor_notes
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update referral status.")

    return {
        "status": "success",
        "record_id": record_id,
        "referral_status": req.referral_status,
        "doctor_notes": req.doctor_notes
    }
