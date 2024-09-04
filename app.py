import gradio as gr
import json
from rag.rag_pipeline import RAGPipeline
from utils.prompts import highlight_prompt, evidence_based_prompt
from utils.prompts import (
    study_characteristics_prompt,
    vaccine_coverage_prompt,
    sample_questions,
)
from config import STUDY_FILES

rag_cache = {}


def get_rag_pipeline(study_name):
    if study_name not in rag_cache:
        study_file = STUDY_FILES.get(study_name)
        if study_file:
            rag_cache[study_name] = RAGPipeline(study_file)
        else:
            raise ValueError(f"Invalid study name: {study_name}")
    return rag_cache[study_name]


def query_rag(study_name, question, prompt_type):
    rag = get_rag_pipeline(study_name)

    if prompt_type == "Highlight":
        prompt = highlight_prompt
    elif prompt_type == "Evidence-based":
        prompt = evidence_based_prompt
    elif prompt_type == "Study Characteristics":
        prompt = study_characteristics_prompt
    elif prompt_type == "Vaccine Coverage":
        prompt = vaccine_coverage_prompt
    else:
        prompt = None

    response = rag.query(question, prompt)

    # Format the response as Markdown
    formatted_response = f"## Question\n\n{response['question']}\n\n## Answer\n\n{response['answer']}\n\n## Sources\n\n"
    for source in response["sources"]:
        formatted_response += f"- {source['title']} ({source['year']})\n"

    return formatted_response


def get_study_info(study_name):
    study_file = STUDY_FILES.get(study_name)
    if study_file:
        with open(study_file, "r") as f:
            data = json.load(f)
        return f"**Number of documents:** {len(data)}\n\n**First document title:** {data[0]['title']}"
    else:
        return "Invalid study name"


def update_sample_questions(study_name):
    return gr.Dropdown.update(choices=sample_questions.get(study_name, []))


with gr.Blocks() as demo:
    gr.Markdown("# RAG Pipeline Demo")

    with gr.Row():
        study_dropdown = gr.Dropdown(
            choices=list(STUDY_FILES.keys()), label="Select Study"
        )
        study_info = gr.Markdown(label="Study Information")

    study_dropdown.change(get_study_info, inputs=[study_dropdown], outputs=[study_info])

    with gr.Row():
        question_input = gr.Textbox(label="Enter your question")
        sample_question_dropdown = gr.Dropdown(choices=[], label="Sample Questions")

    study_dropdown.change(
        update_sample_questions,
        inputs=[study_dropdown],
        outputs=[sample_question_dropdown],
    )
    sample_question_dropdown.change(
        lambda x: x, inputs=[sample_question_dropdown], outputs=[question_input]
    )

    prompt_type = gr.Radio(
        [
            "Default",
            "Highlight",
            "Evidence-based",
            "Study Characteristics",
            "Vaccine Coverage",
        ],
        label="Prompt Type",
        value="Default",
    )

    submit_button = gr.Button("Submit")

    answer_output = gr.Markdown(label="Answer")

    submit_button.click(
        query_rag,
        inputs=[study_dropdown, question_input, prompt_type],
        outputs=[answer_output],
    )

if __name__ == "__main__":
    demo.launch()
