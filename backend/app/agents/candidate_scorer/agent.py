"""
backend/app/agents/candidate_scorer/agent.py
7-node LangGraph scoring pipeline with deterministic cache and 2-pass LLM output.
"""
import os, re, json, hashlib
from typing import Literal, List
from typing_extensions import TypedDict
from pydantic import BaseModel, Field, field_validator
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END
from app.core.config import settings
from app.models.schemas import (CandidateReport, SkillMatch, LanguageMatch, ProjectHighlight, EvaluationScore)

CACHE_FILE = ".recruiter_cache.json"
GROQ_MODEL = "llama-3.3-70b-versatile"

SCORING_RUBRIC = """
═══ DETERMINISTIC SCORING RUBRIC ═══
CATEGORY           WEIGHT  MAX
Technical Skills    35%    35
Programming Langs   20%    20
Project Relevance   20%    20
Years Experience    15%    15
GitHub Quality      10%    10
TOTAL              100%   100

TECHNICAL SKILLS (max 35): identify N must-haves (max 5). Each clearly present = 35/N pts.
PROGRAMMING LANGUAGES (max 20): each required lang candidate knows = 20/L pts.
PROJECT RELEVANCE: 3+ relevant=20, 1-2=10, tangential=5, none=0.
EXPERIENCE: meets/exceeds=15, 6mo short=10, 1yr short=7, <half=3, none=0.
GITHUB: active+relevant=10, exists low=5, none=0.
match_score >= 70 → MATCH; 50-69 → MAYBE; <50 → NO_MATCH.
Show step-by-step calc in cultural_fit_notes.
═══════════════════════════════════
"""

_CACHE: dict = {}

def _load_cache():
    global _CACHE
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f: _CACHE = json.load(f)
        except Exception: _CACHE = {}

def _save_cache():
    try:
        with open(CACHE_FILE, "w") as f: json.dump(_CACHE, f, indent=2)
    except Exception: pass

def _key(resume: str, jd: str) -> str:
    return hashlib.sha256((resume.strip() + "|||" + jd.strip()).encode()).hexdigest()

_load_cache()


class State(TypedDict):
    job_description: str
    resume_text: str
    github_handle: str
    jd_analysis: str
    screening_verdict: str
    github_audit: str
    skill_analysis: str
    project_analysis: str
    is_technical_match: bool
    final_evaluation: CandidateReport
    cache_hit: bool


_llm = ChatGroq(model=GROQ_MODEL, temperature=0, model_kwargs={"seed": 42}, groq_api_key=settings.GROQ_API_KEY)


def _github_audit_run(handle: str) -> str:
    if not handle or handle.lower() in ("unknown", "not_found", "none", ""):
        return "No GitHub handle provided."
    try:
        import os as _os
        from github import Github
        token = _os.getenv("GITHUB_TOKEN", settings.GITHUB_TOKEN if hasattr(settings, 'GITHUB_TOKEN') else "")
        g = Github(token) if token else Github()
        user = g.get_user(handle)
        repos = list(user.get_repos())[:10]
        lang_count: dict = {}
        summaries = []
        total_stars = total_forks = 0
        for r in repos:
            lang = r.language or "Unknown"
            lang_count[lang] = lang_count.get(lang, 0) + 1
            total_stars += r.stargazers_count
            total_forks += r.forks_count
            topics = ", ".join(r.get_topics()[:4]) or "none"
            summaries.append(f"REPO: {r.name} | LANG: {lang} | STARS: {r.stargazers_count} | TOPICS: {topics} | DESC: {r.description or 'N/A'}")
        top = sorted(lang_count.items(), key=lambda x: -x[1])
        lang_str = ", ".join(f"{l}({c})" for l, c in top[:6])
        return (f"Username: {user.login}\nPublic Repos: {user.public_repos}\nFollowers: {user.followers}\n"
                f"Total Stars: {total_stars}\nTop Langs: {lang_str}\n\nREPOS:\n" + "\n".join(summaries))
    except Exception as e:
        return f"GitHub fetch failed: {e}"


def cache_check(state: State):
    k = _key(state["resume_text"], state["job_description"])
    if k in _CACHE:
        try:
            report = CandidateReport(**_CACHE[k])
            if report.match_score > 0 and report.candidate_name not in ("Unknown", "", "Candidate"):
                return {"final_evaluation": report, "cache_hit": True}
            del _CACHE[k]; _save_cache()
        except Exception: pass
    return {"cache_hit": False}


