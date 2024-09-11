import os

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

STUDY_FILES = {
    "Vaccine Coverage": "data/vaccine_coverage_zotero_items.json",
    "Ebola Virus": "data/ebola_virus_zotero_items.json",
    "Gene Xpert": "data/gene_xpert_zotero_items.json",
}
