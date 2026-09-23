import re
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List, Optional

CSV_PATH = Path(__file__).resolve().parent.parent / "datasets" / "processed" / "final_healthcare_dataset.csv"

class KnowledgeBase:
    def __init__(self, csv_path: Path = CSV_PATH):
        self.disease_data: Dict[str, Dict[str, Any]] = {}
        self._load(csv_path)

    def _load(self, csv_path: Path):
        if not csv_path.exists():
            return
        
        df = pd.read_csv(csv_path)
        # Group by disease to collect unique descriptions and precautions
        for disease, group in df.groupby("disease"):
            row = group.iloc[0]
            # Gather unique symptom keywords across rows for this disease
            all_symptoms = set()
            for s in group["symptoms"].dropna():
                for sym in str(s).split(","):
                    clean_sym = sym.strip().lower()
                    if clean_sym:
                        all_symptoms.add(clean_sym)
            
            precautions = []
            for i in range(1, 5):
                col = f"Precaution_{i}"
                if col in row and pd.notna(row[col]) and str(row[col]).strip():
                    precautions.append(str(row[col]).strip().capitalize())

            self.disease_data[disease] = {
                "disease": disease,
                "description": str(row["Description"]) if pd.notna(row.get("Description")) else "",
                "precautions": precautions,
                "symptoms": list(all_symptoms),
                "risk_level": str(row["risk_level"]) if pd.notna(row.get("risk_level")) else "Medium"
            }

    def match_condition(self, user_symptoms: str) -> Optional[Dict[str, Any]]:
        """Find the best matching condition based on symptom keyword overlap."""
        if not self.disease_data:
            return None
            
        user_words = set(re.findall(r'\w+', user_symptoms.lower()))
        if not user_words:
            return None

        best_score = -1.0
        best_disease = None

        for disease, data in self.disease_data.items():
            disease_symptoms_text = " ".join(data["symptoms"]).lower()
            disease_words = set(re.findall(r'\w+', disease_symptoms_text))
            
            # Add disease name words into matching
            disease_words.update(re.findall(r'\w+', disease.lower()))

            intersection = user_words.intersection(disease_words)
            if intersection:
                score = len(intersection) / (len(user_words) + len(disease_words) - len(intersection))
                if score > best_score:
                    best_score = score
                    best_disease = data

        return best_disease

    def get_action_advice(self, risk_level: str) -> str:
        risk_level_norm = risk_level.strip().capitalize()
        if risk_level_norm == "High":
            return "Urgent: Immediate medical attention required. Please visit the nearest Primary Health Centre (PHC) or emergency clinic immediately."
        elif risk_level_norm == "Medium":
            return "Moderate: Schedule a consultation with a local healthcare worker (ASHA / ANM) or primary clinic within 24-48 hours. Monitor symptoms carefully."
        else:
            return "Mild: Home care and observation recommended. Follow basic hygiene, maintain hydration, and observe precautions. Consult a clinic if symptoms worsen."

    def get_generic_medicines(self, condition: Optional[str], risk_level: str) -> List[Dict[str, Any]]:
        """Provides affordable generic medicine alternatives (Jan Aushadhi Scheme) with estimated savings."""
        cond = (condition or "").strip().lower()

        # Standard generic mappings for primary rural healthcare conditions
        catalog = {
            "cold": [
                {"name": "Paracetamol 500mg", "type": "Tablet", "purpose": "Fever & body ache relief", "jan_aushadhi": True, "savings": "60% - 75% savings vs commercial brands"},
                {"name": "Cetirizine 10mg", "type": "Tablet", "purpose": "Sneezing & runny nose relief", "jan_aushadhi": True, "savings": "70% - 80% savings vs commercial brands"},
                {"name": "Normal Saline Nasal Drops", "type": "Drops", "purpose": "Nasal congestion easing", "jan_aushadhi": True, "savings": "50% - 70% savings vs commercial brands"}
            ],
            "fungal": [
                {"name": "Clotrimazole 1% Cream", "type": "Topical Cream", "purpose": "Antifungal skin treatment", "jan_aushadhi": True, "savings": "65% - 80% savings vs commercial brands"},
                {"name": "Cetirizine 10mg", "type": "Tablet", "purpose": "Relief from skin itching", "jan_aushadhi": True, "savings": "70% - 80% savings vs commercial brands"}
            ],
            "allergy": [
                {"name": "Cetirizine 10mg", "type": "Tablet", "purpose": "Anti-allergic symptom relief", "jan_aushadhi": True, "savings": "70% - 80% savings vs commercial brands"},
                {"name": "Calamine Lotion", "type": "Lotion", "purpose": "Soothing skin irritation", "jan_aushadhi": True, "savings": "50% - 65% savings vs commercial brands"}
            ],
            "gerd": [
                {"name": "Omeprazole 20mg / Pantoprazole 40mg", "type": "Capsule/Tablet", "purpose": "Reduces stomach acid & heartburn", "jan_aushadhi": True, "savings": "60% - 75% savings vs commercial brands"},
                {"name": "Aluminium Hydroxide + Magnesium Gel", "type": "Syrup", "purpose": "Rapid acid neutralization", "jan_aushadhi": True, "savings": "55% - 70% savings vs commercial brands"}
            ],
            "gastro": [
                {"name": "Oral Rehydration Salts (ORS WHO Formula)", "type": "Powder Sachet", "purpose": "Prevents dehydration from loose motions", "jan_aushadhi": True, "savings": "50% - 60% savings vs commercial brands"},
                {"name": "Zinc Sulfate 20mg", "type": "Tablet", "purpose": "Gut mucosal recovery in diarrhea", "jan_aushadhi": True, "savings": "60% - 70% savings vs commercial brands"}
            ],
            "asthma": [
                {"name": "Salbutamol Inhaler 100mcg", "type": "Inhaler", "purpose": "Fast-acting bronchodilator for wheezing", "jan_aushadhi": True, "savings": "50% - 65% savings vs commercial brands"},
                {"name": "Levocetirizine 5mg", "type": "Tablet", "purpose": "Allergic airway management", "jan_aushadhi": True, "savings": "60% - 75% savings vs commercial brands"}
            ],
            "fever": [
                {"name": "Paracetamol 500mg / 650mg", "type": "Tablet", "purpose": "Antipyretic for fever reduction", "jan_aushadhi": True, "savings": "60% - 75% savings vs commercial brands"},
                {"name": "ORS Electrolyte Sachet", "type": "Sachet", "purpose": "Electrolyte and fluid replenishment", "jan_aushadhi": True, "savings": "50% - 60% savings vs commercial brands"}
            ],
            "arthritis": [
                {"name": "Paracetamol 650mg", "type": "Tablet", "purpose": "Joint pain management", "jan_aushadhi": True, "savings": "60% - 70% savings vs commercial brands"},
                {"name": "Diclofenac Sodium 1% Gel", "type": "Gel", "purpose": "Topical joint inflammation relief", "jan_aushadhi": True, "savings": "55% - 70% savings vs commercial brands"}
            ],
            "hypertension": [
                {"name": "Amlodipine 5mg", "type": "Tablet (Prescription)", "purpose": "Blood pressure management", "jan_aushadhi": True, "savings": "70% - 85% savings vs commercial brands"}
            ],
            "diabetes": [
                {"name": "Metformin 500mg", "type": "Tablet (Prescription)", "purpose": "Glycemic regulation", "jan_aushadhi": True, "savings": "65% - 80% savings vs commercial brands"}
            ]
        }

        # Match condition
        if "cold" in cond:
            return catalog["cold"]
        elif "fungal" in cond or "tinea" in cond:
            return catalog["fungal"]
        elif "allergy" in cond or "acne" in cond:
            return catalog["allergy"]
        elif "gerd" in cond or "peptic" in cond or "ulcer" in cond:
            return catalog["gerd"]
        elif "gastro" in cond or "diarrh" in cond:
            return catalog["gastro"]
        elif "asthma" in cond or "bronch" in cond:
            return catalog["asthma"]
        elif "malaria" in cond or "dengue" in cond or "typhoid" in cond:
            return catalog["fever"]
        elif "arthritis" in cond or "osteo" in cond or "spondyl" in cond:
            return catalog["arthritis"]
        elif "hypertens" in cond:
            return catalog["hypertension"]
        elif "diabet" in cond:
            return catalog["diabetes"]
        else:
            return [
                {"name": "Paracetamol 500mg", "type": "Tablet", "purpose": "General pain and mild fever management", "jan_aushadhi": True, "savings": "60% - 75% savings vs commercial brands"},
                {"name": "Oral Rehydration Salts (ORS)", "type": "Sachet", "purpose": "Hydration and essential electrolytes", "jan_aushadhi": True, "savings": "50% - 60% savings vs commercial brands"}
            ]

    def get_referral_guidance(self, risk_level: str, condition: Optional[str]) -> Dict[str, Any]:
        """Provides structured referral guidance for ASHA workers and rural clinics."""
        norm_risk = risk_level.strip().capitalize()
        if norm_risk == "High":
            return {
                "urgency": "Immediate / Emergency",
                "facility": "Primary Health Centre (PHC) / Community Health Centre (CHC) / District Hospital",
                "timeframe": "Within 2 to 4 hours",
                "asha_action": "Accompany patient or arrange 108 ambulance transport. Alert Medical Officer at PHC."
            }
        elif norm_risk == "Medium":
            return {
                "urgency": "Sub-Acute / Doctor Consultation",
                "facility": "Ayushman Arogya Mandir (Sub-Centre) or visiting Medical Officer",
                "timeframe": "Within 24 to 48 hours",
                "asha_action": "Schedule telemedicine consultation or guide patient to next outpatient clinic visit."
            }
        else:
            return {
                "urgency": "Self-Care & Observation",
                "facility": "Local ASHA Worker guidance / Jan Aushadhi Kendra",
                "timeframe": "Follow up after 3 to 5 days if not resolved",
                "asha_action": "Advise rest, hydration, generic home medicines, and report back if symptoms progress."
            }

# Singleton instance
kb = KnowledgeBase()