def jd_architect(state: State):
    prompt = ("Analyze this JD deeply. Extract: MUST-HAVE SKILLS, NICE-TO-HAVE, "
              "REQUIRED LANGUAGES, FRAMEWORKS/TOOLS, MIN YEARS EXPERIENCE, PROJECT TYPES, IDEAL PERSONA.\n\n"
              f"JD:\n{state['job_description']}")
    return {"jd_analysis": _llm.invoke(prompt).content}


def resume_screener(state: State):
    prompt = (f"Analyze resume vs JD. Answer:\n1. Technical match? (MATCH if ≥60% must-haves)\n"
              f"2. GitHub username (NOT_FOUND if absent)\n3. Years of experience\n\n"
              f"RESUME:\n{state['resume_text']}\n\nJD:\n{state['jd_analysis']}\n\n"
              f"Respond EXACTLY:\nVERDICT: [MATCH/NO_MATCH]\nGITHUB: [handle or NOT_FOUND]\nEXPERIENCE: [X years]")
    resp = _llm.invoke(prompt).content
    is_match = "VERDICT: MATCH" in resp.upper()
    m = re.search(r"GITHUB:\s*(\S+)", resp, re.IGNORECASE)
    handle = m.group(1) if m else "unknown"
    handle = re.sub(r"https?://(www\.)?github\.com/", "", handle).strip("/")
    if handle.lower() in ("not_found", "none", "n/a", "unknown"): handle = "unknown"
    return {"screening_verdict": resp, "is_technical_match": is_match, "github_handle": handle}


def github_auditor(state: State):
    handle = state.get("github_handle", "unknown")
    return {"github_audit": _github_audit_run(handle)}


def skill_analyzer(state: State):
    prompt = (f"Compare candidate skills vs JD exactly. For each JD skill: has it? proficiency 0-10? evidence? years?\n"
              f"Also note bonus skills.\n\nJD:\n{state['jd_analysis']}\n\n"
              f"RESUME:\n{state['resume_text']}\n\nGITHUB:\n{state.get('github_audit','N/A')}")
    return {"skill_analysis": _llm.invoke(prompt).content}


def project_analyzer(state: State):
    prompt = (f"Evaluate all projects from resume and GitHub. Rate each 0-10 for relevance.\n"
              f"JD:\n{state['jd_analysis']}\n\nRESUME:\n{state['resume_text']}\n\n"
              f"GITHUB:\n{state.get('github_audit','N/A')}")
    return {"project_analysis": _llm.invoke(prompt).content}


