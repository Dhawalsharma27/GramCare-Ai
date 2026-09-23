import pandas as pd

df = pd.read_csv("datasets/processed/final_healthcare_dataset.csv")

print(df["risk_level"].value_counts())

print("\n-----------------------")

print(df["severity_score"].describe())

print("\n-----------------------")

print(df[["severity_score", "risk_level"]].head(20))