import secrets
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Query, Header

from backend.db import (
    create_user,
    authenticate_user,
    get_user_by_id,
    get_family_members,
    add_family_member,
    delete_family_member,
    generate_patient_token,
    get_patient_tokens_by_asha,
    get_token_by_id,
    get_vault_records_for_user,
    get_user_by_username_or_phone
)

router = APIRouter(prefix="/api/auth", tags=["Authentication & Family Vault"])

# In-memory active session tokens for security & privacy validation
ACTIVE_SESSIONS: Dict[str, Dict[str, Any]] = {
    "DEMO-ASHA-TOKEN": {
        "user_id": "ASHA-782",
        "username": "asha@gramcare.gov.in",
        "full_name": "Sunita Devi (ASHA Worker #782)",
        "role": "asha",
        "village": "Rampur"
    },
    "DEMO-PATIENT-TOKEN": {
        "user_id": "USR-1082",
        "username": "patient@gramcare.in",
        "full_name": "Ramesh Kumar",
        "role": "patient",
        "village": "Shivpur"
    }
}

class RegisterRequest(BaseModel):
    username: str = Field(..., example="patient@gramcare.in")
    password: str = Field(..., min_length=4, example="patient123")
    full_name: str = Field(..., example="Ramesh Kumar")
    role: str = Field("patient", example="patient")
    phone: Optional[str] = Field(None, example="9812345678")
    village: Optional[str] = Field(None, example="Shivpur")

class LoginRequest(BaseModel):
    username: str = Field(..., example="patient@gramcare.in")
    password: str = Field(..., example="patient123")

class FamilyMemberCreateRequest(BaseModel):
    user_id: str = Field(..., example="USR-1082")
    name: str = Field(..., example="Aarav Kumar")
    relation: str = Field(..., example="Child")
    age: Optional[int] = Field(None, example=9)
    gender: Optional[str] = Field(None, example="Male")
    is_pregnant: bool = Field(False, example=False)
    comorbidities: List[str] = Field(default_factory=list, example=[])
    allergies: List[str] = Field(default_factory=list, example=[])

class AshaGenerateTokenRequest(BaseModel):
    asha_worker_id: str = Field(..., example="ASHA-782")
    patient_name: str = Field(..., example="Meena Bai")
    phone: Optional[str] = Field(None, example="9899011223")
    village: Optional[str] = Field(None, example="Rampur")
    age: Optional[int] = Field(None, example=34)
    gender: Optional[str] = Field(None, example="Female")

