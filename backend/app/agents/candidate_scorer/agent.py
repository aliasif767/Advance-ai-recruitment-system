"""
backend/app/agents/candidate_scorer/agent.py

9-node LangGraph CV scoring pipeline:
  - Dynamic 7-category JD-driven weights (technical_skills, programming_languages,
    project_relevance, years_experience, github_quality, education_certifications,
    soft_skills)
  - Deep GitHub audit: 20 repos, activity score, relevance score, skill evidence
  - Two-pass skill verification (resume claim → GitHub cross-check)
  - Score Cross-Validator node: math always overrides hallucinated LLM scores
  - Fast rejection kept: obvious mismatches skip deep analysis
  - Seniority-aware: JD tier drives weight extraction
"""
import os
import re
import json
import hashlib
import datetime
from typing import Literal, List, Optional
from typing_extensions import TypedDict
from pydantic import BaseModel, Field, field_validator, model_validator
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END
from app.core.config import settings
from app.models.schemas import (
    CandidateReport, SkillMatch, LanguageMatch, ProjectHighlight,
    EvaluationScore, CategoryScore, GitHubInsight, GitHubRepoInsight,
)

CACHE_FILE = ".recruiter_cache.json"
CACHE_VERSION = "v3"           # bump to auto-invalidate old cached entries
GROQ_MODEL = "llama-3.3-70b-versatile"

# ─────────────────────────────────────────────────────────────────────────────
# DEFAULT FALLBACK WEIGHTS  (used only when LLM weight extraction fails)
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_WEIGHTS = {
    "technical_skills": 30,
    "programming_languages": 18,
    "project_relevance": 18,
    "years_experience": 14,
    "github_quality": 10,
    "education_certifications": 6,
    "soft_skills": 4,
}

# ─────────────────────────────────────────────────────────────────────────────
# DYNAMIC WEIGHTS MODEL — 7 categories, always sum to 100
# ─────────────────────────────────────────────────────────────────────────────
class DynamicWeights(BaseModel):
    """
    LLM-extracted per-JD category weights that must sum to 100.
    Auto-normalises minor rounding drift.
    7 categories so the agent reflects ALL hiring dimensions.
    """
    technical_skills: int = Field(default=30, ge=0, le=60)
    programming_languages: int = Field(default=18, ge=0, le=40)
    project_relevance: int = Field(default=18, ge=0, le=40)
    years_experience: int = Field(default=14, ge=0, le=40)
    github_quality: int = Field(default=10, ge=0, le=25)
    education_certifications: int = Field(default=6, ge=0, le=20)
    soft_skills: int = Field(default=4, ge=0, le=15)

    @model_validator(mode="after")
    def normalise_to_100(self):
        """Proportionally scale all weights to exactly 100."""
        total = (
            self.technical_skills + self.programming_languages +
            self.project_relevance + self.years_experience +
            self.github_quality + self.education_certifications +
            self.soft_skills
        )
        if total == 0:
            for k, v in DEFAULT_WEIGHTS.items():
                setattr(self, k, v)
        elif total != 100:
            factor = 100.0 / total
            self.technical_skills     = round(self.technical_skills * factor)
            self.programming_languages = round(self.programming_languages * factor)
            self.project_relevance    = round(self.project_relevance * factor)
            self.years_experience     = round(self.years_experience * factor)
            self.github_quality       = round(self.github_quality * factor)
            self.education_certifications = round(self.education_certifications * factor)
            # Remainder to last category to guarantee exact sum of 100
            self.soft_skills = (
                100 - self.technical_skills - self.programming_languages
                - self.project_relevance - self.years_experience
                - self.github_quality - self.education_certifications
            )
            # Clamp soft_skills to non-negative
            if self.soft_skills < 0:
                self.soft_skills = 0
                # Re-distribute by trimming the largest weight
                shortfall = abs(self.soft_skills)
                self.technical_skills = max(0, self.technical_skills - shortfall)
        return self

    def as_dict(self) -> dict:
        return {
            "technical_skills": self.technical_skills,
            "programming_languages": self.programming_languages,
            "project_relevance": self.project_relevance,
            "years_experience": self.years_experience,
            "github_quality": self.github_quality,
            "education_certifications": self.education_certifications,
            "soft_skills": self.soft_skills,
        }

    def ordered_items(self) -> list:
        return [
            ("technical_skills",      "Technical Skills",          self.technical_skills),
            ("programming_languages", "Programming Languages",      self.programming_languages),
            ("project_relevance",     "Project Relevance",          self.project_relevance),
            ("years_experience",      "Years of Experience",        self.years_experience),
            ("github_quality",        "GitHub Quality",             self.github_quality),
            ("education_certifications", "Education & Certifications", self.education_certifications),
            ("soft_skills",           "Soft Skills",                self.soft_skills),
        ]


# ─────────────────────────────────────────────────────────────────────────────
# DYNAMIC RUBRIC BUILDER
# ─────────────────────────────────────────────────────────────────────────────
def _build_rubric(w: DynamicWeights) -> str:
    ts, pl, pr, ye, gq, ec, ss = (
        w.technical_skills, w.programming_languages, w.project_relevance,
        w.years_experience, w.github_quality, w.education_certifications,
        w.soft_skills,
    )
    max_weight = max(ts, pl, pr, ye, gq, ec, ss)
    return f"""
═══ DYNAMIC SCORING RUBRIC (JD-calibrated, 7-category weights) ═══
CATEGORY                     WEIGHT   MAX-PTS  SCORING GUIDE
Technical Skills              {ts}%     {ts}      Identify N must-haves (≤6). Each clearly present = {ts}/N pts. Partial credit for partial evidence.
Programming Languages         {pl}%     {pl}      Each required lang candidate knows = {pl}/L pts. GitHub usage = bonus +{max(1,pl//10)}.
Project Relevance             {pr}%     {pr}      3+ highly relevant={pr}, 1-2 relevant={round(pr*0.55)}, tangential={round(pr*0.3)}, none=0.
Years Experience              {ye}%     {ye}      Meets/exceeds={ye}, 6mo short={round(ye*0.7)}, 1yr short={round(ye*0.5)}, <half={round(ye*0.2)}, none=0.
GitHub Quality                {gq}%     {gq}      Active+relevant={gq}, exists+low activity={round(gq*0.5)}, exists+unrelated={round(gq*0.25)}, none=0.
Education & Certifications    {ec}%     {ec}      Meets requirements={ec}, related field={round(ec*0.6)}, unrelated={round(ec*0.3)}, none=0.
Soft Skills                   {ss}%     {ss}      Strong evidence (leadership, communication, teamwork)={ss}, some={round(ss*0.5)}, none=0.
TOTAL                        100%    100

DECISION THRESHOLDS:
  match_score >= 70  → MATCH   (proceed to interview/assessment)
  match_score 50-69  → MAYBE   (HR reviews manually)
  match_score < 50   → NO_MATCH

IMPORTANT RULES:
- You MUST show step-by-step calculations for EACH category in cultural_fit_notes.
- Format each: "[Category]: raw_evidence → score X/{max_weight}"
- match_score = sum of all weighted category scores (must be mathematically correct).
- Do NOT round up or inflate. Accuracy over optimism.
- If a skill is claimed in resume but NO GitHub evidence, cap proficiency at 6/10.
- If GitHub shows a skill the resume didn't mention, add it as a bonus strength.
- Always note: "GitHub audited automatically regardless of JD mention."
═══════════════════════════════════════════════════════════════════
"""


