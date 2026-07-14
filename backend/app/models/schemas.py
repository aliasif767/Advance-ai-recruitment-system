"""
backend/app/models/schemas.py
Pydantic schemas shared by agents and API endpoints.
"""
import re
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class SkillMatch(BaseModel):
    skill_name: str = ""
    required: bool = False
    candidate_has: bool = False
    proficiency: int = 0          # 0-10
    evidence: str = ""
    years: str = "Unknown"
    github_verified: bool = False  # True if skill found in GitHub repos


class LanguageMatch(BaseModel):
    language: str = ""
    jd_requires: bool = False
    candidate_has: bool = False
    proficiency: int = 0
    evidence: str = ""
    github_verified: bool = False  # True if language seen in GitHub repos


class ProjectHighlight(BaseModel):
    project_name: str = ""
    relevance_score: int = 0       # 0-10
    complexity_score: int = 0      # 0-10 — NEW
    tech_stack: List[str] = Field(default_factory=list)
    description: str = ""
    source: str = "Resume"         # "Resume" | "GitHub" | "Both"
    impact: str = ""
    github_url: str = ""           # NEW — direct link if from GitHub


class GitHubRepoInsight(BaseModel):
    """Insight for a single GitHub repository."""
    name: str = ""
    language: str = ""
    stars: int = 0
    forks: int = 0
    topics: List[str] = Field(default_factory=list)
    description: str = ""
    last_pushed: str = ""          # ISO date string
    relevance_to_jd: str = "unrelated"   # "highly_relevant" | "somewhat_relevant" | "unrelated"
    has_readme: bool = False


class GitHubInsight(BaseModel):
    """Aggregated GitHub profile audit result."""
    username: str = ""
    public_repos: int = 0
    followers: int = 0
    top_languages: List[str] = Field(default_factory=list)
    activity_score: int = 0        # 0-100: recency + commit frequency
    relevance_score: int = 0       # 0-100: how well repos align with JD tech stack
    highly_relevant_repos: List[str] = Field(default_factory=list)
    somewhat_relevant_repos: List[str] = Field(default_factory=list)
    skill_evidence: dict = Field(default_factory=dict)   # skill → [repo_name, ...]
    total_stars: int = 0
    total_forks: int = 0
    has_relevant_projects: bool = False
    repos: List[GitHubRepoInsight] = Field(default_factory=list)
    audit_note: str = ""           # any errors or fallback messages


class CategoryScore(BaseModel):
    """Per-category scoring breakdown — replaces the old EvaluationScore."""
    category: str = ""             # e.g. "technical_skills"
    label: str = ""                # human-readable e.g. "Technical Skills"
    weight_used: int = 0           # weight % assigned by dynamic weights
    raw_score: float = 0.0         # 0-100 raw score before weighting
    weighted_score: float = 0.0    # raw_score * weight / 100
    evidence: str = ""             # brief reasoning


class EvaluationScore(BaseModel):
    """Legacy model kept for backwards compatibility."""
    category: str = ""
    score: int = 0
    notes: str = ""


class CandidateReport(BaseModel):
    # ── Basic Info ────────────────────────────────────────────────────────────
    candidate_name: str = "Unknown"
    email: str = ""
    phone_no: str = ""
    university_name: str = ""
    cgpa: str = ""
    github_handle: str = ""
    linkedin_handle: str = ""      # NEW
    years_of_experience: str = "Unknown"
    seniority_tier: str = ""       # NEW: "intern"|"junior"|"mid"|"senior"|"lead"

    # ── Scores ───────────────────────────────────────────────────────────────
    match_score: int = Field(default=0)
    final_decision: str = "NO_MATCH"

    # ── Skill & Language Detail ───────────────────────────────────────────────
    skill_matches: List[SkillMatch] = Field(default_factory=list)
    language_matches: List[LanguageMatch] = Field(default_factory=list)
    project_highlights: List[ProjectHighlight] = Field(default_factory=list)

    # ── New Structured Scores (replaces flat evaluation_scores) ───────────────
    category_scores: List[CategoryScore] = Field(default_factory=list)
    evaluation_scores: List[EvaluationScore] = Field(default_factory=list)   # legacy

    # ── Narrative ─────────────────────────────────────────────────────────────
    strengths: List[str] = Field(default_factory=list)
    red_flags: List[str] = Field(default_factory=list)
    cultural_fit_notes: str = ""

    # ── GitHub ────────────────────────────────────────────────────────────────
    github_summary: str = ""       # raw text (legacy)
    github_insights: Optional[GitHubInsight] = None   # NEW structured insights

    # ── Emails ────────────────────────────────────────────────────────────────
    outreach_email_draft: str = ""
    rejection_email_draft: str = ""

    # ── Scoring Metadata ──────────────────────────────────────────────────────
    scoring_weights: dict = Field(default_factory=dict)
    weight_rationale: str = ""
    score_cross_check_passed: bool = False    # NEW: math verified
    calculated_score: int = 0                 # NEW: math-computed score
    scoring_confidence: str = "medium"        # NEW: "high"|"medium"|"low"

    @field_validator("match_score", mode="before")
    @classmethod
    def ensure_int(cls, v):
        if isinstance(v, str):
            c = re.sub(r"[^0-9]", "", v)
            return int(c) if c else 0
        try:
            return int(v)
        except Exception:
            return 0

    @field_validator("final_decision", mode="before")
    @classmethod
    def normalize_decision(cls, v):
        v = str(v).upper().strip()
        if "NO" in v:    return "NO_MATCH"
        if "MAYBE" in v: return "MAYBE"
        if "MATCH" in v: return "MATCH"
        return "NO_MATCH"


class JobRequirements(BaseModel):
    job_title: str
    company_name: str
    key_requirements: str
    hr_email: Optional[str] = ""
    location: Optional[str] = "Remote"
    experience_years: Optional[int] = 0
    salary_range: Optional[str] = ""
    employment_type: Optional[str] = "Full-time"


class GeneratedJD(BaseModel):
    job_title: str
    company_name: str
    job_description: str
    short_description: str = ""
    required_skills: List[str] = Field(default_factory=list)
    nice_to_have: List[str] = Field(default_factory=list)