@router.post("/register")
def register(req: RegisterRequest):
    """Registers a new Self-Patient or ASHA worker."""
    try:
        user = create_user(
            username=req.username,
            password=req.password,
            full_name=req.full_name,
            role=req.role,
            phone=req.phone,
            village=req.village
        )
        token = f"GC-SESSION-{secrets.token_hex(16)}"
        ACTIVE_SESSIONS[token] = user
        return {
            "status": "success",
            "message": "Registration successful",
            "session_token": token,
            "user": user
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration error: {str(e)}")

@router.post("/login")
def login(req: LoginRequest):
    """Authenticates credentials for ASHA workers and Self Patients."""
    user = authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username/phone or password.")

    token = f"GC-SESSION-{secrets.token_hex(16)}"
    ACTIVE_SESSIONS[token] = user
    return {
        "status": "success",
        "message": f"Welcome back, {user['full_name']}!",
        "session_token": token,
        "user": user
    }

class GoogleAuthRequest(BaseModel):
    email: str = Field(..., example="dhawal.gramcare@gmail.com")
    name: str = Field(..., example="Dhawal Sharma")
    google_id: Optional[str] = None
    village: Optional[str] = "Rural Health Sub-centre"

@router.post("/google")
def login_with_google(req: GoogleAuthRequest):
    """Google Single Sign-On (SSO) login & automatic account provisioning."""
    clean_email = req.email.strip().lower()
    user = get_user_by_username_or_phone(clean_email)

    if not user:
        # Auto-provision new patient account via Google SSO
        random_pwd = secrets.token_hex(16)
        user = create_user(
            username=clean_email,
            password=random_pwd,
            full_name=req.name.strip(),
            role="patient",
            village=req.village
        )

    token = f"GC-GOOGLE-SESSION-{secrets.token_hex(16)}"
    ACTIVE_SESSIONS[token] = user
    return {
        "status": "success",
        "message": f"Successfully signed in with Google as {user['full_name']}",
        "session_token": token,
        "user": user,
        "provider": "google"
    }

@router.get("/me")
def get_current_user(session_token: Optional[str] = Header(None, alias="X-Session-Token")):
    """Returns current active user session."""
    if session_token and session_token in ACTIVE_SESSIONS:
        return {"status": "authenticated", "user": ACTIVE_SESSIONS[session_token]}
    # Return demo patient default if no token provided
    return {"status": "unauthenticated", "user": None}

@router.post("/logout")
def logout(session_token: Optional[str] = Header(None, alias="X-Session-Token")):
    if session_token and session_token in ACTIVE_SESSIONS:
        del ACTIVE_SESSIONS[session_token]
    return {"status": "success", "message": "Logged out successfully"}

# --- Self & Family Health Vault Endpoints ---

@router.get("/family")
def list_family_members(user_id: str = Query(..., example="USR-1082")):
    """Lists all family members registered under a patient's vault."""
    members = get_family_members(user_id)
    return {
        "status": "success",
        "user_id": user_id,
        "count": len(members),
        "family_members": members
    }

@router.post("/family")
def create_family_member(req: FamilyMemberCreateRequest):
    """Adds a new family member (e.g. child, spouse, parent) to the patient's vault."""
    member = add_family_member(
        user_id=req.user_id,
        name=req.name,
        relation=req.relation,
        age=req.age,
        gender=req.gender,
        is_pregnant=req.is_pregnant,
        comorbidities=req.comorbidities,
        allergies=req.allergies
    )
    return {
        "status": "success",
        "message": f"Added family member '{member['name']}' ({member['relation']}) to your vault.",
        "member": member
    }

@router.delete("/family/{member_id}")
def remove_family_member(member_id: str, user_id: str = Query(...)):
    """Removes a family member from user's vault."""
    try:
        deleted = delete_family_member(user_id, member_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Family member not found.")
        return {"status": "success", "message": "Family member removed."}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

@router.get("/vault/history")
def get_vault_history(
    user_id: str = Query(...),
    family_member_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100)
):
    """Returns consultations strictly scoped to the user and selected family member (Data Privacy)."""
    records = get_vault_records_for_user(user_id=user_id, family_member_id=family_member_id, limit=limit)
    return {
        "status": "success",
        "user_id": user_id,
        "family_member_id": family_member_id,
        "count": len(records),
        "records": records
    }

# --- ASHA Worker Patient Intake Token Endpoints ---

@router.post("/asha/generate-token")
def create_token_for_asha(req: AshaGenerateTokenRequest):
    """Generates an encrypted, distinct patient intake token for ASHA community visits."""
    token = generate_patient_token(
        asha_worker_id=req.asha_worker_id,
        patient_name=req.patient_name,
        phone=req.phone,
        village=req.village,
        age=req.age,
        gender=req.gender
    )
    return {
        "status": "success",
        "message": f"Intake Token {token['token_id']} issued for patient {token['patient_name']}",
        "token": token
    }

@router.get("/asha/tokens")
def list_tokens_for_asha(asha_worker_id: str = Query(..., example="ASHA-782")):
    """Returns all patient tokens generated by an ASHA worker."""
    tokens = get_patient_tokens_by_asha(asha_worker_id)
    return {
        "status": "success",
        "asha_worker_id": asha_worker_id,
        "count": len(tokens),
        "tokens": tokens
    }

@router.get("/tokens/{token_id}")
def verify_token(token_id: str):
    """Verifies and fetches a patient token."""
    token = get_token_by_id(token_id)
    if not token:
        raise HTTPException(status_code=404, detail=f"Token '{token_id}' not found.")
    return {"status": "success", "token": token}
