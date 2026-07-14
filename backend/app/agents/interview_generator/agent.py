"""
backend/app/agents/interview_generator/agent.py
6-node LangGraph pipeline for generating questions.
"""
from typing import List, TypedDict, Any, Dict
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langchain_groq import ChatGroq

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

GROQ_MODEL = "llama-3.3-70b-versatile"
_llm = ChatGroq(model=GROQ_MODEL, temperature=0.2, model_kwargs={"seed": 42}, groq_api_key=settings.GROQ_API_KEY)


class GenState(TypedDict):
    job_description: str
    job_title: str
    company: str
    experience_level: str
    skill_analysis: str
    question_plan: str
    easy_count: int
    medium_count: int
    hard_count: int
    mcq_questions: List[Dict[str, Any]]
    coding_questions: List[Dict[str, Any]]
    scenario_questions: List[Dict[str, Any]]
    all_questions: List[Dict[str, Any]]
    validated_questions: List[Dict[str, Any]]


# ─── Output Models ────────────────────────────────────────────────────────────

class MCQOption(BaseModel):
    id: str
    text: str

class MCQQuestion(BaseModel):
    question_text: str
    options: List[MCQOption]
    correct_answers: List[str]
    explanation: str
    difficulty: str
    skill: str
    topic: str
    type: str = "mcq"

class MCQBatch(BaseModel):
    questions: List[MCQQuestion]

class CodingQuestion(BaseModel):
    question_text: str
    difficulty: str
    skill: str
    language: str
    code_template: str
    test_cases: List[Dict[str, Any]]
    explanation: str
    time_limit_seconds: int = 120
    type: str = "coding"

class CodingBatch(BaseModel):
    questions: List[CodingQuestion]

class ScenarioQuestion(BaseModel):
    question_text: str
    difficulty: str
    skill: str
    topic: str
    type: str
    explanation: str

class ScenarioBatch(BaseModel):
    questions: List[ScenarioQuestion]

class SkillAnalysis(BaseModel):
    tech_stack: List[str]
    must_have_skills: List[str]
    experience_level: str
    industry: str
    role_type: str


# ─── Nodes ────────────────────────────────────────────────────────────────────

def jd_skill_extractor(state: GenState) -> GenState:
    logger.info(f"Extracting skills for {state['job_title']}")
    prompt = (
        f"Analyze this Job Description for a {state['job_title']} at {state['company']}.\n\n"
        f"JD:\n{state['job_description']}\n\n"
        "Extract the core technical stack, required skills, and experience level."
    )
    try:
        res = _llm.with_structured_output(SkillAnalysis).invoke(prompt)
        state["experience_level"] = res.experience_level
        state["skill_analysis"] = f"Stack: {', '.join(res.tech_stack)}. Skills: {', '.join(res.must_have_skills)}. Level: {res.experience_level}."
    except Exception as e:
        logger.error(f"jd_skill_extractor error: {e}")
        state["experience_level"] = "mid"
        state["skill_analysis"] = "General Software Engineering"
    return state


def question_planner(state: GenState) -> GenState:
    logger.info("Planning question distribution")
    total = state["easy_count"] + state["medium_count"] + state["hard_count"]
    state["question_plan"] = (
        f"Total: {total}. Create approx {int(total*0.6)} MCQs, {int(total*0.2)} coding, and {int(total*0.2)} scenario questions."
    )
    return state


def mcq_generator(state: GenState) -> GenState:
    logger.info("Generating MCQs")
    prompt = (
        f"Generate {int((state['easy_count']+state['medium_count']+state['hard_count'])*0.6)} highly technical, professional-grade MCQ questions for a {state['job_title']}.\n"
        f"STRICTLY base the questions on the provided Job Description:\n{state['job_description']}\n\n"
        f"Skills to cover: {state['skill_analysis']}.\n"
        "Questions MUST be advanced, realistic, and highly technical, mimicking top-tier tech company assessments. Avoid generic/trivial questions.\n"
        "Ensure options have IDs like 'a', 'b', 'c', 'd'. Include a detailed technical explanation and difficulty level."
    )
    try:
        res = _llm.with_structured_output(MCQBatch).invoke(prompt)
        state["mcq_questions"] = [q.model_dump() for q in res.questions]
    except Exception as e:
        logger.error(f"mcq_generator error: {e}")
        state["mcq_questions"] = []
    return state


