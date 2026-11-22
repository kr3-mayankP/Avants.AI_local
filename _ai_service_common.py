"""Shared AI service client and configuration."""

import io
import os
import logging
import re
from collections import Counter
import openai
from PyPDF2 import PdfReader
from docx import Document
from openai._exceptions import RateLimitError, APIConnectionError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config import Config

logger = logging.getLogger(__name__)
#client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
client = (
    openai.OpenAI(api_key=Config.OPENAI_API_KEY)
    if Config.OPENAI_API_KEY
    else None
)
openrouter_client = openai.OpenAI(
    api_key=Config.OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)
JOB_FIT_VERDICTS = ("Strong Yes", "Yes", "No", "Strong No")
JOB_FIT_VERDICT_SCORE = {"Strong Yes": 100, "Yes": 75, "No": 25, "Strong No": 0}
VERDICT_CRITERIA = (
    "Grade strictly - most candidates should NOT get 'Strong Yes,' and plenty should not get 'Yes' either. "
    "A real recruiter screen filters out the majority of applicants; treat this the same way, not as a "
    "formality on the way to a job offer.\n"
    "- Strong Yes: exceptional, specific, quantified answers across every area probed, with no real "
    "weaknesses surfaced. Rare - reserved for candidates a hiring manager would want to fast-track.\n"
    "- Yes: solid, mostly specific answers backed by real relevant experience, with only minor gaps. Would "
    "genuinely move forward to the next round.\n"
    "- No: vague, generic, unconvincing, or off-target answers; real gaps relative to the role; rambling "
    "instead of concrete specifics. This is where most candidates who don't clearly stand out belong.\n"
    "- Strong No: evasive, contradictory, clearly unqualified, or repeatedly unable to give a concrete answer "
    "when pushed.\n"
    "Confidence and articulateness alone are NOT enough for a Yes - the content must be specific and "
    "substantiated. When genuinely torn between two verdicts, choose the stricter one."
)
VERDICT_FORMAT = (
    "Verdict: <Strong Yes / Yes / No / Strong No>\n\n"
    "Why:\n"
    "+ <specific strength from the conversation>\n"
    "+ <another specific strength, if there genuinely is one>\n"
    "- <specific concern or gap from the conversation>\n"
    "- <another specific concern or gap, if there genuinely is one>\n"
    "(List every substantive strength and every substantive concern you actually observed - don't omit a "
    "real one just to fit a fixed count, and don't pad with trivial or repetitive points to hit one either. "
    "Typically 2-5 of each is honest for a normal-length interview. Be complete about both sides, not just "
    "enough to justify the verdict.)"
)
INTERVIEW_LENGTH_GUIDANCE = {
    "short": (
        "Keep this brief — aim for about 3-4 total exchanges. Cover background/motivation in 1 question, "
        "one hands-on experience deep-dive, and one weak-spot probe. Skip the behavioral question unless "
        "something concerning comes up that needs follow-up."
    ),
    "standard": (
        "A real recruiter screen for a role like this typically runs 5-8 questions across that structure, "
        "but use your own judgment of when you have enough to make a confident call, not a fixed count."
    ),
    "thorough": (
        "Go deeper than a typical screen — aim for roughly 8-12 exchanges. Spend more time on hands-on "
        "experience (3-4 deep-dives across different projects), ask more than one behavioral/situational "
        "question, and probe multiple potential weak spots relative to the role's requirements."
    ),
}
QUESTION_BANK_SIZE = {
    "short": 8,
    "standard": 12,
    "thorough": 15,
}
_ALLOWED_AUDIO_EXTENSIONS = {".webm", ".mp4", ".ogg", ".m4a", ".wav", ".mp3"}

__all__ = ['APIConnectionError', 'Config', 'Counter', 'Document', 'INTERVIEW_LENGTH_GUIDANCE', 'JOB_FIT_VERDICTS', 'JOB_FIT_VERDICT_SCORE', 'PdfReader', 'QUESTION_BANK_SIZE', 'RateLimitError', 'VERDICT_CRITERIA', 'VERDICT_FORMAT', '_ALLOWED_AUDIO_EXTENSIONS', 'client', 'io', 'logger', 'logging', 'openai', 'os', 're', 'retry', 'retry_if_exception_type', 'stop_after_attempt', 'wait_exponential', 'openrouter_client']