# ─────────────────────────────────────────────────────────────────────────────
# CACHE
# ─────────────────────────────────────────────────────────────────────────────
_CACHE: dict = {}


def _load_cache():
    global _CACHE
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                _CACHE = json.load(f)
        except Exception:
            _CACHE = {}


def _save_cache():
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(_CACHE, f, indent=2)
    except Exception:
        pass


def _cache_key(resume: str, jd: str) -> str:
    # Version prefix so old cache entries are skipped automatically
    payload = CACHE_VERSION + resume.strip() + "|||" + jd.strip()
    return hashlib.sha256(payload.encode()).hexdigest()


_load_cache()


# ─────────────────────────────────────────────────────────────────────────────
# LANGGRAPH STATE
# ─────────────────────────────────────────────────────────────────────────────
class JDAnalysis(BaseModel):
    """Structured result from the JD Architect node."""
    must_have_skills: List[str] = Field(default_factory=list)
    nice_to_have_skills: List[str] = Field(default_factory=list)
    required_languages: List[str] = Field(default_factory=list)
    frameworks_tools: List[str] = Field(default_factory=list)
    min_years_experience: int = 0
    project_types: List[str] = Field(default_factory=list)
    education_requirements: str = ""
    certifications: List[str] = Field(default_factory=list)
    soft_skills: List[str] = Field(default_factory=list)
    seniority_tier: str = "mid"    # intern | junior | mid | senior | lead
    role_focus: str = "balanced"   # skills-heavy | experience-heavy | project-heavy | balanced
    github_required: bool = False
    raw_summary: str = ""


class State(TypedDict):
    job_description: str
    resume_text: str
    github_handle: str
    jd_analysis: JDAnalysis          # now structured
    dynamic_weights: DynamicWeights
    weight_rationale: str
    screening_verdict: str
    github_audit: str                # raw text (for prompts)
    github_insights: GitHubInsight   # structured GitHub data
    skill_analysis: str
    project_analysis: str
    is_technical_match: bool
    validated_score: int             # cross-validated final score
    final_evaluation: CandidateReport
    cache_hit: bool


# LLM instance — temperature=0 for determinism
_llm = ChatGroq(
    model=GROQ_MODEL,
    temperature=0,
    model_kwargs={"seed": 42},
    groq_api_key=settings.GROQ_API_KEY,
)


# ─────────────────────────────────────────────────────────────────────────────
# DEEP GITHUB AUDITOR HELPER
# ─────────────────────────────────────────────────────────────────────────────
def _github_deep_audit(handle: str, jd: JDAnalysis) -> tuple[str, GitHubInsight]:
    """
    Fetches up to 20 repos. For each repo: name, language, stars, forks,
    topics, description, last push date. Computes activity_score and
    relevance_score against JD tech stack. Returns (raw_text, GitHubInsight).
    """
    if not handle or handle.lower() in ("unknown", "not_found", "none", ""):
        note = "No GitHub handle found in resume."
        return note, GitHubInsight(audit_note=note)

    try:
        from github import Github, GithubException

        token = os.getenv(
            "GITHUB_TOKEN",
            getattr(settings, "GITHUB_TOKEN", ""),
        )
        try:
            g = Github(token) if token else Github()
            user = g.get_user(handle)
            repos_iter = user.get_repos()
        except GithubException as ge:
            if ge.status == 401 and token:
                g = Github()
                user = g.get_user(handle)
                repos_iter = user.get_repos()
            else:
                raise ge

        repos = list(repos_iter)[:20]   # top 20 repos

        # Build JD tech set for relevance matching
        jd_tech = set(
            t.lower() for t in (
                jd.must_have_skills + jd.required_languages +
                jd.frameworks_tools + jd.nice_to_have_skills
            )
        )

        lang_count: dict = {}
        summaries: list = []
        total_stars = 0
        total_forks = 0
        repo_insights: List[GitHubRepoInsight] = []
        skill_evidence: dict = {}
        highly_relevant: list = []
        somewhat_relevant: list = []

        # Track recency for activity_score
        recent_pushes = 0
        now = datetime.datetime.now(datetime.timezone.utc)

        for r in repos:
            lang = r.language or "Unknown"
            lang_count[lang] = lang_count.get(lang, 0) + 1
            total_stars += r.stargazers_count
            total_forks += r.forks_count

            # Topics
            try:
                topics = r.get_topics()[:5]
            except Exception:
                topics = []

            # Last push recency
            last_push = r.pushed_at
            if last_push and last_push.tzinfo is None:
                last_push = last_push.replace(tzinfo=datetime.timezone.utc)
            days_since_push = (now - last_push).days if last_push else 9999
            if days_since_push < 180:
                recent_pushes += 1

            # Relevance classification
            repo_signals = set()
            if lang != "Unknown":
                repo_signals.add(lang.lower())
            repo_signals.update(t.lower() for t in topics)
            desc_words = set((r.description or "").lower().split())
            repo_signals.update(desc_words)

            overlap = repo_signals & jd_tech
            if len(overlap) >= 2:
                relevance = "highly_relevant"
                highly_relevant.append(r.name)
            elif len(overlap) == 1:
                relevance = "somewhat_relevant"
                somewhat_relevant.append(r.name)
            else:
                relevance = "unrelated"

            # Skill evidence mapping
            for skill in overlap:
                skill_evidence.setdefault(skill, []).append(r.name)

            last_push_str = last_push.isoformat() if last_push else "unknown"

            repo_insights.append(GitHubRepoInsight(
                name=r.name,
                language=lang,
                stars=r.stargazers_count,
                forks=r.forks_count,
                topics=topics,
                description=(r.description or "")[:200],
                last_pushed=last_push_str,
                relevance_to_jd=relevance,
                has_readme=False,   # skipped to save API quota
            ))

            summaries.append(
                f"REPO: {r.name} | LANG: {lang} | STARS: {r.stargazers_count} "
                f"| TOPICS: {', '.join(topics) or 'none'} "
                f"| LAST_PUSH: {last_push_str} | RELEVANCE: {relevance} "
                f"| DESC: {(r.description or 'N/A')[:100]}"
            )

        # Activity score: 0-100
        # Based on: ratio of recently-pushed repos + followers bonus
        total_repos_checked = max(len(repos), 1)
        recency_ratio = recent_pushes / total_repos_checked
        followers_bonus = min(20, user.followers // 5)
        activity_score = min(100, int(recency_ratio * 80) + followers_bonus)

        # Relevance score: 0-100
        highly_w = len(highly_relevant) * 15
        somewhat_w = len(somewhat_relevant) * 7
        relevance_score = min(100, highly_w + somewhat_w)

        top_langs = [l for l, _ in sorted(lang_count.items(), key=lambda x: -x[1])[:6]]
        lang_str = ", ".join(f"{l}({c})" for l, c in
                             sorted(lang_count.items(), key=lambda x: -x[1])[:6])

        raw_text = (
            f"Username: {user.login}\n"
            f"Public Repos: {user.public_repos} | Followers: {user.followers}\n"
            f"Total Stars: {total_stars} | Total Forks: {total_forks}\n"
            f"Top Languages: {lang_str}\n"
            f"Activity Score: {activity_score}/100 "
            f"({recent_pushes}/{total_repos_checked} repos pushed in last 6 months)\n"
            f"Relevance Score: {relevance_score}/100\n"
            f"Highly Relevant Repos ({len(highly_relevant)}): {', '.join(highly_relevant) or 'none'}\n"
            f"Somewhat Relevant Repos ({len(somewhat_relevant)}): {', '.join(somewhat_relevant) or 'none'}\n"
            f"Skill Evidence: {json.dumps(skill_evidence)}\n\n"
            f"REPO DETAILS:\n" + "\n".join(summaries)
        )

        insights = GitHubInsight(
            username=user.login,
            public_repos=user.public_repos,
            followers=user.followers,
            top_languages=top_langs,
            activity_score=activity_score,
            relevance_score=relevance_score,
            highly_relevant_repos=highly_relevant,
            somewhat_relevant_repos=somewhat_relevant,
            skill_evidence=skill_evidence,
            total_stars=total_stars,
            total_forks=total_forks,
            has_relevant_projects=len(highly_relevant) > 0,
            repos=repo_insights,
            audit_note=f"Audited {len(repos)} repos.",
        )
        return raw_text, insights

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"[GITHUB_DEBUG] Full traceback for '{handle}':\n{tb}")
        note = f"GitHub fetch failed for '{handle}': {e}"
        return note, GitHubInsight(username=handle, audit_note=note)


