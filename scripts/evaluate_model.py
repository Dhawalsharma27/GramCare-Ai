import joblib
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

# Load model
model = joblib.load("models/triage_model.pkl")

# Load vectorized data
X_train, X_test, y_train, y_test = joblib.load(
    "models/vectorized_data.pkl"
)

# Predict
predictions = model.predict(X_test)

print("Accuracy:", accuracy_score(y_test, predictions))
print("\nClassification Report:\n")
print(classification_report(y_test, predictions))

print("\nConfusion Matrix:\n")
print(confusion_matrix(y_test, predictions))