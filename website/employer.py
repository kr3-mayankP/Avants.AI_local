# ----------------------------------------------------------------
# CHANGE BLOCK: 2026-11-22
# OLD IMPLEMENTATION - commented snapshot from Git HEAD
# ----------------------------------------------------------------
# OLD CODE: import json
# OLD CODE: import logging
# OLD CODE: import os
# OLD CODE: import secrets
# OLD CODE: from datetime import datetime, timedelta, timezone
# OLD CODE:
# OLD CODE: from sqlalchemy.sql import func
# OLD CODE:
# OLD CODE: logger = logging.getLogger(__name__)
# OLD CODE:
# OLD CODE: import stripe
# OLD CODE: from flask import Blueprint, render_template, request, flash, redirect, url_for, abort, jsonify, current_app, send_from_directory
# OLD CODE: from flask_login import login_required, current_user
# OLD CODE: from functools import wraps
# OLD CODE: from PIL import Image
# OLD CODE: try:
# OLD CODE:     import pillow_heif
# OLD CODE:     pillow_heif.register_heif_opener()
# OLD CODE: except ImportError:
# OLD CODE:     pass
# OLD CODE:
# OLD CODE: from . import db, limiter
# OLD CODE: from .models import (
# OLD CODE:     Company, Job, Application, Notification,
# OLD CODE:     CompanyMember, CompanyInvite, CandidateProfile, User,
# OLD CODE:     MeetingRoom, Message, MeetingProposal, SavedJob, Feedback, DeletedJob,
# OLD CODE:     JOB_CATEGORIES, JOB_LOCATIONS, COMPANY_SIZES, INDUSTRIES,
# OLD CODE:     SUPPORTED_CURRENCIES, DEFAULT_CURRENCY,
# OLD CODE: )
# OLD CODE: from ai_services import generate_interview_question_preview, generate_rejection_feedback, analyze_job_description, transcribe_audio, audio_file_extension, compare_resume_to_job, suggest_candidates_for_jobs
# OLD CODE: from .candidate import _extract_score
# OLD CODE: from .matching import keyword_set, overlap_score, NOTIFY_SCORE_THRESHOLD, NOTIFY_MAX_RECIPIENTS
# OLD CODE: from email_utils import send_branded_email, external_url
# OLD CODE:
# OLD CODE: employer = Blueprint('employer', __name__)
# OLD CODE:
# OLD CODE: MAX_INTERVIEW_QUESTIONS = 15
# OLD CODE: TALENT_POOL_AI_LIMIT = 60  # cap on how many open-to-work profiles get sent to the AI ranker per call
# OLD CODE:
# OLD CODE: _VERDICT_SCORE = {"Strong Yes": 100, "Yes": 75, "No": 25, "Strong No": 0}
# OLD CODE:
# OLD CODE: def compute_composite_score(app, ai_data):
# OLD CODE:     """Weighted overall score. With both an AI-interview verdict and a
# OLD CODE:     manual (live/human) interview score: resume 30%, AI interview 30%,
# OLD CODE:     manual interview 30%, authenticity 10%. With only one of the two
# OLD CODE:     interview signals, that one fills the "interview" slot alone at 45% -
# OLD CODE:     resume 45%, authenticity 10%, same weighting as before this existed.
# OLD CODE:     With neither, falls back to resume score alone."""
# OLD CODE:     resume = app.match_score or 0
# OLD CODE:     ai_penalty = (ai_data.get("score", 0) if ai_data else 0)
# OLD CODE:     authenticity = 100 - ai_penalty
# OLD CODE:
# OLD CODE:     ai_verdict = _VERDICT_SCORE.get(app.interview_verdict)
# OLD CODE:     manual = app.manual_interview_score
# OLD CODE:
# OLD CODE:     if ai_verdict is not None and manual is not None:
# OLD CODE:         return round(resume * 0.30 + ai_verdict * 0.30 + manual * 0.30 + authenticity * 0.10)
# OLD CODE:     if ai_verdict is not None:
# OLD CODE:         return round(resume * 0.45 + ai_verdict * 0.45 + authenticity * 0.10)
# OLD CODE:     if manual is not None:
# OLD CODE:         return round(resume * 0.45 + manual * 0.45 + authenticity * 0.10)
# OLD CODE:     return resume
# OLD CODE: PLATFORM_FEE_PERCENT = 15  # flat rate across every pay type
# OLD CODE:
# OLD CODE: STANDARD_ANNUAL_HOURS = 2080  # 40hrs/week x 52 weeks - used to annualize hourly rates
# OLD CODE:
# OLD CODE:
# OLD CODE: def _placement_fee_basis(application, job):
# OLD CODE:     """Return (basis_amount, fee_percent) for the placement fee.
# OLD CODE:
# OLD CODE:     Uses the actual negotiated compensation entered by the employer when
# OLD CODE:     marking the candidate hired (application.hire_salary_usd/hire_pay_type),
# OLD CODE:     not the job posting's advertised salary - an employer has no incentive
# OLD CODE:     to keep the posting accurate once someone's actually hired, and the
# OLD CODE:     candidate cross-checks this figure before it's ever invoiced (see
# OLD CODE:     candidate.confirm_hire / candidate.dispute_hire). Falls back to the job
# OLD CODE:     posting only for legacy applications hired before this existed.
# OLD CODE:
# OLD CODE:     Salaried/monthly roles use first-year compensation directly. Hourly
# OLD CODE:     roles are annualized to a comparable full-time figure first (then
# OLD CODE:     billed monthly for as long as the engagement is active - see
# OLD CODE:     _create_stripe_subscription_link). Same flat 15% rate throughout.
# OLD CODE:     """
# OLD CODE:     salary = application.hire_salary_usd or job.salary_usd
# OLD CODE:     pay_type = application.hire_pay_type or job.pay_type
# OLD CODE:     if not salary:
# OLD CODE:         return None, None
# OLD CODE:     if pay_type == 'hourly':
# OLD CODE:         return salary * STANDARD_ANNUAL_HOURS, PLATFORM_FEE_PERCENT
# OLD CODE:     if pay_type == 'monthly':
# OLD CODE:         return salary * 12, PLATFORM_FEE_PERCENT
# OLD CODE:     return salary, PLATFORM_FEE_PERCENT
# OLD CODE:
# OLD CODE:
# OLD CODE: HIRE_EVIDENCE_ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}
# OLD CODE:
# OLD CODE:
# OLD CODE: def _hire_evidence_dir():
# OLD CODE:     path = os.path.join(current_app.config["UPLOAD_FOLDER"], "hire_evidence")
# OLD CODE:     os.makedirs(path, exist_ok=True)
# OLD CODE:     return path
# OLD CODE:
# OLD CODE:
# OLD CODE: def _save_hire_evidence(application_id, file_storage):
# OLD CODE:     """Save an optional offer-letter/screenshot upload for a hire. Returns
# OLD CODE:     the stored filename, or None if no valid file was given."""
# OLD CODE:     if not file_storage or not file_storage.filename:
# OLD CODE:         return None
# OLD CODE:     ext = file_storage.filename.rsplit('.', 1)[-1].lower() if '.' in file_storage.filename else ''
# OLD CODE:     if ext not in HIRE_EVIDENCE_ALLOWED_EXTENSIONS:
# OLD CODE:         return None
# OLD CODE:     filename = f"{application_id}_{secrets.token_hex(8)}.{ext}"
# OLD CODE:     file_storage.save(os.path.join(_hire_evidence_dir(), filename))
# OLD CODE:     return filename
# OLD CODE:
# OLD CODE:
# OLD CODE: LOGO_ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
# OLD CODE: LOGO_MAX_SIZE = (800, 800)
# OLD CODE: INTERVIEW_LENGTH_OPTIONS = ["short", "standard", "thorough"]
# OLD CODE:
# OLD CODE: STATUS_EMAIL_COPY = {
# OLD CODE:     "interviewing": {
# OLD CODE:         "subject_tpl": "Your application is moving forward - {job_title}",
# OLD CODE:         "heading": "You're being considered for the role",
# OLD CODE:         "body_tpl": (
# OLD CODE:             "Good news - {company} has moved your application for <strong>{job_title}</strong> "
# OLD CODE:             "into the interviewing stage. They'll be in touch with next steps."
# OLD CODE:         ),
# OLD CODE:     },
# OLD CODE:     "hired": {
# OLD CODE:         "subject_tpl": "You're hired - {job_title}",
# OLD CODE:         "heading": "Congratulations!",
# OLD CODE:         "body_tpl": (
# OLD CODE:             "{company} has decided to move forward with hiring you for the <strong>{job_title}</strong> "
# OLD CODE:             "position. They'll be in touch with next steps."
# OLD CODE:         ),
# OLD CODE:     },
# OLD CODE:     "rejected": {
# OLD CODE:         "subject_tpl": "Update on your application - {job_title}",
# OLD CODE:         "heading": "Application update",
# OLD CODE:         "body_tpl": (
# OLD CODE:             "Thank you for applying to <strong>{job_title}</strong> at {company}. After review, they've "
# OLD CODE:             "decided not to move forward with your application at this time. We encourage you to keep "
# OLD CODE:             "applying to other roles on the platform."
# OLD CODE:         ),
# OLD CODE:     },
# OLD CODE: }
# OLD CODE:
# OLD CODE:
# OLD CODE: # ------------------------------------------------------------------ #
# OLD CODE: #  Auth helpers
# OLD CODE: # ------------------------------------------------------------------ #
# OLD CODE:
# OLD CODE: def get_user_company():
# OLD CODE:     """Return the Company this user owns or is a member of, or None."""
# OLD CODE:     company = Company.query.filter_by(owner_user_id=current_user.id).first()
# OLD CODE:     if company:
# OLD CODE:         return company
# OLD CODE:     membership = CompanyMember.query.filter_by(user_id=current_user.id).first()
# OLD CODE:     if membership:
# OLD CODE:         return membership.company
# OLD CODE:     return None
# OLD CODE:
# OLD CODE:
# OLD CODE: def employer_required(view):
# OLD CODE:     @wraps(view)
# OLD CODE:     def wrapped(*args, **kwargs):
# OLD CODE:         if current_user.role != 'employer':
# OLD CODE:             abort(403)
# OLD CODE:         if not get_user_company():
# OLD CODE:             return redirect(url_for('auth.complete_employer_profile'))
# OLD CODE:         return view(*args, **kwargs)
# OLD CODE:     return wrapped
# OLD CODE:
# OLD CODE:
# OLD CODE: def get_owned_company():
# OLD CODE:     company = get_user_company()
# OLD CODE:     if not company:
# OLD CODE:         abort(403)
# OLD CODE:     return company
# OLD CODE:
# OLD CODE:
# OLD CODE: def is_company_owner():
# OLD CODE:     return Company.query.filter_by(owner_user_id=current_user.id).first() is not None
# OLD CODE:
# OLD CODE:
# OLD CODE: # ------------------------------------------------------------------ #
# OLD CODE: #  Private helpers
# OLD CODE: # ------------------------------------------------------------------ #
# OLD CODE:
# OLD CODE: def notify_candidates_of_new_job(job, company):
# OLD CODE:     """Cheap keyword-match nudge to candidates whose profile overlaps a job
# OLD CODE:     that just went live - not a replacement for the AI-ranked Suggested Jobs
# OLD CODE:     feature, just a lightweight "hey, this might interest you" at the moment
# OLD CODE:     a job is first posted/published, so it doesn't run a real AI call per
# OLD CODE:     candidate on every job post."""
# OLD CODE:     job_words = keyword_set(job.title, job.category, (job.description_text or '')[:500])
# OLD CODE:     if not job_words:
# OLD CODE:         return
# OLD CODE:
# OLD CODE:     from sqlalchemy.orm import joinedload
# OLD CODE:     profiles = (
# OLD CODE:         CandidateProfile.query
# OLD CODE:         .filter(db.or_(CandidateProfile.skills.isnot(None), CandidateProfile.target_roles.isnot(None)))
# OLD CODE:         .options(joinedload(CandidateProfile.user))
# OLD CODE:         .limit(300)
# OLD CODE:         .all()
# OLD CODE:     )
# OLD CODE:
# OLD CODE:     scored = []
# OLD CODE:     for prof in profiles:
# OLD CODE:         if not prof.user or not prof.user.notifications_enabled:
# OLD CODE:             continue
# OLD CODE:         words = keyword_set(prof.skills, prof.target_roles, prof.headline)
# OLD CODE:         score = overlap_score(words, job_words)
# OLD CODE:         if score >= NOTIFY_SCORE_THRESHOLD:
# OLD CODE:             scored.append((score, prof))
# OLD CODE:     scored.sort(key=lambda x: x[0], reverse=True)
# OLD CODE:
# OLD CODE:     for _, prof in scored[:NOTIFY_MAX_RECIPIENTS]:
# OLD CODE:         db.session.add(Notification(
# OLD CODE:             user_id=prof.user_id,
# OLD CODE:             message=f"New job that fits your profile: {job.title} at {company.name}",
# OLD CODE:             link=url_for('candidate.job_detail', job_id=job.id),
# OLD CODE:         ))
# OLD CODE:
# OLD CODE:
# OLD CODE: OVERDUE_FEE_DAYS = 30       # matches the ToS: fee is due within 30 days of the candidate's start date
# OLD CODE: FEE_REMINDER_THROTTLE_DAYS = 4  # don't re-send a reminder more than once every N days
# OLD CODE:
# OLD CODE:
# OLD CODE: def overdue_fee_applications(company):
# OLD CODE:     """Hired applications whose placement fee invoice went out (candidate
# OLD CODE:     confirmed) but was never paid, past the 30-day ToS deadline. Excludes
# OLD CODE:     engagements already marked ended - once billing has legitimately stopped
# OLD CODE:     there's nothing to chase. Note: for hourly roles this only catches a
# OLD CODE:     first payment that was never made - fee_paid flips True on the first
# OLD CODE:     successful Stripe charge and nothing here currently detects a later
# OLD CODE:     monthly subscription payment failing (no invoice.payment_failed webhook
# OLD CODE:     handler exists yet), so a lapsed recurring subscription won't show up."""
# OLD CODE:     cutoff = datetime.now(timezone.utc) - timedelta(days=OVERDUE_FEE_DAYS)
# OLD CODE:     return (
# OLD CODE:         Application.query.join(Job)
# OLD CODE:         .filter(
# OLD CODE:             Job.company_id == company.id,
# OLD CODE:             Application.status == 'hired',
# OLD CODE:             Application.candidate_confirmed_hire.is_(True),
# OLD CODE:             Application.fee_paid.is_(False),
# OLD CODE:             Application.hire_engagement_ended_at.is_(None),
# OLD CODE:             Application.hire_confirmed_at.isnot(None),
# OLD CODE:             Application.hire_confirmed_at <= cutoff,
# OLD CODE:         )
# OLD CODE:         .order_by(Application.hire_confirmed_at.asc())
# OLD CODE:         .all()
# OLD CODE:     )
# OLD CODE:
# OLD CODE:
# OLD CODE: def send_overdue_fee_reminder(application, job, company, employer_user):
# OLD CODE:     """Email + in-app warning for an overdue placement fee, throttled so it
# OLD CODE:     fires at most once every FEE_REMINDER_THROTTLE_DAYS regardless of how
# OLD CODE:     often the employer loads their dashboard."""
# OLD CODE:     now = datetime.now(timezone.utc)
# OLD CODE:     if application.fee_reminder_sent_at:
# OLD CODE:         last = application.fee_reminder_sent_at
# OLD CODE:         if last.tzinfo is None:
# OLD CODE:             last = last.replace(tzinfo=timezone.utc)
# OLD CODE:         if now - last < timedelta(days=FEE_REMINDER_THROTTLE_DAYS):
# OLD CODE:             return
# OLD CODE:
# OLD CODE:     days_overdue = (now - application.hire_confirmed_at.replace(tzinfo=timezone.utc)).days
# OLD CODE:     basis_amount, fee_percent = _placement_fee_basis(application, job)
# OLD CODE:     fee_amount = int(basis_amount * fee_percent / 100) if basis_amount else None
# OLD CODE:     candidate = User.query.get(application.candidate_user_id)
# OLD CODE:     pay_link = application.stripe_payment_link or external_url('employer.applicants', job_id=job.id)
# OLD CODE:
# OLD CODE:     db.session.add(Notification(
# OLD CODE:         user_id=employer_user.id,
# OLD CODE:         message=(
# OLD CODE:             f"Overdue: the placement fee for {candidate.first_name if candidate else 'your hire'} "
# OLD CODE:             f"({job.title}) is {days_overdue} days past due. Your account may be suspended or your "
# OLD CODE:             f"company removed from Avants AI if this isn't resolved."
# OLD CODE:         ),
# OLD CODE:         link=url_for('employer.applicants', job_id=job.id),
# OLD CODE:     ))
# OLD CODE:
# OLD CODE:     try:
# OLD CODE:         send_branded_email(
# OLD CODE:             to_email=employer_user.email,
# OLD CODE:             subject=f"Overdue placement fee - {job.title} - action required",
# OLD CODE:             heading="Placement fee overdue",
# OLD CODE:             body_html=(
# OLD CODE:                 f"The placement fee for <strong>{candidate.first_name if candidate else 'your hire'}</strong> "
# OLD CODE:                 f"(<strong>{job.title}</strong>) is <strong>{days_overdue} days overdue</strong> - "
# OLD CODE:                 f"{f'${fee_amount:,} ' if fee_amount else ''}was due within 30 days of the candidate's start date "
# OLD CODE:                 f"per the Employer Platform Agreement.<br><br>"
# OLD CODE:                 f"Unpaid invoices accrue interest at 1.5% per month after 30 days. "
# OLD CODE:                 f"<strong>Continued non-payment may result in your account being suspended or your "
# OLD CODE:                 f"company profile being removed from Avants AI.</strong><br><br>"
# OLD CODE:                 f"Please pay now to avoid any disruption, or reply to this email if you believe this is in error."
# OLD CODE:             ),
# OLD CODE:             plain_text=(
# OLD CODE:                 f"The placement fee for {candidate.first_name if candidate else 'your hire'} ({job.title}) is "
# OLD CODE:                 f"{days_overdue} days overdue"
# OLD CODE:                 f"{f' (${fee_amount:,})' if fee_amount else ''} - due within 30 days of the candidate's start date "
# OLD CODE:                 f"per the Employer Platform Agreement.\n\n"
# OLD CODE:                 f"Unpaid invoices accrue interest at 1.5%/month after 30 days. Continued non-payment may result "
# OLD CODE:                 f"in your account being suspended or your company profile being removed from Avants AI.\n\n"
# OLD CODE:                 f"Pay here: {pay_link}"
# OLD CODE:             ),
# OLD CODE:             cta_label="Pay Now",
# OLD CODE:             cta_url=pay_link,
# OLD CODE:         )
# OLD CODE:     except Exception as e:
# OLD CODE:         print(f"Overdue fee reminder email failed: {e}")
# OLD CODE:
# OLD CODE:     application.fee_reminder_sent_at = now
# OLD CODE:
# OLD CODE:
# OLD CODE: def send_hire_fee_invoice(application, job, company, candidate, employer_user):
# OLD CODE:     """Create the Stripe placement-fee payment link and invoice the employer.
# OLD CODE:     Only called once the candidate has confirmed the hire - see candidate.confirm_hire."""
# OLD CODE:     hire_salary = application.hire_salary_usd or job.salary_usd
# OLD CODE:     hire_pay_type = application.hire_pay_type or job.pay_type
# OLD CODE:     is_hourly = hire_pay_type == 'hourly'
# OLD CODE:
# OLD CODE:     payment_link_url = None
# OLD CODE:     if not application.stripe_payment_link:
# OLD CODE:         payment_link_url = (
# OLD CODE:             _create_stripe_subscription_link(application, job, company, candidate) if is_hourly
# OLD CODE:             else _create_stripe_payment_link(application, job, company, candidate)
# OLD CODE:         )
# OLD CODE:         if payment_link_url:
# OLD CODE:             application.stripe_payment_link = payment_link_url
# OLD CODE:             db.session.commit()
# OLD CODE:
# OLD CODE:     basis_amount, fee_percent = _placement_fee_basis(application, job)
# OLD CODE:     fee_amount = int(basis_amount * fee_percent / 100) if basis_amount else None
# OLD CODE:     monthly_fee_amount = int(fee_amount / 12) if is_hourly and fee_amount else None
# OLD CODE:     basis_label = (
# OLD CODE:         f"annualized rate of ${basis_amount:,}/yr (${hire_salary:,}/hr x {STANDARD_ANNUAL_HOURS:,} hrs)"
# OLD CODE:         if is_hourly else f"first-year compensation of ${basis_amount:,}"
# OLD CODE:     )
# OLD CODE:     try:
# OLD CODE:         if payment_link_url and fee_amount and is_hourly:
# OLD CODE:             send_branded_email(
# OLD CODE:                 to_email=employer_user.email,
# OLD CODE:                 subject=f"Placement fee billing set up - {candidate.first_name} / {job.title}",
# OLD CODE:                 heading="Monthly placement fee billing",
# OLD CODE:                 body_html=(
# OLD CODE:                     f"<strong>{candidate.first_name}</strong> has confirmed their hire for "
# OLD CODE:                     f"<strong>{job.title}</strong> through Avants AI.<br><br>"
# OLD CODE:                     f"Since this is an hourly role, the placement fee bills monthly for as long as the "
# OLD CODE:                     f"engagement is active - <strong>${monthly_fee_amount:,}/month</strong> "
# OLD CODE:                     f"({fee_percent}% of the {basis_label}, split across 12 months), rather than one lump sum. "
# OLD CODE:                     f"Billing stops automatically once you mark the engagement ended on your dashboard.<br><br>"
# OLD CODE:                     f"Click below to set up billing securely via Stripe."
# OLD CODE:                 ),
# OLD CODE:                 plain_text=(
# OLD CODE:                     f"{candidate.first_name} has confirmed their hire for {job.title} through Avants AI.\n\n"
# OLD CODE:                     f"Since this is an hourly role, the placement fee bills monthly for as long as the "
# OLD CODE:                     f"engagement is active: ${monthly_fee_amount:,}/month ({fee_percent}% of the {basis_label}, "
# OLD CODE:                     f"split across 12 months). Billing stops once you mark the engagement ended on your dashboard.\n"
# OLD CODE:                     f"Set up billing here: {payment_link_url}"
# OLD CODE:                 ),
# OLD CODE:                 cta_label="Set Up Monthly Billing",
# OLD CODE:                 cta_url=payment_link_url,
# OLD CODE:             )
# OLD CODE:         elif payment_link_url and fee_amount:
# OLD CODE:             send_branded_email(
# OLD CODE:                 to_email=employer_user.email,
# OLD CODE:                 subject=f"Placement fee invoice - {candidate.first_name} / {job.title}",
# OLD CODE:                 heading="Placement fee due",
# OLD CODE:                 body_html=(
# OLD CODE:                     f"<strong>{candidate.first_name}</strong> has confirmed their hire for "
# OLD CODE:                     f"<strong>{job.title}</strong> through Avants AI.<br><br>"
# OLD CODE:                     f"The platform placement fee is <strong>${fee_amount:,}</strong> "
# OLD CODE:                     f"({fee_percent}% of {basis_label}).<br><br>"
# OLD CODE:                     f"This is due within 30 days of the candidate's start date. "
# OLD CODE:                     f"Click below to pay securely via Stripe."
# OLD CODE:                 ),
# OLD CODE:                 plain_text=(
# OLD CODE:                     f"{candidate.first_name} has confirmed their hire for {job.title} through Avants AI.\n\n"
# OLD CODE:                     f"Placement fee: ${fee_amount:,} ({fee_percent}% of {basis_label}).\n"
# OLD CODE:                     f"Pay here: {payment_link_url}"
# OLD CODE:                 ),
# OLD CODE:                 cta_label="Pay Placement Fee",
# OLD CODE:                 cta_url=payment_link_url,
# OLD CODE:             )
# OLD CODE:         else:
# OLD CODE:             fee_percent_display = fee_percent or PLATFORM_FEE_PERCENT
# OLD CODE:             send_branded_email(
# OLD CODE:                 to_email=employer_user.email,
# OLD CODE:                 subject=f"Placement fee - {candidate.first_name} / {job.title}",
# OLD CODE:                 heading="Placement fee due",
# OLD CODE:                 body_html=(
# OLD CODE:                     f"<strong>{candidate.first_name}</strong> has confirmed their hire for "
# OLD CODE:                     f"<strong>{job.title}</strong> through Avants AI.<br><br>"
# OLD CODE:                     f"A placement fee of <strong>{fee_percent_display}% of first-year compensation</strong> "
# OLD CODE:                     f"is due within 30 days of the candidate's start date. "
# OLD CODE:                     f"Our team will follow up with an invoice."
# OLD CODE:                 ),
# OLD CODE:                 plain_text=(
# OLD CODE:                     f"{candidate.first_name} has confirmed their hire for {job.title} through Avants AI.\n\n"
# OLD CODE:                     f"A {fee_percent_display}% placement fee will be invoiced to you within 30 days of the start date."
# OLD CODE:                 ),
# OLD CODE:                 cta_label="View Dashboard",
# OLD CODE:                 cta_url=external_url('employer.dashboard'),
# OLD CODE:             )
# OLD CODE:     except Exception as e:
# OLD CODE:         print(f"Hire fee invoice email failed: {e}")
# OLD CODE:
# OLD CODE:
# OLD CODE: def _create_stripe_payment_link(application, job, company, candidate):
# OLD CODE:     """One-time placement fee for salaried/monthly/stipend/contract hires.
# OLD CODE:     Hourly hires use _create_stripe_subscription_link instead - see there
# OLD CODE:     for why."""
# OLD CODE:     stripe.api_key = current_app.config.get("STRIPE_SECRET_KEY")
# OLD CODE:     basis_amount, fee_percent = _placement_fee_basis(application, job)
# OLD CODE:     if not stripe.api_key or not basis_amount:
# OLD CODE:         return None
# OLD CODE:     fee_cents = int(basis_amount * fee_percent / 100 * 100)
# OLD CODE:     if fee_cents <= 0:
# OLD CODE:         return None
# OLD CODE:     try:
# OLD CODE:         product = stripe.Product.create(
# OLD CODE:             name=f"Avants AI Placement Fee - {job.title} at {company.name}",
# OLD CODE:             metadata={"application_id": str(application.id)},
# OLD CODE:         )
# OLD CODE:         price = stripe.Price.create(product=product.id, unit_amount=fee_cents, currency="usd")
# OLD CODE:         link = stripe.PaymentLink.create(
# OLD CODE:             line_items=[{"price": price.id, "quantity": 1}],
# OLD CODE:             metadata={"application_id": str(application.id)},
# OLD CODE:             customer_creation="always",
# OLD CODE:         )
# OLD CODE:         return link.url
# OLD CODE:     except Exception as e:
# OLD CODE:         print("Stripe payment link creation failed:", e)
# OLD CODE:         return None
# OLD CODE:
# OLD CODE:
# OLD CODE: def _create_stripe_subscription_link(application, job, company, candidate):
# OLD CODE:     """Recurring monthly placement fee for hourly hires.
# OLD CODE:
# OLD CODE:     The fee basis is the hourly rate annualized to a full 2,080-hour year
# OLD CODE:     (see _placement_fee_basis), but an hourly engagement might only last a
# OLD CODE:     few weeks - charging the full annualized fee up front the moment
# OLD CODE:     someone's hired would bill the employer for a full year of work that
# OLD CODE:     may never happen. Instead this bills 1/12th of that annualized fee
# OLD CODE:     every month, for as long as the engagement is actually active, so total
# OLD CODE:     revenue tracks actual engagement length instead of a one-time guess.
# OLD CODE:     Stops the moment the employer marks the engagement ended - see
# OLD CODE:     employer.end_hourly_engagement.
# OLD CODE:     """
# OLD CODE:     stripe.api_key = current_app.config.get("STRIPE_SECRET_KEY")
# OLD CODE:     basis_amount, fee_percent = _placement_fee_basis(application, job)
# OLD CODE:     if not stripe.api_key or not basis_amount:
# OLD CODE:         return None
# OLD CODE:     monthly_fee_cents = int(basis_amount * fee_percent / 100 / 12 * 100)
# OLD CODE:     if monthly_fee_cents <= 0:
# OLD CODE:         return None
# OLD CODE:     try:
# OLD CODE:         product = stripe.Product.create(
# OLD CODE:             name=f"Avants AI Placement Fee (monthly) - {job.title} at {company.name}",
# OLD CODE:             metadata={"application_id": str(application.id)},
# OLD CODE:         )
# OLD CODE:         price = stripe.Price.create(
# OLD CODE:             product=product.id,
# OLD CODE:             unit_amount=monthly_fee_cents,
# OLD CODE:             currency="usd",
# OLD CODE:             recurring={"interval": "month"},
# OLD CODE:         )
# OLD CODE:         link = stripe.PaymentLink.create(
# OLD CODE:             line_items=[{"price": price.id, "quantity": 1}],
# OLD CODE:             metadata={"application_id": str(application.id)},
# OLD CODE:             customer_creation="always",
# OLD CODE:         )
# OLD CODE:         return link.url
# OLD CODE:     except Exception as e:
# OLD CODE:         print("Stripe subscription link creation failed:", e)
# OLD CODE:         return None
# OLD CODE:
# OLD CODE:
# OLD CODE: def _extract_description_text(raw):
# OLD CODE:     try:
# OLD CODE:         data = json.loads(raw)
# OLD CODE:         if isinstance(data, dict):
# OLD CODE:             parts = []
# OLD CODE:             for key in ('about', 'requirements', 'preferred', 'what_you_do', 'contract_terms'):
# OLD CODE:                 val = (data.get(key) or '').strip()
# OLD CODE:                 if val:
# OLD CODE:                     parts.append(val)
# OLD CODE:             return '\n\n'.join(parts)
# OLD CODE:     except (ValueError, TypeError):
# OLD CODE:         pass
# OLD CODE:     return raw or ''
# OLD CODE:
# OLD CODE:
# OLD CODE: def _parse_interview_questions(raw):
# OLD CODE:     if not raw:
# OLD CODE:         return None
# OLD CODE:     try:
# OLD CODE:         questions = json.loads(raw)
# OLD CODE:     except (ValueError, TypeError):
# OLD CODE:         return None
# OLD CODE:     if not isinstance(questions, list):
# OLD CODE:         return None
# OLD CODE:     cleaned = [q.strip() for q in questions if isinstance(q, str) and q.strip()]
# OLD CODE:     return json.dumps(cleaned[:MAX_INTERVIEW_QUESTIONS]) if cleaned else None
# OLD CODE:
# OLD CODE:
# OLD CODE: def _existing_interview_questions(job):
# OLD CODE:     if not job or not job.interview_questions:
# OLD CODE:         return []
# OLD CODE:     try:
# OLD CODE:         return json.loads(job.interview_questions)
# OLD CODE:     except (ValueError, TypeError):
# OLD CODE:         return []
# OLD CODE:
# OLD CODE:
# OLD CODE: def summarize_explanation(explanation, max_len=140):
# OLD CODE:     if not explanation:
# OLD CODE:         return "No summary available..."
# OLD CODE:     match_lines = [
# OLD CODE:         line.strip().lstrip('+').strip()
# OLD CODE:         for line in explanation.split('\n')
# OLD CODE:         if line.strip().startswith('+')
# OLD CODE:     ]
# OLD CODE:     text = " ".join(match_lines[:2]) if match_lines else explanation.strip().replace('\n', ' ')
# OLD CODE:     if len(text) > max_len:
# OLD CODE:         text = text[:max_len].rstrip()
# OLD CODE:     return text + "..."
# OLD CODE:
# OLD CODE:
# OLD CODE: # ------------------------------------------------------------------ #
# OLD CODE: #  Employer Dashboard
# OLD CODE: # ------------------------------------------------------------------ #
# OLD CODE:
# OLD CODE: @employer.route('/employer/dashboard')
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: def dashboard():
# OLD CODE:     company = get_owned_company()
# OLD CODE:     jobs = Job.query.filter_by(company_id=company.id).order_by(Job.created_at.desc()).all()
# OLD CODE:     applicant_counts = {job.id: Application.query.filter_by(job_id=job.id).count() for job in jobs}
# OLD CODE:     hired_counts = {job.id: Application.query.filter_by(job_id=job.id, status='hired').count() for job in jobs}
# OLD CODE:
# OLD CODE:     total_applicants = sum(applicant_counts.values())
# OLD CODE:     total_hired = sum(hired_counts.values())
# OLD CODE:     open_jobs = sum(1 for j in jobs if j.status == 'open')
# OLD CODE:
# OLD CODE:     members = CompanyMember.query.filter_by(company_id=company.id).all()
# OLD CODE:     owner_is_current = company.owner_user_id == current_user.id
# OLD CODE:
# OLD CODE:     overdue_apps = overdue_fee_applications(company)
# OLD CODE:     now = datetime.now(timezone.utc)
# OLD CODE:     overdue_fees = []
# OLD CODE:     for app in overdue_apps:
# OLD CODE:         send_overdue_fee_reminder(app, app.job, company, current_user)
# OLD CODE:         basis_amount, fee_percent = _placement_fee_basis(app, app.job)
# OLD CODE:         overdue_fees.append({
# OLD CODE:             "application": app,
# OLD CODE:             "job": app.job,
# OLD CODE:             "candidate": app.candidate,
# OLD CODE:             "days_overdue": (now - app.hire_confirmed_at.replace(tzinfo=timezone.utc)).days,
# OLD CODE:             "fee_amount": int(basis_amount * fee_percent / 100) if basis_amount else None,
# OLD CODE:         })
# OLD CODE:     if overdue_apps:
# OLD CODE:         db.session.commit()
# OLD CODE:
# OLD CODE:     return render_template(
# OLD CODE:         "employer_dashboard.html",
# OLD CODE:         company=company,
# OLD CODE:         jobs=jobs,
# OLD CODE:         applicant_counts=applicant_counts,
# OLD CODE:         hired_counts=hired_counts,
# OLD CODE:         total_applicants=total_applicants,
# OLD CODE:         total_hired=total_hired,
# OLD CODE:         open_jobs=open_jobs,
# OLD CODE:         members=members,
# OLD CODE:         is_owner=owner_is_current,
# OLD CODE:         overdue_fees=overdue_fees,
# OLD CODE:     )
# OLD CODE:
# OLD CODE:
# OLD CODE: # ------------------------------------------------------------------ #
# OLD CODE: #  Job CRUD
# OLD CODE: # ------------------------------------------------------------------ #
# OLD CODE:
# OLD CODE: @employer.route('/employer/jobs/new', methods=['GET', 'POST'])
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: def post_job():
# OLD CODE:     company = get_owned_company()
# OLD CODE:
# OLD CODE:     if request.method == 'POST':
# OLD CODE:         title = request.form.get('title', '').strip()
# OLD CODE:         description = request.form.get('description', '').strip()
# OLD CODE:         work_type = request.form.get('work_type', 'Remote (Worldwide)').strip()
# OLD CODE:         city = request.form.get('location_city', '').strip()
# OLD CODE:         if work_type in ('Hybrid', 'On-site') and city:
# OLD CODE:             location = f"{work_type} - {city}"
# OLD CODE:         else:
# OLD CODE:             location = work_type
# OLD CODE:         employment_type = request.form.get('employment_type', '').strip()
# OLD CODE:         category = request.form.get('category', 'Other')
# OLD CODE:         if category not in JOB_CATEGORIES:
# OLD CODE:             category = 'Other'
# OLD CODE:         interview_length = request.form.get('interview_length', 'standard')
# OLD CODE:         if interview_length not in INTERVIEW_LENGTH_OPTIONS:
# OLD CODE:             interview_length = 'standard'
# OLD CODE:         camera_required = request.form.get('camera_required') == '1'
# OLD CODE:         interview_focus = request.form.get('interview_focus', '').strip()
# OLD CODE:         interview_questions = _parse_interview_questions(request.form.get('interview_questions', ''))
# OLD CODE:
# OLD CODE:         if not title or not description:
# OLD CODE:             flash("Title and description are required.", "error")
# OLD CODE:             return render_template(
# OLD CODE:                 "post_job.html", categories=JOB_CATEGORIES, locations=JOB_LOCATIONS,
# OLD CODE:                 interview_lengths=INTERVIEW_LENGTH_OPTIONS, currencies=SUPPORTED_CURRENCIES,
# OLD CODE:                 interview_questions=json.loads(interview_questions) if interview_questions else [],
# OLD CODE:             )
# OLD CODE:
# OLD CODE:         salary_raw = request.form.get('salary_usd', '').strip()
# OLD CODE:         salary_usd = int(salary_raw) if salary_raw.isdigit() else None
# OLD CODE:         salary_max_raw = request.form.get('salary_max_usd', '').strip()
# OLD CODE:         salary_max_usd = int(salary_max_raw) if salary_max_raw.isdigit() else None
# OLD CODE:         pay_type = request.form.get('pay_type', 'yearly')
# OLD CODE:         if pay_type not in ('yearly', 'hourly', 'monthly', 'stipend', 'contract'):
# OLD CODE:             pay_type = 'yearly'
# OLD CODE:         salary_currency = request.form.get('salary_currency', DEFAULT_CURRENCY)
# OLD CODE:         if salary_currency not in SUPPORTED_CURRENCIES:
# OLD CODE:             salary_currency = DEFAULT_CURRENCY
# OLD CODE:         save_as_draft = request.form.get('save_as_draft') == '1'
# OLD CODE:
# OLD CODE:         if not save_as_draft and not salary_usd:
# OLD CODE:             flash("An estimated salary is required to post a job - candidates need to see it before applying.", "error")
# OLD CODE:             return render_template(
# OLD CODE:                 "post_job.html", categories=JOB_CATEGORIES, locations=JOB_LOCATIONS,
# OLD CODE:                 interview_lengths=INTERVIEW_LENGTH_OPTIONS, currencies=SUPPORTED_CURRENCIES,
# OLD CODE:                 interview_questions=json.loads(interview_questions) if interview_questions else [],
# OLD CODE:             )
# OLD CODE:
# OLD CODE:         job = Job(
# OLD CODE:             company_id=company.id,
# OLD CODE:             title=title,
# OLD CODE:             description=description,
# OLD CODE:             location=location,
# OLD CODE:             employment_type=employment_type,
# OLD CODE:             category=category,
# OLD CODE:             interview_length=interview_length,
# OLD CODE:             camera_required=camera_required,
# OLD CODE:             interview_focus=interview_focus or None,
# OLD CODE:             interview_questions=interview_questions,
# OLD CODE:             salary_usd=salary_usd,
# OLD CODE:             salary_max_usd=salary_max_usd,
# OLD CODE:             pay_type=pay_type,
# OLD CODE:             salary_currency=salary_currency,
# OLD CODE:             status='draft' if save_as_draft else 'open',
# OLD CODE:         )
# OLD CODE:         db.session.add(job)
# OLD CODE:         db.session.commit()
# OLD CODE:         if save_as_draft:
# OLD CODE:             flash("Job saved as draft.", "success")
# OLD CODE:         else:
# OLD CODE:             notify_candidates_of_new_job(job, company)
# OLD CODE:             db.session.commit()
# OLD CODE:             flash("Job posted successfully!", "success")
# OLD CODE:         return redirect(url_for('employer.dashboard'))
# OLD CODE:
# OLD CODE:     return render_template(
# OLD CODE:         "post_job.html",
# OLD CODE:         categories=JOB_CATEGORIES,
# OLD CODE:         locations=JOB_LOCATIONS,
# OLD CODE:         interview_lengths=INTERVIEW_LENGTH_OPTIONS,
# OLD CODE:         currencies=SUPPORTED_CURRENCIES,
# OLD CODE:         interview_questions=[],
# OLD CODE:     )
# OLD CODE:
# OLD CODE:
# OLD CODE: @employer.route('/employer/jobs/<int:job_id>/edit', methods=['GET', 'POST'])
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: def edit_job(job_id):
# OLD CODE:     company = get_owned_company()
# OLD CODE:     job = Job.query.get_or_404(job_id)
# OLD CODE:     if job.company_id != company.id:
# OLD CODE:         abort(403)
# OLD CODE:
# OLD CODE:     if request.method == 'POST':
# OLD CODE:         title = request.form.get('title', '').strip()
# OLD CODE:         description = request.form.get('description', '').strip()
# OLD CODE:         category = request.form.get('category', 'Other')
# OLD CODE:         if category not in JOB_CATEGORIES:
# OLD CODE:             category = 'Other'
# OLD CODE:         interview_length = request.form.get('interview_length', 'standard')
# OLD CODE:         if interview_length not in INTERVIEW_LENGTH_OPTIONS:
# OLD CODE:             interview_length = 'standard'
# OLD CODE:
# OLD CODE:         if not title or not description:
# OLD CODE:             flash("Title and description are required.", "error")
# OLD CODE:             return render_template(
# OLD CODE:                 "post_job.html", job=job, categories=JOB_CATEGORIES, locations=JOB_LOCATIONS,
# OLD CODE:                 interview_lengths=INTERVIEW_LENGTH_OPTIONS, currencies=SUPPORTED_CURRENCIES,
# OLD CODE:                 interview_questions=_existing_interview_questions(job),
# OLD CODE:             )
# OLD CODE:
# OLD CODE:         salary_raw = request.form.get('salary_usd', '').strip()
# OLD CODE:         salary_max_raw = request.form.get('salary_max_usd', '').strip()
# OLD CODE:         save_as_draft = request.form.get('save_as_draft') == '1'
# OLD CODE:         pay_type = request.form.get('pay_type', 'yearly')
# OLD CODE:         if pay_type not in ('yearly', 'hourly', 'monthly', 'stipend', 'contract'):
# OLD CODE:             pay_type = 'yearly'
# OLD CODE:         salary_currency = request.form.get('salary_currency', DEFAULT_CURRENCY)
# OLD CODE:         if salary_currency not in SUPPORTED_CURRENCIES:
# OLD CODE:             salary_currency = DEFAULT_CURRENCY
# OLD CODE:
# OLD CODE:         if not save_as_draft and not salary_raw.isdigit():
# OLD CODE:             flash("An estimated salary is required to post a job - candidates need to see it before applying.", "error")
# OLD CODE:             return render_template(
# OLD CODE:                 "post_job.html", job=job, categories=JOB_CATEGORIES, locations=JOB_LOCATIONS,
# OLD CODE:                 interview_lengths=INTERVIEW_LENGTH_OPTIONS, currencies=SUPPORTED_CURRENCIES,
# OLD CODE:                 interview_questions=_existing_interview_questions(job),
# OLD CODE:             )
# OLD CODE:
# OLD CODE:         was_open = job.status == 'open'
# OLD CODE:         _edit_work_type = request.form.get('work_type', 'Remote (Worldwide)').strip()
# OLD CODE:         _edit_city = request.form.get('location_city', '').strip()
# OLD CODE:         job.title = title
# OLD CODE:         job.description = description
# OLD CODE:         job.location = f"{_edit_work_type} - {_edit_city}" if _edit_work_type in ('Hybrid', 'On-site') and _edit_city else _edit_work_type
# OLD CODE:         job.employment_type = request.form.get('employment_type', '').strip()
# OLD CODE:         job.category = category
# OLD CODE:         job.interview_length = interview_length
# OLD CODE:         job.camera_required = request.form.get('camera_required') == '1'
# OLD CODE:         job.interview_focus = request.form.get('interview_focus', '').strip() or None
# OLD CODE:         job.interview_questions = _parse_interview_questions(request.form.get('interview_questions', ''))
# OLD CODE:         if save_as_draft:
# OLD CODE:             job.status = 'draft'
# OLD CODE:         else:
# OLD CODE:             submitted_status = request.form.get('status', 'open')
# OLD CODE:             job.status = submitted_status if submitted_status in ('open', 'closed') else 'open'
# OLD CODE:         job.salary_usd = int(salary_raw) if salary_raw.isdigit() else None
# OLD CODE:         job.salary_max_usd = int(salary_max_raw) if salary_max_raw.isdigit() else None
# OLD CODE:         job.pay_type = pay_type
# OLD CODE:         job.salary_currency = salary_currency
# OLD CODE:         db.session.commit()
# OLD CODE:         if not was_open and job.status == 'open':
# OLD CODE:             notify_candidates_of_new_job(job, company)
# OLD CODE:             db.session.commit()
# OLD CODE:         flash("Draft saved." if save_as_draft else "Job updated!", "success")
# OLD CODE:         return redirect(url_for('employer.dashboard'))
# OLD CODE:
# OLD CODE:     return render_template(
# OLD CODE:         "post_job.html", job=job, categories=JOB_CATEGORIES, locations=JOB_LOCATIONS,
# OLD CODE:         interview_lengths=INTERVIEW_LENGTH_OPTIONS, currencies=SUPPORTED_CURRENCIES,
# OLD CODE:         interview_questions=_existing_interview_questions(job),
# OLD CODE:     )
# OLD CODE:
# OLD CODE:
# OLD CODE: @employer.route('/employer/jobs/<int:job_id>/publish', methods=['POST'])
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: def publish_job(job_id):
# OLD CODE:     company = get_owned_company()
# OLD CODE:     job = Job.query.get_or_404(job_id)
# OLD CODE:     if job.company_id != company.id:
# OLD CODE:         abort(403)
# OLD CODE:     if not job.salary_usd:
# OLD CODE:         flash("Add an estimated salary before publishing - candidates need to see it before applying.", "error")
# OLD CODE:         return redirect(url_for('employer.edit_job', job_id=job.id))
# OLD CODE:     job.status = 'open'
# OLD CODE:     db.session.commit()
# OLD CODE:     notify_candidates_of_new_job(job, company)
# OLD CODE:     db.session.commit()
# OLD CODE:     flash("Job published successfully.", "success")
# OLD CODE:     return redirect(url_for('employer.dashboard'))
# OLD CODE:
# OLD CODE:
# OLD CODE: @employer.route('/employer/jobs/<int:job_id>/toggle-status', methods=['POST'])
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: def toggle_job_status(job_id):
# OLD CODE:     """One-click close/reopen - the alternative to delete() when a job has
# OLD CODE:     applicants and can't be permanently removed."""
# OLD CODE:     company = get_owned_company()
# OLD CODE:     job = Job.query.get_or_404(job_id)
# OLD CODE:     if job.company_id != company.id:
# OLD CODE:         abort(403)
# OLD CODE:     if job.status not in ('open', 'closed'):
# OLD CODE:         abort(400)
# OLD CODE:     job.status = 'closed' if job.status == 'open' else 'open'
# OLD CODE:     db.session.commit()
# OLD CODE:     flash(f"Job {'closed' if job.status == 'closed' else 'reopened'}.", "success")
# OLD CODE:     return redirect(url_for('employer.dashboard'))
# OLD CODE:
# OLD CODE:
# OLD CODE: @employer.route('/employer/jobs/<int:job_id>/delete', methods=['POST'])
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: def delete_job(job_id):
# OLD CODE:     company = get_owned_company()
# OLD CODE:     job = Job.query.get_or_404(job_id)
# OLD CODE:     if job.company_id != company.id:
# OLD CODE:         abort(403)
# OLD CODE:
# OLD CODE:     if Application.query.filter_by(job_id=job.id).count() > 0:
# OLD CODE:         flash("This job has applicants, so it can't be deleted - close it instead to stop new applications while keeping candidate history.", "error")
# OLD CODE:         return redirect(url_for('employer.dashboard'))
# OLD CODE:
# OLD CODE:     db.session.add(DeletedJob(
# OLD CODE:         original_job_id=job.id,
# OLD CODE:         company_id=company.id,
# OLD CODE:         company_name=company.name,
# OLD CODE:         title=job.title,
# OLD CODE:         snapshot=json.dumps(job.to_snapshot_dict()),
# OLD CODE:         applicant_count=0,
# OLD CODE:         deleted_by_user_id=current_user.id,
# OLD CODE:         deleted_source='employer',
# OLD CODE:     ))
# OLD CODE:     SavedJob.query.filter_by(job_id=job.id).delete()
# OLD CODE:     db.session.delete(job)
# OLD CODE:     db.session.commit()
# OLD CODE:     flash("Job deleted. You can restore it from Deleted Jobs within 30 days.", "success")
# OLD CODE:     return redirect(url_for('employer.dashboard'))
# OLD CODE:
# OLD CODE:
# OLD CODE: @employer.route('/employer/deleted-jobs')
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: def deleted_jobs():
# OLD CODE:     company = get_owned_company()
# OLD CODE:     cutoff = datetime.now(timezone.utc) - timedelta(days=30)
# OLD CODE:     history = DeletedJob.query.filter(
# OLD CODE:         DeletedJob.company_id == company.id,
# OLD CODE:         DeletedJob.restored_job_id.is_(None),
# OLD CODE:         DeletedJob.created_at >= cutoff,
# OLD CODE:     ).order_by(DeletedJob.created_at.desc()).all()
# OLD CODE:     return render_template('deleted_jobs.html', history=history)
# OLD CODE:
# OLD CODE:
# OLD CODE: @employer.route('/employer/deleted-jobs/<int:history_id>/restore', methods=['POST'])
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: def restore_job(history_id):
# OLD CODE:     company = get_owned_company()
# OLD CODE:     entry = DeletedJob.query.get_or_404(history_id)
# OLD CODE:     if entry.company_id != company.id:
# OLD CODE:         abort(403)
# OLD CODE:     if entry.restored_job_id:
# OLD CODE:         flash("That job was already restored.", "error")
# OLD CODE:         return redirect(url_for('employer.deleted_jobs'))
# OLD CODE:
# OLD CODE:     data = json.loads(entry.snapshot)
# OLD CODE:     job = Job(company_id=company.id, **data)
# OLD CODE:     db.session.add(job)
# OLD CODE:     db.session.flush()
# OLD CODE:     entry.restored_job_id = job.id
# OLD CODE:     db.session.commit()
# OLD CODE:     flash(f'"{job.title}" restored.', "success")
# OLD CODE:     return redirect(url_for('employer.dashboard'))
# OLD CODE:
# OLD CODE:
# OLD CODE: @employer.route('/employer/preview-interview-questions', methods=['POST'])
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: @limiter.limit("15 per hour")
# OLD CODE: def preview_interview_questions():
# OLD CODE:     data = request.get_json() or {}
# OLD CODE:     title = (data.get('title') or '').strip()
# OLD CODE:     description = _extract_description_text(data.get('description') or '')
# OLD CODE:     interview_length = data.get('interview_length', 'standard')
# OLD CODE:     interview_focus = (data.get('interview_focus') or '').strip()
# OLD CODE:
# OLD CODE:     if not title or not description:
# OLD CODE:         return jsonify({"error": "Add a job title and description first."}), 400
# OLD CODE:
# OLD CODE:     try:
# OLD CODE:         questions = generate_interview_question_preview(title, description, interview_length, interview_focus)
# OLD CODE:         return jsonify({"questions": questions})
# OLD CODE:     except Exception as e:
# OLD CODE:         logger.exception("preview-interview-questions failed")
# OLD CODE:         msg = str(e)
# OLD CODE:         if "api_key" in msg.lower() or "authentication" in msg.lower():
# OLD CODE:             return jsonify({"error": "OpenAI API key is missing or invalid. Check your environment config."}), 500
# OLD CODE:         if "rate" in msg.lower():
# OLD CODE:             return jsonify({"error": "Rate limit hit. Wait a moment and try again."}), 429
# OLD CODE:         return jsonify({"error": f"Failed to generate questions: {msg}"}), 500
# OLD CODE:
# OLD CODE:
# OLD CODE: @employer.route('/employer/transcribe-question', methods=['POST'])
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: @limiter.limit("20 per hour")
# OLD CODE: def transcribe_question():
# OLD CODE:     """Speech-to-text for an employer recording a custom interview question by voice."""
# OLD CODE:     audio = request.files.get('audio')
# OLD CODE:     if not audio or not audio.filename:
# OLD CODE:         return jsonify({"error": "No audio received."}), 400
# OLD CODE:
# OLD CODE:     import tempfile
# OLD CODE:     tmp_path = None
# OLD CODE:     try:
# OLD CODE:         with tempfile.NamedTemporaryFile(suffix=audio_file_extension(audio.filename), delete=False) as tmp:
# OLD CODE:             audio.save(tmp.name)
# OLD CODE:             tmp_path = tmp.name
# OLD CODE:         text = transcribe_audio(tmp_path)
# OLD CODE:     except Exception:
# OLD CODE:         logger.exception("transcribe-question failed")
# OLD CODE:         return jsonify({"error": "Couldn't transcribe that recording. Try again or type the question."}), 500
# OLD CODE:     finally:
# OLD CODE:         if tmp_path:
# OLD CODE:             os.unlink(tmp_path)
# OLD CODE:
# OLD CODE:     if not text:
# OLD CODE:         return jsonify({"error": "Didn't catch any speech - try recording again."}), 400
# OLD CODE:     return jsonify({"text": text})
# OLD CODE:
# OLD CODE:
# OLD CODE: @employer.route('/employer/jobs/<int:job_id>/score-resume', methods=['POST'])
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: @limiter.limit("20 per hour")
# OLD CODE: def score_resume(job_id):
# OLD CODE:     """Score an externally-sourced resume (referral, LinkedIn candidate, etc.)
# OLD CODE:     against one of this employer's jobs - no application gets created, this
# OLD CODE:     is just a quick sourcing/screening check."""
# OLD CODE:     company = get_owned_company()
# OLD CODE:     job = Job.query.get_or_404(job_id)
# OLD CODE:     if job.company_id != company.id:
# OLD CODE:         abort(403)
# OLD CODE:
# OLD CODE:     data = request.get_json() or {}
# OLD CODE:     resume_text = (data.get('resume_text') or '').strip()
# OLD CODE:     if not resume_text:
# OLD CODE:         return jsonify({"error": "Add resume content first."}), 400
# OLD CODE:
# OLD CODE:     try:
# OLD CODE:         result = compare_resume_to_job(job.description_text, resume_text)
# OLD CODE:     except Exception:
# OLD CODE:         logger.exception("score-resume failed")
# OLD CODE:         return jsonify({"error": "Failed to score this resume. Please try again."}), 500
# OLD CODE:
# OLD CODE:     score = _extract_score(result)
# OLD CODE:     return jsonify({"score": score, "explanation": result.replace('*', '')})
# OLD CODE:
# OLD CODE:
# OLD CODE: # ------------------------------------------------------------------ #
# OLD CODE: #  Applicants
# OLD CODE: # ------------------------------------------------------------------ #
# OLD CODE:
# OLD CODE: @employer.route('/employer/jobs/<int:job_id>/applicants')
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: def applicants(job_id):
# OLD CODE:     company = get_owned_company()
# OLD CODE:     job = Job.query.get_or_404(job_id)
# OLD CODE:     if job.company_id != company.id:
# OLD CODE:         abort(403)
# OLD CODE:
# OLD CODE:     applications = Application.query.filter_by(job_id=job.id).all()
# OLD CODE:     summaries = {app.id: summarize_explanation(app.match_explanation) for app in applications}
# OLD CODE:     audio_logs = {
# OLD CODE:         app.id: json.loads(app.interview_audio_log) if app.interview_audio_log else []
# OLD CODE:         for app in applications
# OLD CODE:     }
# OLD CODE:     ai_likelihoods = {
# OLD CODE:         app.id: json.loads(app.ai_likelihood) if app.ai_likelihood else None
# OLD CODE:         for app in applications
# OLD CODE:     }
# OLD CODE:     work_auths = {
# OLD CODE:         app.id: json.loads(app.work_authorization) if app.work_authorization else None
# OLD CODE:         for app in applications
# OLD CODE:     }
# OLD CODE:     meetings = {
# OLD CODE:         app.id: json.loads(app.scheduled_meeting) if app.scheduled_meeting else None
# OLD CODE:         for app in applications
# OLD CODE:     }
# OLD CODE:     profiles = {
# OLD CODE:         app.candidate_user_id: CandidateProfile.query.filter_by(user_id=app.candidate_user_id).first()
# OLD CODE:         for app in applications
# OLD CODE:     }
# OLD CODE:
# OLD CODE:     composite_scores = {
# OLD CODE:         app.id: compute_composite_score(app, ai_likelihoods.get(app.id))
# OLD CODE:         for app in applications
# OLD CODE:     }
# OLD CODE:     applications.sort(key=lambda a: composite_scores[a.id], reverse=True)
# OLD CODE:
# OLD CODE:     # Blind mode: assign anonymous IDs in composite-score order
# OLD CODE:     blind_labels = {}
# OLD CODE:     if company.blind_mode_enabled:
# OLD CODE:         for i, app in enumerate(applications, 1):
# OLD CODE:             blind_labels[app.id] = f"Candidate #{i}"
# OLD CODE:
# OLD CODE:     # Feedback prompt once a hire is fully closed out (employer marked hired,
# OLD CODE:     # candidate confirmed the compensation figure) and this employer hasn't
# OLD CODE:     # already rated the experience.
# OLD CODE:     already_rated = {
# OLD CODE:         f.application_id
# OLD CODE:         for f in Feedback.query.filter_by(user_id=current_user.id, role='employer', context='hire_closed').all()
# OLD CODE:     }
# OLD CODE:     feedback_prompt_ids = {
# OLD CODE:         app.id for app in applications
# OLD CODE:         if app.status == 'hired' and app.hire_confirmed_at and app.id not in already_rated
# OLD CODE:     }
# OLD CODE:
# OLD CODE:     return render_template(
# OLD CODE:         "job_applicants.html",
# OLD CODE:         job=job,
# OLD CODE:         applications=applications,
# OLD CODE:         summaries=summaries,
# OLD CODE:         audio_logs=audio_logs,
# OLD CODE:         work_auths=work_auths,
# OLD CODE:         meetings=meetings,
# OLD CODE:         profiles=profiles,
# OLD CODE:         blind_mode=company.blind_mode_enabled,
# OLD CODE:         blind_labels=blind_labels,
# OLD CODE:         ai_likelihoods=ai_likelihoods,
# OLD CODE:         composite_scores=composite_scores,
# OLD CODE:         feedback_prompt_ids=feedback_prompt_ids,
# OLD CODE:         verdict_score_map=_VERDICT_SCORE,
# OLD CODE:     )
# OLD CODE:
# OLD CODE:
# OLD CODE: @employer.route('/employer/applications/<int:application_id>/schedule-meeting', methods=['POST'])
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: def schedule_meeting(application_id):
# OLD CODE:     company = get_owned_company()
# OLD CODE:     application = Application.query.get_or_404(application_id)
# OLD CODE:     job = Job.query.get_or_404(application.job_id)
# OLD CODE:     if job.company_id != company.id:
# OLD CODE:         abort(403)
# OLD CODE:
# OLD CODE:     meeting_type = request.form.get('meeting_type')
# OLD CODE:     date = request.form.get('date', '').strip()
# OLD CODE:     time = request.form.get('time', '').strip()
# OLD CODE:     location_or_url = request.form.get('location_or_url', '').strip()
# OLD CODE:     notes = request.form.get('notes', '').strip()
# OLD CODE:
# OLD CODE:     if meeting_type not in ('virtual', 'in_person') or not date or not time or not location_or_url:
# OLD CODE:         flash("Date, time, and a meeting link or address are required.", "error")
# OLD CODE:         return redirect(url_for('employer.applicants', job_id=job.id))
# OLD CODE:
# OLD CODE:     meeting = {"type": meeting_type, "date": date, "time": time, "location_or_url": location_or_url, "notes": notes}
# OLD CODE:     application.scheduled_meeting = json.dumps(meeting)
# OLD CODE:     db.session.commit()
# OLD CODE:
# OLD CODE:     kind_label = "video call" if meeting_type == 'virtual' else "in-person meeting"
# OLD CODE:     where_label = f"Link: {location_or_url}" if meeting_type == 'virtual' else f"Location: {location_or_url}"
# OLD CODE:     candidate = application.candidate
# OLD CODE:     try:
# OLD CODE:         send_branded_email(
# OLD CODE:             to_email=candidate.email,
# OLD CODE:             subject=f"Meeting scheduled - {job.title} at {company.name}",
# OLD CODE:             heading="A meeting has been scheduled",
# OLD CODE:             body_html=(
# OLD CODE:                 f"Hi {candidate.first_name or ''},<br><br>"
# OLD CODE:                 f"<strong>{company.name}</strong> would like to meet with you about your application for "
# OLD CODE:                 f"<strong>{job.title}</strong>.<br><br>"
# OLD CODE:                 f"<strong>Type:</strong> {kind_label}<br>"
# OLD CODE:                 f"<strong>Date:</strong> {date}<br>"
# OLD CODE:                 f"<strong>Time:</strong> {time}<br>"
# OLD CODE:                 f"<strong>{'Link' if meeting_type == 'virtual' else 'Location'}:</strong> {location_or_url}"
# OLD CODE:                 + (f"<br><br><strong>Notes:</strong> {notes}" if notes else "")
# OLD CODE:             ),
# OLD CODE:             plain_text=(
# OLD CODE:                 f"Hi {candidate.first_name or ''},\n\n"
# OLD CODE:                 f"{company.name} would like to meet with you about your application for {job.title}.\n\n"
# OLD CODE:                 f"Type: {kind_label}\nDate: {date}\nTime: {time}\n{where_label}\n"
# OLD CODE:                 + (f"\nNotes: {notes}\n" if notes else "")
# OLD CODE:             ),
# OLD CODE:             cta_label="View My Applications" if meeting_type == 'virtual' else None,
# OLD CODE:             cta_url=external_url('candidate.dashboard') if meeting_type == 'virtual' else None,
# OLD CODE:         )
# OLD CODE:         flash("Meeting scheduled and the candidate has been emailed.", "success")
# OLD CODE:     except Exception as e:
# OLD CODE:         print("Meeting email send failed:", e)
# OLD CODE:         flash("Meeting saved, but the notification email couldn't be sent.", "error")
# OLD CODE:
# OLD CODE:     return redirect(url_for('employer.applicants', job_id=job.id))
# OLD CODE:
# OLD CODE:
# OLD CODE: @employer.route('/employer/applications/<int:application_id>/status', methods=['POST'])
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: def update_status(application_id):
# OLD CODE:     company = get_owned_company()
# OLD CODE:     application = Application.query.get_or_404(application_id)
# OLD CODE:     job = Job.query.get_or_404(application.job_id)
# OLD CODE:     if job.company_id != company.id:
# OLD CODE:         abort(403)
# OLD CODE:
# OLD CODE:     new_status = request.form.get('status')
# OLD CODE:     is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
# OLD CODE:
# OLD CODE:     if new_status in ('applied', 'interviewing', 'rejected', 'hired'):
# OLD CODE:         # Hired/rejected are final decisions - the employer can't walk one
# OLD CODE:         # back to a different status later. (Resubmitting the SAME status is
# OLD CODE:         # still allowed - that's how a disputed hire salary gets corrected.)
# OLD CODE:         if application.status in ('hired', 'rejected') and new_status != application.status:
# OLD CODE:             message = f"This application was already marked \"{application.status}\" - that decision is final and can't be changed."
# OLD CODE:             if is_ajax:
# OLD CODE:                 return jsonify({"status": "error", "error": message}), 400
# OLD CODE:             flash(message, "error")
# OLD CODE:             return redirect(url_for('employer.applicants', job_id=job.id))
# OLD CODE:
# OLD CODE:         if new_status == 'hired':
# OLD CODE:             # The placement fee is based on this figure, not the job posting's
# OLD CODE:             # advertised salary - require it up front rather than invoicing
# OLD CODE:             # off a number the employer has no incentive to keep accurate.
# OLD CODE:             salary_raw = request.form.get('hire_salary_usd', '').strip()
# OLD CODE:             pay_type = request.form.get('hire_pay_type', '').strip()
# OLD CODE:             try:
# OLD CODE:                 salary_value = int(float(salary_raw)) if salary_raw else None
# OLD CODE:             except ValueError:
# OLD CODE:                 salary_value = None
# OLD CODE:             if not salary_value or salary_value <= 0 or pay_type not in ('yearly', 'hourly', 'monthly', 'stipend', 'contract'):
# OLD CODE:                 flash("Enter the candidate's actual compensation (amount and pay type) to mark them hired - the placement fee is calculated from this, not the job posting.", "error")
# OLD CODE:                 return redirect(url_for('employer.applicants', job_id=job.id))
# OLD CODE:
# OLD CODE:             application.hire_salary_usd = salary_value
# OLD CODE:             application.hire_pay_type = pay_type
# OLD CODE:             application.hire_salary_disputed = False  # fresh hire event, not yet re-disputed
# OLD CODE:
# OLD CODE:             evidence_filename = _save_hire_evidence(application.id, request.files.get('hire_evidence'))
# OLD CODE:             if evidence_filename:
# OLD CODE:                 application.hire_evidence_filename = evidence_filename
# OLD CODE:
# OLD CODE:         status_changed = application.status != new_status
# OLD CODE:         application.status = new_status
# OLD CODE:         db.session.commit()
# OLD CODE:
# OLD CODE:         copy = STATUS_EMAIL_COPY.get(new_status)
# OLD CODE:         if status_changed and copy:
# OLD CODE:             candidate = application.candidate
# OLD CODE:
# OLD CODE:             if new_status == 'hired':
# OLD CODE:                 # Reset confirmation state - this is a fresh hire event, not yet verified by the candidate.
# OLD CODE:                 # The placement fee invoice only fires once they confirm (see candidate.confirm_hire).
# OLD CODE:                 application.candidate_confirmed_hire = False
# OLD CODE:                 application.hire_confirmed_at = None
# OLD CODE:                 db.session.commit()
# OLD CODE:
# OLD CODE:             if candidate.notifications_enabled:
# OLD CODE:                 notif_messages = {
# OLD CODE:                     "interviewing": f"Your application for {job.title} at {company.name} is moving forward!",
# OLD CODE:                     "hired": f"Congratulations! {company.name} has hired you for {job.title}.",
# OLD CODE:                     "rejected": f"Update on your application for {job.title} at {company.name}.",
# OLD CODE:                 }
# OLD CODE:                 notif = Notification(
# OLD CODE:                     user_id=candidate.id,
# OLD CODE:                     message=notif_messages.get(new_status, f"Your application status changed to {new_status}."),
# OLD CODE:                     link=url_for('candidate.dashboard', _external=False),
# OLD CODE:                 )
# OLD CODE:                 db.session.add(notif)
# OLD CODE:                 db.session.commit()
# OLD CODE:
# OLD CODE:             try:
# OLD CODE:                 if new_status == 'hired':
# OLD CODE:                     # Email the candidate - congratulations + ask them to confirm the hire.
# OLD CODE:                     # The employer isn't invoiced for the placement fee until the candidate confirms.
# OLD CODE:                     send_branded_email(
# OLD CODE:                         to_email=candidate.email,
# OLD CODE:                         subject=f"You're hired - {job.title}",
# OLD CODE:                         heading="You got the job!",
# OLD CODE:                         body_html=(
# OLD CODE:                             f"Congratulations - <strong>{company.name}</strong> has decided to move forward "
# OLD CODE:                             f"with you for the <strong>{job.title}</strong> role!<br><br>"
# OLD CODE:                             f"Please confirm the hire on your dashboard so we can let {company.name} know. "
# OLD CODE:                             f"Best of luck in your new role!"
# OLD CODE:                         ),
# OLD CODE:                         plain_text=(
# OLD CODE:                             f"Congratulations - {company.name} has offered you the {job.title} role! "
# OLD CODE:                             f"Please confirm the hire on your dashboard."
# OLD CODE:                         ),
# OLD CODE:                         cta_label="Confirm My Hire",
# OLD CODE:                         cta_url=external_url('candidate.dashboard'),
# OLD CODE:                     )
# OLD CODE:                 else:
# OLD CODE:                     send_branded_email(
# OLD CODE:                         to_email=candidate.email,
# OLD CODE:                         subject=copy["subject_tpl"].format(job_title=job.title),
# OLD CODE:                         heading=copy["heading"],
# OLD CODE:                         body_html=copy["body_tpl"].format(company=company.name, job_title=job.title),
# OLD CODE:                         plain_text=copy["body_tpl"].format(company=company.name, job_title=job.title).replace("<strong>", "").replace("</strong>", ""),
# OLD CODE:                         cta_label="View My Applications",
# OLD CODE:                         cta_url=external_url('candidate.dashboard'),
# OLD CODE:                     )
# OLD CODE:             except Exception as e:
# OLD CODE:                 print(f"Status email send failed ({new_status}):", e)
# OLD CODE:         # For rejections, if the caller wants JSON (AJAX), return a feedback draft
# OLD CODE:         if new_status == 'rejected' and status_changed and is_ajax:
# OLD CODE:             try:
# OLD CODE:                 draft = generate_rejection_feedback(
# OLD CODE:                     job_title=job.title,
# OLD CODE:                     company_name=company.name,
# OLD CODE:                     match_score=application.match_score,
# OLD CODE:                     match_explanation=application.match_explanation or '',
# OLD CODE:                     interview_verdict=application.interview_verdict,
# OLD CODE:                     interview_transcript=application.interview_transcript or '',
# OLD CODE:                 )
# OLD CODE:             except Exception:
# OLD CODE:                 draft = ""
# OLD CODE:             return jsonify({
# OLD CODE:                 "status": "ok",
# OLD CODE:                 "application_id": application.id,
# OLD CODE:                 "candidate_name": application.candidate.first_name,
# OLD CODE:                 "feedback_draft": draft,
# OLD CODE:                 "redirect": url_for('employer.applicants', job_id=job.id),
# OLD CODE:             })
# OLD CODE:
# OLD CODE:         flash("Status updated.", "success")
# OLD CODE:
# OLD CODE:     return redirect(url_for('employer.applicants', job_id=job.id))
# OLD CODE:
# OLD CODE:
# OLD CODE: @employer.route('/employer/applications/<int:application_id>/hire-evidence')
# OLD CODE: @login_required
# OLD CODE: def hire_evidence(application_id):
# OLD CODE:     """Serves the optional hire-salary evidence upload. Viewable by the
# OLD CODE:     employer who owns the job or the candidate the application belongs to -
# OLD CODE:     nobody else."""
# OLD CODE:     application = Application.query.get_or_404(application_id)
# OLD CODE:     job = Job.query.get_or_404(application.job_id)
# OLD CODE:
# OLD CODE:     user_company = get_user_company() if current_user.role == 'employer' else None
# OLD CODE:     is_owning_employer = user_company is not None and job.company_id == user_company.id
# OLD CODE:     is_owning_candidate = current_user.id == application.candidate_user_id
# OLD CODE:     if not (is_owning_employer or is_owning_candidate):
# OLD CODE:         abort(403)
# OLD CODE:     if not application.hire_evidence_filename:
# OLD CODE:         abort(404)
# OLD CODE:     return send_from_directory(_hire_evidence_dir(), application.hire_evidence_filename)
# OLD CODE:
# OLD CODE:
# OLD CODE: @employer.route('/employer/applications/<int:application_id>/end-hourly-engagement', methods=['POST'])
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: def end_hourly_engagement(application_id):
# OLD CODE:     """Cancels the recurring monthly placement-fee subscription for an
# OLD CODE:     hourly hire once the engagement actually ends, so billing stops instead
# OLD CODE:     of continuing to charge for work that isn't happening anymore."""
# OLD CODE:     company = get_owned_company()
# OLD CODE:     application = Application.query.get_or_404(application_id)
# OLD CODE:     job = Job.query.get_or_404(application.job_id)
# OLD CODE:     if job.company_id != company.id:
# OLD CODE:         abort(403)
# OLD CODE:
# OLD CODE:     if not application.hire_billing_subscription_id:
# OLD CODE:         flash("No active billing subscription found for this hire.", "error")
# OLD CODE:         return redirect(url_for('employer.applicants', job_id=job.id))
# OLD CODE:     if application.hire_engagement_ended_at:
# OLD CODE:         flash("This engagement is already marked as ended.", "info")
# OLD CODE:         return redirect(url_for('employer.applicants', job_id=job.id))
# OLD CODE:
# OLD CODE:     stripe.api_key = current_app.config.get("STRIPE_SECRET_KEY")
# OLD CODE:     try:
# OLD CODE:         stripe.Subscription.cancel(application.hire_billing_subscription_id)
# OLD CODE:     except Exception as e:
# OLD CODE:         logger.error(f"Failed to cancel Stripe subscription {application.hire_billing_subscription_id}: {e}")
# OLD CODE:         flash("Couldn't reach Stripe to cancel billing. Please try again or cancel it directly in your Stripe dashboard.", "error")
# OLD CODE:         return redirect(url_for('employer.applicants', job_id=job.id))
# OLD CODE:
# OLD CODE:     application.hire_engagement_ended_at = func.now()
# OLD CODE:     db.session.commit()
# OLD CODE:     flash("Engagement marked as ended - monthly billing has been stopped.", "success")
# OLD CODE:     return redirect(url_for('employer.applicants', job_id=job.id))
# OLD CODE:
# OLD CODE:
# OLD CODE: @employer.route('/employer/applications/<int:application_id>/platform-feedback', methods=['POST'])
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: def submit_platform_feedback(application_id):
# OLD CODE:     """Employer rating their own experience hiring through Avants - distinct
# OLD CODE:     from send_candidate_feedback() below, which sends feedback TO a candidate
# OLD CODE:     about their application."""
# OLD CODE:     company = get_owned_company()
# OLD CODE:     application = Application.query.get_or_404(application_id)
# OLD CODE:     job = Job.query.get_or_404(application.job_id)
# OLD CODE:     if job.company_id != company.id:
# OLD CODE:         abort(403)
# OLD CODE:
# OLD CODE:     rating = request.form.get('rating', type=int)
# OLD CODE:     if not rating or rating < 1 or rating > 5:
# OLD CODE:         flash("Please select a rating from 1 to 5.", "error")
# OLD CODE:         return redirect(url_for('employer.applicants', job_id=job.id))
# OLD CODE:
# OLD CODE:     comment = (request.form.get('comment') or '').strip()
# OLD CODE:
# OLD CODE:     existing = Feedback.query.filter_by(
# OLD CODE:         user_id=current_user.id, application_id=application_id, context='hire_closed'
# OLD CODE:     ).first()
# OLD CODE:     if not existing:
# OLD CODE:         db.session.add(Feedback(
# OLD CODE:             user_id=current_user.id,
# OLD CODE:             application_id=application_id,
# OLD CODE:             role='employer',
# OLD CODE:             context='hire_closed',
# OLD CODE:             rating=rating,
# OLD CODE:             comment=comment or None,
# OLD CODE:         ))
# OLD CODE:         db.session.commit()
# OLD CODE:
# OLD CODE:     flash("Thanks for the feedback!", "success")
# OLD CODE:     return redirect(url_for('employer.applicants', job_id=job.id))
# OLD CODE:
# OLD CODE:
# OLD CODE: @employer.route('/employer/applications/<int:application_id>/send-feedback', methods=['POST'])
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: def send_candidate_feedback(application_id):
# OLD CODE:     company = get_owned_company()
# OLD CODE:     application = Application.query.get_or_404(application_id)
# OLD CODE:     job = Job.query.get_or_404(application.job_id)
# OLD CODE:     if job.company_id != company.id:
# OLD CODE:         abort(403)
# OLD CODE:
# OLD CODE:     feedback_text = (request.get_json() or {}).get('feedback', '').strip()
# OLD CODE:     if not feedback_text:
# OLD CODE:         return jsonify({"error": "No feedback provided"}), 400
# OLD CODE:
# OLD CODE:     application.candidate_feedback = feedback_text
# OLD CODE:     db.session.commit()
# OLD CODE:
# OLD CODE:     # Notify candidate
# OLD CODE:     candidate = application.candidate
# OLD CODE:     if candidate.notifications_enabled:
# OLD CODE:         notif = Notification(
# OLD CODE:             user_id=candidate.id,
# OLD CODE:             message=f"You received feedback on your {job.title} application from {company.name}.",
# OLD CODE:             link=url_for('candidate.dashboard', _external=False),
# OLD CODE:         )
# OLD CODE:         db.session.add(notif)
# OLD CODE:         db.session.commit()
# OLD CODE:
# OLD CODE:     try:
# OLD CODE:         send_branded_email(
# OLD CODE:             to_email=candidate.email,
# OLD CODE:             subject=f"Feedback on your {job.title} application",
# OLD CODE:             heading="Application feedback",
# OLD CODE:             body_html=(
# OLD CODE:                 f"<strong>{company.name}</strong> wanted to share some feedback on your "
# OLD CODE:                 f"application for <strong>{job.title}</strong>:<br><br>"
# OLD CODE:                 f"<blockquote style='border-left:3px solid #6366f1;padding-left:14px;color:#374151;'>"
# OLD CODE:                 f"{feedback_text}</blockquote>"
# OLD CODE:             ),
# OLD CODE:             plain_text=f"Feedback from {company.name} on your {job.title} application:\n\n{feedback_text}",
# OLD CODE:             cta_label="View My Applications",
# OLD CODE:             cta_url=external_url('candidate.dashboard'),
# OLD CODE:         )
# OLD CODE:     except Exception as e:
# OLD CODE:         print("Feedback email failed:", e)
# OLD CODE:
# OLD CODE:     return jsonify({"status": "sent"})
# OLD CODE:
# OLD CODE:
# OLD CODE: @employer.route('/employer/jobs/analyze-jd', methods=['POST'])
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: @limiter.limit("15 per hour")
# OLD CODE: def analyze_jd():
# OLD CODE:     data = request.get_json() or {}
# OLD CODE:     try:
# OLD CODE:         result = analyze_job_description(
# OLD CODE:             title=data.get('title', ''),
# OLD CODE:             about=data.get('about', ''),
# OLD CODE:             requirements=data.get('requirements', ''),
# OLD CODE:             preferred=data.get('preferred', ''),
# OLD CODE:             what_you_do=data.get('what_you_do', ''),
# OLD CODE:             contract_terms=data.get('contract_terms', ''),
# OLD CODE:             salary_provided=bool(data.get('salary_usd')),
# OLD CODE:             category=data.get('category', ''),
# OLD CODE:         )
# OLD CODE:         return jsonify(result)
# OLD CODE:     except Exception as e:
# OLD CODE:         print("JD analysis failed:", e)
# OLD CODE:         return jsonify({"error": "Analysis failed"}), 500
# OLD CODE:
# OLD CODE:
# OLD CODE: @employer.route('/employer/talent')
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: def talent_pool():
# OLD CODE:     import re as _re
# OLD CODE:     company = get_owned_company()
# OLD CODE:     open_jobs = Job.query.filter_by(company_id=company.id, status='open').all()
# OLD CODE:
# OLD CODE:     # Build keyword set from employer's open jobs - used for the "All Candidates"
# OLD CODE:     # browse tab, which stays a cheap heuristic rather than an AI call per view.
# OLD CODE:     job_corpus = ' '.join(
# OLD CODE:         f"{j.title} {j.category} {(j.description_text or '')[:300]}"
# OLD CODE:         for j in open_jobs
# OLD CODE:     ).lower()
# OLD CODE:     job_words = set(_re.findall(r'\b\w{3,}\b', job_corpus))
# OLD CODE:
# OLD CODE:     # Eagerly load users to avoid N+1 queries
# OLD CODE:     from sqlalchemy.orm import joinedload
# OLD CODE:     profiles = (
# OLD CODE:         CandidateProfile.query
# OLD CODE:         .filter_by(open_to_work=True)
# OLD CODE:         .options(joinedload(CandidateProfile.user))
# OLD CODE:         .all()
# OLD CODE:     )
# OLD CODE:
# OLD CODE:     def _score(prof):
# OLD CODE:         text = ' '.join(filter(None, [
# OLD CODE:             prof.skills, prof.target_roles, prof.headline
# OLD CODE:         ])).lower()
# OLD CODE:         words = set(_re.findall(r'\b\w{3,}\b', text))
# OLD CODE:         if not words or not job_words:
# OLD CODE:             return 0
# OLD CODE:         return round(len(words & job_words) / len(words) * 100)
# OLD CODE:
# OLD CODE:     all_scored = sorted(
# OLD CODE:         [{"profile": p, "user": p.user, "score": _score(p)} for p in profiles if p.user],
# OLD CODE:         key=lambda x: x["score"],
# OLD CODE:         reverse=True,
# OLD CODE:     )
# OLD CODE:
# OLD CODE:     return render_template(
# OLD CODE:         "talent_pool.html",
# OLD CODE:         all_scored=all_scored,
# OLD CODE:         company=company,
# OLD CODE:         open_jobs=open_jobs,
# OLD CODE:     )
# OLD CODE:
# OLD CODE:
# OLD CODE: @employer.route('/employer/talent/suggested')
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: @limiter.limit("30 per hour")
# OLD CODE: def suggested_candidates():
# OLD CODE:     """AI-ranked candidates from the open-to-work pool that fit this employer's
# OLD CODE:     open roles - the mirror of candidate.suggested_jobs. Loaded async from
# OLD CODE:     talent_pool.html rather than computed on every page render, since it's a
# OLD CODE:     real OpenAI call."""
# OLD CODE:     company = get_owned_company()
# OLD CODE:     open_jobs = Job.query.filter_by(company_id=company.id, status='open').all()
# OLD CODE:     if not open_jobs:
# OLD CODE:         return jsonify({"suggestions": []})
# OLD CODE:
# OLD CODE:     from sqlalchemy.orm import joinedload
# OLD CODE:     profiles = (
# OLD CODE:         CandidateProfile.query
# OLD CODE:         .filter_by(open_to_work=True)
# OLD CODE:         .options(joinedload(CandidateProfile.user))
# OLD CODE:         .limit(TALENT_POOL_AI_LIMIT)
# OLD CODE:         .all()
# OLD CODE:     )
# OLD CODE:     profiles = [p for p in profiles if p.user]
# OLD CODE:     if not profiles:
# OLD CODE:         return jsonify({"suggestions": []})
# OLD CODE:
# OLD CODE:     jobs_payload = [
# OLD CODE:         {"id": j.id, "title": j.title, "category": j.category, "description": j.description_text}
# OLD CODE:         for j in open_jobs
# OLD CODE:     ]
# OLD CODE:     candidates_payload = [
# OLD CODE:         {
# OLD CODE:             "id": p.id,
# OLD CODE:             "headline": p.headline,
# OLD CODE:             "skills": p.skills,
# OLD CODE:             "target_roles": p.target_roles,
# OLD CODE:             "years_experience": p.years_experience,
# OLD CODE:         }
# OLD CODE:         for p in profiles
# OLD CODE:     ]
# OLD CODE:
# OLD CODE:     try:
# OLD CODE:         ranked = suggest_candidates_for_jobs(jobs_payload, candidates_payload)
# OLD CODE:     except Exception:
# OLD CODE:         return jsonify({"error": "Failed to generate suggestions. Please try again."}), 500
# OLD CODE:
# OLD CODE:     profiles_by_id = {p.id: p for p in profiles}
# OLD CODE:     suggestions = []
# OLD CODE:     for item in ranked[:12]:
# OLD CODE:         prof = profiles_by_id.get(item["candidate_id"])
# OLD CODE:         if not prof:
# OLD CODE:             continue
# OLD CODE:         user = prof.user
# OLD CODE:         suggestions.append({
# OLD CODE:             "user_id": user.id,
# OLD CODE:             "name": user.first_name or "Candidate",
# OLD CODE:             "headline": prof.headline or "",
# OLD CODE:             "availability": prof.availability or "",
# OLD CODE:             "work_preference": prof.work_preference or "",
# OLD CODE:             "location": prof.location or "",
# OLD CODE:             "years_experience": prof.years_experience or "",
# OLD CODE:             "skills": [s.strip() for s in (prof.skills or "").split(",") if s.strip()][:6],
# OLD CODE:             "score": item["score"],
# OLD CODE:             "reason": item["reason"],
# OLD CODE:             "url": url_for('candidate.public_profile', user_id=user.id),
# OLD CODE:         })
# OLD CODE:
# OLD CODE:     return jsonify({"suggestions": suggestions})
# OLD CODE:
# OLD CODE:
# OLD CODE: @employer.route('/employer/analytics')
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: def analytics():
# OLD CODE:     company = get_owned_company()
# OLD CODE:     jobs = Job.query.filter_by(company_id=company.id).all()
# OLD CODE:     job_ids = [j.id for j in jobs]
# OLD CODE:
# OLD CODE:     if not job_ids:
# OLD CODE:         return render_template('employer_analytics.html', company=company, stats={}, top_jobs=[])
# OLD CODE:
# OLD CODE:     all_apps = Application.query.filter(Application.job_id.in_(job_ids)).all()
# OLD CODE:
# OLD CODE:     total = len(all_apps)
# OLD CODE:     interviewed = sum(1 for a in all_apps if a.interview_transcript)
# OLD CODE:     hired = sum(1 for a in all_apps if a.status == 'hired')
# OLD CODE:     rejected = sum(1 for a in all_apps if a.status == 'rejected')
# OLD CODE:     scores = [a.match_score for a in all_apps if a.match_score is not None]
# OLD CODE:     avg_score = round(sum(scores) / len(scores)) if scores else None
# OLD CODE:     interview_rate = round(interviewed / total * 100) if total else 0
# OLD CODE:     hire_rate = round(hired / total * 100) if total else 0
# OLD CODE:
# OLD CODE:     # Per-job breakdown
# OLD CODE:     jobs_by_id = {j.id: j for j in jobs}
# OLD CODE:     job_counts = {}
# OLD CODE:     for a in all_apps:
# OLD CODE:         jid = a.job_id
# OLD CODE:         if jid not in job_counts:
# OLD CODE:             job_counts[jid] = {"title": jobs_by_id[jid].title, "total": 0, "interviewed": 0, "hired": 0}
# OLD CODE:         job_counts[jid]["total"] += 1
# OLD CODE:         if a.interview_transcript:
# OLD CODE:             job_counts[jid]["interviewed"] += 1
# OLD CODE:         if a.status == "hired":
# OLD CODE:             job_counts[jid]["hired"] += 1
# OLD CODE:
# OLD CODE:     top_jobs = sorted(job_counts.values(), key=lambda x: x["total"], reverse=True)[:5]
# OLD CODE:
# OLD CODE:     stats = {
# OLD CODE:         "total": total,
# OLD CODE:         "interviewed": interviewed,
# OLD CODE:         "hired": hired,
# OLD CODE:         "rejected": rejected,
# OLD CODE:         "avg_score": avg_score,
# OLD CODE:         "interview_rate": interview_rate,
# OLD CODE:         "hire_rate": hire_rate,
# OLD CODE:         "open_jobs": sum(1 for j in jobs if j.status == 'open'),
# OLD CODE:     }
# OLD CODE:
# OLD CODE:     return render_template('employer_analytics.html', company=company, stats=stats, top_jobs=top_jobs)
# OLD CODE:
# OLD CODE:
# OLD CODE: @employer.route('/employer/applications/<int:application_id>/notes', methods=['POST'])
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: def save_notes(application_id):
# OLD CODE:     company = get_owned_company()
# OLD CODE:     application = Application.query.get_or_404(application_id)
# OLD CODE:     job = Job.query.get_or_404(application.job_id)
# OLD CODE:     if job.company_id != company.id:
# OLD CODE:         abort(403)
# OLD CODE:     application.employer_notes = request.get_json().get('notes', '').strip() or None
# OLD CODE:     db.session.commit()
# OLD CODE:     return jsonify({"status": "saved"})
# OLD CODE:
# OLD CODE:
# OLD CODE: @employer.route('/employer/applications/<int:application_id>/manual-interview-score', methods=['POST'])
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: def save_manual_interview_score(application_id):
# OLD CODE:     """The employer's own 0-100 rating after conducting a live/manual
# OLD CODE:     interview themselves - factored into the composite score alongside the
# OLD CODE:     AI screening interview verdict, see compute_composite_score()."""
# OLD CODE:     company = get_owned_company()
# OLD CODE:     application = Application.query.get_or_404(application_id)
# OLD CODE:     job = Job.query.get_or_404(application.job_id)
# OLD CODE:     if job.company_id != company.id:
# OLD CODE:         abort(403)
# OLD CODE:
# OLD CODE:     raw = (request.get_json() or {}).get('score')
# OLD CODE:     try:
# OLD CODE:         score = int(raw)
# OLD CODE:     except (TypeError, ValueError):
# OLD CODE:         return jsonify({"error": "Score must be a number from 0 to 100."}), 400
# OLD CODE:     if not 0 <= score <= 100:
# OLD CODE:         return jsonify({"error": "Score must be between 0 and 100."}), 400
# OLD CODE:
# OLD CODE:     application.manual_interview_score = score
# OLD CODE:     db.session.commit()
# OLD CODE:     return jsonify({"status": "saved", "score": score})
# OLD CODE:
# OLD CODE:
# OLD CODE: # ------------------------------------------------------------------ #
# OLD CODE: #  Company Settings
# OLD CODE: # ------------------------------------------------------------------ #
# OLD CODE:
# OLD CODE: @employer.route('/employer/company/settings', methods=['GET', 'POST'])
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: def company_settings():
# OLD CODE:     company = get_owned_company()
# OLD CODE:
# OLD CODE:     if request.method == 'POST':
# OLD CODE:         action = request.form.get('action', 'save_profile')
# OLD CODE:
# OLD CODE:         if action == 'save_profile':
# OLD CODE:             name = request.form.get('name', '').strip()
# OLD CODE:             your_name = request.form.get('your_name', '').strip()
# OLD CODE:             if your_name:
# OLD CODE:                 current_user.first_name = your_name
# OLD CODE:             if not name:
# OLD CODE:                 flash("Company name is required.", "error")
# OLD CODE:             else:
# OLD CODE:                 company.name = name
# OLD CODE:                 company.website = request.form.get('website', '').strip() or None
# OLD CODE:                 company.description = request.form.get('description', '').strip() or None
# OLD CODE:                 company.industry = request.form.get('industry', '').strip() or None
# OLD CODE:                 company.size = request.form.get('size', '').strip() or None
# OLD CODE:                 company.location = request.form.get('location', '').strip() or None
# OLD CODE:                 company.blind_mode_enabled = request.form.get('blind_mode_enabled') == 'on'
# OLD CODE:                 db.session.commit()
# OLD CODE:                 flash("Company profile updated.", "success")
# OLD CODE:
# OLD CODE:         elif action == 'remove_logo':
# OLD CODE:             if company.logo_filename:
# OLD CODE:                 logos_dir = os.path.join(os.path.dirname(__file__), "static", "logos")
# OLD CODE:                 filepath = os.path.join(logos_dir, company.logo_filename)
# OLD CODE:                 try:
# OLD CODE:                     os.remove(filepath)
# OLD CODE:                 except FileNotFoundError:
# OLD CODE:                     pass
# OLD CODE:                 company.logo_filename = None
# OLD CODE:                 company.logo_version = (company.logo_version or 0) + 1
# OLD CODE:                 db.session.commit()
# OLD CODE:             flash("Logo removed.", "success")
# OLD CODE:
# OLD CODE:         elif action == 'remove_member':
# OLD CODE:             member_id = request.form.get('member_id', type=int)
# OLD CODE:             if company.owner_user_id != current_user.id:
# OLD CODE:                 flash("Only the company owner can remove team members.", "error")
# OLD CODE:             elif member_id:
# OLD CODE:                 member = CompanyMember.query.filter_by(id=member_id, company_id=company.id).first()
# OLD CODE:                 if member:
# OLD CODE:                     db.session.delete(member)
# OLD CODE:                     db.session.commit()
# OLD CODE:                     flash("Team member removed.", "success")
# OLD CODE:
# OLD CODE:         return redirect(url_for('employer.company_settings'))
# OLD CODE:
# OLD CODE:     owner = User.query.get(company.owner_user_id)
# OLD CODE:     members = CompanyMember.query.filter_by(company_id=company.id).all()
# OLD CODE:     pending_invites = CompanyInvite.query.filter_by(company_id=company.id, used=False).all()
# OLD CODE:     open_jobs_count = Job.query.filter_by(company_id=company.id, status='open').count()
# OLD CODE:
# OLD CODE:     return render_template(
# OLD CODE:         "company_settings.html",
# OLD CODE:         company=company,
# OLD CODE:         owner=owner,
# OLD CODE:         members=members,
# OLD CODE:         pending_invites=pending_invites,
# OLD CODE:         sizes=COMPANY_SIZES,
# OLD CODE:         industries=INDUSTRIES,
# OLD CODE:         is_owner=(company.owner_user_id == current_user.id),
# OLD CODE:         open_jobs_count=open_jobs_count,
# OLD CODE:     )
# OLD CODE:
# OLD CODE:
# OLD CODE: def _detect_image_format(path):
# OLD CODE:     """Return detected format from magic bytes, or None if unrecognised."""
# OLD CODE:     try:
# OLD CODE:         with open(path, 'rb') as f:
# OLD CODE:             h = f.read(16)
# OLD CODE:         if h[:8] == b'\x89PNG\r\n\x1a\n':
# OLD CODE:             return 'PNG'
# OLD CODE:         if h[:3] == b'\xff\xd8\xff':
# OLD CODE:             return 'JPEG'
# OLD CODE:         if h[:6] in (b'GIF87a', b'GIF89a'):
# OLD CODE:             return 'GIF'
# OLD CODE:         if h[:4] == b'RIFF' and h[8:12] == b'WEBP':
# OLD CODE:             return 'WEBP'
# OLD CODE:         if h[:2] == b'BM':
# OLD CODE:             return 'BMP'
# OLD CODE:         if h[:4] in (b'II*\x00', b'MM\x00*'):
# OLD CODE:             return 'TIFF'
# OLD CODE:         # HEIC/HEIF: 'ftyp' box appears at offset 4
# OLD CODE:         if h[4:8] == b'ftyp':
# OLD CODE:             return 'HEIF'
# OLD CODE:         if h[:4] == b'\x00\x00\x00\x0c' and h[8:12] in (b'avif', b'avis'):
# OLD CODE:             return 'AVIF'
# OLD CODE:     except OSError:
# OLD CODE:         pass
# OLD CODE:     return None
# OLD CODE:
# OLD CODE:
# OLD CODE: @employer.route('/employer/company/logo', methods=['POST'])
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: def upload_logo():
# OLD CODE:     company = get_owned_company()
# OLD CODE:     file = request.files.get('logo')
# OLD CODE:
# OLD CODE:     if not file or not file.filename:
# OLD CODE:         flash("No file selected.", "error")
# OLD CODE:         return redirect(url_for('employer.company_settings'))
# OLD CODE:
# OLD CODE:     ext = (file.filename.rsplit('.', 1)[-1] if '.' in file.filename else '').lower()
# OLD CODE:     if ext not in LOGO_ALLOWED_EXTENSIONS:
# OLD CODE:         flash("Unsupported file type. Use PNG, JPG, GIF, or WebP.", "error")
# OLD CODE:         return redirect(url_for('employer.company_settings'))
# OLD CODE:
# OLD CODE:     logos_dir = os.path.join(os.path.dirname(__file__), "static", "logos")
# OLD CODE:     os.makedirs(logos_dir, exist_ok=True)
# OLD CODE:
# OLD CODE:     tmp_path = os.path.join(logos_dir, f"_tmp_{company.id}.bin")
# OLD CODE:     final_path = os.path.join(logos_dir, f"company_{company.id}.png")
# OLD CODE:
# OLD CODE:     try:
# OLD CODE:         file.save(tmp_path)
# OLD CODE:
# OLD CODE:         # Guard: empty file
# OLD CODE:         if os.path.getsize(tmp_path) == 0:
# OLD CODE:             flash("The uploaded file was empty. Please try again.", "error")
# OLD CODE:             return redirect(url_for('employer.company_settings'))
# OLD CODE:
# OLD CODE:         raw = Image.open(tmp_path)
# OLD CODE:         raw.load()  # force full decode so errors surface here, not later
# OLD CODE:
# OLD CODE:         if raw.mode == 'RGBA':
# OLD CODE:             bg = Image.new("RGB", raw.size, (255, 255, 255))
# OLD CODE:             bg.paste(raw, mask=raw.split()[3])
# OLD CODE:             img = bg
# OLD CODE:         elif raw.mode == 'P':
# OLD CODE:             converted = raw.convert("RGBA")
# OLD CODE:             bg = Image.new("RGB", converted.size, (255, 255, 255))
# OLD CODE:             bg.paste(converted, mask=converted.split()[3])
# OLD CODE:             img = bg
# OLD CODE:         else:
# OLD CODE:             img = raw.convert("RGB")
# OLD CODE:
# OLD CODE:         img.thumbnail(LOGO_MAX_SIZE, Image.LANCZOS)
# OLD CODE:         img.save(final_path, "PNG", optimize=True)
# OLD CODE:         company.logo_filename = f"company_{company.id}.png"
# OLD CODE:         company.logo_version = (company.logo_version or 0) + 1
# OLD CODE:         db.session.commit()
# OLD CODE:         flash("Logo updated.", "success")
# OLD CODE:     except Exception as e:
# OLD CODE:         flash(f"Could not process image: {e}", "error")
# OLD CODE:     finally:
# OLD CODE:         if os.path.exists(tmp_path):
# OLD CODE:             os.remove(tmp_path)
# OLD CODE:
# OLD CODE:     return redirect(url_for('employer.company_settings'))
# OLD CODE:
# OLD CODE:
# OLD CODE: # ------------------------------------------------------------------ #
# OLD CODE: #  Team Invitations
# OLD CODE: # ------------------------------------------------------------------ #
# OLD CODE:
# OLD CODE: @employer.route('/employer/company/invite', methods=['POST'])
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: def invite_member():
# OLD CODE:     company = get_owned_company()
# OLD CODE:
# OLD CODE:     if company.owner_user_id != current_user.id:
# OLD CODE:         flash("Only the company owner can send invitations.", "error")
# OLD CODE:         return redirect(url_for('employer.company_settings'))
# OLD CODE:
# OLD CODE:     email = request.form.get('email', '').strip().lower()
# OLD CODE:     if not email or '@' not in email:
# OLD CODE:         flash("A valid email address is required.", "error")
# OLD CODE:         return redirect(url_for('employer.company_settings'))
# OLD CODE:
# OLD CODE:     from .models import FREE_EMAIL_DOMAINS, User
# OLD CODE:     domain = email.split('@')[-1]
# OLD CODE:     if domain in FREE_EMAIL_DOMAINS:
# OLD CODE:         flash("Please invite using a company email address - personal email providers like Gmail aren't accepted.", "error")
# OLD CODE:         return redirect(url_for('employer.company_settings'))
# OLD CODE:
# OLD CODE:     owner = User.query.get(company.owner_user_id)
# OLD CODE:     owner_domain = owner.email.split('@')[-1].lower() if owner and owner.email else None
# OLD CODE:     if owner_domain and domain != owner_domain:
# OLD CODE:         flash(f"You can only invite teammates with an @{owner_domain} email address.", "error")
# OLD CODE:         return redirect(url_for('employer.company_settings'))
# OLD CODE:
# OLD CODE:     # Don't invite someone already a member or the owner
# OLD CODE:     existing_user = User.query.filter(db.func.lower(User.email) == email).first()
# OLD CODE:     if existing_user:
# OLD CODE:         if existing_user.id == company.owner_user_id:
# OLD CODE:             flash("That person is already the company owner.", "error")
# OLD CODE:             return redirect(url_for('employer.company_settings'))
# OLD CODE:         already = CompanyMember.query.filter_by(company_id=company.id, user_id=existing_user.id).first()
# OLD CODE:         if already:
# OLD CODE:             flash("That person is already a team member.", "error")
# OLD CODE:             return redirect(url_for('employer.company_settings'))
# OLD CODE:
# OLD CODE:         # Already has an account - add them immediately instead of making
# OLD CODE:         # them find and click an email link (that's what left someone stuck
# OLD CODE:         # as 'candidate' with an unused invite before this existed).
# OLD CODE:         existing_user.role = 'employer'
# OLD CODE:         db.session.add(CompanyMember(company_id=company.id, user_id=existing_user.id))
# OLD CODE:         CompanyInvite.query.filter_by(company_id=company.id, email=email, used=False).update({"used": True})
# OLD CODE:         db.session.commit()
# OLD CODE:         flash(f"{existing_user.email} added to {company.name}.", "success")
# OLD CODE:         return redirect(url_for('employer.company_settings'))
# OLD CODE:
# OLD CODE:     # Delete any previous unused invite for this email + company
# OLD CODE:     CompanyInvite.query.filter_by(company_id=company.id, email=email, used=False).delete()
# OLD CODE:     db.session.commit()
# OLD CODE:
# OLD CODE:     token = secrets.token_urlsafe(32)
# OLD CODE:     invite = CompanyInvite(
# OLD CODE:         company_id=company.id,
# OLD CODE:         invited_by_user_id=current_user.id,
# OLD CODE:         email=email,
# OLD CODE:         token=token,
# OLD CODE:     )
# OLD CODE:     db.session.add(invite)
# OLD CODE:     db.session.commit()
# OLD CODE:
# OLD CODE:     invite_url = external_url('employer.accept_invite', token=token)
# OLD CODE:     try:
# OLD CODE:         send_branded_email(
# OLD CODE:             to_email=email,
# OLD CODE:             subject=f"You've been invited to join {company.name} on Avants AI",
# OLD CODE:             heading=f"Join {company.name} on Avants AI",
# OLD CODE:             body_html=(
# OLD CODE:                 f"<strong>{current_user.first_name or current_user.email}</strong> has invited you to join "
# OLD CODE:                 f"<strong>{company.name}</strong> as a team member on Avants AI. "
# OLD CODE:                 f"As a team member, you'll be able to post jobs and manage applicants for {company.name}.<br><br>"
# OLD CODE:                 f"This invite expires if not used."
# OLD CODE:             ),
# OLD CODE:             plain_text=(
# OLD CODE:                 f"{current_user.first_name or current_user.email} has invited you to join {company.name} on Avants AI.\n\n"
# OLD CODE:                 f"Accept the invite here: {invite_url}"
# OLD CODE:             ),
# OLD CODE:             cta_label="Accept Invitation",
# OLD CODE:             cta_url=invite_url,
# OLD CODE:         )
# OLD CODE:         flash(f"Invitation sent to {email}.", "success")
# OLD CODE:     except Exception as e:
# OLD CODE:         print("Invite email failed:", e)
# OLD CODE:         flash(f"Invite created but email delivery failed. Share this link manually: {invite_url}", "error")
# OLD CODE:
# OLD CODE:     return redirect(url_for('employer.company_settings'))
# OLD CODE:
# OLD CODE:
# OLD CODE: @employer.route('/employer/company/sync-domain-members', methods=['POST'])
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: def sync_domain_members():
# OLD CODE:     """One-click catch-up: adds every existing account whose email matches
# OLD CODE:     this company's verified domain but isn't a member yet - covers people who
# OLD CODE:     signed up before this domain had a hub, or whose account got stuck as a
# OLD CODE:     'candidate' by the case-sensitivity bug an earlier fix closed."""
# OLD CODE:     company = get_owned_company()
# OLD CODE:
# OLD CODE:     if company.owner_user_id != current_user.id:
# OLD CODE:         flash("Only the company owner can do this.", "error")
# OLD CODE:         return redirect(url_for('employer.company_settings'))
# OLD CODE:
# OLD CODE:     if not company.email_domain:
# OLD CODE:         flash("This company doesn't have a verified email domain on file.", "error")
# OLD CODE:         return redirect(url_for('employer.company_settings'))
# OLD CODE:
# OLD CODE:     domain = company.email_domain.lower()
# OLD CODE:     matches = User.query.filter(User.email.ilike(f"%@{domain}")).all()
# OLD CODE:     existing_member_ids = {m.user_id for m in CompanyMember.query.filter_by(company_id=company.id).all()}
# OLD CODE:
# OLD CODE:     added = []
# OLD CODE:     for user in matches:
# OLD CODE:         if user.id == company.owner_user_id or user.id in existing_member_ids:
# OLD CODE:             continue
# OLD CODE:         if not user.email or user.email.split('@')[-1].lower() != domain:
# OLD CODE:             continue
# OLD CODE:         user.role = 'employer'
# OLD CODE:         db.session.add(CompanyMember(company_id=company.id, user_id=user.id))
# OLD CODE:         CompanyInvite.query.filter_by(company_id=company.id, email=user.email.lower(), used=False).update({"used": True})
# OLD CODE:         added.append(user.email)
# OLD CODE:
# OLD CODE:     db.session.commit()
# OLD CODE:
# OLD CODE:     if added:
# OLD CODE:         flash(f"Added {len(added)} teammate(s) from @{domain}: {', '.join(added)}.", "success")
# OLD CODE:     else:
# OLD CODE:         flash(f"No additional @{domain} accounts found to add.", "info")
# OLD CODE:     return redirect(url_for('employer.company_settings'))
# OLD CODE:
# OLD CODE:
# OLD CODE: @employer.route('/employer/join/<token>')
# OLD CODE: @login_required
# OLD CODE: def accept_invite(token):
# OLD CODE:     invite = CompanyInvite.query.filter_by(token=token, used=False).first()
# OLD CODE:
# OLD CODE:     if not invite:
# OLD CODE:         flash("This invitation is invalid or has already been used.", "error")
# OLD CODE:         return redirect(url_for('views.home'))
# OLD CODE:
# OLD CODE:     if current_user.role != 'employer':
# OLD CODE:         flash("You need an employer account to accept this invitation.", "error")
# OLD CODE:         return redirect(url_for('views.home'))
# OLD CODE:
# OLD CODE:     if invite.email.lower() != current_user.email.lower():
# OLD CODE:         flash("This invitation was sent to a different email address.", "error")
# OLD CODE:         return redirect(url_for('views.home'))
# OLD CODE:
# OLD CODE:     company = Company.query.get_or_404(invite.company_id)
# OLD CODE:
# OLD CODE:     # Check if already a member or owner
# OLD CODE:     if company.owner_user_id == current_user.id:
# OLD CODE:         flash("You are already the owner of this company.", "info")
# OLD CODE:         return redirect(url_for('employer.dashboard'))
# OLD CODE:
# OLD CODE:     existing = CompanyMember.query.filter_by(company_id=company.id, user_id=current_user.id).first()
# OLD CODE:     if existing:
# OLD CODE:         flash(f"You're already a team member of {company.name}.", "info")
# OLD CODE:         return redirect(url_for('employer.dashboard'))
# OLD CODE:
# OLD CODE:     member = CompanyMember(company_id=company.id, user_id=current_user.id)
# OLD CODE:     db.session.add(member)
# OLD CODE:     invite.used = True
# OLD CODE:     db.session.commit()
# OLD CODE:
# OLD CODE:     flash(f"Welcome to {company.name}! You can now post jobs and manage applicants.", "success")
# OLD CODE:     return redirect(url_for('employer.dashboard'))
# OLD CODE:
# OLD CODE:
# OLD CODE: # ------------------------------------------------------------------ #
# OLD CODE: #  Public Company Page
# OLD CODE: # ------------------------------------------------------------------ #
# OLD CODE:
# OLD CODE: # ------------------------------------------------------------------ #
# OLD CODE: #  Meeting Scheduling - Propose Times
# OLD CODE: # ------------------------------------------------------------------ #
# OLD CODE:
# OLD CODE: @employer.route('/employer/applications/<int:application_id>/propose-times', methods=['POST'])
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: def propose_times(application_id):
# OLD CODE:     company = get_owned_company()
# OLD CODE:     application = Application.query.get_or_404(application_id)
# OLD CODE:     job = Job.query.get_or_404(application.job_id)
# OLD CODE:     if job.company_id != company.id:
# OLD CODE:         abort(403)
# OLD CODE:
# OLD CODE:     notes = request.form.get('notes', '').strip()
# OLD CODE:     slots = []
# OLD CODE:     for i in range(1, 4):
# OLD CODE:         d = request.form.get(f'date_{i}', '').strip()
# OLD CODE:         t = request.form.get(f'time_{i}', '').strip()
# OLD CODE:         if d and t:
# OLD CODE:             slots.append({'date': d, 'time': t})
# OLD CODE:
# OLD CODE:     if not slots:
# OLD CODE:         flash("Add at least one time slot.", "error")
# OLD CODE:         return redirect(url_for('employer.applicants', job_id=job.id))
# OLD CODE:
# OLD CODE:     # Cancel any existing pending proposal for this application
# OLD CODE:     MeetingProposal.query.filter_by(
# OLD CODE:         application_id=application_id, status='pending'
# OLD CODE:     ).update({'status': 'expired'})
# OLD CODE:
# OLD CODE:     proposal = MeetingProposal(
# OLD CODE:         application_id=application_id,
# OLD CODE:         employer_user_id=current_user.id,
# OLD CODE:         slots=json.dumps(slots),
# OLD CODE:         notes=notes or None,
# OLD CODE:     )
# OLD CODE:     db.session.add(proposal)
# OLD CODE:
# OLD CODE:     candidate = application.candidate
# OLD CODE:     notif = Notification(
# OLD CODE:         user_id=candidate.id,
# OLD CODE:         message=f"{company.name} wants to schedule an interview for {job.title} - pick a time!",
# OLD CODE:         link=url_for('candidate.interviews'),
# OLD CODE:     )
# OLD CODE:     db.session.add(notif)
# OLD CODE:     db.session.commit()
# OLD CODE:
# OLD CODE:     try:
# OLD CODE:         slot_lines = ''.join(
# OLD CODE:             f"<li><strong>{s['date']}</strong> at {s['time']}</li>" for s in slots
# OLD CODE:         )
# OLD CODE:         send_branded_email(
# OLD CODE:             to_email=candidate.email,
# OLD CODE:             subject=f"{company.name} wants to schedule an interview - {job.title}",
# OLD CODE:             heading=f"{company.name} wants to meet you!",
# OLD CODE:             body_html=(
# OLD CODE:                 f"Hi {candidate.first_name or 'there'},<br><br>"
# OLD CODE:                 f"<strong>{company.name}</strong> would like to schedule a live video interview "
# OLD CODE:                 f"for <strong>{job.title}</strong>. Pick whichever time works best for you:<br><br>"
# OLD CODE:                 f"<ul>{slot_lines}</ul>"
# OLD CODE:                 + (f"<br><strong>Notes:</strong> {notes}<br>" if notes else "")
# OLD CODE:                 + "<br>Click below to choose your slot - the interview room will be created instantly."
# OLD CODE:             ),
# OLD CODE:             plain_text=(
# OLD CODE:                 f"Hi {candidate.first_name or 'there'},\n\n"
# OLD CODE:                 f"{company.name} wants to interview you for {job.title}.\n\n"
# OLD CODE:                 "Available times:\n"
# OLD CODE:                 + ''.join(f"  • {s['date']} at {s['time']}\n" for s in slots)
# OLD CODE:                 + (f"\nNotes: {notes}\n" if notes else "")
# OLD CODE:             ),
# OLD CODE:             cta_label="Pick a Time",
# OLD CODE:             cta_url=external_url('candidate.interviews'),
# OLD CODE:         )
# OLD CODE:         flash(f"Time slots sent to {candidate.first_name or candidate.email}.", "success")
# OLD CODE:     except Exception:
# OLD CODE:         flash("Proposal saved - email notification failed.", "error")
# OLD CODE:
# OLD CODE:     return redirect(url_for('employer.applicants', job_id=job.id))
# OLD CODE:
# OLD CODE:
# OLD CODE: # ------------------------------------------------------------------ #
# OLD CODE: #  In-App Messaging
# OLD CODE: # ------------------------------------------------------------------ #
# OLD CODE:
# OLD CODE: @employer.route('/employer/applications/<int:application_id>/messages.json')
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: def messages_json(application_id):
# OLD CODE:     company = get_owned_company()
# OLD CODE:     application = Application.query.get_or_404(application_id)
# OLD CODE:     job = Job.query.get_or_404(application.job_id)
# OLD CODE:     if job.company_id != company.id:
# OLD CODE:         abort(403)
# OLD CODE:
# OLD CODE:     # Mark unread messages (from candidate) as read
# OLD CODE:     Message.query.filter_by(application_id=application_id, read=False).filter(
# OLD CODE:         Message.sender_user_id != current_user.id
# OLD CODE:     ).update({"read": True})
# OLD CODE:     db.session.commit()
# OLD CODE:
# OLD CODE:     msgs = Message.query.filter_by(application_id=application_id).order_by(Message.created_at).all()
# OLD CODE:     return jsonify([{
# OLD CODE:         "id": m.id,
# OLD CODE:         "body": m.body,
# OLD CODE:         "sender_name": m.sender.first_name or m.sender.email,
# OLD CODE:         "is_mine": m.sender_user_id == current_user.id,
# OLD CODE:         "time": m.created_at.strftime("%b %d, %H:%M") if m.created_at else "",
# OLD CODE:     } for m in msgs])
# OLD CODE:
# OLD CODE:
# OLD CODE: @employer.route('/employer/applications/<int:application_id>/message', methods=['POST'])
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: def send_message(application_id):
# OLD CODE:     company = get_owned_company()
# OLD CODE:     application = Application.query.get_or_404(application_id)
# OLD CODE:     job = Job.query.get_or_404(application.job_id)
# OLD CODE:     if job.company_id != company.id:
# OLD CODE:         abort(403)
# OLD CODE:
# OLD CODE:     body = (request.json or {}).get('body', '').strip() if request.is_json else request.form.get('body', '').strip()
# OLD CODE:     if not body:
# OLD CODE:         return jsonify({"error": "Message body is required"}), 400
# OLD CODE:
# OLD CODE:     msg = Message(application_id=application_id, sender_user_id=current_user.id, body=body)
# OLD CODE:     db.session.add(msg)
# OLD CODE:
# OLD CODE:     # Notify candidate
# OLD CODE:     candidate = application.candidate
# OLD CODE:     notif = Notification(
# OLD CODE:         user_id=candidate.id,
# OLD CODE:         message=f"New message from {company.name} about your {job.title} application.",
# OLD CODE:         link=url_for('candidate.dashboard'),
# OLD CODE:     )
# OLD CODE:     db.session.add(notif)
# OLD CODE:     db.session.commit()
# OLD CODE:
# OLD CODE:     return jsonify({
# OLD CODE:         "id": msg.id,
# OLD CODE:         "body": msg.body,
# OLD CODE:         "sender_name": current_user.first_name or current_user.email,
# OLD CODE:         "is_mine": True,
# OLD CODE:         "time": msg.created_at.strftime("%b %d, %H:%M") if msg.created_at else "",
# OLD CODE:     })
# OLD CODE:
# OLD CODE:
# OLD CODE:
# OLD CODE:
# OLD CODE: # ------------------------------------------------------------------ #
# OLD CODE: #  In-App Video Meetings (Daily.co)
# OLD CODE: # ------------------------------------------------------------------ #
# OLD CODE:
# OLD CODE: @employer.route('/employer/applications/<int:application_id>/meeting/create', methods=['POST'])
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: def create_meeting_room(application_id):
# OLD CODE:     from daily_utils import create_room
# OLD CODE:     company = get_owned_company()
# OLD CODE:     application = Application.query.get_or_404(application_id)
# OLD CODE:     job = Job.query.get_or_404(application.job_id)
# OLD CODE:     if job.company_id != company.id:
# OLD CODE:         abort(403)
# OLD CODE:
# OLD CODE:     date = request.form.get('date', '').strip()
# OLD CODE:     time_ = request.form.get('time', '').strip()
# OLD CODE:     notes = request.form.get('notes', '').strip()
# OLD CODE:
# OLD CODE:     if not date or not time_:
# OLD CODE:         flash("Date and time are required.", "error")
# OLD CODE:         return redirect(url_for('employer.applicants', job_id=job.id))
# OLD CODE:
# OLD CODE:     api_key = current_app.config.get('DAILY_API_KEY')
# OLD CODE:     if not api_key:
# OLD CODE:         flash("Daily.co API key is not configured.", "error")
# OLD CODE:         return redirect(url_for('employer.applicants', job_id=job.id))
# OLD CODE:
# OLD CODE:     try:
# OLD CODE:         room_data = create_room(api_key)
# OLD CODE:     except Exception as e:
# OLD CODE:         logger.exception("Daily.co room creation failed")
# OLD CODE:         flash(f"Could not create meeting room: {e}", "error")
# OLD CODE:         return redirect(url_for('employer.applicants', job_id=job.id))
# OLD CODE:
# OLD CODE:     room = MeetingRoom(
# OLD CODE:         application_id=application_id,
# OLD CODE:         employer_user_id=current_user.id,
# OLD CODE:         room_name=room_data['name'],
# OLD CODE:         room_url=room_data['url'],
# OLD CODE:         scheduled_date=date,
# OLD CODE:         scheduled_time=time_,
# OLD CODE:         notes=notes or None,
# OLD CODE:     )
# OLD CODE:     db.session.add(room)
# OLD CODE:
# OLD CODE:     join_url = external_url('views.join_meeting', room_name=room_data['name'])
# OLD CODE:     application.scheduled_meeting = json.dumps({
# OLD CODE:         "type": "virtual",
# OLD CODE:         "date": date,
# OLD CODE:         "time": time_,
# OLD CODE:         "location_or_url": join_url,
# OLD CODE:         "notes": notes,
# OLD CODE:         "in_app": True,
# OLD CODE:     })
# OLD CODE:     db.session.commit()
# OLD CODE:
# OLD CODE:     candidate = application.candidate
# OLD CODE:
# OLD CODE:     # In-app notification (shows in the bell)
# OLD CODE:     notif = Notification(
# OLD CODE:         user_id=candidate.id,
# OLD CODE:         message=f"{company.name} wants to meet you! Interview scheduled for {job.title} on {date} at {time_}.",
# OLD CODE:         link=url_for('candidate.interviews'),
# OLD CODE:     )
# OLD CODE:     db.session.add(notif)
# OLD CODE:     db.session.commit()
# OLD CODE:
# OLD CODE:     # Email
# OLD CODE:     try:
# OLD CODE:         send_branded_email(
# OLD CODE:             to_email=candidate.email,
# OLD CODE:             subject=f"{company.name} wants to interview you - {job.title}",
# OLD CODE:             heading=f"{company.name} wants to meet you!",
# OLD CODE:             body_html=(
# OLD CODE:                 f"Hi {candidate.first_name or 'there'},<br><br>"
# OLD CODE:                 f"Great news - <strong>{company.name}</strong> has scheduled a live video interview "
# OLD CODE:                 f"with you for <strong>{job.title}</strong>.<br><br>"
# OLD CODE:                 f"<strong>Date:</strong> {date}<br>"
# OLD CODE:                 f"<strong>Time:</strong> {time_}<br>"
# OLD CODE:                 + (f"<strong>Notes:</strong> {notes}<br>" if notes else "")
# OLD CODE:                 + "<br>The interview takes place directly on Avants - no Zoom needed. "
# OLD CODE:                 "Click the button below when it's time."
# OLD CODE:             ),
# OLD CODE:             plain_text=(
# OLD CODE:                 f"Hi {candidate.first_name or 'there'},\n\n"
# OLD CODE:                 f"{company.name} has scheduled a live interview for {job.title}.\n\n"
# OLD CODE:                 f"Date: {date}\nTime: {time_}\n"
# OLD CODE:                 + (f"Notes: {notes}\n" if notes else "")
# OLD CODE:                 + f"\nJoin here: {join_url}\n"
# OLD CODE:             ),
# OLD CODE:             cta_label="Join Interview",
# OLD CODE:             cta_url=join_url,
# OLD CODE:         )
# OLD CODE:         flash("Interview room created - candidate notified by email and in-app.", "success")
# OLD CODE:     except Exception:
# OLD CODE:         flash("Interview room created and candidate notified in-app (email failed).", "error")
# OLD CODE:
# OLD CODE:     return redirect(url_for('employer.applicants', job_id=job.id))
# OLD CODE:
# OLD CODE:
# OLD CODE: @employer.route('/employer/meetings')
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: def employer_meetings():
# OLD CODE:     company = get_owned_company()
# OLD CODE:     jobs = Job.query.filter_by(company_id=company.id).all()
# OLD CODE:     job_ids = [j.id for j in jobs]
# OLD CODE:     job_map = {j.id: j for j in jobs}
# OLD CODE:
# OLD CODE:     rooms = (
# OLD CODE:         MeetingRoom.query
# OLD CODE:         .join(Application, Application.id == MeetingRoom.application_id)
# OLD CODE:         .filter(Application.job_id.in_(job_ids))
# OLD CODE:         .order_by(MeetingRoom.created_at.desc())
# OLD CODE:         .all()
# OLD CODE:     )
# OLD CODE:
# OLD CODE:     candidate_map = {}
# OLD CODE:     for room in rooms:
# OLD CODE:         app = room.application
# OLD CODE:         if app.candidate_user_id not in candidate_map:
# OLD CODE:             candidate_map[app.candidate_user_id] = app.candidate
# OLD CODE:
# OLD CODE:     from datetime import date as _date
# OLD CODE:     return render_template(
# OLD CODE:         'employer_meetings.html',
# OLD CODE:         company=company,
# OLD CODE:         rooms=rooms,
# OLD CODE:         job_map=job_map,
# OLD CODE:         candidate_map=candidate_map,
# OLD CODE:         now_date=_date.today().isoformat(),
# OLD CODE:     )
# OLD CODE:
# OLD CODE:
# OLD CODE: @employer.route('/employer/meetings/<int:room_id>/recordings')
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: def room_recordings(room_id):
# OLD CODE:     from daily_utils import get_recordings
# OLD CODE:     company = get_owned_company()
# OLD CODE:     room = MeetingRoom.query.get_or_404(room_id)
# OLD CODE:     job = Job.query.get_or_404(room.application.job_id)
# OLD CODE:     if job.company_id != company.id:
# OLD CODE:         abort(403)
# OLD CODE:
# OLD CODE:     api_key = current_app.config.get('DAILY_API_KEY')
# OLD CODE:     if not api_key:
# OLD CODE:         return jsonify({"error": "Daily.co not configured"}), 503
# OLD CODE:     try:
# OLD CODE:         recordings = get_recordings(api_key, room.room_name)
# OLD CODE:         return jsonify(recordings)
# OLD CODE:     except Exception as e:
# OLD CODE:         logger.exception("Failed to fetch recordings for room %s", room.room_name)
# OLD CODE:         return jsonify({"error": str(e)}), 502
# OLD CODE:
# OLD CODE:
# OLD CODE: @employer.route('/employer/meetings/<int:room_id>/recording/<recording_id>/link')
# OLD CODE: @login_required
# OLD CODE: @employer_required
# OLD CODE: def recording_link(room_id, recording_id):
# OLD CODE:     from daily_utils import get_recording_link
# OLD CODE:     company = get_owned_company()
# OLD CODE:     room = MeetingRoom.query.get_or_404(room_id)
# OLD CODE:     job = Job.query.get_or_404(room.application.job_id)
# OLD CODE:     if job.company_id != company.id:
# OLD CODE:         abort(403)
# OLD CODE:
# OLD CODE:     api_key = current_app.config.get('DAILY_API_KEY')
# OLD CODE:     if not api_key:
# OLD CODE:         return jsonify({"error": "Daily.co not configured"}), 503
# OLD CODE:     try:
# OLD CODE:         link = get_recording_link(api_key, recording_id)
# OLD CODE:         return jsonify({"download_link": link})
# OLD CODE:     except Exception as e:
# OLD CODE:         logger.exception("Failed to get recording link %s", recording_id)
# OLD CODE:         return jsonify({"error": str(e)}), 502
# OLD CODE:
# OLD CODE:
# OLD CODE: @employer.route('/companies/<int:company_id>')
# OLD CODE: def company_page(company_id):
# OLD CODE:     company = Company.query.get_or_404(company_id)
# OLD CODE:     open_jobs = Job.query.filter_by(company_id=company.id, status='open').order_by(Job.created_at.desc()).all()
# OLD CODE:     total_hires = Application.query.join(Job).filter(
# OLD CODE:         Job.company_id == company.id,
# OLD CODE:         Application.status == 'hired',
# OLD CODE:     ).count()
# OLD CODE:     member_count = CompanyMember.query.filter_by(company_id=company.id).count() + 1  # +1 for owner
# OLD CODE:     return render_template(
# OLD CODE:         "company_page.html",
# OLD CODE:         company=company,
# OLD CODE:         open_jobs=open_jobs,
# OLD CODE:         total_hires=total_hires,
# OLD CODE:         member_count=member_count,
# OLD CODE:     )
# ----------------------------------------------------------------
# NEW IMPLEMENTATION - active code starts below
# ----------------------------------------------------------------
"""Shared employer blueprint, helpers, and constants."""

