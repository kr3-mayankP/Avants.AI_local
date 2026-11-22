# ----------------------------------------------------------------
# CHANGE BLOCK: 2026-11-22
# NEW FILE - active implementation
# ----------------------------------------------------------------
"""Employer application review and hiring routes moved from employer.py."""

import json
import logging

import stripe
from flask import (
    abort, current_app, flash, jsonify, redirect, render_template, request,
    send_from_directory, url_for,
)
from flask_login import current_user, login_required
from sqlalchemy.sql import func

from ai_services import generate_rejection_feedback
from email_utils import external_url, send_branded_email
from . import db
from .employer import (
    STATUS_EMAIL_COPY,
    _VERDICT_SCORE,
    _hire_evidence_dir,
    _save_hire_evidence,
    compute_composite_score,
    employer,
    employer_required,
    get_owned_company,
    get_user_company,
    summarize_explanation,
)
from .models import Application, CandidateProfile, Feedback, Job, JobActivity, Notification

logger = logging.getLogger(__name__)

# Moved from manage-jobs: single-job detail workspace
@employer.route('/employer/jobs/<int:job_id>/detail')
@login_required
@employer_required
def job_detail(job_id):
    company = get_owned_company()
    job = Job.query.get_or_404(job_id)
    if job.company_id != company.id:
        abort(403)

    applications = Application.query.filter_by(job_id=job.id).all()
    ai_likelihoods = {
        app.id: json.loads(app.ai_likelihood) if app.ai_likelihood else None
        for app in applications
    }
    composite_scores = {
        app.id: compute_composite_score(app, ai_likelihoods.get(app.id))
        for app in applications
    }
    applications.sort(key=lambda app: composite_scores[app.id], reverse=True)

    blind_labels = {}
    if company.blind_mode_enabled:
        for index, app in enumerate(applications, 1):
            blind_labels[app.id] = f"Candidate #{index}"

    application_rows = []
    for app in applications:
        candidate_name = blind_labels.get(app.id) if company.blind_mode_enabled else (
            app.candidate.full_name or f"{app.candidate.first_name or ''} {app.candidate.last_name or ''}".strip() or app.candidate.email
        )
        application_rows.append({
            "application": app,
            "candidate_name": candidate_name,
            "score": composite_scores[app.id],
            "match_score": app.match_score,
            "explanation": summarize_explanation(app.match_explanation),
            "profile": CandidateProfile.query.filter_by(user_id=app.candidate_user_id).first(),
        })

    shortlisted = [row for row in application_rows if row["application"].status == "interviewing" or (row["match_score"] or 0) >= 70]
    interviewed = [row for row in application_rows if row["application"].interview_transcript or row["application"].status == "interviewing"]
    hired = [row for row in application_rows if row["application"].status == "hired"]
    offers = sum(1 for row in application_rows if row["application"].status == "hired")

    activities = JobActivity.query.filter_by(job_id=job.id).order_by(JobActivity.created_at.desc()).all()
    fallback_activity = []
    for app in applications:
        fallback_activity.append({
            "created_at": app.created_at,
            "action": "application",
            "detail": f"{blind_labels.get(app.id, app.candidate.full_name or app.candidate.email)} submitted an application.",
        })
    if not activities:
        activity_items = fallback_activity
    else:
        activity_items = [{
            "created_at": item.created_at,
            "action": item.action,
            "detail": item.detail,
        } for item in activities]

    tab = request.args.get("tab", "overview")
    if tab not in ("overview", "applications", "matches", "pipeline", "activity"):
        tab = "overview"

    return render_template(
        "employer_job_detail.html",
        job=job,
        company=company,
        tab=tab,
        applications=application_rows,
        shortlisted=shortlisted,
        interviewed=interviewed,
        hired=hired,
        offers=offers,
        activity_items=activity_items,
        active_status="active" if job.status == "open" else job.status,
    )

