"""
backend/app/services/code_runner_service.py
Executes candidate code in a secure sandbox and evaluates against test cases.
Note: For production, this should run inside isolated Docker containers (e.g. gVisor).
This implementation uses Python's subprocess as a basic sandbox for demonstration,
or an LLM-based mock evaluator if code execution is disabled.
"""
import os
import tempfile
import subprocess
import asyncio
from typing import List, Dict, Any, Tuple

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


async def run_code_against_tests(
    language: str,
    code: str,
    test_cases: List[Dict[str, Any]],
    timeout_ms: int = None,
) -> Dict[str, Any]:
    """
    Run the provided code against all test cases.
    Returns results dict with pass/fail status per case and overall score.
    """
    timeout = (timeout_ms or settings.CODE_EXECUTION_TIMEOUT_MS) / 1000.0

    if not settings.CODE_EXECUTION_ENABLED:
        logger.info("[CodeRunner] Code execution disabled in settings. Using LLM mock evaluation.")
        return await _llm_mock_evaluation(language, code, test_cases)

    if language.lower() == "python":
        return await _run_python(code, test_cases, timeout)
    elif language.lower() in ["javascript", "js", "node"]:
        return await _run_javascript(code, test_cases, timeout)
    else:
        # Fallback to LLM for unsupported languages locally
        logger.warning(f"[CodeRunner] Local execution not supported for {language}. Using LLM.")
        return await _llm_mock_evaluation(language, code, test_cases)


async def analyze_complexity(code: str, language: str) -> Dict[str, str]:
    """Use LLM to estimate Big-O time and space complexity."""
    try:
        from langchain_groq import ChatGroq
        from pydantic import BaseModel
        
        class Complexity(BaseModel):
            time_complexity: str
            space_complexity: str
            explanation: str

        llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0, groq_api_key=settings.GROQ_API_KEY)
        
        prompt = (
            f"Analyze the following {language} code and determine its asymptotic Time and Space Complexity (Big-O).\n\n"
            f"CODE:\n{code}\n\n"
            "Return structured JSON with time_complexity, space_complexity, and a 1-sentence explanation."
        )
        
        res = llm.with_structured_output(Complexity).invoke(prompt)
        return {
            "time": res.time_complexity,
            "space": res.space_complexity,
            "explanation": res.explanation
        }
    except Exception as e:
        logger.error(f"[CodeRunner] Complexity analysis failed: {e}")
        return {"time": "O(N)", "space": "O(N)", "explanation": "Analysis failed."}


# ─── Language Specific Runners ───────────────────────────────────────────────

async def _run_python(code: str, test_cases: List[Dict[str, Any]], timeout: float) -> Dict[str, Any]:
    results = []
    passed_count = 0
    total_time = 0.0

    for i, tc in enumerate(test_cases):
        input_data = tc.get("input", "")
        expected = tc.get("expected_output", "").strip()
        hidden = tc.get("hidden", False)

        wrapper_code = f"""
import sys
# Candidate Code:
{code}
"""
        # If it's a function definition, we need a way to call it with the input.
        # For simplicity in this demo, we assume the candidate code reads from sys.stdin
        # OR we could wrap it. Assuming stdin for algorithmic style questions:
        
        try:
            start_time = asyncio.get_event_loop().time()
            proc = await asyncio.create_subprocess_exec(
                "python", "-c", wrapper_code,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=input_data.encode()),
                timeout=timeout
            )
            exec_time = asyncio.get_event_loop().time() - start_time
            total_time += exec_time
            
            out_str = stdout.decode().strip()
            err_str = stderr.decode().strip()

            if proc.returncode != 0:
                results.append({
                    "case_index": i,
                    "passed": False,
                    "output": err_str if not hidden else "Hidden Test Failed",
                    "expected": expected if not hidden else "Hidden",
                    "error": "Runtime Error"
                })
            elif out_str == expected:
                passed_count += 1
                results.append({
                    "case_index": i,
                    "passed": True,
                    "output": out_str if not hidden else "Hidden output",
                    "expected": expected if not hidden else "Hidden",
                    "time_ms": int(exec_time * 1000)
                })
            else:
                results.append({
                    "case_index": i,
                    "passed": False,
                    "output": out_str if not hidden else "Incorrect output",
                    "expected": expected if not hidden else "Hidden",
                })
                
        except asyncio.TimeoutError:
            proc.kill()
            results.append({
                "case_index": i,
                "passed": False,
                "output": "Timeout Exceeded",
                "expected": expected if not hidden else "Hidden",
                "error": "Timeout"
            })
        except Exception as e:
            results.append({
                "case_index": i,
                "passed": False,
                "error": str(e)
            })

    score = (passed_count / max(len(test_cases), 1)) * 100.0
    return {
        "score": score,
        "passed_cases": passed_count,
        "total_cases": len(test_cases),
        "results": results,
        "avg_time_ms": int((total_time / max(len(test_cases), 1)) * 1000)
    }