import json
import logging
import os
import secrets
from functools import wraps
from PIL import Image

from flask import Blueprint, abort, current_app, redirect, url_for
from flask_login import current_user

from . import db
from .matching import (
    keyword_set, overlap_score, NOTIFY_SCORE_THRESHOLD, NOTIFY_MAX_RECIPIENTS,
)
from .models import Application, CandidateProfile, Company, CompanyMember, Notification
from datetime import datetime

logger = logging.getLogger(__name__)
employer = Blueprint('employer', __name__)

MAX_INTERVIEW_QUESTIONS = 15

TALENT_POOL_AI_LIMIT = 60  # cap on how many open-to-work profiles get sent to the AI ranker per call

_VERDICT_SCORE = {"Strong Yes": 100, "Yes": 75, "No": 25, "Strong No": 0}

PLATFORM_FEE_PERCENT = 15  # flat rate across every pay type

STANDARD_ANNUAL_HOURS = 2080  # 40hrs/week x 52 weeks - used to annualize hourly rates

HIRE_EVIDENCE_ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}

LOGO_ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

LOGO_MAX_SIZE = (800, 800)

INTERVIEW_LENGTH_OPTIONS = ["short", "standard", "thorough"]

STATUS_EMAIL_COPY = {
    "interviewing": {
        "subject_tpl": "Your application is moving forward - {job_title}",
        "heading": "You're being considered for the role",
        "body_tpl": (
            "Good news - {company} has moved your application for <strong>{job_title}</strong> "
            "into the interviewing stage. They'll be in touch with next steps."
        ),
    },
    "hired": {
        "subject_tpl": "You're hired - {job_title}",
        "heading": "Congratulations!",
        "body_tpl": (
            "{company} has decided to move forward with hiring you for the <strong>{job_title}</strong> "
            "position. They'll be in touch with next steps."
        ),
    },
    "rejected": {
        "subject_tpl": "Update on your application - {job_title}",
        "heading": "Application update",
        "body_tpl": (
            "Thank you for applying to <strong>{job_title}</strong> at {company}. After review, they've "
            "decided not to move forward with your application at this time. We encourage you to keep "
            "applying to other roles on the platform."
        ),
    },
}

