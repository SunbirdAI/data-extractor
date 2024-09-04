import os

# Database configuration
DB_PATH = 'vaccine_coverage_study.db'

# RAG Pipeline configuration
METADATA_FILE = os.path.join('data', 'metadata_map.json')
PDF_DIR = os.path.join('data', 'pdfs')

# OpenAI configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')