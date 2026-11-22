# ----------------------------------------------------------------
# CHANGE BLOCK: 2026-11-22
# NEW FILE - active implementation
# ----------------------------------------------------------------
"""Employer dashboard and job management routes."""

import json
import logging
import os
from datetime import datetime, timedelta, timezone

from flask import (
    abort, current_app, flash, jsonify, redirect, render_template, request, url_for, Response,
)
from flask_login import current_user, login_required

from ai_services import (
    analyze_job_description, audio_file_extension, compare_resume_to_job,
    generate_employer_dashboard_answer, generate_interview_question_preview,
    transcribe_audio, generate_job_post_assistant,
)
from . import db, limiter
from .candidate import _extract_score
from .employer import (
    INTERVIEW_LENGTH_OPTIONS, employer, employer_required, get_owned_company,
    notify_candidates_of_new_job, _existing_interview_questions,
    _extract_description_text, _parse_interview_questions,
)
from .employer_billing import (
    overdue_fee_applications, send_overdue_fee_reminder,
)
from .models import (
    Application, CompanyMember, DEFAULT_CURRENCY, DeletedJob, Job, JobActivity,
    JOB_CATEGORIES, JOB_LOCATIONS, MeetingRoom, Message, Notification,
    SavedJob, SUPPORTED_CURRENCIES,
)

logger = logging.getLogger(__name__)


