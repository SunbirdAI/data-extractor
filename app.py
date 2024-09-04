import gradio as gr
import os
from database.vaccine_coverage_db import VaccineCoverageDB
from rag.rag_pipeline import RAGPipeline
from utils.helpers import process_response
from config import DB_PATH, METADATA_FILE, PDF_DIR
from initialize_db import initialize_database, populate_database

# Initialize database if it doesn't exist
if not os.path.exists(DB_PATH):
    print("Database not found. Initializing...")
    initialize_database()
    populate_database()

# Initialize database and RAG pipeline
db = VaccineCoverageDB(DB_PATH)
rag = RAGPipeline(METADATA_FILE, PDF_DIR, use_semantic_splitter=True)


def query_rag(question, prompt_type):
    if prompt_type == "Highlight":
        response = rag.query(question, prompt_type="highlight")
    else:
        response = rag.query(question, prompt_type="evidence_based")

    processed = process_response(response)
    return processed["markdown"]


def save_pdf(item_key):
    attachments = db.get_attachments_for_item(item_key)
    if attachments:
        attachment_key = attachments[0]["key"]
        output_path = os.path.join(PDF_DIR, f"{attachment_key}.pdf")
        if db.save_pdf_to_file(attachment_key, output_path):
            return f"PDF saved successfully to {output_path}"
    return "Failed to save PDF or no attachments found"


# Gradio interface
with gr.Blocks() as demo:
    gr.Markdown("# Vaccine Coverage Study RAG System")

    with gr.Tab("Query"):
        question_input = gr.Textbox(label="Enter your question")
        prompt_type = gr.Radio(["Highlight", "Evidence-based"], label="Prompt Type")
        query_button = gr.Button("Submit Query")
        output = gr.Markdown(label="Response")

        query_button.click(
            query_rag, inputs=[question_input, prompt_type], outputs=output
        )

    with gr.Tab("Save PDF"):
        item_key_input = gr.Textbox(label="Enter item key")
        save_button = gr.Button("Save PDF")
        save_output = gr.Textbox(label="Save Result")

        save_button.click(save_pdf, inputs=item_key_input, outputs=save_output)

if __name__ == "__main__":
    demo.launch()
