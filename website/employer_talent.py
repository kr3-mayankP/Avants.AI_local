"""Employer talent discovery and analytics routes."""

from flask import jsonify, render_template, url_for
from flask_login import login_required
from sqlalchemy.orm import joinedload

from ai_services import suggest_candidates_for_jobs
from . import limiter
from .employer import TALENT_POOL_AI_LIMIT, employer, employer_required, get_owned_company
from .models import Application, CandidateProfile, Job


# Moved from employer.py: talent_pool
@employer.route('/employer/talent')
@login_required
@employer_required
def talent_pool():
    import re as _re
    company = get_owned_company()
    open_jobs = Job.query.filter_by(company_id=company.id, status='open').all()

    # Build keyword set from employer's open jobs - used for the "All Candidates"
    # browse tab, which stays a cheap heuristic rather than an AI call per view.
    job_corpus = ' '.join(
        f"{j.title} {j.category} {(j.description_text or '')[:300]}"
        for j in open_jobs
    ).lower()
    job_words = set(_re.findall(r'\b\w{3,}\b', job_corpus))

    # Eagerly load users to avoid N+1 queries
    from sqlalchemy.orm import joinedload
    profiles = (
        CandidateProfile.query
        .filter_by(open_to_work=True)
        .options(joinedload(CandidateProfile.user))
        .all()
    )

    def _score(prof):
        text = ' '.join(filter(None, [
            prof.skills, prof.target_roles, prof.headline
        ])).lower()
        words = set(_re.findall(r'\b\w{3,}\b', text))
        if not words or not job_words:
            return 0
        return round(len(words & job_words) / len(words) * 100)

    all_scored = sorted(
        [{"profile": p, "user": p.user, "score": _score(p)} for p in profiles if p.user],
        key=lambda x: x["score"],
        reverse=True,
    )

    return render_template(
        "talent_pool.html",
        all_scored=all_scored,
        company=company,
        open_jobs=open_jobs,
    )


# Moved from employer.py: suggested_candidates
@employer.route('/employer/talent/suggested')
@login_required
@employer_required
@limiter.limit("30 per hour")
def suggested_candidates():
    """AI-ranked candidates from the open-to-work pool that fit this employer's
    open roles - the mirror of candidate.suggested_jobs. Loaded async from
    talent_pool.html rather than computed on every page render, since it's a
    real OpenAI call."""
    company = get_owned_company()
    open_jobs = Job.query.filter_by(company_id=company.id, status='open').all()
    if not open_jobs:
        return jsonify({"suggestions": []})

    from sqlalchemy.orm import joinedload
    profiles = (
        CandidateProfile.query
        .filter_by(open_to_work=True)
        .options(joinedload(CandidateProfile.user))
        .limit(TALENT_POOL_AI_LIMIT)
        .all()
    )
    profiles = [p for p in profiles if p.user]
    if not profiles:
        return jsonify({"suggestions": []})

    jobs_payload = [
        {"id": j.id, "title": j.title, "category": j.category, "description": j.description_text}
        for j in open_jobs
    ]
    candidates_payload = [
        {
            "id": p.id,
            "headline": p.headline,
            "skills": p.skills,
            "target_roles": p.target_roles,
            "years_experience": p.years_experience,
        }
        for p in profiles
    ]

    try:
        ranked = suggest_candidates_for_jobs(jobs_payload, candidates_payload)
    except Exception:
        return jsonify({"error": "Failed to generate suggestions. Please try again."}), 500

    profiles_by_id = {p.id: p for p in profiles}
    suggestions = []
    for item in ranked[:12]:
        prof = profiles_by_id.get(item["candidate_id"])
        if not prof:
            continue
        user = prof.user
        suggestions.append({
            "user_id": user.id,
            #new change: return both name fields for suggested-candidate cards.
            "name": user.full_name or "Candidate",
            "headline": prof.headline or "",
            "availability": prof.availability or "",
            "work_preference": prof.work_preference or "",
            "location": prof.location or "",
            "years_experience": prof.years_experience or "",
            "skills": [s.strip() for s in (prof.skills or "").split(",") if s.strip()][:6],
            "score": item["score"],
            "reason": item["reason"],
            "url": url_for('candidate.public_profile', user_id=user.id),
        })

    return jsonify({"suggestions": suggestions})


# Moved from employer.py: analytics
@employer.route('/employer/analytics')
@login_required
@employer_required
def analytics():
    company = get_owned_company()
    jobs = Job.query.filter_by(company_id=company.id).all()
    job_ids = [j.id for j in jobs]

    if not job_ids:
        return render_template('employer_analytics.html', company=company, stats={}, top_jobs=[])

    all_apps = Application.query.filter(Application.job_id.in_(job_ids)).all()

    total = len(all_apps)
    interviewed = sum(1 for a in all_apps if a.interview_transcript)
    hired = sum(1 for a in all_apps if a.status == 'hired')
    rejected = sum(1 for a in all_apps if a.status == 'rejected')
    scores = [a.match_score for a in all_apps if a.match_score is not None]
    avg_score = round(sum(scores) / len(scores)) if scores else None
    interview_rate = round(interviewed / total * 100) if total else 0
    hire_rate = round(hired / total * 100) if total else 0

    # Per-job breakdown
    jobs_by_id = {j.id: j for j in jobs}
    job_counts = {}
    for a in all_apps:
        jid = a.job_id
        if jid not in job_counts:
            job_counts[jid] = {"title": jobs_by_id[jid].title, "total": 0, "interviewed": 0, "hired": 0}
        job_counts[jid]["total"] += 1
        if a.interview_transcript:
            job_counts[jid]["interviewed"] += 1
        if a.status == "hired":
            job_counts[jid]["hired"] += 1

    top_jobs = sorted(job_counts.values(), key=lambda x: x["total"], reverse=True)[:5]

    stats = {
        "total": total,
        "interviewed": interviewed,
        "hired": hired,
        "rejected": rejected,
        "avg_score": avg_score,
        "interview_rate": interview_rate,
        "hire_rate": hire_rate,
        "open_jobs": sum(1 for j in jobs if j.status == 'open'),
    }

    return render_template('employer_analytics.html', company=company, stats=stats, top_jobs=top_jobs)
