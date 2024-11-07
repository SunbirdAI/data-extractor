"""
Gradio interface module for ACRES RAG Platform.
Defines the UI components and layout.
"""

import gradio as gr


def create_chat_interface() -> gr.Blocks:
    """Create the chat interface component."""
    with gr.Blocks() as chat_interface:
        with gr.Row():
            with gr.Column(scale=7):
                chat_history = gr.Chatbot(
                    value=[], elem_id="chatbot", height=600, show_label=False
                )
            with gr.Column(scale=3):
                pdf_preview = gr.Image(label="Source Page", height=600)

        with gr.Row():
            with gr.Column(scale=8):
                query_input = gr.Textbox(
                    show_label=False,
                    placeholder="Ask a question about your documents...",
                    container=False,
                )
            with gr.Column(scale=2):
                submit_btn = gr.Button("Send", variant="primary")

        with gr.Row():
            pdf_files = gr.File(
                file_count="multiple", file_types=[".pdf"], label="Upload PDF Files"
            )
            collection_name = gr.Textbox(
                label="Collection Name", placeholder="Name this collection of PDFs..."
            )

    return (
        chat_interface,
        chat_history,
        pdf_preview,
        query_input,
        submit_btn,
        pdf_files,
        collection_name,
    )
