import os

# Base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Database configuration
DB_NAME = "vaccine_coverage_study.db"
DB_PATH = os.path.join(BASE_DIR, DB_NAME)

# RAG Pipeline configuration
DATA_DIR = os.path.join(BASE_DIR, "data")
METADATA_FILE = os.path.join(DATA_DIR, "metadata_map.json")
PDF_DIR = os.path.join(DATA_DIR, "pdfs")

# Create directories if they don't exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(PDF_DIR, exist_ok=True)

# OpenAI configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
