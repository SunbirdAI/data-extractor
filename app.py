import gradio as gr
import json
from rag.rag_pipeline import RAGPipeline
from utils.prompts import highlight_prompt, evidence_based_prompt, sample_questions
from config import STUDY_FILES

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

    if prompt_type == "Highlight":
        prompt = highlight_prompt
    elif prompt_type == "Evidence-based":
        prompt = evidence_based_prompt
    else:
        prompt = None

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


with gr.Blocks() as demo:
    gr.Markdown("# RAG Pipeline Demo")

    with gr.Row():
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

    chatbot = gr.Chatbot()
    msg = gr.Textbox()
    clear = gr.Button("Clear")

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
    clear.click(lambda: None, None, chatbot, queue=False)

    study_dropdown.change(
        fn=get_study_info,
        inputs=study_dropdown,
        outputs=study_info,
    ).then(lambda: None, None, chatbot, queue=False)

    gr.Examples(examples=sample_questions[list(STUDY_FILES.keys())[0]], inputs=msg)

if __name__ == "__main__":
    demo.launch(share=True, debug=True)
