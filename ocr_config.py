import os

# Base paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(BASE_DIR, "samples")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")

# Default input/output paths
DEFAULT_IMAGE_PATH = os.path.join(SAMPLES_DIR, "sample_packaging.jpg")
DEFAULT_OUTPUT_PATH = os.path.join(OUTPUTS_DIR, "ocr_result.json")

# OCR settings
OCR_LANG = "en"
USE_GPU = False
USE_PREPROCESSING = False