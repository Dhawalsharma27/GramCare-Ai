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

    def check_emergency_override(self, symptoms: str) -> Optional[Dict[str, Any]]:
        """
        Safety Protocol: Detects critical red-flag emergency symptoms that must bypass
        normal triage and unconditionally trigger immediate emergency medical care.
        """
        text = symptoms.lower()
        emergency_flags = [
            ("chest pain", "Acute chest pain / potential cardiac crisis"),
            ("heart attack", "Suspected myocardial infarction / heart attack"),
            ("shortness of breath", "Severe respiratory distress"),
            ("difficulty breathing", "Severe airway obstruction / acute dyspnea"),
            ("breathlessness", "Acute breathlessness"),
            ("loss of consciousness", "Unconsciousness / syncope"),
            ("unconscious", "Unconsciousness / altered sensorium"),
            ("fainting", "Acute collapse / fainting spell"),
            ("heavy bleeding", "Acute hemorrhage / severe blood loss"),
            ("stomach bleeding", "Internal GI hemorrhage"),
            ("blood vomiting", "Hematemesis / upper GI bleeding"),
            ("slurred speech", "Suspected acute stroke / cerebrovascular event"),
            ("paralysis", "Acute neurological deficit / stroke symptoms"),
            ("convulsion", "Seizure activity / status epilepticus"),
            ("seizure", "Acute seizure / neurological emergency"),
            ("coma", "Comatose state / severe depression of consciousness")
        ]

        for flag, description in emergency_flags:
            if flag in text:
                return {
                    "is_emergency": True,
                    "matched_symptom": flag,
                    "description": description,
                    "action": "Immediate 108 Emergency Ambulance transfer to Primary Health Centre (PHC) or District Hospital required. Do not delay."
                }
        return None

    def match_condition(self, user_symptoms: str) -> Optional[Dict[str, Any]]:
        """Find the best matching condition based on symptom keyword overlap."""
        top_list = self.match_top_conditions(user_symptoms, top_k=1)
        return top_list[0] if top_list else None

    def match_top_conditions(self, user_symptoms: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Find the top-K probable conditions with relative percentage confidence scores."""
        if not self.disease_data:
            return []
            
        user_words = set(re.findall(r'\w+', user_symptoms.lower()))
        if not user_words:
            return []

        scored_matches = []

        for disease, data in self.disease_data.items():
            disease_symptoms_text = " ".join(data["symptoms"]).lower()
            disease_words = set(re.findall(r'\w+', disease_symptoms_text))
            disease_words.update(re.findall(r'\w+', disease.lower()))

            intersection = user_words.intersection(disease_words)
            if intersection:
                # Jaccard index + weighting for disease name mentions
                jaccard = len(intersection) / (len(user_words) + len(disease_words) - len(intersection))
                name_bonus = 0.3 if any(w in disease.lower() for w in user_words) else 0.0
                final_score = jaccard + name_bonus
                scored_matches.append((final_score, data))

        if not scored_matches:
            # Fallback if no exact symptom word matched
            first_key = list(self.disease_data.keys())[0]
            return [{**self.disease_data[first_key], "relative_confidence": 1.0, "confidence_pct": 100}]

        # Sort descending by score
        scored_matches.sort(key=lambda x: x[0], reverse=True)
        top_matches = scored_matches[:top_k]

        total_score = sum(score for score, _ in top_matches) or 1.0
        results = []
        for score, data in top_matches:
            rel_conf = round(score / total_score, 3)
            conf_pct = max(5, int(rel_conf * 100))
            results.append({
                **data,
                "match_score": round(score, 3),
                "relative_confidence": rel_conf,
                "confidence_pct": conf_pct
            })

        # Ensure percentages sum to approx 100
        if len(results) == 1:
            results[0]["confidence_pct"] = 100

        return results

    def get_action_advice(self, risk_level: str) -> str:
        risk_level_norm = risk_level.strip().capitalize()
        if risk_level_norm == "High":
            return "Urgent: Immediate medical attention required. Please visit the nearest Primary Health Centre (PHC) or emergency clinic immediately."
        elif risk_level_norm == "Medium":
            return "Medium Risk: Clinical evaluation required. Do NOT rely on self-cure. Connect immediately with an online doctor via the live Video Call consultation below, or visit an Ayushman Arogya Mandir / PHC within 24 hours."
        else:
            return "Mild: Home care and observation recommended. Follow basic hygiene, maintain hydration, and observe precautions. Consult a clinic if symptoms worsen."

    def get_generic_medicines(self, condition: Optional[str], risk_level: str, allergies: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Provides affordable generic medicine alternatives (Jan Aushadhi Scheme) with allergy filtering."""
        cond = (condition or "").strip().lower()
        allergies_clean = [a.lower().strip() for a in (allergies or [])]

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
            selected_meds = catalog["cold"]
        elif "fungal" in cond or "tinea" in cond:
            selected_meds = catalog["fungal"]
        elif "allergy" in cond or "acne" in cond:
            selected_meds = catalog["allergy"]
        elif "gerd" in cond or "peptic" in cond or "ulcer" in cond:
            selected_meds = catalog["gerd"]
        elif "gastro" in cond or "diarrh" in cond:
            selected_meds = catalog["gastro"]
        elif "asthma" in cond or "bronch" in cond:
            selected_meds = catalog["asthma"]
        elif "malaria" in cond or "dengue" in cond or "typhoid" in cond:
            selected_meds = catalog["fever"]
        elif "arthritis" in cond or "osteo" in cond or "spondyl" in cond:
            selected_meds = catalog["arthritis"]
        elif "hypertens" in cond:
            selected_meds = catalog["hypertension"]
        elif "diabet" in cond:
            selected_meds = catalog["diabetes"]
        else:
            selected_meds = [
                {"name": "Paracetamol 500mg", "type": "Tablet", "purpose": "General pain and mild fever management", "jan_aushadhi": True, "savings": "60% - 75% savings vs commercial brands"},
                {"name": "Oral Rehydration Salts (ORS)", "type": "Sachet", "purpose": "Hydration and essential electrolytes", "jan_aushadhi": True, "savings": "50% - 60% savings vs commercial brands"}
            ]

        # Drug Allergy Safety Screening
        if allergies_clean:
            filtered = []
            for m in selected_meds:
                m_name = m["name"].lower()
                is_allergic = False
                for a in allergies_clean:
                    if not a:
                        continue
                    if a in m_name:
                        is_allergic = True
                        break
                    if a in ("nsaid", "nsaids", "aspirin") and ("diclofenac" in m_name or "ibuprofen" in m_name or "aspirin" in m_name):
                        is_allergic = True
                        break
                    if a in ("penicillin", "amoxicillin") and ("amoxicillin" in m_name or "penicillin" in m_name):
                        is_allergic = True
                        break
                if not is_allergic:
                    filtered.append(m)
            return filtered

        return selected_meds

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
                "urgency": "Telemedicine Video Consultation Required (Medium Risk)",
                "facility": "Online Medical Officer (e-Sanjeevani / GramCare Telehealth Network)",
                "timeframe": "Connect Online Now (Doctor on Standby)",
                "asha_action": "Click 'Connect to Doctor Online (Live Video Call)' to start video consultation. Do not advise self-cure."
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
