import os
import sys
import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer

sys.stdout.reconfigure(encoding='utf-8')

os.makedirs("models", exist_ok=True)

# Load your final dataset
df = pd.read_csv("datasets/processed/final_healthcare_dataset.csv")

# Features and labels
X = df["symptoms"]
y = df["risk_level"]      # or "disease" if you're training disease prediction

# Split
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y
)

# TF-IDF
vectorizer = TfidfVectorizer(
    max_features=5000,
    ngram_range=(1, 2),
    stop_words="english"
)

X_train_vec = vectorizer.fit_transform(X_train)
X_test_vec = vectorizer.transform(X_test)

# Save everything
joblib.dump(vectorizer, "models/vectorizer.pkl")
joblib.dump((X_train_vec, X_test_vec, y_train, y_test),
            "models/vectorized_data.pkl")

print("✅ TF-IDF completed")
print("Training shape:", X_train_vec.shape)
print("Testing shape:", X_test_vec.shape)