def compute_composite_score(app, ai_data):
    """Weighted overall score. With both an AI-interview verdict and a
    manual (live/human) interview score: resume 30%, AI interview 30%,
    manual interview 30%, authenticity 10%. With only one of the two
    interview signals, that one fills the "interview" slot alone at 45% -
    resume 45%, authenticity 10%, same weighting as before this existed.
    With neither, falls back to resume score alone."""
    resume = app.match_score or 0
    ai_penalty = (ai_data.get("score", 0) if ai_data else 0)
    authenticity = 100 - ai_penalty

    ai_verdict = _VERDICT_SCORE.get(app.interview_verdict)
    manual = app.manual_interview_score

    if ai_verdict is not None and manual is not None:
        return round(resume * 0.30 + ai_verdict * 0.30 + manual * 0.30 + authenticity * 0.10)
    if ai_verdict is not None:
        return round(resume * 0.45 + ai_verdict * 0.45 + authenticity * 0.10)
    if manual is not None:
        return round(resume * 0.45 + manual * 0.45 + authenticity * 0.10)
    return resume

def _placement_fee_basis(application, job):
    """Return (basis_amount, fee_percent) for the placement fee.

    Uses the actual negotiated compensation entered by the employer when
    marking the candidate hired (application.hire_salary_usd/hire_pay_type),
    not the job posting's advertised salary - an employer has no incentive
    to keep the posting accurate once someone's actually hired, and the
    candidate cross-checks this figure before it's ever invoiced (see
    candidate.confirm_hire / candidate.dispute_hire). Falls back to the job
    posting only for legacy applications hired before this existed.

    Salaried/monthly roles use first-year compensation directly. Hourly
    roles are annualized to a comparable full-time figure first (then
    billed monthly for as long as the engagement is active - see
    _create_stripe_subscription_link). Same flat 15% rate throughout.
    """
    salary = application.hire_salary_usd or job.salary_usd
    pay_type = application.hire_pay_type or job.pay_type
    if not salary:
        return None, None
    if pay_type == 'hourly':
        return salary * STANDARD_ANNUAL_HOURS, PLATFORM_FEE_PERCENT
    if pay_type == 'monthly':
        return salary * 12, PLATFORM_FEE_PERCENT
    return salary, PLATFORM_FEE_PERCENT

