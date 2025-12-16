import os
import requests
import sys

MODEL_URL = 'https://zenodo.org/record/2592612/files/resnet50_v1.onnx'
TARGET_DIR = 'models'
TARGET_FILENAME = 'resnet50.onnx'

def main():
    if not os.path.exists(TARGET_DIR):
        os.makedirs(TARGET_DIR)
        print(f"Created directory: {TARGET_DIR}")

    target_path = os.path.join(TARGET_DIR, TARGET_FILENAME)

    if os.path.exists(target_path):
        print(f"Model already exists at: {target_path}")
        return

    print(f"Downloading ResNet50 from {MODEL_URL}...")
    try:
        response = requests.get(MODEL_URL, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(target_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total_size:
                    sys.stdout.write(f"\rProgress: {int(downloaded/total_size*100)}%")
                    sys.stdout.flush()
        
        print(f"\nSuccessfully saved to {target_path}")

    except Exception as e:
        print(f"\nDownload failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