def quality_control_officer(state: State):
    context = (f"RESUME:\n{state['resume_text']}\n\nJD:\n{state['jd_analysis']}\n\n"
               f"SCREENING:\n{state.get('screening_verdict','N/A')}\n\n"
               f"GITHUB:\n{state.get('github_audit','N/A')}\n\n"
               f"SKILLS:\n{state.get('skill_analysis','N/A')}\n\n"
               f"PROJECTS:\n{state.get('project_analysis','N/A')}")

    class CoreReport(BaseModel):
        candidate_name: str = "Unknown"
        email: str = ""
        phone_no: str = ""
        university_name: str = ""
        cgpa: str = ""
        github_handle: str = ""
        years_of_experience: str = "Unknown"
        match_score: int = Field(default=0)
        final_decision: str = "NO_MATCH"
        cultural_fit_notes: str = ""
        strengths: List[str] = Field(default_factory=list)
        red_flags: List[str] = Field(default_factory=list)
        outreach_email_draft: str = ""
        rejection_email_draft: str = ""

        @field_validator("match_score", mode="before")
        @classmethod
        def to_int(cls, v):
            if isinstance(v, str):
                c = re.sub(r"[^0-9]", "", v); return int(c) if c else 0
            try: return int(v)
            except: return 0

        @field_validator("final_decision", mode="before")
        @classmethod
        def fix_d(cls, v):
            v = str(v).upper().strip()
            if "NO" in v: return "NO_MATCH"
            if "MAYBE" in v: return "MAYBE"
            if "MATCH" in v: return "MATCH"
            return "NO_MATCH"

    core = None
    for _ in range(3):
        try:
            core = _llm.with_structured_output(CoreReport).invoke(
                "Fill CoreReport. match_score = plain integer.\n" + SCORING_RUBRIC + "\nAlso generate outreach_email_draft (for MATCH/MAYBE) and rejection_email_draft (for NO_MATCH).\n\n" + context)
            if core.match_score > 0 and core.candidate_name not in ("Unknown", ""): break
        except Exception: core = None

    if core is None or core.match_score == 0:
        raw = _llm.invoke("Extract: NAME, EMAIL, PHONE, UNIVERSITY, CGPA, GITHUB, EXPERIENCE, SCORE(0-100), DECISION(MATCH/MAYBE/NO_MATCH)\n" + SCORING_RUBRIC + "\n\n" + context).content
        def ex(lbl): m = re.search(rf"{lbl}:\s*(.+)", raw, re.IGNORECASE); return m.group(1).strip() if m else ""
        sc = ex("SCORE"); si = int(re.sub(r"[^0-9]","",sc)) if sc else 50
        dv = ex("DECISION").upper()
        dv = "NO_MATCH" if "NO" in dv else "MAYBE" if "MAYBE" in dv else "MATCH" if "MATCH" in dv else ("MAYBE" if si>=50 else "NO_MATCH")
        core = CoreReport(candidate_name=ex("NAME") or "Candidate", email=ex("EMAIL"), phone_no=ex("PHONE"),
                          university_name=ex("UNIVERSITY"), cgpa=ex("CGPA"), github_handle=ex("GITHUB"),
                          years_of_experience=ex("EXPERIENCE") or "Unknown", match_score=si, final_decision=dv,
                          cultural_fit_notes="Extracted via fallback.", strengths=[], red_flags=[],
                          outreach_email_draft="", rejection_email_draft="")

    class ListsReport(BaseModel):
        skill_matches: List[SkillMatch] = Field(default_factory=list)
        language_matches: List[LanguageMatch] = Field(default_factory=list)
        project_highlights: List[ProjectHighlight] = Field(default_factory=list)
        evaluation_scores: List[EvaluationScore] = Field(default_factory=list)

    try:
        lists = _llm.with_structured_output(ListsReport).invoke(
            "Fill ListsReport. skill_matches: JD must-haves + extras. language_matches: all langs. "
            "project_highlights: top 5. evaluation_scores: 6 categories scored 0-100: "
            "Technical Skills, Programming Languages, Project Relevance, Experience Level, Code Quality, Learning & Growth.\n\n" + context)
    except Exception:
        lists = ListsReport()

    report = CandidateReport(
        candidate_name=core.candidate_name, email=core.email, phone_no=core.phone_no,
        university_name=core.university_name, cgpa=core.cgpa, github_handle=core.github_handle,
        years_of_experience=core.years_of_experience, match_score=core.match_score,
        final_decision=core.final_decision, cultural_fit_notes=core.cultural_fit_notes,
        strengths=core.strengths, red_flags=core.red_flags,
        outreach_email_draft=core.outreach_email_draft, rejection_email_draft=core.rejection_email_draft,
        skill_matches=lists.skill_matches, language_matches=lists.language_matches,
        project_highlights=lists.project_highlights, evaluation_scores=lists.evaluation_scores,
        github_summary=state.get("github_audit", ""),
    )

    if report.match_score > 0 and report.candidate_name not in ("Unknown", "", "Candidate"):
        _CACHE[_key(state["resume_text"], state["job_description"])] = report.model_dump()
        _save_cache()

    return {"final_evaluation": report, "cache_hit": False}


def route_cache(state: State) -> Literal["analyze_jd", "done"]:
    return "done" if state.get("cache_hit") else "analyze_jd"

def route_screen(state: State) -> Literal["deep_dive", "quick_report"]:
    return "deep_dive" if state["is_technical_match"] else "quick_report"


_wf = StateGraph(State)
_wf.add_node("check_cache", cache_check)
_wf.add_node("analyze_jd", jd_architect)
_wf.add_node("screen_resume", resume_screener)
_wf.add_node("audit_github", github_auditor)
_wf.add_node("analyze_skills", skill_analyzer)
_wf.add_node("analyze_projects", project_analyzer)
_wf.add_node("finalize_report", quality_control_officer)
_wf.add_edge(START, "check_cache")
_wf.add_conditional_edges("check_cache", route_cache, {"analyze_jd": "analyze_jd", "done": END})
_wf.add_edge("analyze_jd", "screen_resume")
_wf.add_conditional_edges("screen_resume", route_screen, {"deep_dive": "audit_github", "quick_report": "finalize_report"})
_wf.add_edge("audit_github", "analyze_skills")
_wf.add_edge("analyze_skills", "analyze_projects")
_wf.add_edge("analyze_projects", "finalize_report")
_wf.add_edge("finalize_report", END)
scoring_graph = _wf.compile()


def score_candidate(resume_text: str, job_description: str) -> CandidateReport:
    result = scoring_graph.invoke({
        "resume_text": resume_text, "job_description": job_description,
        "github_handle": "", "jd_analysis": "", "screening_verdict": "",
        "github_audit": "", "skill_analysis": "", "project_analysis": "",
        "is_technical_match": False, "final_evaluation": None, "cache_hit": False,
    })
    return result["final_evaluation"]
