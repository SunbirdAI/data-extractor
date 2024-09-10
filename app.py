import gradio as gr
from rag.rag_pipeline import RAGPipeline
from utils.prompts import highlight_prompt, evidence_based_prompt, sample_questions
from config import STUDY_FILES
import json

# Cache for RAG pipelines
rag_cache = {}


def get_rag_pipeline(study_name):
    if study_name not in rag_cache:
        study_file = STUDY_FILES.get(study_name)
        if study_file:
            rag_cache[study_name] = RAGPipeline(study_file)
        else:
            raise ValueError(f"Invalid study name: {study_name}")
    return rag_cache[study_name]


def chat_function(message, history, study_name, prompt_type):
    if not message.strip():
        return "Please enter a valid query."

    rag = get_rag_pipeline(study_name)
    prompt = (
        highlight_prompt
        if prompt_type == "Highlight"
        else evidence_based_prompt if prompt_type == "Evidence-based" else None
    )
    response = rag.query(message, prompt_template=prompt)
    return response.response


def get_study_info(study_name):
    study_file = STUDY_FILES.get(study_name)
    if study_file:
        with open(study_file, "r") as f:
            data = json.load(f)
        return f"Number of documents: {len(data)}\nFirst document title: {data[0]['title']}"
    else:
        return "Invalid study name"


def update_interface(study_name):
    study_info = get_study_info(study_name)
    questions = sample_questions.get(study_name, [])[:3]
    return (
        study_info,
        *[gr.update(visible=True, value=q) for q in questions],
        *[gr.update(visible=False) for _ in range(3 - len(questions))],
    )


def set_question(question):
    return question


with gr.Blocks() as demo:
    gr.Markdown("# ACRES RAG Platform")

    with gr.Row():
        with gr.Column(scale=2):
            chatbot = gr.Chatbot(elem_id="chatbot", show_label=False, height=400)
            with gr.Row():
                msg = gr.Textbox(
                    show_label=False,
                    placeholder="Type your message here...",
                    scale=4,
                    lines=1,
                    autofocus=True,
                )
                send_btn = gr.Button("Send", scale=1)
            with gr.Accordion("Sample Questions", open=False):
                sample_btn1 = gr.Button("Sample Question 1", visible=False)
                sample_btn2 = gr.Button("Sample Question 2", visible=False)
                sample_btn3 = gr.Button("Sample Question 3", visible=False)

        with gr.Column(scale=1):
            gr.Markdown("### Study Information")
            study_dropdown = gr.Dropdown(
                choices=list(STUDY_FILES.keys()),
                label="Select Study",
                value=list(STUDY_FILES.keys())[0],
            )
            study_info = gr.Textbox(label="Study Details", lines=4)
            gr.Markdown("### Settings")
            prompt_type = gr.Radio(
                ["Default", "Highlight", "Evidence-based"],
                label="Prompt Type",
                value="Default",
            )
            clear = gr.Button("Clear Chat")

    def user(user_message, history):
        if not user_message.strip():
            return "", history  # Return unchanged if the message is empty
        return "", history + [[user_message, None]]

    def bot(history, study_name, prompt_type):
        if not history:
            return history
        user_message = history[-1][0]
        bot_message = chat_function(user_message, history, study_name, prompt_type)
        history[-1][1] = bot_message
        return history

    msg.submit(user, [msg, chatbot], [msg, chatbot], queue=False).then(
        bot, [chatbot, study_dropdown, prompt_type], chatbot
    )
    send_btn.click(user, [msg, chatbot], [msg, chatbot], queue=False).then(
        bot, [chatbot, study_dropdown, prompt_type], chatbot
    )
    clear.click(lambda: None, None, chatbot, queue=False)

    study_dropdown.change(
        fn=update_interface,
        inputs=study_dropdown,
        outputs=[study_info, sample_btn1, sample_btn2, sample_btn3],
    )

    sample_btn1.click(set_question, inputs=[sample_btn1], outputs=[msg])
    sample_btn2.click(set_question, inputs=[sample_btn2], outputs=[msg])
    sample_btn3.click(set_question, inputs=[sample_btn3], outputs=[msg])


if __name__ == "__main__":
    demo.launch(share=True, debug=True)
