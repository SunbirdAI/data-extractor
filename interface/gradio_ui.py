import os

import gradio as gr
from cachetools import LRUCache
from dotenv import load_dotenv

from config import GRADIO_URL, STUDY_FILES, logger
from services.file_service import (
    cleanup_temp_files,
    download_as_csv,
    handle_pdf_upload,
    new_study_choices,
    process_pdf_query,
)
from services.rag_service import process_multi_input
# Import service functions
from services.zotero_service import get_study_info, process_zotero_library_items

load_dotenv()

# Create a cache instance for session state
cache = LRUCache(maxsize=100)


def get_cache_value(key):
    return cache.get(key)


process_zotero_library_items(
    os.getenv("ZOTERO_LIBRARY_ID"), os.getenv("ZOTERO_API_ACCESS_KEY"), cache
)


zotero_library_id = get_cache_value("zotero_library_id")
logger.info(f"zotero_library_id cache: {zotero_library_id}")


def create_gr_interface() -> gr.Blocks:
    """Create and configure the Gradio interface for the ACRES RAG Platform."""
    with gr.Blocks(theme=gr.themes.Base()) as demo:
        gr.Markdown("# ACRES RAG Platform")

        with gr.Tabs() as tabs:
            # ----- Tab 1: Study Analysis Interface -----
            with gr.Tab("Study Analysis"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### Zotero Credentials")
                        zotero_library_id_param = gr.Textbox(
                            label="Zotero Library ID",
                            type="password",
                            placeholder="Enter Your Zotero Library ID here...",
                        )
                        zotero_api_access_key = gr.Textbox(
                            label="Zotero API Access Key",
                            type="password",
                            placeholder="Enter Your Zotero API Access Key...",
                        )
                        process_zotero_btn = gr.Button("Process your Zotero Library")
                        zotero_output = gr.Markdown(label="Zotero")

                        gr.Markdown("### Study Information")
                        study_choices = list(STUDY_FILES.keys())
                        study_dropdown = gr.Dropdown(
                            choices=study_choices,
                            label="Select Study",
                            value=(study_choices[0] if study_choices else None),
                            allow_custom_value=True,
                        )
                        refresh_button = gr.Button("Refresh Studies")
                        study_info = gr.Markdown(label="Study Details")
                        new_studies = gr.Markdown(label="Your Studies")
                        prompt_type = gr.Radio(
                            ["Default", "Highlight", "Evidence-based"],
                            label="Prompt Type",
                            value="Default",
                        )

                    with gr.Column(scale=3):
                        gr.Markdown("### Study Variables")
                        with gr.Row():
                            study_variables = gr.Textbox(
                                show_label=False,
                                placeholder="Type your variables separated by commas e.g. (Study ID, Study Title, Authors etc)",
                                scale=4,
                                lines=1,
                                autofocus=True,
                            )
                            submit_btn = gr.Button("Submit", scale=1)
                        answer_output = gr.DataFrame(label="Answer")
                        download_btn = gr.DownloadButton(
                            "Download as CSV",
                            variant="primary",
                            size="sm",
                            scale=1,
                            visible=False,
                        )

            # ----- Tab 2: PDF Query Interface -----
            with gr.Tab("PDF Query"):
                with gr.Row():
                    with gr.Column(scale=7):
                        gr.Markdown("### PDF Query Variables")
                        pdf_variables = gr.Textbox(
                            show_label=False,
                            placeholder="Type your variables separated by commas (e.g., STUDYID, AUTHOR, YEAR, TITLE)",
                            scale=8,
                            lines=1,
                            autofocus=True,
                        )
                        pdf_submit_btn = gr.Button("Submit", scale=2)
                        pdf_answer_output = gr.DataFrame(label="Answer")
                        pdf_download_btn = gr.DownloadButton(
                            "Download as CSV",
                            variant="primary",
                            size="sm",
                            scale=1,
                            visible=False,
                        )
                    with gr.Column(scale=3):
                        with gr.Row():
                            pdf_files = gr.File(
                                file_count="multiple",
                                file_types=[".pdf"],
                                label="Upload PDFs",
                            )
                        with gr.Row():
                            collection_name = gr.Textbox(
                                label="Collection Name",
                                placeholder="Name this PDF collection...",
                            )
                        with gr.Row():
                            upload_variables = gr.Textbox(
                                label="Initial Variables (Optional)",
                                placeholder="Optional: Variables to extract during upload (e.g., STUDYID, AUTHOR, YEAR)",
                                lines=1,
                            )
                        with gr.Row():
                            upload_btn = gr.Button("Process PDFs", variant="primary")
                        pdf_status = gr.Markdown()
                        current_collection = gr.State(value=None)

                # Event handler for processing PDF uploads.
                upload_btn.click(
                    handle_pdf_upload,
                    inputs=[pdf_files, collection_name, upload_variables],
                    outputs=[pdf_status, current_collection],
                )

                # Event handler for processing the PDF query.
                pdf_submit_btn.click(
                    process_pdf_query,
                    inputs=[pdf_variables, current_collection],
                    outputs=[pdf_answer_output, pdf_download_btn],
                )

                # Download button handler.
                pdf_download_btn.click(
                    download_as_csv,
                    inputs=[pdf_answer_output],
                    outputs=[pdf_download_btn],
                ).then(cleanup_temp_files, inputs=None, outputs=None)

        # ----- Event Handlers for the Study Analysis Tab -----
        process_zotero_btn.click(
            lambda lib_id, api_key: (
                process_zotero_library_items(lib_id, api_key, cache),
                *new_study_choices(lib_id),
            ),
            inputs=[zotero_library_id_param, zotero_api_access_key],
            outputs=[zotero_output, new_studies, study_dropdown],
        )

        study_dropdown.change(
            get_study_info, inputs=[study_dropdown], outputs=[study_info]
        )

        submit_btn.click(
            lambda vars, study, prompt: process_multi_input(vars, study, prompt, cache),
            inputs=[study_variables, study_dropdown, prompt_type],
            outputs=[answer_output, download_btn],
        )

        download_btn.click(
            download_as_csv, inputs=[answer_output], outputs=[download_btn]
        ).then(cleanup_temp_files, inputs=None, outputs=None)

        refresh_button.click(
            lambda zotero_id: new_study_choices(
                zotero_id if zotero_id else zotero_library_id
            ),
            inputs=[zotero_library_id_param],
            outputs=[new_studies, study_dropdown],
        )

    return demo


demo = create_gr_interface()
