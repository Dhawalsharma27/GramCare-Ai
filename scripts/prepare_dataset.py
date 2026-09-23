import pandas as pd

# Load cleaned dataset
df = pd.read_csv("datasets/processed/cleaned_symptom2disease.csv")

print("Shape:", df.shape)

print("\nColumns:")
print(df.columns)

print("\nUnique Diseases:", df["label"].nunique())

print("\nSample Diseases:")
print(df["label"].unique()[:10])

print("\nClass Distribution:")
print(df["label"].value_counts())