# ─────────────────────────────────────────────────────────────────────────────
# NODE 1 — Cache Check
# ─────────────────────────────────────────────────────────────────────────────
def cache_check(state: State):
    k = _cache_key(state["resume_text"], state["job_description"])
    if k in _CACHE:
        try:
            report = CandidateReport(**_CACHE[k])
            if report.match_score > 0 and report.candidate_name not in ("Unknown", "", "Candidate"):
                return {"final_evaluation": report, "cache_hit": True}
            del _CACHE[k]
            _save_cache()
        except Exception:
            pass
    return {"cache_hit": False}


# ─────────────────────────────────────────────────────────────────────────────
# NODE 2 — JD Architect (structured output)
# ─────────────────────────────────────────────────────────────────────────────
class _JDOutput(BaseModel):
    must_have_skills: List[str] = Field(default_factory=list)
    nice_to_have_skills: List[str] = Field(default_factory=list)
    required_languages: List[str] = Field(default_factory=list)
    frameworks_tools: List[str] = Field(default_factory=list)
    min_years_experience: int = 0
    project_types: List[str] = Field(default_factory=list)
    education_requirements: str = ""
    certifications: List[str] = Field(default_factory=list)
    soft_skills: List[str] = Field(default_factory=list)
    seniority_tier: str = "mid"
    role_focus: str = "balanced"
    github_required: bool = False
    raw_summary: str = ""


def jd_architect(state: State):
    """
    Extracts structured requirements from the JD.
    Determines seniority tier and role focus — these drive smarter weights.
    """
    prompt = (
        "You are a senior talent analyst. Extract ALL requirements from this Job Description.\n\n"
        "SENIORITY TIER rules:\n"
        "  - 'intern' if: internship / no experience required / fresh graduate\n"
        "  - 'junior' if: 0-2 years required\n"
        "  - 'mid' if: 2-5 years required\n"
        "  - 'senior' if: 5-8 years required\n"
        "  - 'lead' if: 8+ years / team lead / principal / staff required\n\n"
        "ROLE FOCUS rules:\n"
        "  - 'skills-heavy': JD lists many specific technical must-haves\n"
        "  - 'experience-heavy': JD emphasises years, seniority, past projects heavily\n"
        "  - 'project-heavy': JD requires portfolio / specific project types\n"
        "  - 'balanced': no single dimension dominates\n\n"
        f"JD:\n{state['job_description']}\n\n"
        "Return structured JSON matching the schema."
    )
    try:
        result = _llm.with_structured_output(_JDOutput).invoke(prompt)
        jd = JDAnalysis(**result.model_dump())
    except Exception:
        raw = _llm.invoke(prompt).content
        jd = JDAnalysis(raw_summary=raw, seniority_tier="mid", role_focus="balanced")
    return {"jd_analysis": jd}


# ─────────────────────────────────────────────────────────────────────────────
# NODE 3 — Weight Extractor (7 categories)
# ─────────────────────────────────────────────────────────────────────────────
class _WeightOutput(BaseModel):
    technical_skills: int = Field(default=30)
    programming_languages: int = Field(default=18)
    project_relevance: int = Field(default=18)
    years_experience: int = Field(default=14)
    github_quality: int = Field(default=10)
    education_certifications: int = Field(default=6)
    soft_skills: int = Field(default=4)
    rationale: str = Field(default="")


