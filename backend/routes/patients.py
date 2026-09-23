from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException

from backend.db import list_patients, get_patient_by_id, get_patient_consultations

router = APIRouter(prefix="/api/patients", tags=["Patients"])

@router.get("")
def get_all_patients(search: Optional[str] = None, limit: int = 50):
    """Retrieve list of rural patients for ASHA workers with visit counts & latest risk status."""
    return list_patients(search=search, limit=limit)

@router.get("/{patient_id}")
def get_patient_details(patient_id: str):
    """Get single patient profile details."""
    patient = get_patient_by_id(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found.")
    return patient

@router.get("/{patient_id}/timeline")
def get_patient_timeline(patient_id: str):
    """
    Returns full longitudinal history of consultations for this patient,
    enabling ASHA workers and doctors to view health progression over time.
    """
    patient = get_patient_by_id(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found.")
    
    consultations = get_patient_consultations(patient_id, limit=25)
    return {
        "patient": patient,
        "total_consultations": len(consultations),
        "timeline": consultations
    }