def coding_generator(state: GenState) -> GenState:
    logger.info("Generating Coding Questions")
    target = int((state["easy_count"] + state["medium_count"] + state["hard_count"]) * 0.2)
    if target <= 0:
        state["coding_questions"] = []
        return state
        
    prompt = (
        f"Generate {target} advanced, professional-level coding algorithm questions for {state['job_title']}.\n"
        f"STRICTLY align the problems with the context of the Job Description:\n{state['job_description']}\n\n"
        f"Skills: {state['skill_analysis']}.\n"
        "The coding tasks MUST be complex, practical, and similar to rigorous technical assessments from top-tier tech companies. Avoid trivial or generic textbook problems.\n"
        "Provide question_text, a professional python code_template with type hints, and exactly 5 rigorous test_cases (3 visible, 2 hidden)."
    )
    try:
        res = _llm.with_structured_output(CodingBatch).invoke(prompt)
        state["coding_questions"] = [q.model_dump() for q in res.questions]
    except Exception as e:
        logger.error(f"coding_generator error: {e}")
        state["coding_questions"] = []
    return state


def scenario_generator(state: GenState) -> GenState:
    logger.info("Generating Scenario Questions")
    target = int((state["easy_count"] + state["medium_count"] + state["hard_count"]) * 0.2)
    if target <= 0:
        state["scenario_questions"] = []
        return state

    prompt = (
        f"Generate {target} advanced, professional-grade scenario/case-study/system-design questions for {state['job_title']}.\n"
        f"STRICTLY anchor the scenarios in the context of the Job Description:\n{state['job_description']}\n\n"
        f"Skills: {state['skill_analysis']}.\n"
        "These MUST be complex, real-world engineering, architectural, or debugging problems expected in senior/professional interviews.\n"
        "These require text explanations from candidates. Set type to 'case_study' or 'system_design'."
    )
    try:
        res = _llm.with_structured_output(ScenarioBatch).invoke(prompt)
        state["scenario_questions"] = [q.model_dump() for q in res.questions]
    except Exception as e:
        logger.error(f"scenario_generator error: {e}")
        state["scenario_questions"] = []
    return state


def question_validator(state: GenState) -> GenState:
    logger.info("Validating and combining questions")
    all_q = state.get("mcq_questions", []) + state.get("coding_questions", []) + state.get("scenario_questions", [])
    state["all_questions"] = all_q
    
    # Very basic dedup and validation logic for now
    validated = []
    seen_texts = set()
    for q in all_q:
        qt = q.get("question_text", "")
        if qt and qt not in seen_texts:
            seen_texts.add(qt)
            validated.append(q)
            
    state["validated_questions"] = validated
    return state


# ─── Graph Construction ───────────────────────────────────────────────────────

builder = StateGraph(GenState)

builder.add_node("jd_skill_extractor", jd_skill_extractor)
builder.add_node("question_planner", question_planner)
builder.add_node("mcq_generator", mcq_generator)
builder.add_node("coding_generator", coding_generator)
builder.add_node("scenario_generator", scenario_generator)
builder.add_node("question_validator", question_validator)

builder.add_edge(START, "jd_skill_extractor")
builder.add_edge("jd_skill_extractor", "question_planner")
builder.add_edge("question_planner", "mcq_generator")
builder.add_edge("mcq_generator", "coding_generator")
builder.add_edge("coding_generator", "scenario_generator")
builder.add_edge("scenario_generator", "question_validator")
builder.add_edge("question_validator", END)

pipeline = builder.compile()

# ─── Public API ───────────────────────────────────────────────────────────────

def generate_questions(
    job_description: str,
    job_title: str,
    company: str = "",
    easy_count: int = 10,
    medium_count: int = 15,
    hard_count: int = 5,
) -> List[Dict[str, Any]]:
    
    initial_state = {
        "job_description": job_description,
        "job_title": job_title,
        "company": company,
        "easy_count": easy_count,
        "medium_count": medium_count,
        "hard_count": hard_count,
        "mcq_questions": [],
        "coding_questions": [],
        "scenario_questions": [],
        "all_questions": [],
        "validated_questions": [],
    }
    
    final_state = pipeline.invoke(initial_state)
    return final_state["validated_questions"]
