"""
backend/app/agents/assessment_evaluator/agent.py
7-node LangGraph evaluation pipeline for candidate assessments.
"""
import json
from typing import List, TypedDict, Any, Dict
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langchain_groq import ChatGroq

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

GROQ_MODEL = "llama-3.3-70b-versatile"
_llm = ChatGroq(model=GROQ_MODEL, temperature=0, model_kwargs={"seed": 42}, groq_api_key=settings.GROQ_API_KEY)


class EvalState(TypedDict):
    candidate_id: str
    job_id: str
    assessment_id: str
    resume_score: int
    session_data: dict
    questions: List[dict]
    answers: List[dict]
    mcq_results: List[dict]
    code_results: List[dict]
    short_answer_results: List[dict]
    essay_results: List[dict]
    mcq_score: float
    coding_score: float
    short_answer_score: float
    communication_score: float
    problem_solving_score: float
    cheating_penalty: int
    final_composite_score: float
    report: dict


# ─── Output Models ────────────────────────────────────────────────────────────

class ShortAnswerScore(BaseModel):
    score: int = Field(description="Score from 0 to 10")
    feedback: str

class EssayScore(BaseModel):
    logic_score: int = Field(description="Score from 0 to 10")
    communication_score: int = Field(description="Score from 0 to 10")
    problem_solving_score: int = Field(description="Score from 0 to 10")
    feedback: str

class FinalReport(BaseModel):
    candidate_summary: str
    strengths: List[str]
    weaknesses: List[str]
    technical_analysis: str
    soft_skills_analysis: str
    coding_performance: str
    communication_assessment: str
    recommendation: str = Field(description="strongly_hire | hire | maybe | reject")
    hiring_confidence: int = Field(description="0-100")
    risk_analysis: str
    overall_rating: float = Field(description="0-5.0")


# ─── Nodes ────────────────────────────────────────────────────────────────────

def answer_collector(state: EvalState) -> EvalState:
    logger.info(f"Collecting answers for assessment {state['assessment_id']}")
    session = state["session_data"]

    def extract_id(q: dict) -> str:
        """
        Safely extract the string ID from a question dict that was serialized
        via model_dump(mode='json'). Beanie/MongoDB ObjectIds serialize as
        {"$oid": "<hex>"} dicts under the "id" or "_id" key.
        """
        raw = q.get("id") or q.get("_id")
        if raw is None:
            return ""
        if isinstance(raw, dict):
            # Handles {"$oid": "..."} produced by model_dump(mode='json')
            return str(raw.get("$oid", ""))
        return str(raw)

    questions = {extract_id(q): q for q in state["questions"] if extract_id(q)}
    logger.info(f"answer_collector: mapped {len(questions)} questions, session has {len(session.get('answers', []))} answers")
    
    mcq_ans, code_ans, short_ans, essay_ans = [], [], [], []
    
    for a in session.get("answers", []):
        qid = a["question_id"]
        if qid not in questions:
            logger.warning(f"answer_collector: question_id '{qid}' not found in questions map. Available: {list(questions.keys())[:5]}")
            continue
        q = questions[qid]
        a["question"] = q
        
        qt = q.get("type", "mcq")
        if qt in ("mcq", "true_false", "fill_blank"):
            mcq_ans.append(a)
        elif qt == "coding":
            code_ans.append(a)
        elif qt == "short_answer":
            short_ans.append(a)
        else:
            essay_ans.append(a)

    logger.info(f"answer_collector: MCQ={len(mcq_ans)}, Code={len(code_ans)}, Short={len(short_ans)}, Essay={len(essay_ans)}")
    state["answers"] = session.get("answers", [])
    state["mcq_results"] = mcq_ans
    state["code_results"] = code_ans
    state["short_answer_results"] = short_ans
    state["essay_results"] = essay_ans
    return state