# Moved from employer.py: applicants
@employer.route('/employer/jobs/<int:job_id>/applicants')
@login_required
@employer_required
def applicants(job_id):
    company = get_owned_company()
    job = Job.query.get_or_404(job_id)
    if job.company_id != company.id:
        abort(403)

    applications = Application.query.filter_by(job_id=job.id).all()
    summaries = {app.id: summarize_explanation(app.match_explanation) for app in applications}
    audio_logs = {
        app.id: json.loads(app.interview_audio_log) if app.interview_audio_log else []
        for app in applications
    }
    ai_likelihoods = {
        app.id: json.loads(app.ai_likelihood) if app.ai_likelihood else None
        for app in applications
    }
    work_auths = {
        app.id: json.loads(app.work_authorization) if app.work_authorization else None
        for app in applications
    }
    meetings = {
        app.id: json.loads(app.scheduled_meeting) if app.scheduled_meeting else None
        for app in applications
    }
    profiles = {
        app.candidate_user_id: CandidateProfile.query.filter_by(user_id=app.candidate_user_id).first()
        for app in applications
    }

    composite_scores = {
        app.id: compute_composite_score(app, ai_likelihoods.get(app.id))
        for app in applications
    }
    applications.sort(key=lambda a: composite_scores[a.id], reverse=True)

    # Blind mode: assign anonymous IDs in composite-score order
    blind_labels = {}
    if company.blind_mode_enabled:
        for i, app in enumerate(applications, 1):
            blind_labels[app.id] = f"Candidate #{i}"

    # Feedback prompt once a hire is fully closed out (employer marked hired,
    # candidate confirmed the compensation figure) and this employer hasn't
    # already rated the experience.
    already_rated = {
        f.application_id
        for f in Feedback.query.filter_by(user_id=current_user.id, role='employer', context='hire_closed').all()
    }
    feedback_prompt_ids = {
        app.id for app in applications
        if app.status == 'hired' and app.hire_confirmed_at and app.id not in already_rated
    }

    return render_template(
        "job_applicants.html",
        job=job,
        applications=applications,
        summaries=summaries,
        audio_logs=audio_logs,
        work_auths=work_auths,
        meetings=meetings,
        profiles=profiles,
        blind_mode=company.blind_mode_enabled,
        blind_labels=blind_labels,
        ai_likelihoods=ai_likelihoods,
        composite_scores=composite_scores,
        feedback_prompt_ids=feedback_prompt_ids,
        verdict_score_map=_VERDICT_SCORE,
    )

# Moved from employer.py: update_status
@employer.route('/employer/applications/<int:application_id>/status', methods=['POST'])
@login_required
@employer_required
def update_status(application_id):
    company = get_owned_company()
    application = Application.query.get_or_404(application_id)
    job = Job.query.get_or_404(application.job_id)
    if job.company_id != company.id:
        abort(403)

    new_status = request.form.get('status')
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if new_status in ('applied', 'interviewing', 'rejected', 'hired'):
        # Hired/rejected are final decisions - the employer can't walk one
        # back to a different status later. (Resubmitting the SAME status is
        # still allowed - that's how a disputed hire salary gets corrected.)
        if application.status in ('hired', 'rejected') and new_status != application.status:
            message = f"This application was already marked \"{application.status}\" - that decision is final and can't be changed."
            if is_ajax:
                return jsonify({"status": "error", "error": message}), 400
            flash(message, "error")
            return redirect(url_for('employer.applicants', job_id=job.id))

        if new_status == 'hired':
            # The placement fee is based on this figure, not the job posting's
            # advertised salary - require it up front rather than invoicing
            # off a number the employer has no incentive to keep accurate.
            salary_raw = request.form.get('hire_salary_usd', '').strip()
            pay_type = request.form.get('hire_pay_type', '').strip()
            try:
                salary_value = int(float(salary_raw)) if salary_raw else None
            except ValueError:
                salary_value = None
            if not salary_value or salary_value <= 0 or pay_type not in ('yearly', 'hourly', 'monthly', 'stipend', 'contract'):
                flash("Enter the candidate's actual compensation (amount and pay type) to mark them hired - the placement fee is calculated from this, not the job posting.", "error")
                return redirect(url_for('employer.applicants', job_id=job.id))

            application.hire_salary_usd = salary_value
            application.hire_pay_type = pay_type
            application.hire_salary_disputed = False  # fresh hire event, not yet re-disputed

            evidence_filename = _save_hire_evidence(application.id, request.files.get('hire_evidence'))
            if evidence_filename:
                application.hire_evidence_filename = evidence_filename

        status_changed = application.status != new_status
        application.status = new_status
        db.session.commit()
        if status_changed:
            candidate_name = application.candidate.full_name or application.candidate.email
            db.session.add(JobActivity(
                job_id=job.id,
                company_id=company.id,
                application_id=application.id,
                actor_user_id=current_user.id,
                action="candidate_status",
                detail=f"Candidate {candidate_name} moved to {new_status}.",
            ))
            db.session.commit()

        copy = STATUS_EMAIL_COPY.get(new_status)
        if status_changed and copy:
            candidate = application.candidate

            if new_status == 'hired':
                # Reset confirmation state - this is a fresh hire event, not yet verified by the candidate.
                # The placement fee invoice only fires once they confirm (see candidate.confirm_hire).
                application.candidate_confirmed_hire = False
                application.hire_confirmed_at = None
                db.session.commit()

            if candidate.notifications_enabled:
                notif_messages = {
                    "interviewing": f"Your application for {job.title} at {company.name} is moving forward!",
                    "hired": f"Congratulations! {company.name} has hired you for {job.title}.",
                    "rejected": f"Update on your application for {job.title} at {company.name}.",
                }
                notif = Notification(
                    user_id=candidate.id,
                    message=notif_messages.get(new_status, f"Your application status changed to {new_status}."),
                    link=url_for('candidate.dashboard', _external=False),
                )
                db.session.add(notif)
                db.session.commit()

            try:
                if new_status == 'hired':
                    # Email the candidate - congratulations + ask them to confirm the hire.
                    # The employer isn't invoiced for the placement fee until the candidate confirms.
                    send_branded_email(
                        to_email=candidate.email,
                        subject=f"You're hired - {job.title}",
                        heading="You got the job!",
                        body_html=(
                            f"Congratulations - <strong>{company.name}</strong> has decided to move forward "
                            f"with you for the <strong>{job.title}</strong> role!<br><br>"
                            f"Please confirm the hire on your dashboard so we can let {company.name} know. "
                            f"Best of luck in your new role!"
                        ),
                        plain_text=(
                            f"Congratulations - {company.name} has offered you the {job.title} role! "
                            f"Please confirm the hire on your dashboard."
                        ),
                        cta_label="Confirm My Hire",
                        cta_url=external_url('candidate.dashboard'),
                    )
                else:
                    send_branded_email(
                        to_email=candidate.email,
                        subject=copy["subject_tpl"].format(job_title=job.title),
                        heading=copy["heading"],
                        body_html=copy["body_tpl"].format(company=company.name, job_title=job.title),
                        plain_text=copy["body_tpl"].format(company=company.name, job_title=job.title).replace("<strong>", "").replace("</strong>", ""),
                        cta_label="View My Applications",
                        cta_url=external_url('candidate.dashboard'),
                    )
            except Exception as e:
                print(f"Status email send failed ({new_status}):", e)
        # For rejections, if the caller wants JSON (AJAX), return a feedback draft
        if new_status == 'rejected' and status_changed and is_ajax:
            try:
                draft = generate_rejection_feedback(
                    job_title=job.title,
                    company_name=company.name,
                    match_score=application.match_score,
                    match_explanation=application.match_explanation or '',
                    interview_verdict=application.interview_verdict,
                    interview_transcript=application.interview_transcript or '',
                )
            except Exception:
                draft = ""
            return jsonify({
                "status": "ok",
                "application_id": application.id,
                #new change: return the candidate's combined name to the client.
                "candidate_name": application.candidate.full_name,
                "feedback_draft": draft,
                "redirect": url_for('employer.job_detail', job_id=job.id, tab='pipeline'),
            })

        flash("Status updated.", "success")

    return redirect(url_for('employer.job_detail', job_id=job.id, tab='pipeline'))

