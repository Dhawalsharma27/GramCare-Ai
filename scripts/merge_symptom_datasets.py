import pandas as pd
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

os.makedirs("datasets/processed", exist_ok=True)

# -----------------------
# Load datasets
# -----------------------
training = pd.read_csv("datasets/raw/Training.csv")
description = pd.read_csv("datasets/raw/symptom_Description.csv")
precaution = pd.read_csv("datasets/raw/symptom_precaution.csv")
severity = pd.read_csv("datasets/raw/Symptom-severity.csv")

# -----------------------
# Convert Training.csv
# into symptoms + disease
# -----------------------

symptom_columns = training.columns[:-1]

rows = []

for _, row in training.iterrows():

    disease = row["prognosis"]

    symptoms = []

    for col in symptom_columns:
        if pd.notna(row[col]) and row[col] == 1:
            symptoms.append(col.replace("_", " "))

    rows.append({
        "disease": disease,
        "symptoms": ", ".join(symptoms)
    })

merged = pd.DataFrame(rows)

# -----------------------
# Add Description
# -----------------------

merged = merged.merge(
    description,
    left_on="disease",
    right_on="Disease",
    how="left"
)

merged.drop(columns=["Disease"], inplace=True)

# -----------------------
# Add Precautions
# -----------------------

merged = merged.merge(
    precaution,
    left_on="disease",
    right_on="Disease",
    how="left"
)

merged.drop(columns=["Disease"], inplace=True)

# -----------------------
# Save
# -----------------------

merged.to_csv(
    "datasets/processed/healthcare_master_dataset.csv",
    index=False
)

print("✅ Dataset merged successfully!")

print(merged.head())