def mcq_evaluator(state: EvalState) -> EvalState:
    logger.info("Evaluating MCQs")
    correct_count = 0
    total = len(state["mcq_results"])
    
    for a in state["mcq_results"]:
        q = a["question"]
        ans = a.get("answer")
        is_correct = False

        raw_correct = q.get("correct_answers", [])
        # Normalize correct answers to lowercase strings
        correct_ids = [str(c).lower() for c in raw_correct]
        options = q.get("options", [])  # [{"id": "a", "text": "..."}, ...] or ["str", ...]

        def _normalize_answer(ans_val) -> list:
            """
            Return a list of candidate strings to check against correct_ids.
            Handles:
              - str  → the option id/text directly (e.g. "a", "Python")
              - int  → index into options list → option id
              - list → multi-select, each element processed recursively
            """
            if ans_val is None:
                return []
            if isinstance(ans_val, list):
                results = []
                for item in ans_val:
                    results.extend(_normalize_answer(item))
                return results
            if isinstance(ans_val, int):
                # Frontend sent numeric index — map to option id
                if 0 <= ans_val < len(options):
                    opt = options[ans_val]
                    if isinstance(opt, dict):
                        return [str(opt.get("id", ans_val)).lower()]
                    return [str(opt).lower()]
                return [str(ans_val).lower()]
            # It's a string — could be option id ("a"), letter ("A"), or full text
            val = str(ans_val).strip()
            candidates = [val.lower()]
            # Also check if it matches an option's text → map to id
            for opt in options:
                if isinstance(opt, dict):
                    opt_text = str(opt.get("text", "") or opt.get("label", "")).strip().lower()
                    opt_id   = str(opt.get("id",   "") or opt.get("value", "")).strip().lower()
                    if val.lower() == opt_text and opt_id:
                        candidates.append(opt_id)
            return candidates

        normalized = _normalize_answer(ans)

        if isinstance(ans, list):
            # Multi-select: all correct answers must be selected, nothing extra
            is_correct = set(normalized) == set(correct_ids)
        else:
            # Single-select: any of the normalized candidates matches a correct id
            is_correct = bool(set(normalized) & set(correct_ids))

        a["is_correct"] = is_correct
        logger.debug(f"MCQ: ans={ans!r} → normalized={normalized}, correct={correct_ids}, is_correct={is_correct}")
        if is_correct:
            correct_count += 1
            
    state["mcq_score"] = (correct_count / total * 100.0) if total > 0 else 0.0
    logger.info(f"MCQ score: {correct_count}/{total} = {state['mcq_score']:.1f}%")
    return state


def code_evaluator(state: EvalState) -> EvalState:
    logger.info("Evaluating Code")
    # For simplicity, we use LLM static analysis for code evaluation if code_runner wasn't executed
    # In a real system, the answers would already contain runner results, or we run them here.
    total = len(state["code_results"])
    total_score = 0
    
    for a in state["code_results"]:
        q = a["question"]
        ans = a["answer"]
        if not ans or not isinstance(ans, str):
            a["score"] = 0
            continue
            
        prompt = (
            f"Evaluate this code for question: {q['question_text']}\n"
            f"Language: {q.get('language')}\n"
            f"Code:\n{ans}\n"
            "Score it from 0 to 10 on correctness and quality. Return ONLY the integer score."
        )
        try:
            res = _llm.invoke(prompt).content.strip()
            score = int(''.join(filter(str.isdigit, res)))
            score = min(max(score, 0), 10)
        except Exception:
            score = 5
        a["score"] = score
        total_score += score
        
    state["coding_score"] = (total_score / (total * 10) * 100.0) if total > 0 else 0.0
    return state


def short_answer_evaluator(state: EvalState) -> EvalState:
    logger.info("Evaluating Short Answers")
    total = len(state["short_answer_results"])
    total_score = 0
    
    for a in state["short_answer_results"]:
        q = a["question"]
        ans = a["answer"]
        if not ans:
            a["score"] = 0
            continue
            
        prompt = (
            f"Question: {q['question_text']}\nExpected: {q.get('explanation')}\nAnswer: {ans}\n"
            "Score this answer from 0 to 10."
        )
        try:
            res = _llm.with_structured_output(ShortAnswerScore).invoke(prompt)
            a["score"] = min(max(res.score, 0), 10)
        except Exception:
            a["score"] = 5
        total_score += a["score"]
        
    state["short_answer_score"] = (total_score / (total * 10) * 100.0) if total > 0 else 0.0
    return state


def essay_evaluator(state: EvalState) -> EvalState:
    logger.info("Evaluating Essays")
    total = len(state["essay_results"])
    comm_total, prob_total = 0, 0
    
    for a in state["essay_results"]:
        q = a["question"]
        ans = a["answer"]
        if not ans:
            continue
            
        prompt = (
            f"Question: {q['question_text']}\nAnswer: {ans}\n"
            "Evaluate logic, communication, and problem solving from 0 to 10."
        )
        try:
            res = _llm.with_structured_output(EssayScore).invoke(prompt)
            a["score"] = res.logic_score
            comm_total += res.communication_score
            prob_total += res.problem_solving_score
        except Exception:
            comm_total += 5
            prob_total += 5
            
    state["communication_score"] = (comm_total / (total * 10) * 100.0) if total > 0 else 75.0
    state["problem_solving_score"] = (prob_total / (total * 10) * 100.0) if total > 0 else 75.0
    return state