# Moved from employer.py: hire_evidence
@employer.route('/employer/applications/<int:application_id>/hire-evidence')
@login_required
def hire_evidence(application_id):
    """Serves the optional hire-salary evidence upload. Viewable by the
    employer who owns the job or the candidate the application belongs to -
    nobody else."""
    application = Application.query.get_or_404(application_id)
    job = Job.query.get_or_404(application.job_id)

    user_company = get_user_company() if current_user.role == 'employer' else None
    is_owning_employer = user_company is not None and job.company_id == user_company.id
    is_owning_candidate = current_user.id == application.candidate_user_id
    if not (is_owning_employer or is_owning_candidate):
        abort(403)
    if not application.hire_evidence_filename:
        abort(404)
    return send_from_directory(_hire_evidence_dir(), application.hire_evidence_filename)

# Moved from employer.py: end_hourly_engagement
@employer.route('/employer/applications/<int:application_id>/end-hourly-engagement', methods=['POST'])
@login_required
@employer_required
def end_hourly_engagement(application_id):
    """Cancels the recurring monthly placement-fee subscription for an
    hourly hire once the engagement actually ends, so billing stops instead
    of continuing to charge for work that isn't happening anymore."""
    company = get_owned_company()
    application = Application.query.get_or_404(application_id)
    job = Job.query.get_or_404(application.job_id)
    if job.company_id != company.id:
        abort(403)

    if not application.hire_billing_subscription_id:
        flash("No active billing subscription found for this hire.", "error")
        return redirect(url_for('employer.applicants', job_id=job.id))
    if application.hire_engagement_ended_at:
        flash("This engagement is already marked as ended.", "info")
        return redirect(url_for('employer.applicants', job_id=job.id))

    stripe.api_key = current_app.config.get("STRIPE_SECRET_KEY")
    try:
        stripe.Subscription.cancel(application.hire_billing_subscription_id)
    except Exception as e:
        logger.error(f"Failed to cancel Stripe subscription {application.hire_billing_subscription_id}: {e}")
        flash("Couldn't reach Stripe to cancel billing. Please try again or cancel it directly in your Stripe dashboard.", "error")
        return redirect(url_for('employer.applicants', job_id=job.id))

    application.hire_engagement_ended_at = func.now()
    db.session.commit()
    flash("Engagement marked as ended - monthly billing has been stopped.", "success")
    return redirect(url_for('employer.applicants', job_id=job.id))

