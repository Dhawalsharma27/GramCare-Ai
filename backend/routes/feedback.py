from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from backend.db import save_feedback, get_feedbacks, get_triage_record_by_id

router = APIRouter(prefix="/api/feedback", tags=["Feedback"])

class FeedbackRequest(BaseModel):
    record_id: Optional[int] = Field(None, description="Associated triage record ID", example=1)
    user_name: Optional[str] = Field(None, example="Dr. Sharma")
    rating: int = Field(..., ge=1, le=5, description="1 (Poor) to 5 (Excellent)", example=5)
    corrected_risk: Optional[str] = Field(None, description="Doctor-corrected risk level if model was wrong", example="High")
    comments: Optional[str] = Field(None, example="Accurate diagnosis and precautions.")

@router.post("")
def submit_feedback(req: FeedbackRequest):
    if req.record_id is not None:
        rec = get_triage_record_by_id(req.record_id)
        if not rec:
            raise HTTPException(status_code=404, detail="Referenced triage record not found.")

    feedback_id = save_feedback(
        record_id=req.record_id,
        user_name=req.user_name,
        rating=req.rating,
        corrected_risk=req.corrected_risk,
        comments=req.comments
    )
    return {
        "status": "success",
        "message": "Feedback recorded successfully",
        "feedback_id": feedback_id
    }

@router.get("", response_model=List[Dict[str, Any]])
def list_feedback(limit: int = 50):
    return get_feedbacks(limit=limit)
