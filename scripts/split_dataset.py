import pandas as pd
from sklearn.model_selection import train_test_split

df = pd.read_csv("datasets/processed/encoded_dataset.csv")

X = df["text"]
y = df["label_encoded"]

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y
)

print("Training Samples:", len(X_train))
print("Testing Samples:", len(X_test))