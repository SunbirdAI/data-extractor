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
        return f"**Number of documents:** {len(data)}\n\n**First document title:** {data[0]['title']}"
    else:
        return "Invalid study name"


with gr.Blocks(css="#chatbot {height: 600px; overflow-y: auto;}") as demo:
    gr.Markdown("# RAG Pipeline Demo")

    with gr.Row():
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(elem_id="chatbot")
            with gr.Row():
                msg = gr.Textbox(
                    show_label=False, placeholder="Enter your message here...", scale=4
                )
                send_btn = gr.Button("Send", scale=1)

        with gr.Column(scale=1):
            study_dropdown = gr.Dropdown(
                choices=list(STUDY_FILES.keys()),
                label="Select Study",
                value=list(STUDY_FILES.keys())[0],
            )
            study_info = gr.Markdown()
            prompt_type = gr.Radio(
                ["Default", "Highlight", "Evidence-based"],
                label="Prompt Type",
                value="Default",
            )
            clear = gr.Button("Clear Chat")

    gr.Examples(examples=sample_questions[list(STUDY_FILES.keys())[0]], inputs=msg)

    def user(user_message, history):
        return "", history + [[user_message, None]]

    def bot(history, study_name, prompt_type):
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
        fn=get_study_info,
        inputs=study_dropdown,
        outputs=study_info,
    )

if __name__ == "__main__":
    demo.launch(share=True, debug=True)