def _hire_evidence_dir():
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], "hire_evidence")
    os.makedirs(path, exist_ok=True)
    return path

def _save_hire_evidence(application_id, file_storage):
    """Save an optional offer-letter/screenshot upload for a hire. Returns
    the stored filename, or None if no valid file was given."""
    if not file_storage or not file_storage.filename:
        return None
    ext = file_storage.filename.rsplit('.', 1)[-1].lower() if '.' in file_storage.filename else ''
    if ext not in HIRE_EVIDENCE_ALLOWED_EXTENSIONS:
        return None
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size <= 0 or size > 5 * 1024 * 1024:
        return None
    header = file_storage.stream.read(16)
    file_storage.stream.seek(0)
    if ext == 'pdf':
        if not header.startswith(b'%PDF-'):
            return None
    else:
        try:
            with Image.open(file_storage.stream) as image:
                image.verify()
        except Exception:
            return None
        file_storage.stream.seek(0)
    filename = f"{application_id}_{secrets.token_hex(8)}.{ext}"
    file_storage.save(os.path.join(_hire_evidence_dir(), filename))
    return filename

def get_user_company():
    """Return the Company this user owns or is a member of, or None."""
    company = Company.query.filter_by(owner_user_id=current_user.id).first()
    if company:
        return company
    membership = CompanyMember.query.filter_by(user_id=current_user.id).first()
    if membership:
        return membership.company
    return None

