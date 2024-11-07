# config.py

import os

from dotenv import load_dotenv

from utils.helpers import read_study_files

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


STUDY_FILES = read_study_files(("study_files.json"))
