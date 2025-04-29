# config.py

import logging
import os

from dotenv import load_dotenv

from utils.helpers import read_study_files

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Directory paths
DATA_DIR = "data"
UPLOAD_DIR = "zotero_data/uploads"

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Gradio URL (used for Gradio client, if needed elsewhere)
GRADIO_URL = os.getenv("GRADIO_URL", "http://localhost:7860/")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


STUDY_FILES = read_study_files(("study_files.json"))