def composite_scorer(state: EvalState) -> EvalState:
    logger.info("Calculating Composite Score")
    # Apply weights from settings
    w_res = settings.WEIGHT_RESUME / 100.0
    w_mcq = settings.WEIGHT_MCQ / 100.0
    w_code = settings.WEIGHT_CODING / 100.0
    w_short = settings.WEIGHT_SHORT_ANSWER / 100.0
    w_comm = settings.WEIGHT_COMMUNICATION / 100.0
    w_prob = settings.WEIGHT_PROBLEM_SOLVING / 100.0
    
    score = (
        (state["resume_score"] * w_res) +
        (state["mcq_score"] * w_mcq) +
        (state["coding_score"] * w_code) +
        (state["short_answer_score"] * w_short) +
        (state["communication_score"] * w_comm) +
        (state["problem_solving_score"] * w_prob)
    )
    
    score -= state["cheating_penalty"]
    state["final_composite_score"] = max(min(score, 100.0), 0.0)
    return state


def report_generator(state: EvalState) -> EvalState:
    logger.info("Generating Final Report")
    prompt = (
        f"Generate a final evaluation report for candidate {state['candidate_id']}.\n"
        f"Resume Score: {state['resume_score']}%\n"
        f"MCQ Score: {state['mcq_score']:.1f}%\n"
        f"Coding Score: {state['coding_score']:.1f}%\n"
        f"Short Answer Score: {state['short_answer_score']:.1f}%\n"
        f"Final Composite Score: {state['final_composite_score']:.1f}%\n"
        f"Cheating Penalty: -{state['cheating_penalty']}\n"
        "Provide a comprehensive structured report."
    )
    try:
        res = _llm.with_structured_output(FinalReport).invoke(prompt)
        state["report"] = res.model_dump()
    except Exception as e:
        logger.error(f"report_generator error: {e}")
        state["report"] = {
            "candidate_summary": "Report generation failed.",
            "recommendation": "maybe",
            "overall_rating": 3.0,
            "hiring_confidence": 50,
        }
    return state


# ─── Graph Construction ───────────────────────────────────────────────────────

builder = StateGraph(EvalState)

builder.add_node("answer_collector", answer_collector)
builder.add_node("mcq_evaluator", mcq_evaluator)
builder.add_node("code_evaluator", code_evaluator)
builder.add_node("short_answer_evaluator", short_answer_evaluator)
builder.add_node("essay_evaluator", essay_evaluator)
builder.add_node("composite_scorer", composite_scorer)
builder.add_node("report_generator", report_generator)

builder.add_edge(START, "answer_collector")
builder.add_edge("answer_collector", "mcq_evaluator")
builder.add_edge("mcq_evaluator", "code_evaluator")
builder.add_edge("code_evaluator", "short_answer_evaluator")
builder.add_edge("short_answer_evaluator", "essay_evaluator")
builder.add_edge("essay_evaluator", "composite_scorer")
builder.add_edge("composite_scorer", "report_generator")
builder.add_edge("report_generator", END)

pipeline = builder.compile()

# ─── Public API ───────────────────────────────────────────────────────────────

def evaluate_assessment(
    candidate_id: str,
    job_id: str,
    assessment_id: str,
    resume_score: int,
    session_data: dict,
    questions: List[dict],
    cheating_penalty: int = 0,
) -> dict:
    
    initial_state = {
        "candidate_id": candidate_id,
        "job_id": job_id,
        "assessment_id": assessment_id,
        "resume_score": resume_score,
        "session_data": session_data,
        "questions": questions,
        "cheating_penalty": cheating_penalty,
        "answers": [],
        "mcq_results": [],
        "code_results": [],
        "short_answer_results": [],
        "essay_results": [],
        "mcq_score": 0.0,
        "coding_score": 0.0,
        "short_answer_score": 0.0,
        "communication_score": 0.0,
        "problem_solving_score": 0.0,
        "final_composite_score": 0.0,
        "report": {},
    }
    
    final_state = pipeline.invoke(initial_state)
    report = final_state["report"]
    report.update({
        "mcq_score": final_state["mcq_score"],
        "coding_score": final_state["coding_score"],
        "short_answer_score": final_state["short_answer_score"],
        "communication_score": final_state["communication_score"],
        "problem_solving_score": final_state["problem_solving_score"],
        "final_composite_score": final_state["final_composite_score"],
    })
    return report
