import os
import pandas as pd

RAW_FOLDER = "datasets/raw"

print("=" * 80)
print("EXPLORING ALL DATASETS")
print("=" * 80)

# Check if raw folder exists
if not os.path.exists(RAW_FOLDER):
    print(f"Folder '{RAW_FOLDER}' not found!")
    exit()

# Find all CSV files
csv_files = [f for f in os.listdir(RAW_FOLDER) if f.endswith(".csv")]

if not csv_files:
    print("No CSV files found in datasets/raw")
    exit()

# Explore each CSV
for file in csv_files:

    print("\n" + "=" * 80)
    print(f"Dataset: {file}")
    print("=" * 80)

    try:
        df = pd.read_csv(os.path.join(RAW_FOLDER, file))

        print(f"Rows: {df.shape[0]}")
        print(f"Columns: {df.shape[1]}")

        print("\nColumn Names:")
        print(df.columns.tolist())

        print("\nData Types:")
        print(df.dtypes)

        print("\nMissing Values:")
        print(df.isnull().sum())

        print("\nDuplicate Rows:")
        print(df.duplicated().sum())

        print("\nFirst 5 Rows:")
        print(df.head())

        print("\nBasic Statistics:")
        print(df.describe(include="all"))

    except Exception as e:
        print(f"Error reading {file}")
        print(e)

print("\nDataset exploration completed!")