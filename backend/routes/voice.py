from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional, Dict, Any

router = APIRouter(prefix="/api/voice", tags=["Voice"])

@router.post("/transcribe")
async def transcribe_voice(
    audio: UploadFile = File(..., description="Audio file in WAV, MP3, or OGG format"),
    language: Optional[str] = Form("hi-IN", description="Language code e.g. hi-IN (Hindi) or en-IN (Indian English)")
) -> Dict[str, Any]:
    """
    Accepts voice audio from rural community workers / patients,
    returning transcribed symptoms for downstream triage.
    """
    if not audio.filename:
        raise HTTPException(status_code=400, detail="No audio file uploaded.")
    
    # Read audio metadata
    content = await audio.read()
    file_size_kb = round(len(content) / 1024, 2)
    
    return {
        "status": "received",
        "filename": audio.filename,
        "size_kb": file_size_kb,
        "language": language,
        "message": "Audio received. Voice transcription gateway ready."
    }