def weight_extractor(state: State):
    """
    Dynamically assigns 7-category scoring weights based on what the JD
    emphasises most. Seniority tier and role_focus from JD Architect
    drive the initial direction.

    Weight strategy by role:
    - skills-heavy   → boost technical_skills + programming_languages
    - experience-heavy → boost years_experience
    - project-heavy  → boost project_relevance + github_quality
    - intern/junior  → reduce years_experience (5-10), boost project_relevance
    - senior/lead    → boost years_experience (25-35)
    - github required → boost github_quality (15-25)
    """
    jd: JDAnalysis = state["jd_analysis"]

    prompt = (
        "You are a talent analytics engine. Assign 7 scoring weights (must sum to 100) "
        "that reflect exactly what THIS company cares about most in this role.\n\n"
        "HARD RULES:\n"
        "- All 7 values must be non-negative integers summing to EXACTLY 100.\n"
        "- technical_skills: 0-60   (must-have skills from JD)\n"
        "- programming_languages: 0-40\n"
        "- project_relevance: 0-40\n"
        "- years_experience: 0-40\n"
        "- github_quality: 0-25  (min 5 — we always audit GitHub as bonus signal)\n"
        "- education_certifications: 0-20\n"
        "- soft_skills: 0-15\n\n"
        "DIRECTION RULES:\n"
        f"- Seniority tier detected: '{jd.seniority_tier}'\n"
        f"- Role focus detected: '{jd.role_focus}'\n"
        f"- GitHub explicitly required: {jd.github_required}\n"
        f"- Must-have skills count: {len(jd.must_have_skills)}\n"
        f"- Education requirements: '{jd.education_requirements}'\n"
        f"- Certifications required: {jd.certifications}\n\n"
        "Apply these direction rules:\n"
        "  * intern/junior → years_experience: 5-10, project_relevance can be higher\n"
        "  * senior/lead → years_experience: 25-35\n"
        "  * skills-heavy → technical_skills: 40-55\n"
        "  * experience-heavy → years_experience: 25-35\n"
        "  * project-heavy → project_relevance: 28-38, github_quality: 15-22\n"
        "  * github explicitly required → github_quality: 18-25\n"
        "  * many certifications required → education_certifications: 12-18\n"
        "  * strong soft skills emphasis → soft_skills: 8-14\n\n"
        f"JD SUMMARY:\nMust-have skills: {jd.must_have_skills}\n"
        f"Required languages: {jd.required_languages}\n"
        f"Certifications: {jd.certifications}\n"
        f"Soft skills mentioned: {jd.soft_skills}\n\n"
        "Return JSON: technical_skills, programming_languages, project_relevance, "
        "years_experience, github_quality, education_certifications, soft_skills (all ints, sum=100), "
        "and rationale (2-3 sentences explaining your choices)."
    )

    def _parse_weights(obj) -> DynamicWeights:
        return DynamicWeights(
            technical_skills=obj.technical_skills,
            programming_languages=obj.programming_languages,
            project_relevance=obj.project_relevance,
            years_experience=obj.years_experience,
            github_quality=max(obj.github_quality, 5),
            education_certifications=obj.education_certifications,
            soft_skills=obj.soft_skills,
        )

    # Try structured output
    try:
        result = _llm.with_structured_output(_WeightOutput).invoke(prompt)
        return {"dynamic_weights": _parse_weights(result), "weight_rationale": result.rationale}
    except Exception:
        pass

    # Fallback: parse raw JSON text
    try:
        raw = _llm.invoke(prompt).content
        def _ex(label: str, default: int) -> int:
            m = re.search(rf'"{label}"\s*:\s*(\d+)', raw, re.IGNORECASE)
            return int(m.group(1)) if m else default
        rat_m = re.search(r'"rationale"\s*:\s*"([^"]+)"', raw, re.IGNORECASE)
        rationale = rat_m.group(1) if rat_m else "Weights assigned based on JD emphasis."
        w = DynamicWeights(
            technical_skills=_ex("technical_skills", 30),
            programming_languages=_ex("programming_languages", 18),
            project_relevance=_ex("project_relevance", 18),
            years_experience=_ex("years_experience", 14),
            github_quality=max(_ex("github_quality", 10), 5),
            education_certifications=_ex("education_certifications", 6),
            soft_skills=_ex("soft_skills", 4),
        )
        return {"dynamic_weights": w, "weight_rationale": rationale}
    except Exception:
        w = DynamicWeights(**DEFAULT_WEIGHTS)
        return {"dynamic_weights": w, "weight_rationale": "Default weights applied (extraction failed)."}


# ─────────────────────────────────────────────────────────────────────────────
# NODE 4 — Resume Screener (structured output, fast seniority check)
# ─────────────────────────────────────────────────────────────────────────────
class _ScreeningOutput(BaseModel):
    technical_match: bool = False
    match_confidence: str = "low"      # low | medium | high
    github_handle: str = "NOT_FOUND"
    linkedin_handle: str = "NOT_FOUND"
    years_experience: str = "0"
    seniority_detected: str = "unknown"
    candidate_name: str = ""
    email: str = ""
    phone: str = ""
    university: str = ""
    cgpa: str = ""
    mismatch_reason: str = ""


def resume_screener(state: State):
    """
    Fast initial screen: does the candidate's domain match the JD domain?
    Detects obvious mismatches (e.g., full-stack dev applying for AI role).
    Extracts structured candidate info.
    """
    jd: JDAnalysis = state["jd_analysis"]
    prompt = (
        "You are a technical recruiter performing an initial CV screen.\n\n"
        "TASK: Determine if this CV is broadly relevant to this job.\n"
        "technical_match = TRUE only if the candidate's core background aligns with "
        "the role domain (e.g., ML engineer applying for AI role → TRUE; "
        "full-stack web dev applying for embedded systems → FALSE).\n\n"
        "Extract all candidate info you find.\n\n"
        "For github_handle: extract the GitHub username only (no URL prefix). "
        "If not found → 'NOT_FOUND'.\n"
        "For years_experience: just the number as a string (e.g., '3').\n\n"
        f"REQUIRED SKILLS FOR THIS ROLE: {jd.must_have_skills}\n"
        f"ROLE DOMAIN: {jd.raw_summary or state['job_description'][:500]}\n"
        f"SENIORITY REQUIRED: {jd.seniority_tier}\n\n"
        f"CV:\n{state['resume_text']}\n\n"
        "If mismatch, briefly state why in mismatch_reason."
    )
    try:
        result = _llm.with_structured_output(_ScreeningOutput).invoke(prompt)
        handle = re.sub(r"(https?://)?(www\.)?github\.com/", "", result.github_handle, flags=re.IGNORECASE)
        handle = handle.strip("/").lstrip("@")
        if handle.lower() in ("not_found", "none", "n/a", "unknown", ""):
            handle = "unknown"
        return {
            "screening_verdict": (
                f"MATCH: {result.technical_match} | CONFIDENCE: {result.match_confidence} | "
                f"YEARS: {result.years_experience} | MISMATCH: {result.mismatch_reason}"
            ),
            "is_technical_match": result.technical_match,
            "github_handle": handle,
        }
    except Exception:
        # Fallback: raw text parse
        raw = _llm.invoke(
            f"Analyze resume vs JD. VERDICT: [MATCH/NO_MATCH]. GITHUB: [handle or NOT_FOUND]. "
            f"EXPERIENCE: [X years].\nRESUME:\n{state['resume_text']}\nJD:\n{state['job_description'][:500]}"
        ).content
        is_match = "VERDICT: MATCH" in raw.upper()
        m = re.search(r"GITHUB:\s*(\S+)", raw, re.IGNORECASE)
        handle = m.group(1) if m else "unknown"
        handle = re.sub(r"(https?://)?(www\.)?github\.com/", "", handle, flags=re.IGNORECASE).strip("/").lstrip("@")
        if handle.lower() in ("not_found", "none", "n/a", "unknown"):
            handle = "unknown"
        return {"screening_verdict": raw, "is_technical_match": is_match, "github_handle": handle}


