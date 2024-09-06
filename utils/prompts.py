from llama_index.core import PromptTemplate
from typing import Optional, List
from pydantic import BaseModel, Field
from llama_index.core.prompts import PromptTemplate


class StudyCharacteristics(BaseModel):
    STUDYID: str
    AUTHOR: str
    YEAR: int
    TITLE: str
    APPENDIX: Optional[str]
    PUBLICATION_TYPE: str
    STUDY_DESIGN: str
    STUDY_AREA_REGION: str
    STUDY_POPULATION: str
    IMMUNISABLE_DISEASE_UNDER_STUDY: str
    ROUTE_OF_VACCINE_ADMINISTRATION: str
    DURATION_OF_STUDY: str
    DURATION_IN_RELATION_TO_COVID19: str
    STUDY_COMMENTS: Optional[str]


class VaccineCoverageVariables(BaseModel):
    STUDYID: str
    AUTHOR: str
    YEAR: int
    TITLE: str
    VACCINE_COVERAGE_RATES: float = Field(..., ge=0, le=100)
    PROPORTION_ADMINISTERED_WITHIN_RECOMMENDED_AGE: float = Field(..., ge=0, le=100)
    IMMUNISATION_UPTAKE: float = Field(..., ge=0, le=100)
    VACCINE_DROP_OUT_RATES: float = Field(..., ge=0, le=100)
    INTENTIONS_TO_VACCINATE: float = Field(..., ge=0, le=100)
    VACCINE_CONFIDENCE: float = Field(..., ge=0, le=100)
    STUDY_COMMENTS: Optional[str]


study_characteristics_prompt = PromptTemplate(
    "Based on the given text, extract the following study characteristics:\n"
    "STUDYID: {studyid}\n"
    "AUTHOR: {author}\n"
    "YEAR: {year}\n"
    "TITLE: {title}\n"
    "APPENDIX: {appendix}\n"
    "PUBLICATION_TYPE: {publication_type}\n"
    "STUDY_DESIGN: {study_design}\n"
    "STUDY_AREA_REGION: {study_area_region}\n"
    "STUDY_POPULATION: {study_population}\n"
    "IMMUNISABLE_DISEASE_UNDER_STUDY: {immunisable_disease}\n"
    "ROUTE_OF_VACCINE_ADMINISTRATION: {route_of_administration}\n"
    "DURATION_OF_STUDY: {duration_of_study}\n"
    "DURATION_IN_RELATION_TO_COVID19: {duration_covid19}\n"
    "STUDY_COMMENTS: {study_comments}\n"
    "Provide the information in a JSON format. If a field is not found, leave it as null."
)

vaccine_coverage_prompt = PromptTemplate(
    "Based on the given text, extract the following vaccine coverage variables:\n"
    "STUDYID: {studyid}\n"
    "AUTHOR: {author}\n"
    "YEAR: {year}\n"
    "TITLE: {title}\n"
    "VACCINE_COVERAGE_RATES: {coverage_rates}\n"
    "PROPORTION_ADMINISTERED_WITHIN_RECOMMENDED_AGE: {proportion_recommended_age}\n"
    "IMMUNISATION_UPTAKE: {immunisation_uptake}\n"
    "VACCINE_DROP_OUT_RATES: {drop_out_rates}\n"
    "INTENTIONS_TO_VACCINATE: {intentions_to_vaccinate}\n"
    "VACCINE_CONFIDENCE: {vaccine_confidence}\n"
    "STUDY_COMMENTS: {study_comments}\n"
    "Provide the information in a JSON format. For numerical values, provide percentages as floats between 0 and 100. If a field is not found, leave it as null."
)

sample_questions = {
    "Vaccine Coverage": [
        "What are the vaccine coverage rates reported in the study?",
        "Are there any reported adverse events following immunization (AEFI)?",
        "How does the study account for different vaccine types or schedules?",
        "Extract and present in a tabular format the following variables for each vaccine coverage study: STUDYID, AUTHOR, YEAR, TITLE, PUBLICATION_TYPE, STUDY_DESIGN, STUDY_AREA_REGION, STUDY_POPULATION, IMMUNISABLE_DISEASE_UNDER_STUDY, ROUTE_OF_VACCINE_ADMINISTRATION, DURATION_OF_STUDY, DURATION_IN_RELATION_TO_COVID19, VACCINE_COVERAGE_RATES, PROPORTION_ADMINISTERED_WITHIN_RECOMMENDED_AGE, IMMUNISATION_UPTAKE, VACCINE_DROP_OUT_RATES, INTENTIONS_TO_VACCINATE, VACCINE_CONFIDENCE, HESITANCY_FACTORS, DEMOGRAPHIC_DIFFERENCES, INTERVENTIONS, EQUITY_CONSIDERATIONS, GEOGRAPHICAL_SCOPE, AEFI, VACCINE_TYPES, and STUDY_COMMENTS.",
    ],
    "Ebola Virus": [
        "What is the sample size of the study?",
        "What is the type of plasma used in the study?",
        "What biosafety measures were implemented during the study?",
        "Were there any ethical considerations or challenges reported?",
        "Create a structured table for each Ebola virus study, including the following information: STUDYID, AUTHOR, YEAR, TITLE, PUBLICATION_TYPE, STUDY_DESIGN, STUDY_AREA_REGION, STUDY_POPULATION, SAMPLE_SIZE, PLASMA_TYPE, DOSAGE, FREQUENCY, SIDE_EFFECTS, VIRAL_LOAD_CHANGE, SURVIVAL_RATE, INCLUSION_CRITERIA, EXCLUSION_CRITERIA, SUBGROUP_ANALYSES, FOLLOW_UP_DURATION, LONG_TERM_OUTCOMES, DISEASE_SEVERITY_ASSESSMENT, BIOSAFETY_MEASURES, ETHICAL_CONSIDERATIONS, and STUDY_COMMENTS.",
    ],
    "Gene Xpert": [
        "What is the main objective of the study?",
        "What is the study design?",
        "What disease condition is being studied?",
        "Extract and present in a tabular format the following variables for each Gene Xpert study: STUDYID, AUTHOR, YEAR, TITLE, PUBLICATION_TYPE, STUDY_DESIGN, STUDY_AREA_REGION, STUDY_POPULATION, DISEASE_CONDITION, OBJECTIVE, OUTCOME_MEASURES, SENSITIVITY, SPECIFICITY, COST_COMPARISON, TURNAROUND_TIME, IMPLEMENTATION_CHALLENGES, PERFORMANCE_VARIATIONS, QUALITY_CONTROL, EQUIPMENT_ISSUES, PATIENT_OUTCOME_IMPACT, TRAINING_REQUIREMENTS, SCALABILITY_CONSIDERATIONS, and STUDY_COMMENTS.",
    ],
}


highlight_prompt = PromptTemplate(
    "Context information is below.\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n"
    "Given this information, please answer the question: {query_str}\n"
    "Include all relevant information from the provided context. "
    "Highlight key information by enclosing it in **asterisks**. "
    "When quoting specific information, please use square brackets to indicate the source, e.g. [1], [2], etc."
)

evidence_based_prompt = PromptTemplate(
    "Context information is below.\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n"
    "Given this information, please answer the question: {query_str}\n"
    "Provide an answer to the question using evidence from the context above. "
    "Cite sources using square brackets."
)
