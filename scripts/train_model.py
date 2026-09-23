import sys
import joblib
import numpy as np
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import accuracy_score

sys.stdout.reconfigure(encoding='utf-8')

# 1. Load vectorized data
X_train, X_test, y_train, y_test = joblib.load(
    "models/vectorized_data.pkl"
)

classes = np.unique(y_train)

# 2. Build Multi-Layer Perceptron Neural Network
# Architecture: Input (651) -> Dense(128, ReLU) -> Dense(64, ReLU) -> Softmax(3)
# Optimization: Backpropagation using Adam optimizer & Cross-Entropy Loss
model = MLPClassifier(
    hidden_layer_sizes=(128, 64),
    activation="relu",
    solver="adam",
    learning_rate_init=0.001,
    random_state=42
)

# 3. Train with Backpropagation across Epochs
epochs = 25
batch_size = 64
n_samples = X_train.shape[0]

print(f"🚀 Training Neural Network using Backpropagation ({epochs} Epochs, batch_size={batch_size})...\n")

for epoch in range(1, epochs + 1):
    # Shuffle mini-batch indices each epoch
    indices = np.random.permutation(n_samples)
    
    for start_idx in range(0, n_samples, batch_size):
        batch_idx = indices[start_idx:start_idx + batch_size]
        X_batch = X_train[batch_idx]
        y_batch = y_train.iloc[batch_idx]
        
        # Forward pass, compute loss, backpropagation gradient step
        model.partial_fit(X_batch, y_batch, classes=classes)

    current_loss = model.loss_
    val_acc = accuracy_score(y_test, model.predict(X_test))
    
    print(f"Epoch {epoch:02d}/{epochs} | Cross-Entropy Loss: {current_loss:.4f} | Validation Accuracy: {val_acc * 100:.2f}%", flush=True)

# 4. Save trained neural network model
joblib.dump(model, "models/triage_model.pkl")

print(f"\n✅ Model trained successfully with backpropagation over {epochs} epochs!")
print(f"✅ Final Test Accuracy: {accuracy_score(y_test, model.predict(X_test)) * 100:.2f}%")