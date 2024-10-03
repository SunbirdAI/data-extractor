import json
from typing import List, Tuple
import os

import gradio as gr
from dotenv import load_dotenv
from slugify import slugify

from config import STUDY_FILES
from rag.rag_pipeline import RAGPipeline
from utils.helpers import generate_follow_up_questions, append_to_study_files
from utils.prompts import (
    highlight_prompt,
    evidence_based_prompt,
    sample_questions,
)
import openai

from config import STUDY_FILES, OPENAI_API_KEY
from utils.zotero_manager import ZoteroManager

load_dotenv()

openai.api_key = OPENAI_API_KEY

# Cache for RAG pipelines
rag_cache = {}

def process_zotero_library_items(zotero_library_id: str, zotero_api_access_key: str) -> str:
    if not zotero_library_id or not zotero_api_access_key:
        return "Please enter your zotero library Id and API Access Key"

    zotero_library_id = zotero_library_id
    zotero_library_type = "user"  # or "group"
    zotero_api_access_key = zotero_api_access_key

    message = ""

    try:
        zotero_manager = ZoteroManager(
            zotero_library_id, zotero_library_type, zotero_api_access_key
        )

        zotero_collections = zotero_manager.get_collections()
        zotero_collection_lists = zotero_manager.list_zotero_collections(zotero_collections)
        filtered_zotero_collection_lists = (
            zotero_manager.filter_and_return_collections_with_items(zotero_collection_lists)
        )

        for collection in filtered_zotero_collection_lists:
            collection_name = collection.get("name")
            if collection_name not in STUDY_FILES:
                collection_key = collection.get("key")
                collection_items = zotero_manager.get_collection_items(collection_key)
                zotero_collection_items = (
                    zotero_manager.get_collection_zotero_items_by_key(collection_key)
                )
                #### Export zotero collection items to json ####
                zotero_items_json = zotero_manager.zotero_items_to_json(zotero_collection_items)
                export_file = f"{slugify(collection_name)}_zotero_items.json"
                zotero_manager.write_zotero_items_to_json_file(
                    zotero_items_json, f"data/{export_file}"
                )
                append_to_study_files("study_files.json", collection_name, f"data/{export_file}")
        message = "Successfully processed items in your zotero library"
    except Exception as e:
        message = f"Error process your zotero library: {str(e)}"
    
    return message


def get_rag_pipeline(study_name: str) -> RAGPipeline:
    """Get or create a RAGPipeline instance for the given study."""
    if study_name not in rag_cache:
        study_file = STUDY_FILES.get(study_name)
        if not study_file:
            raise ValueError(f"Invalid study name: {study_name}")
        rag_cache[study_name] = RAGPipeline(study_file)
    return rag_cache[study_name]


def chat_function(
    message: str, study_name: str, prompt_type: str
) -> str:
    """Process a chat message and generate a response using the RAG pipeline."""

    if not message.strip():
        return "Please enter a valid query."

    rag = get_rag_pipeline(study_name)
    prompt = {
        "Highlight": highlight_prompt,
        "Evidence-based": evidence_based_prompt,
    }.get(prompt_type)

    response = rag.query(message, prompt_template=prompt)
    return response.response


def get_study_info(study_name: str) -> str:
    """Retrieve information about the specified study."""

    study_file = STUDY_FILES.get(study_name)
    if not study_file:
        return "Invalid study name"

    with open(study_file, "r") as f:
        data = json.load(f)
    return f"### Number of documents: {len(data)}"


def update_interface(study_name: str) -> Tuple[str, gr.update, gr.update, gr.update]:
    """Update the interface based on the selected study."""

    study_info = get_study_info(study_name)
    questions = sample_questions.get(study_name, [])[:3]
    if not questions:
        questions = sample_questions.get("General", [])[:3]
    visible_questions = [gr.update(visible=True, value=q) for q in questions]
    hidden_questions = [gr.update(visible=False) for _ in range(3 - len(questions))]
    return (study_info, *visible_questions, *hidden_questions)


def set_question(question: str) -> str:
    return question.lstrip("✨ ")

def process_multi_input(text, study_name, prompt_type):
    # Split input based on commas and strip any extra spaces
    variable_list = [word.strip().upper() for word in text.split(',')]
    user_message =f"Extract and present in a tabular format the following variables for each {study_name} study: {', '.join(variable_list)}"
    response = chat_function(user_message, study_name, prompt_type)
    return response


