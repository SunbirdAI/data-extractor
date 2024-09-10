import json
from typing import List, Tuple

import gradio as gr

from config import STUDY_FILES
from rag.rag_pipeline import RAGPipeline
from utils.helpers import generate_follow_up_questions
from utils.prompts import (
    highlight_prompt,
    evidence_based_prompt,
    sample_questions,
)

rag_cache = {}


def get_rag_pipeline(study_name: str) -> RAGPipeline:
    """Get or create a RAGPipeline instance for the given study."""
    if study_name not in rag_cache:
        study_file = STUDY_FILES.get(study_name)
        if not study_file:
            raise ValueError(f"Invalid study name: {study_name}")
        rag_cache[study_name] = RAGPipeline(study_file)
    return rag_cache[study_name]


def chat_function(
    message: str, history: List[List[str]], study_name: str, prompt_type: str
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
    visible_questions = [gr.update(visible=True, value=q) for q in questions]
    hidden_questions = [gr.update(visible=False) for _ in range(3 - len(questions))]
    return (study_info, *visible_questions, *hidden_questions)


def set_question(question: str) -> str:
    return question.lstrip("✨ ")


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
            with gr.Column(scale=2):
                chatbot = gr.Chatbot(
                    elem_id="chatbot",
                    show_label=False,
                    height=600,
                    container=False,
                    show_copy_button=False,
                    layout="bubble",
                    visible=True,
                )
                with gr.Row():
                    msg = gr.Textbox(
                        show_label=False,
                        placeholder="Type your message here...",
                        scale=4,
                        lines=1,
                        autofocus=True,
                    )
                    send_btn = gr.Button("Send", scale=1)

            with gr.Column(scale=1):
                gr.Markdown("### Study Information")
                study_dropdown = gr.Dropdown(
                    choices=list(STUDY_FILES.keys()),
                    label="Select Study",
                    value=list(STUDY_FILES.keys())[0],
                )
                study_info = gr.Markdown(label="Study Details")
                with gr.Accordion("Sample Questions", open=False):
                    sample_btns = [
                        gr.Button(f"Sample Question {i+1}", visible=False)
                        for i in range(3)
                    ]

                gr.Markdown("### ✨ Generated Questions")
                with gr.Row():
                    follow_up_btns = [
                        gr.Button(f"Follow-up {i+1}", visible=False) for i in range(3)
                    ]

                gr.Markdown("### Settings")
                prompt_type = gr.Radio(
                    ["Default", "Highlight", "Evidence-based"],
                    label="Prompt Type",
                    value="Default",
                )
                clear = gr.Button("Clear Chat")

        def user(
            user_message: str, history: List[List[str]]
        ) -> Tuple[str, List[List[str]]]:
            return "", (
                history + [[user_message, None]] if user_message.strip() else history
            )

        def bot(
            history: List[List[str]], study_name: str, prompt_type: str
        ) -> Tuple[List[List[str]], gr.update, gr.update, gr.update]:
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

            rag = get_rag_pipeline(study_name)
            follow_up_questions = generate_follow_up_questions(
                rag, bot_message, user_message, study_name
            )

            visible_questions = [
                gr.update(visible=True, value=q) for q in follow_up_questions
            ]
            hidden_questions = [
                gr.update(visible=False) for _ in range(3 - len(follow_up_questions))
            ]

            return (history, *visible_questions, *hidden_questions)

        msg.submit(user, [msg, chatbot], [msg, chatbot], queue=False).then(
            bot,
            [chatbot, study_dropdown, prompt_type],
            [chatbot, *follow_up_btns],
        )
        send_btn.click(user, [msg, chatbot], [msg, chatbot], queue=False).then(
            bot,
            [chatbot, study_dropdown, prompt_type],
            [chatbot, *follow_up_btns],
        )

        for btn in follow_up_btns + sample_btns:
            btn.click(set_question, inputs=[btn], outputs=[msg])

        clear.click(lambda: None, None, chatbot, queue=False)

        study_dropdown.change(
            fn=update_interface,
            inputs=study_dropdown,
            outputs=[study_info, *sample_btns],
        )

    return demo


demo = create_gr_interface()

if __name__ == "__main__":
    # demo = create_gr_interface()
    demo.launch(share=True, debug=True)