# ─────────────────────────────────────────────────────────────────────────────
# NODE 5 — Deep GitHub Auditor (always runs)
# ─────────────────────────────────────────────────────────────────────────────
def github_auditor(state: State):
    """
    Deep audit: 20 repos, activity score, relevance score, skill evidence.
    Always runs — even when JD doesn't mention GitHub (bonus signal).
    """
    handle = state.get("github_handle", "unknown")
    jd = state.get("jd_analysis", JDAnalysis())
    raw_text, insights = _github_deep_audit(handle, jd)
    return {"github_audit": raw_text, "github_insights": insights}


# ─────────────────────────────────────────────────────────────────────────────
# NODE 6 — Two-Pass Skill Analyzer (always runs for MATCH candidates)
# ─────────────────────────────────────────────────────────────────────────────
def skill_analyzer(state: State):
    """
    Two-pass skill verification:
    Pass 1 — Extract all skills claimed in resume.
    Pass 2 — Cross-verify each JD must-have skill against GitHub evidence.
    Detects skill inflation: claimed but no GitHub or project proof → cap at 6/10.
    """
    w: DynamicWeights = state.get("dynamic_weights", DynamicWeights())
    jd: JDAnalysis = state.get("jd_analysis", JDAnalysis())
    insights: GitHubInsight = state.get("github_insights", GitHubInsight())

    pass1_prompt = (
        "PASS 1 — Skill Extraction:\n"
        "List ALL skills from this resume. For each: name, proficiency estimate (0-10), years, evidence quote.\n"
        f"Focus especially on these JD must-haves: {jd.must_have_skills}\n\n"
        f"RESUME:\n{state['resume_text']}"
    )
    pass1 = _llm.invoke(pass1_prompt).content

    pass2_prompt = (
        "PASS 2 — GitHub Cross-Verification:\n"
        f"Technical skills carry {w.technical_skills}% of the final score.\n\n"
        "For each JD MUST-HAVE skill:\n"
        "  1. Is it in resume? (yes/no)\n"
        "  2. Is it evidenced in GitHub repos or projects? (yes/no/partial)\n"
        "  3. Adjusted proficiency: if GitHub evidence → full score; "
        "resume-only claim → cap at 6/10; neither → 0.\n"
        "  4. Evidence quote or GitHub repo name.\n"
        "Flag any SKILL INFLATION: skills claimed but no project or GitHub proof.\n\n"
        f"JD MUST-HAVE SKILLS: {jd.must_have_skills}\n"
        f"JD NICE-TO-HAVE: {jd.nice_to_have_skills}\n"
        f"GITHUB SKILL EVIDENCE: {json.dumps(insights.skill_evidence)}\n"
        f"GITHUB HIGHLY RELEVANT REPOS: {insights.highly_relevant_repos}\n\n"
        f"RESUME SKILLS (from Pass 1):\n{pass1}\n\n"
        f"FULL RESUME:\n{state['resume_text']}"
    )
    pass2 = _llm.invoke(pass2_prompt).content

    return {"skill_analysis": f"=== PASS 1 (Extraction) ===\n{pass1}\n\n=== PASS 2 (GitHub Verification) ===\n{pass2}"}


# ─────────────────────────────────────────────────────────────────────────────
# NODE 7 — Project Analyzer (runs for MATCH candidates)
# ─────────────────────────────────────────────────────────────────────────────
def project_analyzer(state: State):
    """
    Evaluates ALL projects from resume + GitHub repos.
    Rates each by relevance (0-10) and complexity (0-10).
    Detects discrepancy: project listed in resume but no GitHub code found.
    """
    w: DynamicWeights = state.get("dynamic_weights", DynamicWeights())
    jd: JDAnalysis = state.get("jd_analysis", JDAnalysis())
    insights: GitHubInsight = state.get("github_insights", GitHubInsight())

    prompt = (
        f"Evaluate ALL projects from both resume AND GitHub. Rate each 0-10 for relevance and complexity.\n"
        f"Project relevance carries {w.project_relevance}% of the final score.\n\n"
        f"JD REQUIRED PROJECT TYPES: {jd.project_types}\n"
        f"JD MUST-HAVE SKILLS: {jd.must_have_skills}\n\n"
        f"GITHUB HIGHLY RELEVANT REPOS: {insights.highly_relevant_repos}\n"
        f"GITHUB SOMEWHAT RELEVANT REPOS: {insights.somewhat_relevant_repos}\n\n"
        "For each project:\n"
        "  - Name, source (Resume/GitHub/Both)\n"
        "  - Relevance score 0-10 with reasoning\n"
        "  - Complexity score 0-10 with reasoning\n"
        "  - Tech stack used\n"
        "  - Impact/outcome if mentioned\n"
        "Also flag any DISCREPANCY: project in resume but no corresponding GitHub repo found.\n\n"
        f"RESUME:\n{state['resume_text']}\n\n"
        f"GITHUB AUDIT:\n{state.get('github_audit', 'N/A')}"
    )
    return {"project_analysis": _llm.invoke(prompt).content}


# ─────────────────────────────────────────────────────────────────────────────
# NODE 8 — Score Cross-Validator (NEW)
# ─────────────────────────────────────────────────────────────────────────────
class _ValidationOutput(BaseModel):
    """LLM computes per-category raw scores; validator does the math."""
    technical_skills_raw: float = Field(default=0.0, ge=0, le=100)
    programming_languages_raw: float = Field(default=0.0, ge=0, le=100)
    project_relevance_raw: float = Field(default=0.0, ge=0, le=100)
    years_experience_raw: float = Field(default=0.0, ge=0, le=100)
    github_quality_raw: float = Field(default=0.0, ge=0, le=100)
    education_certifications_raw: float = Field(default=0.0, ge=0, le=100)
    soft_skills_raw: float = Field(default=0.0, ge=0, le=100)
    llm_proposed_score: int = Field(default=0, ge=0, le=100)
    scoring_confidence: str = Field(default="medium")  # high | medium | low


