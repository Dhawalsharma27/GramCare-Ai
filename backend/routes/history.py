from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query

from backend.db import get_triage_records, get_triage_record_by_id

router = APIRouter(prefix="/api/history", tags=["History"])

@router.get("", response_model=List[Dict[str, Any]])
def list_history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    risk_level: Optional[str] = Query(None, description="Filter by risk level: High, Medium, Low")
):
    """Retrieve paginated triage records."""
    return get_triage_records(limit=limit, offset=offset, risk_level=risk_level)

@router.get("/{record_id}", response_model=Dict[str, Any])
def get_record(record_id: int):
    """Get single triage assessment by ID."""
    record = get_triage_record_by_id(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Triage record not found.")
    return record
