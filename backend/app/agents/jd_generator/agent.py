"""
backend/app/agents/jd_generator/agent.py
"""
import json
import re
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from app.core.config import settings
from app.models.schemas import JobRequirements, GeneratedJD
from app.agents.jd_generator.prompt import SYSTEM_PROMPT, JD_GENERATION_PROMPT


class JDGeneratorAgent:
    def __init__(self):
        self.llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.7, groq_api_key=settings.GROQ_API_KEY)

    def generate(self, requirements: JobRequirements) -> GeneratedJD:
        prompt = ChatPromptTemplate.from_messages([("system", SYSTEM_PROMPT), ("user", JD_GENERATION_PROMPT)])
        result = (prompt | self.llm).invoke(requirements.model_dump())
        text = result.content

        def extract(label):
            m = re.search(rf"{label}:\s*(.*?)(?=\n[A-Z_]+:|$)", text, re.DOTALL)
            return m.group(1).strip() if m else ""

        def extract_json(label):
            m = re.search(rf"{label}:\s*(\[.*?\])", text, re.DOTALL)
            try:
                return json.loads(m.group(1)) if m else []
            except Exception:
                return []

        return GeneratedJD(
            job_title=requirements.job_title,
            company_name=requirements.company_name,
            job_description=extract("FULL_JD") or text,
            short_description=extract("SHORT_LINKEDIN"),
            required_skills=extract_json("REQUIRED_SKILLS_JSON"),
            nice_to_have=extract_json("NICE_TO_HAVE_JSON"),
        )