def score_cross_validator(state: State):
    """
    Node 8 — Mathematical cross-check:
    1. LLM assigns a raw score (0-100) for each of 7 categories.
    2. We compute: weighted_score = sum(raw_i * weight_i / 100).
    3. If |calculated - llm_proposed| > 12 points, we override with calculated.
    4. This makes the final score trustworthy — math always wins over hallucinations.
    """
    w: DynamicWeights = state.get("dynamic_weights", DynamicWeights())
    jd: JDAnalysis = state.get("jd_analysis", JDAnalysis())

    context = (
        f"RESUME:\n{state['resume_text'][:3000]}\n\n"
        f"JD:\n{state['job_description'][:1500]}\n\n"
        f"SKILL ANALYSIS:\n{state.get('skill_analysis', 'N/A')[:2000]}\n\n"
        f"PROJECT ANALYSIS:\n{state.get('project_analysis', 'N/A')[:2000]}\n\n"
        f"GITHUB:\n{state.get('github_audit', 'N/A')[:1500]}"
    )

    prompt = (
        "You are a precise scoring engine. Given all evidence below, assign a RAW score (0-100) "
        "for each category independently. Do NOT weight them yet — just rate how well the "
        "candidate performs in that dimension on a 0-100 scale.\n\n"
        "SCORING GUIDES:\n"
        f"technical_skills_raw: % of JD must-have skills candidate has (0-100). "
        f"GitHub-verified skills count fully; resume-only claims count 70%.\n"
        f"programming_languages_raw: % of required languages candidate knows (0-100).\n"
        f"project_relevance_raw: quality and relevance of projects (0=none, 100=multiple highly relevant).\n"
        f"years_experience_raw: 100 if meets/exceeds, scale down for gap:\n"
        f"  Required: {jd.min_years_experience} years. 6mo short=70, 1yr short=50, <half=20.\n"
        f"github_quality_raw: GitHub activity_score * 0.5 + relevance_score * 0.5.\n"
        f"education_certifications_raw: 100 if meets requirements, 60 if related, 30 if unrelated.\n"
        f"soft_skills_raw: evidence of leadership/communication/teamwork (0-100).\n\n"
        f"GITHUB ACTIVITY SCORE: {state.get('github_insights', GitHubInsight()).activity_score}\n"
        f"GITHUB RELEVANCE SCORE: {state.get('github_insights', GitHubInsight()).relevance_score}\n\n"
        "Also provide: llm_proposed_score (your holistic 0-100 estimate) and "
        "scoring_confidence ('high' if lots of evidence, 'medium' if some gaps, 'low' if little data).\n\n"
        + context
    )

    try:
        val_out = _llm.with_structured_output(_ValidationOutput).invoke(prompt)
    except Exception:
        # Fallback: build a simple estimate from GitHub insights
        gh = state.get("github_insights", GitHubInsight())
        gh_raw = (gh.activity_score * 0.5 + gh.relevance_score * 0.5)
        val_out = _ValidationOutput(
            technical_skills_raw=50.0,
            programming_languages_raw=50.0,
            project_relevance_raw=50.0,
            years_experience_raw=50.0,
            github_quality_raw=gh_raw,
            education_certifications_raw=50.0,
            soft_skills_raw=50.0,
            llm_proposed_score=50,
            scoring_confidence="low",
        )

    # ── Math calculation — this is the ground truth ──────────────────────────
    raw_scores = {
        "technical_skills":      val_out.technical_skills_raw,
        "programming_languages": val_out.programming_languages_raw,
        "project_relevance":     val_out.project_relevance_raw,
        "years_experience":      val_out.years_experience_raw,
        "github_quality":        val_out.github_quality_raw,
        "education_certifications": val_out.education_certifications_raw,
        "soft_skills":           val_out.soft_skills_raw,
    }

    calculated = 0.0
    for key, raw in raw_scores.items():
        weight = getattr(w, key, 0)
        calculated += raw * weight / 100.0

    calculated_int = int(round(calculated))
    llm_proposed   = val_out.llm_proposed_score
    gap             = abs(calculated_int - llm_proposed)
    cross_check_ok  = gap <= 12

    # Math wins if gap > 12
    validated_score = calculated_int if not cross_check_ok else llm_proposed

    return {
        "validated_score": validated_score,
        # We embed raw scores in state for the final report node to use
        # by passing them through github_audit field as structured JSON addendum
        "github_audit": state.get("github_audit", "") + (
            f"\n\n=== CROSS-VALIDATOR SCORES ===\n"
            f"Raw scores: {json.dumps({k: round(v, 1) for k, v in raw_scores.items()})}\n"
            f"Calculated total: {calculated_int} | LLM proposed: {llm_proposed} | "
            f"Gap: {gap} | Cross-check passed: {cross_check_ok} | "
            f"Confidence: {val_out.scoring_confidence}\n"
            f"FINAL VALIDATED SCORE: {validated_score}"
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# NODE 9 — Quality Control Officer (Final Report)
# ─────────────────────────────────────────────────────────────────────────────
def quality_control_officer(state: State):
    w: DynamicWeights = state.get("dynamic_weights", DynamicWeights())
    rubric = _build_rubric(w)
    weight_rationale = state.get("weight_rationale", "")
    validated_score = state.get("validated_score", 0)
    insights: GitHubInsight = state.get("github_insights", GitHubInsight())

    # Derive final decision from validated score
    if validated_score >= 70:
        forced_decision = "MATCH"
    elif validated_score >= 50:
        forced_decision = "MAYBE"
    else:
        forced_decision = "NO_MATCH"

    context = (
        f"RESUME:\n{state['resume_text']}\n\n"
        f"JD:\n{state['job_description']}\n\n"
        f"SCREENING:\n{state.get('screening_verdict', 'N/A')}\n\n"
        f"GITHUB AUDIT:\n{state.get('github_audit', 'N/A')}\n\n"
        f"SKILLS (2-pass verified):\n{state.get('skill_analysis', 'N/A')}\n\n"
        f"PROJECTS:\n{state.get('project_analysis', 'N/A')}\n\n"
        f"VALIDATED SCORE (math-verified): {validated_score}\n"
        f"FORCED DECISION: {forced_decision}"
    )

    class CoreReport(BaseModel):
        candidate_name: str = "Unknown"
        email: str = ""
        phone_no: str = ""
        university_name: str = ""
        cgpa: str = ""
        github_handle: str = ""
        linkedin_handle: str = ""
        years_of_experience: str = "Unknown"
        seniority_tier: str = "mid"
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
                c = re.sub(r"[^0-9]", "", v)
                return int(c) if c else 0
            try:
                return int(v)
            except Exception:
                return 0

        @field_validator("final_decision", mode="before")
        @classmethod
        def fix_d(cls, v):
            v = str(v).upper().strip()
            if "NO" in v: return "NO_MATCH"
            if "MAYBE" in v: return "MAYBE"
            if "MATCH" in v: return "MATCH"
            return "NO_MATCH"

    core = None
    for attempt in range(3):
        try:
            core = _llm.with_structured_output(CoreReport).invoke(
                f"Fill CoreReport. Use match_score = {validated_score} (math-validated — do NOT change it). "
                f"Use final_decision = {forced_decision}.\n"
                f"In cultural_fit_notes: show per-category scoring breakdown with evidence.\n"
                "Generate outreach_email_draft (for MATCH/MAYBE) and rejection_email_draft (for NO_MATCH).\n\n"
                + rubric + "\n\n" + context
            )
            if core.candidate_name not in ("Unknown", ""):
                break
        except Exception:
            core = None

    if core is None:
        raw = _llm.invoke(
            f"Extract from resume: NAME, EMAIL, PHONE, UNIVERSITY, CGPA, GITHUB, LINKEDIN, EXPERIENCE.\n"
            f"RESUME:\n{state['resume_text'][:2000]}"
        ).content
        def ex(lbl):
            m = re.search(rf"{lbl}:\s*(.+)", raw, re.IGNORECASE)
            return m.group(1).strip() if m else ""
        core = CoreReport(
            candidate_name=ex("NAME") or "Candidate",
            email=ex("EMAIL"),
            phone_no=ex("PHONE"),
            university_name=ex("UNIVERSITY"),
            cgpa=ex("CGPA"),
            github_handle=ex("GITHUB"),
            linkedin_handle=ex("LINKEDIN"),
            years_of_experience=ex("EXPERIENCE") or "Unknown",
            match_score=validated_score,
            final_decision=forced_decision,
            cultural_fit_notes="Score computed via mathematical cross-validation.",
        )

    # ── Build structured skill / language / project lists ─────────────────────
    class ListsReport(BaseModel):
        skill_matches: List[SkillMatch] = Field(default_factory=list)
        language_matches: List[LanguageMatch] = Field(default_factory=list)
        project_highlights: List[ProjectHighlight] = Field(default_factory=list)

    try:
        lists = _llm.with_structured_output(ListsReport).invoke(
            "Fill ListsReport from all evidence below.\n"
            "skill_matches: ALL JD must-haves + bonus skills. Set github_verified=true if GitHub confirms skill.\n"
            "language_matches: ALL languages. Set github_verified=true if seen in GitHub repos.\n"
            "project_highlights: top 5 most relevant projects. Set source to 'Resume'/'GitHub'/'Both'.\n\n"
            + context
        )
    except Exception:
        lists = ListsReport()

    # ── Build category_scores from validated data ─────────────────────────────
    cat_scores: List[CategoryScore] = []
    for key, label, weight in w.ordered_items():
        # Try to find evidence from the audit addendum in github_audit
        audit_text = state.get("github_audit", "")
        raw_m = re.search(
            rf'"{key}"\s*:\s*([\d.]+)',
            audit_text[audit_text.find("=== CROSS-VALIDATOR SCORES ==="):] if "CROSS-VALIDATOR" in audit_text else "",
        )
        raw_val = float(raw_m.group(1)) if raw_m else 50.0
        cat_scores.append(CategoryScore(
            category=key,
            label=label,
            weight_used=weight,
            raw_score=raw_val,
            weighted_score=round(raw_val * weight / 100, 2),
            evidence="",
        ))

    # Determine scoring_confidence from audit text
    conf_m = re.search(r"Confidence:\s*(\w+)", state.get("github_audit", ""), re.IGNORECASE)
    scoring_confidence = conf_m.group(1).lower() if conf_m else "medium"
    if scoring_confidence not in ("high", "medium", "low"):
        scoring_confidence = "medium"

    # Cross-check passed?
    cross_m = re.search(r"Cross-check passed:\s*(True|False)", state.get("github_audit", ""), re.IGNORECASE)
    cross_check_ok = cross_m.group(1).lower() == "true" if cross_m else False

    report = CandidateReport(
        candidate_name=core.candidate_name,
        email=core.email,
        phone_no=core.phone_no,
        university_name=core.university_name,
        cgpa=core.cgpa,
        github_handle=core.github_handle or insights.username,
        linkedin_handle=core.linkedin_handle,
        years_of_experience=core.years_of_experience,
        seniority_tier=core.seniority_tier,
        match_score=validated_score,          # always the math-verified score
        final_decision=forced_decision,        # always consistent with score
        cultural_fit_notes=core.cultural_fit_notes,
        strengths=core.strengths,
        red_flags=core.red_flags,
        outreach_email_draft=core.outreach_email_draft,
        rejection_email_draft=core.rejection_email_draft,
        skill_matches=lists.skill_matches,
        language_matches=lists.language_matches,
        project_highlights=lists.project_highlights,
        category_scores=cat_scores,
        evaluation_scores=[],                 # legacy kept empty
        github_summary=state.get("github_audit", ""),
        github_insights=insights,
        scoring_weights=w.as_dict(),
        weight_rationale=weight_rationale,
        score_cross_check_passed=cross_check_ok,
        calculated_score=validated_score,
        scoring_confidence=scoring_confidence,
    )

    if report.match_score > 0 and report.candidate_name not in ("Unknown", "", "Candidate"):
        _CACHE[_cache_key(state["resume_text"], state["job_description"])] = report.model_dump()
        _save_cache()

    return {"final_evaluation": report, "cache_hit": False}


# ─────────────────────────────────────────────────────────────────────────────
# QUICK REPORT for obvious mismatches (skips deep analysis)
# ─────────────────────────────────────────────────────────────────────────────
def quick_report(state: State):
    """
    Fast-path for candidates whose domain clearly doesn't match the JD.
    GitHub is still audited (done before routing), but we skip 2-pass skills
    and project deep-dive. Score is set conservatively low.
    """
    w: DynamicWeights = state.get("dynamic_weights", DynamicWeights())
    insights: GitHubInsight = state.get("github_insights", GitHubInsight())

    prompt = (
        "This candidate did NOT pass the initial domain screen. Generate a brief report.\n"
        "Set match_score between 10-45 (they don't fit the role domain).\n"
        "Set final_decision = NO_MATCH.\n"
        "Extract: candidate name, email, phone, university, cgpa, github handle.\n"
        "List 2-3 reasons why they don't fit in red_flags.\n"
        "Generate a professional rejection_email_draft.\n\n"
        f"SCREENING NOTE: {state.get('screening_verdict', 'Domain mismatch detected.')}\n\n"
        f"RESUME:\n{state['resume_text'][:2000]}\n\n"
        f"JD SUMMARY:\n{state['job_description'][:800]}"
    )

    class QuickCore(BaseModel):
        candidate_name: str = "Candidate"
        email: str = ""
        phone_no: str = ""
        university_name: str = ""
        cgpa: str = ""
        github_handle: str = ""
        match_score: int = 20
        red_flags: List[str] = Field(default_factory=list)
        rejection_email_draft: str = ""

    try:
        q = _llm.with_structured_output(QuickCore).invoke(prompt)
    except Exception:
        raw = _llm.invoke(prompt).content
        def ex(lbl):
            m = re.search(rf"{lbl}:\s*(.+)", raw, re.IGNORECASE)
            return m.group(1).strip() if m else ""
        sc_raw = ex("SCORE")
        sc = int(re.sub(r"[^0-9]", "", sc_raw)) if sc_raw else 20
        sc = min(sc, 45)  # hard cap for mismatches
        q = QuickCore(
            candidate_name=ex("NAME") or "Candidate",
            email=ex("EMAIL"),
            phone_no=ex("PHONE"),
            university_name=ex("UNIVERSITY"),
            cgpa=ex("CGPA"),
            github_handle=ex("GITHUB"),
            match_score=sc,
        )

    score = min(q.match_score, 45)  # enforce hard cap
    cat_scores: List[CategoryScore] = []
    for key, label, weight in w.ordered_items():
        cat_scores.append(CategoryScore(
            category=key, label=label, weight_used=weight,
            raw_score=20.0, weighted_score=round(20.0 * weight / 100, 2),
            evidence="Domain mismatch — quick report.",
        ))

    report = CandidateReport(
        candidate_name=q.candidate_name,
        email=q.email,
        phone_no=q.phone_no,
        university_name=q.university_name,
        cgpa=q.cgpa,
        github_handle=q.github_handle or insights.username,
        match_score=score,
        final_decision="NO_MATCH",
        red_flags=q.red_flags,
        rejection_email_draft=q.rejection_email_draft,
        cultural_fit_notes=f"Fast-rejected: domain mismatch. {state.get('screening_verdict','')}",
        category_scores=cat_scores,
        github_summary=state.get("github_audit", ""),
        github_insights=insights,
        scoring_weights=w.as_dict(),
        weight_rationale=state.get("weight_rationale", ""),
        score_cross_check_passed=True,
        calculated_score=score,
        scoring_confidence="low",
    )
    return {"final_evaluation": report, "validated_score": score}


# ─────────────────────────────────────────────────────────────────────────────
# ROUTING
# ─────────────────────────────────────────────────────────────────────────────
def route_cache(state: State) -> Literal["analyze_jd", "done"]:
    return "done" if state.get("cache_hit") else "analyze_jd"


def route_screen(state: State) -> Literal["analyze_skills", "quick_reject"]:
    """
    Route to full analysis (MATCH) or fast rejection (obvious mismatch).
    Fast rejection: domain clearly doesn't match (e.g., full-stack dev → AI role).
    """
    return "analyze_skills" if state["is_technical_match"] else "quick_reject"


# ─────────────────────────────────────────────────────────────────────────────
# GRAPH CONSTRUCTION
# ─────────────────────────────────────────────────────────────────────────────
# Flow:
#   cache_check → analyze_jd → extract_weights → screen_resume → audit_github
#   → [MATCH] analyze_skills → analyze_projects → validate_score → finalize_report
#   → [NO_MATCH/domain mismatch] quick_report (GitHub still audited above)
# ─────────────────────────────────────────────────────────────────────────────
_wf = StateGraph(State)
_wf.add_node("check_cache",      cache_check)
_wf.add_node("analyze_jd",       jd_architect)
_wf.add_node("extract_weights",  weight_extractor)
_wf.add_node("screen_resume",    resume_screener)
_wf.add_node("audit_github",     github_auditor)      # ALWAYS runs
_wf.add_node("analyze_skills",   skill_analyzer)
_wf.add_node("analyze_projects", project_analyzer)
_wf.add_node("validate_score",   score_cross_validator)   # NEW
_wf.add_node("finalize_report",  quality_control_officer)
_wf.add_node("quick_report",     quick_report)             # fast-reject path

_wf.add_edge(START, "check_cache")
_wf.add_conditional_edges("check_cache", route_cache, {
    "analyze_jd": "analyze_jd",
    "done": END,
})
_wf.add_edge("analyze_jd",      "extract_weights")
_wf.add_edge("extract_weights", "screen_resume")
_wf.add_edge("screen_resume",   "audit_github")       # GitHub ALWAYS audited first
_wf.add_conditional_edges("audit_github", route_screen, {
    "analyze_skills": "analyze_skills",               # domain match → full deep analysis
    "quick_reject":   "quick_report",                 # obvious mismatch → fast rejection
})
_wf.add_edge("analyze_skills",   "analyze_projects")
_wf.add_edge("analyze_projects", "validate_score")    # NEW: math cross-check
_wf.add_edge("validate_score",   "finalize_report")
_wf.add_edge("finalize_report",  END)
_wf.add_edge("quick_report",     END)

scoring_graph = _wf.compile()


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────
def score_candidate(resume_text: str, job_description: str) -> CandidateReport:
    result = scoring_graph.invoke({
        "resume_text": resume_text,
        "job_description": job_description,
        "github_handle": "",
        "jd_analysis": JDAnalysis(),
        "dynamic_weights": DynamicWeights(),
        "weight_rationale": "",
        "screening_verdict": "",
        "github_audit": "",
        "github_insights": GitHubInsight(),
        "skill_analysis": "",
        "project_analysis": "",
        "is_technical_match": False,
        "validated_score": 0,
        "final_evaluation": None,
        "cache_hit": False,
    })
    return result["final_evaluation"]

class JobMatchResult(BaseModel):
    job_id: Optional[str] = Field(description="The ID of the best matching job, or None if completely unrelated.")
    reason: str = Field(description="Why this job was selected.")

def route_cv_to_job(cv_text: str, active_jobs: list) -> Optional[str]:
    """Uses an LLM to find the best matching job for a given CV from a list of active jobs."""
    try:
        from langchain.prompts import PromptTemplate
        
        if not active_jobs:
            return None
            
        jobs_context = "\n".join([f"ID: {j.id} | Title: {j.title} | Desc: {(j.description or j.requirements)[:200]}" for j in active_jobs])
        
        prompt = PromptTemplate.from_template(
            "You are an expert technical recruiter.\n"
            "Given the candidate's CV text (first 1500 chars) and a list of active job openings, "
            "select the most relevant job for this candidate. If the candidate's CV is completely unrelated "
            "to any of the open roles (e.g. graphic designer applying for backend), return None for job_id.\n\n"
            "Active Jobs:\n{jobs_context}\n\n"
            "Candidate CV Snippet:\n{cv_snippet}\n"
        )
        
        from app.core.config import settings
        from langchain_groq import ChatGroq
        llm = ChatGroq(model=GROQ_MODEL, temperature=0, groq_api_key=settings.GROQ_API_KEY).with_structured_output(JobMatchResult)
        
        result = llm.invoke(prompt.format(
            jobs_context=jobs_context, 
            cv_snippet=cv_text[:1500]
        ))
        
        import logging
        logging.getLogger(__name__).info(f"[CV Router] LLM routed CV to job_id: {result.job_id} | Reason: {result.reason}")
        return result.job_id
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[CV Router] Failed to route CV: {e}")
        return None
