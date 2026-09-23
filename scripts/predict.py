import joblib

model = joblib.load("models/triage_model.pkl")
vectorizer = joblib.load("models/vectorizer.pkl")

print("--- GramcareAi Triage Neural Network (Trained with Backpropagation & Epochs) ---")
print("Enter symptoms to predict triage risk level (or type 'exit' to quit)\n")

while True:
    symptoms = input("Enter symptoms: ")

    if symptoms.lower().strip() == "exit":
        break

    if not symptoms.strip():
        continue

    x = vectorizer.transform([symptoms])
    prediction = model.predict(x)[0]

    if hasattr(model, "predict_proba"):
        probs = model.predict_proba(x)[0]
        prob_str = " | ".join([f"{cls}: {p*100:.1f}%" for cls, p in zip(model.classes_, probs)])
        print(f"-> Risk Level: {prediction} ({prob_str})\n")
    else:
        print(f"-> Prediction: {prediction}\n")