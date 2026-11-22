import io
import json
import logging
import os
import re
import httpx
from concurrent.futures import ThreadPoolExecutor
import uuid

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, abort, send_from_directory, Response
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from sqlalchemy import or_, func
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet

from . import db, limiter
from .models import Job, Application, CandidateProfile, Company, CompanyMember, Notification, SavedJob, Message, MeetingRoom, MeetingProposal, User, Feedback, JOB_CATEGORIES, JOB_LOCATIONS, COUNTRIES
from .matching import keyword_set, overlap_score, NOTIFY_SCORE_THRESHOLD, NOTIFY_MAX_RECIPIENTS
from email_utils import send_branded_email, external_url
from video_storage import (
    get_signed_video_url, delete_interview_videos,
    create_interview_answer_upload_url, download_interview_answer_to_file,
)

from ai_services import (
    extract_text_from_file,
    compare_resume_to_job,
    run_interview_turn,
    transcribe_audio,
    extract_audio_for_transcription,
    audio_file_extension,
    AudioTooLargeError,
    synthesize_speech,
    generate_resume_from_profile,
    suggest_jobs_for_profile,
    find_similar_jobs,
    generate_interview_coaching,
    generate_skills_roadmap,
    analyze_ai_likelihood,
    generate_interview_question_preview,
)

candidate = Blueprint('candidate', __name__)

logger = logging.getLogger(__name__)

SUGGESTION_JOB_POOL = 40

AUDIO_BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio", "interviews")


def _audio_dir_for_application(application_id):
    path = os.path.join(AUDIO_BASE_DIR, str(application_id))
    os.makedirs(path, exist_ok=True)
    return path


def _notify_employers_of_open_to_work(profile):
    """Cheap keyword-match nudge to employers whose open jobs overlap a
    candidate who just opted into the talent pool - mirrors
    employer.notify_candidates_of_new_job, same reasoning: no real AI call
    per profile save."""
    candidate_words = keyword_set(profile.skills, profile.target_roles, profile.headline)
    if not candidate_words:
        return

    from sqlalchemy.orm import joinedload
    jobs = (
        Job.query.filter_by(status='open')
        .options(joinedload(Job.company))
        .limit(300)
        .all()
    )

    # Keep only the best-matching job per company, so a company with many
    # open roles doesn't get notified once per role.
    scored_by_company = {}
    for job in jobs:
        owner = job.company.owner_user_id if job.company else None
        if not owner:
            continue
        job_words = keyword_set(job.title, job.category, (job.description_text or '')[:500])
        score = overlap_score(candidate_words, job_words)
        if score < NOTIFY_SCORE_THRESHOLD:
            continue
        best = scored_by_company.get(job.company_id)
        if not best or score > best[0]:
            scored_by_company[job.company_id] = (score, job, owner)

    ranked = sorted(scored_by_company.values(), key=lambda x: x[0], reverse=True)
    for _, job, owner_id in ranked[:NOTIFY_MAX_RECIPIENTS]:
        owner = User.query.get(owner_id)
        if not owner or not owner.notifications_enabled:
            continue
        db.session.add(Notification(
            user_id=owner_id,
            message=f"A candidate who fits {job.title} just joined the talent pool.",
            link=url_for('employer.talent_pool'),
        ))


def _company_recipients(company):
    """Owner plus every team member of a company - used for notifications that
    matter to whoever is actually handling hiring day-to-day, not just the
    account that originally signed up."""
    recipients = []
    owner = User.query.get(company.owner_user_id)
    if owner:
        recipients.append(owner)
    member_ids = [m.user_id for m in CompanyMember.query.filter_by(company_id=company.id).all()]
    if member_ids:
        recipients.extend(User.query.filter(User.id.in_(member_ids)).all())
    return recipients


def _can_access_application_audio(application):
    if current_user.id == application.candidate_user_id:
        return True
    if current_user.role == 'employer':
        job = Job.query.get(application.job_id)
        if job:
            owns = Company.query.filter_by(owner_user_id=current_user.id, id=job.company_id).first()
            member = CompanyMember.query.filter_by(user_id=current_user.id, company_id=job.company_id).first()
            if owns or member:
                return True
    return False


def _extract_score(result_text):
    for num in re.findall(r"\b(\d{1,3})\b", result_text):
        val = int(num)
        if 0 <= val <= 100:
            return val
    return 0




CHAT_SEARCH_STOPWORDS = {
    "a", "an", "the", "is", "are", "am", "be", "do", "does", "did", "you", "your",
    "have", "has", "any", "for", "in", "on", "at", "with", "and", "or", "to", "of",
    "i", "me", "my", "we", "us", "job", "jobs", "role", "roles", "position", "positions",
    "looking", "look", "find", "search", "want", "need", "that", "this", "match",
    "matches", "matching", "please", "hi", "hello", "hey", "can", "could", "would",
    "there", "here", "what", "which", "some", "get", "give", "show", "see",
}


def search_jobs_by_text(text, limit=5):
    """Cheap keyword search against open jobs, for surfacing relevant listings
    from free-text chat input (no AI call - just the same ilike pattern
    browse_jobs() above uses). Returns [] if nothing meaningful to search on."""
    words = re.findall(r"[a-zA-Z0-9+#]+", (text or "").lower())
    keywords = [w for w in words if len(w) > 2 and w not in CHAT_SEARCH_STOPWORDS]
    if not keywords:
        return []

    conditions = []
    for kw in keywords[:8]:
        pattern = f"%{kw}%"
        conditions.extend([
            Job.title.ilike(pattern),
            Job.description.ilike(pattern),
            Job.location.ilike(pattern),
            Job.category.ilike(pattern),
        ])

    return (
        Job.query.filter_by(status="open")
        .filter(or_(*conditions))
        .order_by(Job.created_at.desc())
        .limit(limit)
        .all()
    )


















































SIMILAR_JOB_POOL = 50























# ------------------------------------------------------------------ #
#  In-App Messaging (candidate side)
# ------------------------------------------------------------------ #





# ------------------------------------------------------------------ #
#  Account deletion (GDPR right to erasure)
# ------------------------------------------------------------------ #

from . import candidate_jobs as _candidate_jobs
from . import candidate_interviews as _candidate_interviews
from . import candidate_dashboard as _candidate_dashboard
from . import candidate_profile as _candidate_profile
from . import candidate_practice as _candidate_practice
from . import candidate_account as _candidate_account
