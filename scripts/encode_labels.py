import pandas as pd
from sklearn.preprocessing import LabelEncoder
import joblib
import os

os.makedirs("models", exist_ok=True)

df = pd.read_csv("datasets/processed/cleaned_symptom2disease.csv")

encoder = LabelEncoder()

df["label_encoded"] = encoder.fit_transform(df["label"])

joblib.dump(encoder, "models/label_encoder.pkl")

df.to_csv("datasets/processed/encoded_dataset.csv", index=False)

print(df.head())
print("\nClasses:")
print(encoder.classes_)
