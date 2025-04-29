# ACRES RAG Project Refactor Plan

## Overview

The current `app.py` has grown large and complex. This plan outlines how to modularize and refactor the codebase for better readability, maintainability, and reusability.

---

## 1. Identify Major Functional Areas

- **Configuration & Setup**: Environment variables, logging, directory creation.
- **Database & Storage**: ChromaDB, SQLite, file helpers.
- **Zotero & PDF Management**: ZoteroManager, PDFProcessor, file upload.
- **RAG Pipeline**: Retrieval, variable extraction, chat.
- **Gradio UI**: Interface and event handlers.
- **Utility Functions**: Cleanup, CSV/markdown conversion, etc.

---

## 2. Proposed Module Structure

```
acres/
│
├── app.py                # Only launches the Gradio app, minimal logic
├── config.py             # All configuration, env, logging, directory setup
├── interface/            # Gradio UI and event handlers
│   └── gradio_ui.py
├── rag/
│   └── rag_pipeline.py   # Already exists
├── services/
│   ├── zotero_service.py
│   ├── pdf_service.py
│   ├── rag_service.py
│   └── file_service.py
├── utils/
│   ├── db.py
│   ├── helpers.py
│   ├── prompts.py
│   ├── zotero_manager.py
│   ├── pdf_processor.py
│   └── ...
└── ...
```

---

## 3. Refactor Steps

### A. Move Configuration and Setup
- Move all env, logging, and directory setup to `config.py`.
- Expose config variables and logger for import.

### B. Move Gradio UI to `interface/gradio_ui.py`
- All Gradio Blocks, event handlers, and UI logic go here.
- `app.py` just calls `from interface.gradio_ui import demo` and launches it.

### C. Move Service Logic
- **Zotero/PDF**: All Zotero and PDF management functions to `services/zotero_service.py` and `services/pdf_service.py`.
- **RAG**: All RAG pipeline and chat logic to `services/rag_service.py`.
- **File/CSV**: File upload, CSV export, and cleanup to `services/file_service.py`.

### D. Utility Functions
- Keep helpers, db, and prompts in `utils/`.

### E. Event Handlers
- Event handler functions (for Gradio) should call into the service layer, not contain business logic.

---

## 4. Example: What Each File Might Look Like

### app.py
```python
from interface.gradio_ui import demo

if __name__ == "__main__":
    demo.launch(share=True, debug=True)
```

### config.py
```python
import os
import logging
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_DIR = "data"
UPLOAD_DIR = "zotero_data/uploads"
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
```

### interface/gradio_ui.py
```python
import gradio as gr
from services.zotero_service import process_zotero_library_items, get_study_info
from services.rag_service import process_multi_input
from services.file_service import handle_pdf_upload, process_pdf_query, download_as_csv, cleanup_temp_files

def create_gr_interface():
    # ... all Gradio Blocks and event handlers, calling service functions
    return demo

demo = create_gr_interface()
```

### services/zotero_service.py
```python
from utils.zotero_manager import ZoteroManager
from utils.helpers import append_to_study_files

def process_zotero_library_items(library_id, api_key):
    # ...logic from app.py, but no UI code
    return message

def get_study_info(study_name):
    # ...logic from app.py
    return info
```

### services/rag_service.py
```python
from rag.rag_pipeline import RAGPipeline

def process_multi_input(text, study_name, prompt_type):
    # ...logic from app.py
    return [response, gr.update(visible=True)]
```

### services/file_service.py
```python
def handle_pdf_upload(files, name, variables=""):
    # ...logic from app.py
    return status, collection_id

def process_pdf_query(variable_text, collection_id):
    # ...logic from app.py
    return df, gr.update(visible=True)

def download_as_csv(df):
    # ...logic from app.py
    return temp_path

def cleanup_temp_files():
    # ...logic from app.py
```

---

## 5. Benefits

- **Readability**: Each file is focused and easier to navigate.
- **Reusability**: Service functions can be reused in API endpoints or tests.
- **Testability**: Logic is separated from UI, making unit testing easier.
- **Maintainability**: Adding new features or fixing bugs is less error-prone.

---

## 6. Next Steps

- Start by moving configuration and setup to `config.py`.
- Move Gradio UI code to `interface/gradio_ui.py`.
- Move business logic to the appropriate service modules.
- Refactor event handlers to call service functions.
- Test each module after migration.

---

**Let the team know which part you want to start with, or if you want a full code refactor for a specific section!**