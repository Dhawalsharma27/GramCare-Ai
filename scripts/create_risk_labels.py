import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Load files
master = pd.read_csv("datasets/processed/healthcare_master_dataset.csv")
severity = pd.read_csv("datasets/raw/Symptom-severity.csv")

# Clean severity table
severity.columns = severity.columns.str.strip()
severity["Symptom"] = severity["Symptom"].str.replace("_", " ").str.lower()

# Create dictionary
severity_dict = dict(zip(severity["Symptom"], severity["weight"]))

# Calculate severity score
def calculate_score(symptoms):
    score = 0

    for symptom in str(symptoms).split(","):
        symptom = symptom.strip().lower()
        score += severity_dict.get(symptom, 0)

    return score

master["severity_score"] = master["symptoms"].apply(calculate_score)

# Disease-level triage categorization based on clinical urgency and rural healthcare triage standards
HIGH_RISK_DISEASES = {
    'Heart attack', 'Paralysis (brain hemorrhage)', 'Pneumonia', 'Tuberculosis',
    'Dengue', 'Typhoid', 'AIDS', 'Alcoholic hepatitis', 'Hepatitis B', 'Hepatitis C',
    'Hepatitis D', 'Hepatitis E', 'hepatitis A', 'Hypoglycemia', 'Hypertension ', 'Diabetes '
}

MEDIUM_RISK_DISEASES = {
    'Bronchial Asthma', 'Jaundice', 'Malaria', 'Peptic ulcer diseae', 'GERD',
    'Gastroenteritis', 'Urinary tract infection', 'Migraine', 'Chronic cholestasis',
    'Hyperthyroidism', 'Hypothyroidism', 'Chicken pox', 'Dimorphic hemmorhoids(piles)',
    '(vertigo) Paroymsal  Positional Vertigo', 'Varicose veins'
}

LOW_RISK_DISEASES = {
    'Common Cold', 'Allergy', 'Acne', 'Fungal infection', 'Psoriasis',
    'Impetigo', 'Arthritis', 'Osteoarthristis', 'Cervical spondylosis', 'Drug Reaction'
}

def assign_risk(disease):
    d = str(disease).strip()
    # Check matching ignoring trailing whitespace
    for hd in HIGH_RISK_DISEASES:
        if d == hd.strip():
            return "High"
    for md in MEDIUM_RISK_DISEASES:
        if d == md.strip():
            return "Medium"
    return "Low"

master["risk_level"] = master["disease"].apply(assign_risk)

# Save
master.to_csv(
    "datasets/processed/final_healthcare_dataset.csv",
    index=False
)

print(master[["disease", "severity_score", "risk_level"]].drop_duplicates(subset=["disease"]))
print("\nRisk Level Distribution:")
print(master["risk_level"].value_counts())
print("\n✅ Final dataset created!")