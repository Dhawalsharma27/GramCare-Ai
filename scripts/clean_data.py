import os
import sys
import re
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

# Folder paths
RAW_FOLDER = "datasets/raw"
PROCESSED_FOLDER = "datasets/processed"

# Create processed folder if it doesn't exist
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

# Possible symptom column names
SYMPTOM_COLUMNS = [
    "text",
    "symptoms",
    "Symptoms",
    "symptom",
    "Symptom",
    "Disease_Description"
]

# Cleaning function
def clean_text(text):
    text = str(text).lower()
    text = re.sub(r'[^a-zA-Z ]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# Process every CSV
for file in os.listdir(RAW_FOLDER):

    if file.endswith(".csv"):

        filepath = os.path.join(RAW_FOLDER, file)

        print(f"\nProcessing: {file}")

        try:
            df = pd.read_csv(filepath)

            # Find symptom/text column
            found = False

            for col in SYMPTOM_COLUMNS:

                if col in df.columns:
                    df[col] = df[col].apply(clean_text)
                    found = True
                    print(f"✓ Cleaned column: {col}")
                    break

            if not found:
                print("⚠ No symptom/text column found.")
                print("Columns:", list(df.columns))

            # Save cleaned dataset
            output = os.path.join(PROCESSED_FOLDER, f"cleaned_{file}")

            df.to_csv(output, index=False)

            print(f"✓ Saved -> {output}")

        except Exception as e:
            print(f"❌ Error processing {file}")
            print(e)

print("\n✅ All datasets cleaned successfully!")