# Moved from employer.py: dashboard
@employer.route('/employer/dashboard')
@login_required
@employer_required
def dashboard():
    company = get_owned_company()
    jobs = Job.query.filter_by(company_id=company.id).order_by(Job.created_at.desc()).all()
    job_ids = [job.id for job in jobs]

    # --------------------------------------------------------------------------------
    # OLD DASHBOARD COUNTS - commented out for review.
    # applicant_counts = {job.id: Application.query.filter_by(job_id=job.id).count() for job in jobs}
    # hired_counts = {job.id: Application.query.filter_by(job_id=job.id, status='hired').count() for job in jobs}
    # total_applicants = sum(applicant_counts.values())
    # total_hired = sum(hired_counts.values())
    # open_jobs = sum(1 for job in jobs if job.status == 'open')
    # --------------------------------------------------------------------------------
    # Code: Load job counts with grouped database queries
    applicant_counts = {job.id: 0 for job in jobs}
    hired_counts = {job.id: 0 for job in jobs}

    if job_ids:
        applicant_rows = (
            db.session.query(Application.job_id, db.func.count(Application.id))
            .filter(Application.job_id.in_(job_ids))
            .group_by(Application.job_id)
            .all()
        )
        hired_rows = (
            db.session.query(Application.job_id, db.func.count(Application.id))
            .filter(Application.job_id.in_(job_ids), Application.status == 'hired')
            .group_by(Application.job_id)
            .all()
        )
        applicant_counts.update(dict(applicant_rows))
        hired_counts.update(dict(hired_rows))

    # Code: Calculate the live dashboard summary
    total_applicants = sum(applicant_counts.values())
    total_hired = sum(hired_counts.values())
    open_jobs = sum(1 for j in jobs if j.status == 'open')

    members = CompanyMember.query.filter_by(company_id=company.id).all()
    owner_is_current = company.owner_user_id == current_user.id
    now = datetime.now(timezone.utc)
    last_30_days = now - timedelta(days=30)
    last_7_days = now - timedelta(days=7)

    recent_applications = []
    recent_rooms = []
    recent_messages = []
    application_dates = []
    top_matches = []
    interview_application_ids = set()
    scheduled_interviews = 0
    shortlist_count = 0
    new_applications = 0
    unread_employer_messages = 0
    dashboard_notifications = []

    if job_ids:
        # Code: Load recent applications, interviews, messages, and candidate matches
        recent_applications = (
            Application.query
            .filter(Application.job_id.in_(job_ids))
            .order_by(Application.created_at.desc())
            .limit(8)
            .all()
        )
        application_dates = (
            db.session.query(Application.created_at)
            .filter(
                Application.job_id.in_(job_ids),
                Application.created_at >= last_30_days,
            )
            .all()
        )
        shortlist_count = Application.query.filter(
            Application.job_id.in_(job_ids),
            db.or_(
                Application.status == 'interviewing',
                Application.interview_verdict.in_(('Strong Yes', 'Yes')),
            ),
        ).count()
        new_applications = Application.query.filter(
            Application.job_id.in_(job_ids),
            Application.created_at >= last_7_days,
        ).count()
        room_application_ids = {
            row[0] for row in (
                db.session.query(db.func.distinct(MeetingRoom.application_id))
                .join(Application, Application.id == MeetingRoom.application_id)
                .filter(Application.job_id.in_(job_ids))
                .all()
            )
        }
        completed_interview_ids = {
            row[0] for row in (
                db.session.query(Application.id)
                .filter(
                    Application.job_id.in_(job_ids),
                    Application.interview_transcript.isnot(None),
                    Application.interview_transcript != '',
                )
                .all()
            )
        }
        scheduled_interviews = (
            MeetingRoom.query
            .join(Application, Application.id == MeetingRoom.application_id)
            .filter(Application.job_id.in_(job_ids))
            .count()
        )
        interview_application_ids = room_application_ids | completed_interview_ids
        unread_employer_messages = (
            Message.query
            .join(Application, Application.id == Message.application_id)
            .filter(
                Application.job_id.in_(job_ids),
                Message.read.is_(False),
                Message.sender_user_id != current_user.id,
            )
            .count()
        )
        recent_rooms = (
            MeetingRoom.query
            .join(Application, Application.id == MeetingRoom.application_id)
            .filter(Application.job_id.in_(job_ids))
            .order_by(MeetingRoom.created_at.desc())
            .limit(5)
            .all()
        )
        recent_messages = (
            Message.query
            .join(Application, Application.id == Message.application_id)
            .filter(Application.job_id.in_(job_ids))
            .order_by(Message.created_at.desc())
            .limit(5)
            .all()
        )
        top_matches = (
            Application.query
            .filter(
                Application.job_id.in_(job_ids),
                Application.match_score.isnot(None),
                Application.withdrawn.is_(False),
                Application.status.in_(('applied', 'interviewing')),
            )
            .order_by(Application.match_score.desc(), Application.created_at.desc())
            .limit(5)
            .all()
        )

    dashboard_notifications = (
        Notification.query
        .filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(5)
        .all()
    )
    unread_notifications = Notification.query.filter_by(
        user_id=current_user.id,
        read=False,
    ).count()

    interview_count = len(interview_application_ids)

    chart_buckets = [0, 0, 0, 0, 0]
    first_chart_day = (now - timedelta(days=29)).date()
    for row in application_dates:
        created_at = row[0]
        if created_at:
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            days_ago = (created_at.date() - first_chart_day).days
            bucket_index = min(max(days_ago * 5 // 30, 0), 4)
            chart_buckets[bucket_index] += 1
    chart_max = max(chart_buckets) or 1
    hiring_chart = [
        {
            "label": (first_chart_day + timedelta(days=index * 6)).strftime("%b %d"),
            "count": count,
            "height": max(8, round(count / chart_max * 100)) if count else 4,
        }
        for index, count in enumerate(chart_buckets)
    ]

    def _active_job_sort_key(job):
        created_at = job.created_at or datetime.min.replace(tzinfo=timezone.utc)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return applicant_counts.get(job.id, 0), created_at

    active_jobs = sorted(
        (job for job in jobs if job.status == 'open'),
        key=_active_job_sort_key,
        reverse=True,
    )

    activity_items = []
    for application in recent_applications:
        candidate = application.candidate
        if company.blind_mode_enabled:
            candidate_name = "Candidate"
        else:
            candidate_name = (candidate.full_name or candidate.email) if candidate else "Candidate"
        activity_items.append({
            "kind": "application",
            "title": "New application received",
            "detail": f"{candidate_name} · {application.job.title}",
            "created_at": application.created_at,
            "url": url_for('employer.applicants', job_id=application.job_id),
            "icon": "fa-user-plus",
        })

    for room in recent_rooms:
        application = room.application
        candidate = application.candidate if application else None
        candidate_name = (
            "Candidate" if company.blind_mode_enabled
            else (candidate.full_name or candidate.email) if candidate
            else "Candidate"
        )
        activity_items.append({
            "kind": "interview",
            "title": "Interview scheduled",
            "detail": f"{candidate_name} · {application.job.title}",
            "created_at": room.created_at,
            "url": url_for('employer.employer_meetings'),
            "icon": "fa-calendar-check",
        })

    for message in recent_messages:
        application = message.application
        sender = message.sender
        sender_name = (
            "Candidate" if company.blind_mode_enabled and sender and sender.id != current_user.id
            else (sender.full_name or sender.email) if sender
            else "Team member"
        )
        activity_items.append({
            "kind": "message",
            "title": "New message" if sender and sender.id != current_user.id else "Message sent",
            "detail": f"{sender_name} · {application.job.title}" if application else sender_name,
            "created_at": message.created_at,
            "url": url_for('employer.applicants', job_id=application.job_id) if application else url_for('employer.dashboard'),
            "icon": "fa-message",
        })

    def _activity_time(item):
        created_at = item.get("created_at")
        if created_at is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        if created_at.tzinfo is None:
            return created_at.replace(tzinfo=timezone.utc)
        return created_at

    recent_activity = sorted(activity_items, key=_activity_time, reverse=True)[:6]

    sorted_matches = sorted(
        top_matches,
        key=lambda application: application.match_score or 0,
        reverse=True,
    )
    dashboard_candidates = []
    for index, application in enumerate(sorted_matches, start=1):
        profile = getattr(application.candidate, "candidate_profile", None) if application.candidate else None
        dashboard_candidates.append({
            "name": (
                f"Candidate #{index}" if company.blind_mode_enabled
                else (application.candidate.full_name or "Candidate") if application.candidate
                else "Candidate"
            ),
            "headline": profile.headline if profile else None,
            "experience": profile.years_experience if profile else None,
            "skills": [skill.strip() for skill in (profile.skills or "").split(",") if skill.strip()][:3] if profile else [],
            "score": application.match_score or 0,
            "job_title": application.job.title,
            "url": url_for('employer.applicants', job_id=application.job_id),
        })

    average_match_score = round(
        sum(app.match_score for app in top_matches if app.match_score is not None) / len(top_matches)
    ) if top_matches else None
    ai_insights = []
    if not open_jobs:
        ai_insights.append({
            "title": "Start with an open role",
            "detail": "Publish a job to begin receiving applications and matching candidates.",
            "icon": "fa-lightbulb",
            "url": url_for('employer.post_job'),
        })
    elif any(applicant_counts.get(job.id, 0) == 0 for job in jobs if job.status == 'open'):
        ai_insights.append({
            "title": "Some jobs have no applicants yet",
            "detail": "Review the job description and requirements to make the role easier to discover.",
            "icon": "fa-bullseye",
            "url": url_for('employer.dashboard'),
        })
    if shortlist_count:
        ai_insights.append({
            "title": f"{shortlist_count} candidates are moving forward",
            "detail": "Review shortlisted applicants and schedule the next interview.",
            "icon": "fa-arrow-trend-up",
            "url": url_for('employer.dashboard'),
        })
    if average_match_score is not None:
        ai_insights.append({
            "title": f"Average top match score: {average_match_score}%",
            "detail": "Compare candidate match explanations before making a hiring decision.",
            "icon": "fa-chart-line",
            "url": url_for('employer.talent_pool'),
        })
    if not ai_insights:
        ai_insights.append({
            "title": "Your hiring overview is ready",
            "detail": "New applications and interviews will appear here as candidates move through your pipeline.",
            "icon": "fa-circle-info",
            "url": url_for('employer.analytics'),
        })

    overdue_apps = overdue_fee_applications(company)
    notification_badge_count = unread_notifications + len(overdue_apps)
    overdue_fees = []
    for app in overdue_apps:
        send_overdue_fee_reminder(app, app.job, company, current_user)
        basis_amount, fee_percent = _placement_fee_basis(app, app.job)
        overdue_fees.append({
            "application": app,
            "job": app.job,
            "candidate": app.candidate,
            "days_overdue": (now - app.hire_confirmed_at.replace(tzinfo=timezone.utc)).days,
            "fee_amount": int(basis_amount * fee_percent / 100) if basis_amount else None,
        })
    if overdue_apps:
        db.session.commit()

    return render_template(
        "employer_dashboard.html",
        company=company,
        jobs=jobs,
        today_label=now.strftime("%A, %B %d").replace(" 0", " "),
        applicant_counts=applicant_counts,
        hired_counts=hired_counts,
        total_applicants=total_applicants,
        total_hired=total_hired,
        open_jobs=open_jobs,
        new_applications=new_applications,
        shortlist_count=shortlist_count,
        interview_count=interview_count,
        unread_employer_messages=unread_employer_messages,
        dashboard_notifications=dashboard_notifications,
        notification_badge_count=notification_badge_count,
        scheduled_interviews=scheduled_interviews,
        hiring_chart=hiring_chart,
        active_jobs=active_jobs,
        recent_activity=recent_activity,
        dashboard_candidates=dashboard_candidates,
        ai_insights=ai_insights,
        members=members,
        is_owner=owner_is_current,
        overdue_fees=overdue_fees,
    )


# --------------------------------------------------------------------------------
# Recruiter dashboard AI assistant
# --------------------------------------------------------------------------------

@employer.route('/employer/dashboard/assistant', methods=['POST'])
@login_required
@employer_required
@limiter.limit("10 per hour")
def dashboard_assistant():
    company = get_owned_company()
    payload = request.get_json(silent=True) or {}
    message = payload.get("message")
    question = message.strip() if isinstance(message, str) else ""
    if not question:
        return jsonify({"error": "Type a question first."}), 400
    if len(question) > 1000:
        return jsonify({"error": "Please keep your question under 1000 characters."}), 400

    jobs = Job.query.filter_by(company_id=company.id, status='open').order_by(Job.created_at.desc()).limit(10).all()
    job_ids = [job.id for job in jobs]
    applications_count = (
        Application.query.filter(Application.job_id.in_(job_ids)).count()
        if job_ids else 0
    )
    hires_count = (
        Application.query.filter(
            Application.job_id.in_(job_ids),
            Application.status == 'hired',
        ).count()
        if job_ids else 0
    )
    context = {
        "company": company.name,
        "open_jobs": [
            {"title": job.title, "category": job.category, "location": job.location}
            for job in jobs
        ],
        "applications_for_open_jobs": applications_count,
        "hires_for_open_jobs": hires_count,
    }
    try:
        answer = generate_employer_dashboard_answer(question, context)
    except Exception:
        logger.exception("Recruiter dashboard assistant failed")
        return jsonify({"error": "The assistant is unavailable right now. Please try again shortly."}), 503
    return jsonify({"reply": answer})


# Moved from employer.py: post_job
@employer.route('/employer/jobs/new', methods=['GET', 'POST'])
@login_required
@employer_required
def post_job():
    company = get_owned_company()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        work_type = request.form.get('work_type', 'Remote (Worldwide)').strip()
        city = request.form.get('location_city', '').strip()
        if work_type in ('Hybrid', 'On-site') and city:
            location = f"{work_type} - {city}"
        else:
            location = work_type
        employment_type = request.form.get('employment_type', '').strip()
        category = request.form.get('category', 'Other')
        if category not in JOB_CATEGORIES:
            category = 'Other'
        interview_length = request.form.get('interview_length', 'standard')
        if interview_length not in INTERVIEW_LENGTH_OPTIONS:
            interview_length = 'standard'
        camera_required = request.form.get('camera_required') == '1'
        interview_focus = request.form.get('interview_focus', '').strip()
        interview_questions = _parse_interview_questions(request.form.get('interview_questions', ''))

        if not title or not description:
            flash("Title and description are required.", "error")
            return render_template(
                "post_job.html", categories=JOB_CATEGORIES, locations=JOB_LOCATIONS,
                interview_lengths=INTERVIEW_LENGTH_OPTIONS, currencies=SUPPORTED_CURRENCIES,
                interview_questions=json.loads(interview_questions) if interview_questions else [],
            )

        salary_raw = request.form.get('salary_usd', '').strip()
        salary_usd = int(salary_raw) if salary_raw.isdigit() else None
        salary_max_raw = request.form.get('salary_max_usd', '').strip()
        salary_max_usd = int(salary_max_raw) if salary_max_raw.isdigit() else None
        pay_type = request.form.get('pay_type', 'yearly')
        if pay_type not in ('yearly', 'hourly', 'monthly', 'stipend', 'contract'):
            pay_type = 'yearly'
        salary_currency = request.form.get('salary_currency', DEFAULT_CURRENCY)
        if salary_currency not in SUPPORTED_CURRENCIES:
            salary_currency = DEFAULT_CURRENCY
        save_as_draft = request.form.get('save_as_draft') == '1'

        if not save_as_draft and not salary_usd:
            flash("An estimated salary is required to post a job - candidates need to see it before applying.", "error")
            return render_template(
                "post_job.html", categories=JOB_CATEGORIES, locations=JOB_LOCATIONS,
                interview_lengths=INTERVIEW_LENGTH_OPTIONS, currencies=SUPPORTED_CURRENCIES,
                interview_questions=json.loads(interview_questions) if interview_questions else [],
            )

        job = Job(
            company_id=company.id,
            title=title,
            description=description,
            location=location,
            employment_type=employment_type,
            category=category,
            interview_length=interview_length,
            camera_required=camera_required,
            interview_focus=interview_focus or None,
            interview_questions=interview_questions,
            salary_usd=salary_usd,
            salary_max_usd=salary_max_usd,
            pay_type=pay_type,
            salary_currency=salary_currency,
            status='draft' if save_as_draft else 'open',
        )
        db.session.add(job)
        db.session.commit()
        if save_as_draft:
            flash("Job saved as draft.", "success")
        else:
            notify_candidates_of_new_job(job, company)
            db.session.commit()
            flash("Job posted successfully!", "success")
        return redirect(url_for('employer.manage_jobs'))

    return render_template(
        "post_job.html",
        categories=JOB_CATEGORIES,
        locations=JOB_LOCATIONS,
        interview_lengths=INTERVIEW_LENGTH_OPTIONS,
        currencies=SUPPORTED_CURRENCIES,
        interview_questions=[],
    )


# Moved from employer.py: edit_job
@employer.route('/employer/jobs/<int:job_id>/edit', methods=['GET', 'POST'])
@login_required
@employer_required
def edit_job(job_id):
    company = get_owned_company()
    job = Job.query.get_or_404(job_id)
    if job.company_id != company.id:
        abort(403)

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category = request.form.get('category', 'Other')
        if category not in JOB_CATEGORIES:
            category = 'Other'
        interview_length = request.form.get('interview_length', 'standard')
        if interview_length not in INTERVIEW_LENGTH_OPTIONS:
            interview_length = 'standard'

        if not title or not description:
            flash("Title and description are required.", "error")
            return render_template(
                "post_job.html", job=job, categories=JOB_CATEGORIES, locations=JOB_LOCATIONS,
                interview_lengths=INTERVIEW_LENGTH_OPTIONS, currencies=SUPPORTED_CURRENCIES,
                interview_questions=_existing_interview_questions(job),
            )

        salary_raw = request.form.get('salary_usd', '').strip()
        salary_max_raw = request.form.get('salary_max_usd', '').strip()
        save_as_draft = request.form.get('save_as_draft') == '1'
        pay_type = request.form.get('pay_type', 'yearly')
        if pay_type not in ('yearly', 'hourly', 'monthly', 'stipend', 'contract'):
            pay_type = 'yearly'
        salary_currency = request.form.get('salary_currency', DEFAULT_CURRENCY)
        if salary_currency not in SUPPORTED_CURRENCIES:
            salary_currency = DEFAULT_CURRENCY

        if not save_as_draft and not salary_raw.isdigit():
            flash("An estimated salary is required to post a job - candidates need to see it before applying.", "error")
            return render_template(
                "post_job.html", job=job, categories=JOB_CATEGORIES, locations=JOB_LOCATIONS,
                interview_lengths=INTERVIEW_LENGTH_OPTIONS, currencies=SUPPORTED_CURRENCIES,
                interview_questions=_existing_interview_questions(job),
            )

        was_open = job.status == 'open'
        _edit_work_type = request.form.get('work_type', 'Remote (Worldwide)').strip()
        _edit_city = request.form.get('location_city', '').strip()
        job.title = title
        job.description = description
        job.location = f"{_edit_work_type} - {_edit_city}" if _edit_work_type in ('Hybrid', 'On-site') and _edit_city else _edit_work_type
        job.employment_type = request.form.get('employment_type', '').strip()
        job.category = category
        job.interview_length = interview_length
        job.camera_required = request.form.get('camera_required') == '1'
        job.interview_focus = request.form.get('interview_focus', '').strip() or None
        job.interview_questions = _parse_interview_questions(request.form.get('interview_questions', ''))
        if save_as_draft:
            job.status = 'draft'
        else:
            submitted_status = request.form.get('status', 'open')
            job.status = submitted_status if submitted_status in ('open', 'closed') else 'open'
        job.salary_usd = int(salary_raw) if salary_raw.isdigit() else None
        job.salary_max_usd = int(salary_max_raw) if salary_max_raw.isdigit() else None
        job.pay_type = pay_type
        job.salary_currency = salary_currency
        db.session.commit()
        db.session.add(JobActivity(job_id=job.id, company_id=company.id, actor_user_id=current_user.id, action='job_edit', detail='Job details updated.'))
        db.session.commit()
        if not was_open and job.status == 'open':
            notify_candidates_of_new_job(job, company)
            db.session.commit()
        flash("Draft saved." if save_as_draft else "Job updated!", "success")
        return redirect(url_for('employer.dashboard'))

    return render_template(
        "post_job.html", job=job, categories=JOB_CATEGORIES, locations=JOB_LOCATIONS,
        interview_lengths=INTERVIEW_LENGTH_OPTIONS, currencies=SUPPORTED_CURRENCIES,
        interview_questions=_existing_interview_questions(job),
    )


@employer.route('/employer/jobs')
@login_required
@employer_required
def manage_jobs():
    company = get_owned_company()
    jobs = Job.query.filter_by(company_id=company.id).order_by(Job.created_at.desc()).all()

    status_filter = (request.args.get('status') or 'all').strip().lower()
    search = (request.args.get('q') or '').strip().lower()
    location_filter = (request.args.get('location') or '').strip().lower()
    department_filter = (request.args.get('department') or '').strip().lower()
    employment_filter = (request.args.get('employment') or '').strip().lower()
    owner_filter = (request.args.get('owner') or '').strip().lower()
    date_filter = (request.args.get('date') or '').strip().lower()

    counts = {'all': len(jobs), 'active': 0, 'draft': 0, 'paused': 0, 'closed': 0}
    for job in jobs:
        key = 'active' if job.status == 'open' else job.status
        if key in counts:
            counts[key] += 1

    now = datetime.now(timezone.utc)
    application_counts = {}
    filtered = []
    for job in jobs:
        application_counts[job.id] = Application.query.filter_by(job_id=job.id).count()
        job_status = 'active' if job.status == 'open' else job.status
        if status_filter != 'all' and job_status != status_filter:
            continue
        if search and search not in f"{job.title} {job.id}".lower():
            continue
        if location_filter and location_filter not in (job.location or '').lower():
            continue
        if department_filter and department_filter not in (job.category or '').lower():
            continue
        if employment_filter and employment_filter not in (job.employment_type or '').lower():
            continue
        if owner_filter == 'me' and job.company_id != company.id:
            continue
        if date_filter:
            created = job.created_at
            if created:
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                age_days = (now - created).days
                if date_filter == 'today' and age_days != 0:
                    continue
                if date_filter == '7days' and age_days > 7:
                    continue
                if date_filter == '30days' and age_days > 30:
                    continue
        filtered.append(job)

    locations = sorted({job.location for job in jobs if job.location})
    return render_template(
        'manage_jobs.html',
        jobs=filtered,
        application_counts=application_counts,
        counts=counts,
        status_filter=status_filter,
        search=search,
        locations=locations,
        departments=sorted({job.category for job in jobs if job.category}),
        employment_types=sorted({job.employment_type for job in jobs if job.employment_type}),
    )


@employer.route('/employer/jobs/<int:job_id>/pause', methods=['POST'])
@login_required
@employer_required
def pause_job(job_id):
    company = get_owned_company()
    job = Job.query.get_or_404(job_id)
    if job.company_id != company.id:
        abort(403)
    job.status = 'paused'
    db.session.commit()
    db.session.add(JobActivity(job_id=job.id, company_id=company.id, actor_user_id=current_user.id, action='job_status', detail='Job paused.'))
    db.session.commit()
    flash("Job paused.", "success")
    return redirect(url_for('employer.manage_jobs'))


@employer.route('/employer/jobs/<int:job_id>/activate', methods=['POST'])
@login_required
@employer_required
def activate_job(job_id):
    company = get_owned_company()
    job = Job.query.get_or_404(job_id)
    if job.company_id != company.id:
        abort(403)
    if not job.salary_usd:
        flash("Add an estimated salary before activating this job.", "error")
        return redirect(url_for('employer.edit_job', job_id=job.id))
    job.status = 'open'
    db.session.commit()
    db.session.add(JobActivity(job_id=job.id, company_id=company.id, actor_user_id=current_user.id, action='job_status', detail='Job activated.'))
    db.session.commit()
    flash("Job activated.", "success")
    return redirect(url_for('employer.manage_jobs'))


@employer.route('/employer/jobs/<int:job_id>/duplicate', methods=['POST'])
@login_required
@employer_required
def duplicate_job(job_id):
    company = get_owned_company()
    source = Job.query.get_or_404(job_id)
    if source.company_id != company.id:
        abort(403)
    duplicate = Job(
        company_id=company.id,
        title=f"{source.title} (Copy)",
        description=source.description,
        location=source.location,
        employment_type=source.employment_type,
        category=source.category,
        status='draft',
        interview_length=source.interview_length,
        interview_focus=source.interview_focus,
        interview_questions=source.interview_questions,
        camera_required=source.camera_required,
        salary_usd=source.salary_usd,
        salary_max_usd=source.salary_max_usd,
        pay_type=source.pay_type,
        salary_currency=source.salary_currency,
    )
    db.session.add(duplicate)
    db.session.commit()
    flash("Draft duplicated. Review it before publishing.", "success")
    return redirect(url_for('employer.edit_job', job_id=duplicate.id))


@employer.route('/employer/jobs/bulk-close', methods=['POST'])
@login_required
@employer_required
def bulk_close_jobs():
    company = get_owned_company()
    ids = request.form.getlist('job_ids')
    jobs = Job.query.filter(Job.company_id == company.id, Job.id.in_([int(i) for i in ids if i.isdigit()])).all()
    for job in jobs:
        if job.status in ('open', 'paused'):
            job.status = 'closed'
    db.session.commit()
    flash(f"{len(jobs)} job{'s' if len(jobs) != 1 else ''} closed.", "success")
    return redirect(url_for('employer.manage_jobs'))


@employer.route('/employer/jobs/export', methods=['POST'])
@login_required
@employer_required
def export_jobs():
    company = get_owned_company()
    ids = request.form.getlist('job_ids')
    query = Job.query.filter_by(company_id=company.id)
    if ids:
        query = query.filter(Job.id.in_([int(i) for i in ids if i.isdigit()]))
    jobs = query.order_by(Job.created_at.desc()).all()
    lines = ["ID,Title,Location,Employment,Status,Applications,Posted,Updated"]
    for job in jobs:
        count = Application.query.filter_by(job_id=job.id).count()
        row = [job.id, job.title, job.location or '', job.employment_type or '', job.status, count, job.created_at, job.created_at]
        lines.append(",".join(f'"{str(value).replace(chr(34), chr(34)*2)}"' for value in row))
    csv_text = "\n".join(lines)
    return Response(csv_text, mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=jobs.csv'})


# Moved from employer.py: publish_job
@employer.route('/employer/jobs/<int:job_id>/publish', methods=['POST'])
@login_required
@employer_required
def publish_job(job_id):
    company = get_owned_company()
    job = Job.query.get_or_404(job_id)
    if job.company_id != company.id:
        abort(403)
    if not job.salary_usd:
        flash("Add an estimated salary before publishing - candidates need to see it before applying.", "error")
        return redirect(url_for('employer.edit_job', job_id=job.id))
    job.status = 'open'
    db.session.commit()
    db.session.add(JobActivity(job_id=job.id, company_id=company.id, actor_user_id=current_user.id, action='job_status', detail='Job published.'))
    db.session.commit()
    notify_candidates_of_new_job(job, company)
    db.session.commit()
    flash("Job published successfully.", "success")
    return redirect(url_for('employer.manage_jobs'))


# Moved from employer.py: toggle_job_status
@employer.route('/employer/jobs/<int:job_id>/toggle-status', methods=['POST'])
@login_required
@employer_required
def toggle_job_status(job_id):
    """One-click close/reopen - the alternative to delete() when a job has
    applicants and can't be permanently removed."""
    company = get_owned_company()
    job = Job.query.get_or_404(job_id)
    if job.company_id != company.id:
        abort(403)
    if job.status not in ('open', 'closed', 'paused'):
        abort(400)
    job.status = 'closed' if job.status in ('open', 'paused') else 'open'
    db.session.commit()
    db.session.add(JobActivity(job_id=job.id, company_id=company.id, actor_user_id=current_user.id, action='job_status', detail=f"Job {'closed' if job.status == 'closed' else 'reopened'}."))
    db.session.commit()
    flash(f"Job {'closed' if job.status == 'closed' else 'reopened'}.", "success")
    return redirect(url_for('employer.manage_jobs'))


# Moved from employer.py: delete_job
@employer.route('/employer/jobs/<int:job_id>/delete', methods=['POST'])
@login_required
@employer_required
def delete_job(job_id):
    company = get_owned_company()
    job = Job.query.get_or_404(job_id)
    if job.company_id != company.id:
        abort(403)

    if Application.query.filter_by(job_id=job.id).count() > 0:
        flash("This job has applicants, so it can't be deleted - close it instead to stop new applications while keeping candidate history.", "error")
        return redirect(url_for('employer.manage_jobs'))

    db.session.add(DeletedJob(
        original_job_id=job.id,
        company_id=company.id,
        company_name=company.name,
        title=job.title,
        snapshot=json.dumps(job.to_snapshot_dict()),
        applicant_count=0,
        deleted_by_user_id=current_user.id,
        deleted_source='employer',
    ))
    SavedJob.query.filter_by(job_id=job.id).delete()
    db.session.delete(job)
    db.session.commit()
    flash("Job deleted. You can restore it from Deleted Jobs within 30 days.", "success")
    return redirect(url_for('employer.manage_jobs'))


# Moved from employer.py: deleted_jobs
@employer.route('/employer/deleted-jobs')
@login_required
@employer_required
def deleted_jobs():
    company = get_owned_company()
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    history = DeletedJob.query.filter(
        DeletedJob.company_id == company.id,
        DeletedJob.restored_job_id.is_(None),
        DeletedJob.created_at >= cutoff,
    ).order_by(DeletedJob.created_at.desc()).all()
    return render_template('deleted_jobs.html', history=history)


# Moved from employer.py: restore_job
@employer.route('/employer/deleted-jobs/<int:history_id>/restore', methods=['POST'])
@login_required
@employer_required
def restore_job(history_id):
    company = get_owned_company()
    entry = DeletedJob.query.get_or_404(history_id)
    if entry.company_id != company.id:
        abort(403)
    if entry.restored_job_id:
        flash("That job was already restored.", "error")
        return redirect(url_for('employer.deleted_jobs'))

    data = json.loads(entry.snapshot)
    job = Job(company_id=company.id, **data)
    db.session.add(job)
    db.session.flush()
    entry.restored_job_id = job.id
    db.session.commit()
    flash(f'"{job.title}" restored.', "success")
    return redirect(url_for('employer.manage_jobs'))


# Moved from employer.py: preview_interview_questions
@employer.route('/employer/preview-interview-questions', methods=['POST'])
@login_required
@employer_required
@limiter.limit("15 per hour")
def preview_interview_questions():
    data = request.get_json() or {}
    title = (data.get('title') or '').strip()
    description = _extract_description_text(data.get('description') or '')
    interview_length = data.get('interview_length', 'standard')
    interview_focus = (data.get('interview_focus') or '').strip()

    if not title or not description:
        return jsonify({"error": "Add a job title and description first."}), 400

    try:
        questions = generate_interview_question_preview(title, description, interview_length, interview_focus)
        return jsonify({"questions": questions})
    except Exception as e:
        logger.exception("preview-interview-questions failed")
        msg = str(e)
        if "api_key" in msg.lower() or "authentication" in msg.lower():
            return jsonify({"error": "OpenAI API key is missing or invalid. Check your environment config."}), 500
        if "rate" in msg.lower():
            return jsonify({"error": "Rate limit hit. Wait a moment and try again."}), 429
        return jsonify({"error": f"Failed to generate questions: {msg}"}), 500


# Moved from employer.py: transcribe_question
@employer.route('/employer/transcribe-question', methods=['POST'])
@login_required
@employer_required
@limiter.limit("20 per hour")
def transcribe_question():
    """Speech-to-text for an employer recording a custom interview question by voice."""
    audio = request.files.get('audio')
    if not audio or not audio.filename:
        return jsonify({"error": "No audio received."}), 400

    import tempfile
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=audio_file_extension(audio.filename), delete=False) as tmp:
            audio.save(tmp.name)
            tmp_path = tmp.name
        text = transcribe_audio(tmp_path)
    except Exception:
        logger.exception("transcribe-question failed")
        return jsonify({"error": "Couldn't transcribe that recording. Try again or type the question."}), 500
    finally:
        if tmp_path:
            os.unlink(tmp_path)

    if not text:
        return jsonify({"error": "Didn't catch any speech - try recording again."}), 400
    return jsonify({"text": text})


# Moved from employer.py: score_resume
@employer.route('/employer/jobs/<int:job_id>/score-resume', methods=['POST'])
@login_required
@employer_required
@limiter.limit("20 per hour")
def score_resume(job_id):
    """Score an externally-sourced resume (referral, LinkedIn candidate, etc.)
    against one of this employer's jobs - no application gets created, this
    is just a quick sourcing/screening check."""
    company = get_owned_company()
    job = Job.query.get_or_404(job_id)
    if job.company_id != company.id:
        abort(403)

    data = request.get_json() or {}
    resume_text = (data.get('resume_text') or '').strip()
    if not resume_text:
        return jsonify({"error": "Add resume content first."}), 400

    try:
        result = compare_resume_to_job(job.description_text, resume_text)
    except Exception:
        logger.exception("score-resume failed")
        return jsonify({"error": "Failed to score this resume. Please try again."}), 500

    score = _extract_score(result)
    return jsonify({"score": score, "explanation": result.replace('*', '')})


# Moved from employer.py: analyze_jd
@employer.route('/employer/jobs/analyze-jd', methods=['POST'])
@login_required
@employer_required
@limiter.limit("15 per hour")
def analyze_jd():
    data = request.get_json() or {}
    try:
        result = analyze_job_description(
            title=data.get('title', ''),
            about=data.get('about', ''),
            requirements=data.get('requirements', ''),
            preferred=data.get('preferred', ''),
            what_you_do=data.get('what_you_do', ''),
            contract_terms=data.get('contract_terms', ''),
            salary_provided=bool(data.get('salary_usd')),
            category=data.get('category', ''),
        )
        return jsonify(result)
    except Exception as e:
        print("JD analysis failed:", e)
        return jsonify({"error": "Analysis failed"}), 500


@employer.route('/employer/jobs/ai-assist', methods=['POST'])
@login_required
@employer_required
@limiter.limit("30 per hour")
def job_post_ai_assist():
    data = request.get_json(silent=True) or {}
    action = (data.get('action') or '').strip().lower()
    prompt = (data.get('prompt') or '').strip()
    current_job = data.get('current_job') or {}

    if action not in ('generate', 'improve', 'suggest_skills'):
        return jsonify({"error": "Choose a supported AI action."}), 400
    if action in ('generate', 'suggest_skills') and not prompt and not current_job:
        return jsonify({"error": "Describe the role or add a few details first."}), 400

    try:
        result = generate_job_post_assistant(action, prompt, current_job)
        return jsonify({"generated": result})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        logger.exception("job-post AI assistant failed")
        return jsonify({"error": "AI generation is temporarily unavailable. Please try again."}), 503
