"""
backend/app/agents/resume_parser/agent.py
"""
import os
from typing import List
from app.utils.text_processing import extract_text_from_file, clean_text

SUPPORTED = {".pdf", ".docx", ".txt"}


class ResumeParserAgent:
    def parse_folder(self, folder_path: str) -> List[tuple]:
        results = []
        if not os.path.isdir(folder_path):
            return results
        for filename in os.listdir(folder_path):
            _, ext = os.path.splitext(filename.lower())
            if ext not in SUPPORTED:
                continue
            full_path = os.path.join(folder_path, filename)
            text = self._safe_extract(full_path)
            if text:
                results.append((full_path, text))
        return results

    def parse_file(self, file_path: str) -> str:
        return self._safe_extract(file_path)

    def _safe_extract(self, file_path: str) -> str:
        try:
            raw = extract_text_from_file(file_path)
            return clean_text(raw)
        except Exception as e:
            print(f"[ResumeParser] Failed: {file_path}: {e}")
            return ""
