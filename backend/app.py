import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from backend.db import init_db
from backend.routes.predict import router as predict_router, MODEL_PATH, VEC_PATH
from backend.routes.patients import router as patients_router
from backend.routes.history import router as history_router
from backend.routes.feedback import router as feedback_router
from backend.routes.voice import router as voice_router

sys.stdout.reconfigure(encoding='utf-8')

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables and migrations on startup
    init_db()
    yield

app = FastAPI(
    title="GramcareAi - Rural Healthcare Triage & Assistant API",
    description="AI-powered rural symptom triage, longitudinal risk progression, generic medicines, and ASHA decision support.",
    version="1.1.0",
    lifespan=lifespan
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API endpoints
app.include_router(predict_router)
app.include_router(patients_router)
app.include_router(history_router)
app.include_router(feedback_router)
app.include_router(voice_router)

@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "model_loaded": MODEL_PATH.exists(),
        "vectorizer_loaded": VEC_PATH.exists(),
        "service": "GramcareAi Triage Engine & Longitudinal Analysis"
    }

@app.get("/api")
def api_info():
    return {
        "name": "GramcareAi Rural Healthcare API",
        "status": "online",
        "docs_url": "/docs",
        "endpoints": [
            "POST /api/predict",
            "GET /api/patients",
            "GET /api/patients/{patient_id}/timeline",
            "GET /api/history",
            "GET /api/history/{id}",
            "POST /api/feedback",
            "GET /api/feedback",
            "POST /api/voice/transcribe",
            "GET /api/health"
        ]
    }

# Mount static frontend application
FRONTEND_DIR = BASE_DIR / "frontend"
FRONTEND_DIR.mkdir(exist_ok=True)
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=True)