# Moved from employer.py: submit_platform_feedback
@employer.route('/employer/applications/<int:application_id>/platform-feedback', methods=['POST'])
@login_required
@employer_required
def submit_platform_feedback(application_id):
    """Employer rating their own experience hiring through Avants - distinct
    from send_candidate_feedback() below, which sends feedback TO a candidate
    about their application."""
    company = get_owned_company()
    application = Application.query.get_or_404(application_id)
    job = Job.query.get_or_404(application.job_id)
    if job.company_id != company.id:
        abort(403)

    rating = request.form.get('rating', type=int)
    if not rating or rating < 1 or rating > 5:
        flash("Please select a rating from 1 to 5.", "error")
        return redirect(url_for('employer.applicants', job_id=job.id))

    comment = (request.form.get('comment') or '').strip()

    existing = Feedback.query.filter_by(
        user_id=current_user.id, application_id=application_id, context='hire_closed'
    ).first()
    if not existing:
        db.session.add(Feedback(
            user_id=current_user.id,
            application_id=application_id,
            role='employer',
            context='hire_closed',
            rating=rating,
            comment=comment or None,
        ))
        db.session.commit()

    flash("Thanks for the feedback!", "success")
    return redirect(url_for('employer.applicants', job_id=job.id))

# Moved from employer.py: send_candidate_feedback
@employer.route('/employer/applications/<int:application_id>/send-feedback', methods=['POST'])
@login_required
@employer_required
def send_candidate_feedback(application_id):
    company = get_owned_company()
    application = Application.query.get_or_404(application_id)
    job = Job.query.get_or_404(application.job_id)
    if job.company_id != company.id:
        abort(403)

    feedback_text = (request.get_json() or {}).get('feedback', '').strip()
    if not feedback_text:
        return jsonify({"error": "No feedback provided"}), 400

    application.candidate_feedback = feedback_text
    db.session.commit()

    # Notify candidate
    candidate = application.candidate
    if candidate.notifications_enabled:
        notif = Notification(
            user_id=candidate.id,
            message=f"You received feedback on your {job.title} application from {company.name}.",
            link=url_for('candidate.dashboard', _external=False),
        )
        db.session.add(notif)
        db.session.commit()

    try:
        send_branded_email(
            to_email=candidate.email,
            subject=f"Feedback on your {job.title} application",
            heading="Application feedback",
            body_html=(
                f"<strong>{company.name}</strong> wanted to share some feedback on your "
                f"application for <strong>{job.title}</strong>:<br><br>"
                f"<blockquote style='border-left:3px solid #6366f1;padding-left:14px;color:#374151;'>"
                f"{feedback_text}</blockquote>"
            ),
            plain_text=f"Feedback from {company.name} on your {job.title} application:\n\n{feedback_text}",
            cta_label="View My Applications",
            cta_url=external_url('candidate.dashboard'),
        )
    except Exception as e:
        print("Feedback email failed:", e)

    return jsonify({"status": "sent"})

# Moved from employer.py: save_notes
@employer.route('/employer/applications/<int:application_id>/notes', methods=['POST'])
@login_required
@employer_required
def save_notes(application_id):
    company = get_owned_company()
    application = Application.query.get_or_404(application_id)
    job = Job.query.get_or_404(application.job_id)
    if job.company_id != company.id:
        abort(403)
    application.employer_notes = request.get_json().get('notes', '').strip() or None
    db.session.commit()
    return jsonify({"status": "saved"})

# Moved from employer.py: save_manual_interview_score
@employer.route('/employer/applications/<int:application_id>/manual-interview-score', methods=['POST'])
@login_required
@employer_required
def save_manual_interview_score(application_id):
    """The employer's own 0-100 rating after conducting a live/manual
    interview themselves - factored into the composite score alongside the
    AI screening interview verdict, see compute_composite_score()."""
    company = get_owned_company()
    application = Application.query.get_or_404(application_id)
    job = Job.query.get_or_404(application.job_id)
    if job.company_id != company.id:
        abort(403)

    raw = (request.get_json() or {}).get('score')
    try:
        score = int(raw)
    except (TypeError, ValueError):
        return jsonify({"error": "Score must be a number from 0 to 100."}), 400
    if not 0 <= score <= 100:
        return jsonify({"error": "Score must be between 0 and 100."}), 400

    application.manual_interview_score = score
    db.session.commit()
    return jsonify({"status": "saved", "score": score})