async def _run_javascript(code: str, test_cases: List[Dict[str, Any]], timeout: float) -> Dict[str, Any]:
    # Similar to Python, requires Node.js installed.
    # Leaving as placeholder that returns mock fail if Node isn't present
    results = []
    passed_count = 0
    for i, tc in enumerate(test_cases):
        input_data = tc.get("input", "")
        expected = tc.get("expected_output", "").strip()
        hidden = tc.get("hidden", False)
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "node", "-e", code,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=input_data.encode()),
                timeout=timeout
            )
            out_str = stdout.decode().strip()
            if out_str == expected:
                passed_count += 1
                results.append({"case_index": i, "passed": True, "output": out_str if not hidden else "Hidden"})
            else:
                results.append({"case_index": i, "passed": False, "output": out_str if not hidden else "Hidden", "expected": expected if not hidden else "Hidden"})
        except Exception as e:
            results.append({"case_index": i, "passed": False, "error": str(e)})

    score = (passed_count / max(len(test_cases), 1)) * 100.0
    return {
        "score": score,
        "passed_cases": passed_count,
        "total_cases": len(test_cases),
        "results": results
    }


async def _llm_mock_evaluation(language: str, code: str, test_cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Use LLM to statically analyze if the code would pass the test cases."""
    try:
        from langchain_groq import ChatGroq
        from pydantic import BaseModel
        
        class MockEval(BaseModel):
            passed_cases: int
            feedback: str

        llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0, groq_api_key=settings.GROQ_API_KEY)
        
        tc_str = ""
        for i, tc in enumerate(test_cases):
            tc_str += f"Case {i+1}: Input: {tc.get('input')} -> Expected: {tc.get('expected_output')}\n"
            
        prompt = (
            f"You are a code evaluator. Read this {language} code and determine how many of the following "
            f"test cases it would pass if executed. Be strict about syntax and logic errors.\n\n"
            f"CODE:\n{code}\n\n"
            f"TEST CASES:\n{tc_str}\n\n"
            f"Total cases: {len(test_cases)}. Return the integer number of passed cases and brief feedback."
        )
        
        res = llm.with_structured_output(MockEval).invoke(prompt)
        passed = min(res.passed_cases, len(test_cases))
        score = (passed / max(len(test_cases), 1)) * 100.0
        
        # Mock the results array
        results = []
        for i, tc in enumerate(test_cases):
            results.append({
                "case_index": i,
                "passed": i < passed,
                "output": tc.get("expected_output") if i < passed else "Logic Error",
                "expected": tc.get("expected_output") if not tc.get("hidden") else "Hidden",
                "feedback": res.feedback if i == 0 else ""
            })
            
        return {
            "score": score,
            "passed_cases": passed,
            "total_cases": len(test_cases),
            "results": results,
            "mocked_by_llm": True
        }
    except Exception as e:
        logger.error(f"[CodeRunner] LLM mock eval failed: {e}")
        return {"score": 0.0, "passed_cases": 0, "total_cases": len(test_cases), "results": []}
