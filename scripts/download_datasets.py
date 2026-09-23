import os
import shutil
import kagglehub

# Create destination folder
os.makedirs("datasets/raw", exist_ok=True)

datasets = [
    "niyarrbarman/symptom2disease",
    "itachi9604/disease-symptom-description-dataset",
    "kaushil268/disease-prediction-using-machine-learning"
]

for ds in datasets:

    print(f"\nDownloading {ds}")

    path = kagglehub.dataset_download(ds)

    print("Downloaded to:", path)

    # Walk through all files in the downloaded dataset
    for root, dirs, files in os.walk(path):

        for file in files:

            if file.endswith(".csv"):

                source = os.path.join(root, file)
                destination = os.path.join("datasets/raw", file)

                shutil.copy2(source, destination)

                print(f"Copied: {file}")

print("\nAll datasets copied successfully!")