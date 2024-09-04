import gradio as gr
import os
from rag_pipeline import RAGPipeline
import openai
openai.api_key = os.environ.get('OPENAI_API_KEY')

# Initialize the RAG pipeline
rag = RAGPipeline("metadata_map.json", "pdfs")

def process_query(question, response_format):
    response = rag.query(question)
    
    if response_format == "Markdown":
        return response["markdown"]
    else:
        return response["raw"]

# Define the Gradio interface
iface = gr.Interface(
    fn=process_query,
    inputs=[
        gr.Textbox(lines=2, placeholder="Enter your question here...", label="Question"),
        gr.Radio(["Markdown", "Raw Text"], label="Response Format", value="Markdown")
    ],
    outputs=gr.Markdown(label="Response"),
    title="Vaccine Coverage and Hesitancy Research QA",
    description="Ask questions about vaccine coverage and hesitancy. The system will provide answers based on the available research papers.",
    examples=[
        ["What are the main factors contributing to vaccine hesitancy?", "Markdown"],
        ["What are the current vaccine coverage rates in African countries?", "Raw Text"],
    ],
    allow_flagging="never"
)

# Launch the app
iface.launch()