def create_gr_interface() -> gr.Blocks:
    """
    Create and configure the Gradio interface for the RAG platform.

    This function sets up the entire user interface, including:
    - Chat interface with message input and display
    - Study selection dropdown
    - Sample and follow-up question buttons
    - Prompt type selection
    - Event handlers for user interactions

    Returns:
        gr.Blocks: The configured Gradio interface ready for launching.
    """

    with gr.Blocks() as demo:
        gr.Markdown("# ACRES RAG Platform")
        
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### Zotero Credentials")
                zotero_library_id = gr.Textbox(label="Zotero Library ID", type="password", placeholder="Enter Your Zotero Library ID here...")
                zotero_api_access_key = gr.Textbox(label="Zotero API Access Key", type="password", placeholder="Enter Your Zotero API Access Key...")
                process_zotero_btn = gr.Button("Process your Zotero Library")
                zotero_output = gr.Markdown(label="Zotero")

                gr.Markdown("### Study Information")
                study_dropdown = gr.Dropdown(
                    choices=list(STUDY_FILES.keys()),
                    label="Select Study",
                    value=list(STUDY_FILES.keys())[0],
                )
                study_info = gr.Markdown(label="Study Details")

                gr.Markdown("### Settings")
                prompt_type = gr.Radio(
                    ["Default", "Highlight", "Evidence-based"],
                    label="Prompt Type",
                    value="Default",
                )
                # clear = gr.Button("Clear Chat")
            
            with gr.Column(scale=3):
                gr.Markdown("### Study Variables")
                with gr.Row():
                    study_variables = gr.Textbox(
                        show_label=False,
                        placeholder="Type your variables separated by commas e.g (Study ID, Study Title, Authors etc)",
                        scale=4,
                        lines=1,
                        autofocus=True,
                    )
                    submit_btn = gr.Button("Submit", scale=1)
                answer_output = gr.Markdown(label="Answer")

        def user(
            user_message: str, history: List[List[str]]
        ) -> Tuple[str, List[List[str]]]:
            return "", (
                history + [[user_message, None]] if user_message.strip() else history
            )

        def bot(
            history: List[List[str]], study_name: str, prompt_type: str
        ) -> List[List[str]]:
            """
            Generate bot response and update the interface.

            This function:
            1. Processes the latest user message
            2. Generates a response using the RAG pipeline
            3. Updates the chat history
            4. Generates follow-up questions
            5. Prepares interface updates for follow-up buttons

            Args:
                history (List[List[str]]): The current chat history.
                study_name (str): The name of the current study.
                prompt_type (str): The type of prompt being used.

            Returns:
                Tuple[List[List[str]], gr.update, gr.update, gr.update]:
                Updated chat history and interface components for follow-up questions.
            """
            if not history:
                return history, [], [], []

            user_message = history[-1][0]
            bot_message = chat_function(user_message, history, study_name, prompt_type)
            history[-1][1] = bot_message

            return history

        # msg.submit(user, [msg, chatbot], [msg, chatbot], queue=False).then(
        #     bot,
        #     [chatbot, study_dropdown, prompt_type],
        #     [chatbot, *follow_up_btns],
        # )
        # send_btn.click(user, [msg, chatbot], [msg, chatbot], queue=False).then(
        #     bot,
        #     [chatbot, study_dropdown, prompt_type],
        #     [chatbot, *follow_up_btns],
        # )
        # for btn in follow_up_btns + sample_btns:
        #     btn.click(set_question, inputs=[btn], outputs=[msg])

        # clear.click(lambda: None, None, chatbot, queue=False)

        study_dropdown.change(
            fn=get_study_info,
            inputs=study_dropdown,
            outputs=[study_info],
        )

        process_zotero_btn.click(process_zotero_library_items, inputs=[zotero_library_id, zotero_api_access_key], outputs=[zotero_output], queue=False)
        submit_btn.click(process_multi_input, inputs=[study_variables, study_dropdown, prompt_type], outputs=[answer_output], queue=False)

    return demo


demo = create_gr_interface()

if __name__ == "__main__":
    # demo = create_gr_interface()
    demo.launch(share=True, debug=True)
