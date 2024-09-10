from typing import Dict, Any
from llama_index.core import Response
from typing import List
from rag.rag_pipeline import RAGPipeline
from utils.prompts import (
    structured_follow_up_prompt,
    VaccineCoverageVariables,
    StudyCharacteristics,
)


def generate_follow_up_questions(
    rag: RAGPipeline, response: str, query: str, study_name: str
) -> List[str]:
    """
    Generates follow-up questions based on the given RAGPipeline, response, query, and study_name.
    Args:
        rag (RAGPipeline): The RAGPipeline object used for generating follow-up questions.
        response (str): The response to the initial query.
        query (str): The initial query.
        study_name (str): The name of the study.
    Returns:
        List[str]: A list of generated follow-up questions.
    Raises:
        None
    """

    # Determine the study type based on the study_name
    if "Vaccine Coverage" in study_name:
        study_type = "Vaccine Coverage"
        key_variables = list(VaccineCoverageVariables.__annotations__.keys())
    elif "Ebola Virus" in study_name:
        study_type = "Ebola Virus"
        key_variables = [
            "SAMPLE_SIZE",
            "PLASMA_TYPE",
            "DOSAGE",
            "FREQUENCY",
            "SIDE_EFFECTS",
            "VIRAL_LOAD_CHANGE",
            "SURVIVAL_RATE",
        ]
    elif "Gene Xpert" in study_name:
        study_type = "Gene Xpert"
        key_variables = [
            "OBJECTIVE",
            "OUTCOME_MEASURES",
            "SENSITIVITY",
            "SPECIFICITY",
            "COST_COMPARISON",
            "TURNAROUND_TIME",
        ]
    else:
        study_type = "General"
        key_variables = list(StudyCharacteristics.__annotations__.keys())

    # Add key variables to the context
    context = f"Study type: {study_type}\nKey variables to consider: {', '.join(key_variables)}\n\n{response}"

    follow_up_response = rag.query(
        structured_follow_up_prompt.format(
            context_str=context,
            query_str=query,
            response_str=response,
            study_type=study_type,
        )
    )

    questions = follow_up_response.response.strip().split("\n")
    cleaned_questions = []
    for q in questions:
        # Remove leading numbers and periods, and strip whitespace
        cleaned_q = q.split(". ", 1)[-1].strip()
        # Ensure the question ends with a question mark
        if cleaned_q and not cleaned_q.endswith("?"):
            cleaned_q += "?"
        if cleaned_q:
            cleaned_questions.append(f"✨ {cleaned_q}")
    return cleaned_questions[:3]
