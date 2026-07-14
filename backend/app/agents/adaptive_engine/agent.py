"""
backend/app/agents/adaptive_engine/agent.py
Adaptive difficulty router — adjusts question difficulty based on candidate performance.
"""
from typing import List, Optional, Dict, Any
import random


def get_next_difficulty(
    current_difficulty: str,
    correct_streak: int,
    wrong_streak: int,
    correct_count: int,
    total_answered: int,
) -> str:
    """
    Adaptive difficulty algorithm:
    - If correct_streak >= 3 and current != hard: increase difficulty
    - If wrong_streak >= 2 and current != easy: decrease difficulty
    - Otherwise: maintain current difficulty
    - After 10 questions: use accuracy-based leveling
      (accuracy > 80% → hard, 50-80% → medium, < 50% → easy)
    """
    if total_answered >= 10:
        accuracy = correct_count / total_answered
        if accuracy >= 0.8:
            return "hard"
        elif accuracy >= 0.5:
            return "medium"
        else:
            return "easy"

    if correct_streak >= 3:
        if current_difficulty == "easy":
            return "medium"
        elif current_difficulty == "medium":
            return "hard"
            
    if wrong_streak >= 2:
        if current_difficulty == "hard":
            return "medium"
        elif current_difficulty == "medium":
            return "easy"

    return current_difficulty


def select_next_question(
    question_bank: List[Dict[str, Any]],
    asked_ids: List[str],
    target_difficulty: str,
    question_type_weights: dict = None,
) -> Optional[Dict[str, Any]]:
    """
    Select the next best question from the bank:
    1. Filter by target_difficulty and not in asked_ids
    2. Fallback to adjacent difficulty if no questions available
    """
    available = [q for q in question_bank if str(q.get("_id", q.get("id"))) not in asked_ids]
    if not available:
        return None

    # Try matching target difficulty
    matching = [q for q in available if q.get("difficulty") == target_difficulty]
    
    # Fallback to any difficulty if none match target
    if not matching:
        matching = available

    # Basic random selection from valid pool
    return random.choice(matching)