def employer_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user.role != 'employer':
            abort(403)
        if not get_user_company():
            return redirect(url_for('auth.complete_employer_profile'))
        return view(*args, **kwargs)
    return wrapped

def get_owned_company():
    company = get_user_company()
    if not company:
        abort(403)
    return company

def is_company_owner():
    return Company.query.filter_by(owner_user_id=current_user.id).first() is not None

def notify_candidates_of_new_job(job, company):
    """Cheap keyword-match nudge to candidates whose profile overlaps a job
    that just went live - not a replacement for the AI-ranked Suggested Jobs
    feature, just a lightweight "hey, this might interest you" at the moment
    a job is first posted/published, so it doesn't run a real AI call per
    candidate on every job post."""
    job_words = keyword_set(job.title, job.category, (job.description_text or '')[:500])
    if not job_words:
        return

    from sqlalchemy.orm import joinedload
    profiles = (
        CandidateProfile.query
        .filter(db.or_(CandidateProfile.skills.isnot(None), CandidateProfile.target_roles.isnot(None)))
        .options(joinedload(CandidateProfile.user))
        .limit(300)
        .all()
    )

    scored = []
    for prof in profiles:
        if not prof.user or not prof.user.notifications_enabled:
            continue
        words = keyword_set(prof.skills, prof.target_roles, prof.headline)
        score = overlap_score(words, job_words)
        if score >= NOTIFY_SCORE_THRESHOLD:
            scored.append((score, prof))
    scored.sort(key=lambda x: x[0], reverse=True)

    for _, prof in scored[:NOTIFY_MAX_RECIPIENTS]:
        db.session.add(Notification(
            user_id=prof.user_id,
            message=f"New job that fits your profile: {job.title} at {company.name}",
            link=url_for('candidate.job_detail', job_id=job.id),
        ))

def _extract_description_text(raw):
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            parts = []
            for key in ('about', 'requirements', 'preferred', 'what_you_do', 'contract_terms'):
                val = (data.get(key) or '').strip()
                if val:
                    parts.append(val)
            return '\n\n'.join(parts)
    except (ValueError, TypeError):
        pass
    return raw or ''

def _parse_interview_questions(raw):
    if not raw:
        return None
    try:
        questions = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(questions, list):
        return None
    cleaned = [q.strip() for q in questions if isinstance(q, str) and q.strip()]
    return json.dumps(cleaned[:MAX_INTERVIEW_QUESTIONS]) if cleaned else None

def _existing_interview_questions(job):
    if not job or not job.interview_questions:
        return []
    try:
        return json.loads(job.interview_questions)
    except (ValueError, TypeError):
        return []

def summarize_explanation(explanation, max_len=140):
    if not explanation:
        return "No summary available..."
    match_lines = [
        line.strip().lstrip('+').strip()
        for line in explanation.split('\n')
        if line.strip().startswith('+')
    ]
    text = " ".join(match_lines[:2]) if match_lines else explanation.strip().replace('\n', ' ')
    if len(text) > max_len:
        text = text[:max_len].rstrip()
    return text + "..."
