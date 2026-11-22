# ----------------------------------------------------------------
# CHANGE BLOCK: 2026-11-22
# OLD IMPLEMENTATION - commented snapshot from Git HEAD
# ----------------------------------------------------------------
# OLD CODE: import stripe
# OLD CODE: from flask import Blueprint, render_template, redirect, url_for, request, current_app, Response, abort
# OLD CODE: from flask_login import current_user, login_required
# OLD CODE: from datetime import timezone
# OLD CODE: from sqlalchemy.sql import func
# OLD CODE:
# OLD CODE: from . import db
# OLD CODE: from .models import Application, Job, User, Company, MeetingRoom, Referral, Notification
# OLD CODE: from .employer import _placement_fee_basis
# OLD CODE: from .candidate import _company_recipients
# OLD CODE: from email_utils import send_branded_email, external_url
# OLD CODE:
# OLD CODE: REFERRAL_COMMISSION_PERCENT = 10  # referrer's cut of the platform's placement fee, not of the hire's salary
# OLD CODE:
# OLD CODE: views = Blueprint('views', __name__)
# OLD CODE:
# OLD CODE: def _landing_context():
# OLD CODE:     latest_jobs = (Job.query
# OLD CODE:         .filter_by(status='open')
# OLD CODE:         .order_by(Job.created_at.desc())
# OLD CODE:         .limit(8)
# OLD CODE:         .all())
# OLD CODE:
# OLD CODE:     job_data = [{"job": job} for job in latest_jobs]
# OLD CODE:
# OLD CODE:     return {"job_data": job_data}
# OLD CODE:
# OLD CODE:
# OLD CODE: @views.route('/')
# OLD CODE: @views.route('/home')
# OLD CODE: def home():
# OLD CODE:     if current_user.is_authenticated:
# OLD CODE:         if current_user.role == 'employer':
# OLD CODE:             return redirect(url_for('employer.dashboard'))
# OLD CODE:         return redirect(url_for('candidate.browse_jobs'))
# OLD CODE:
# OLD CODE:     return render_template("landing.html", **_landing_context())
# OLD CODE:
# OLD CODE:
# OLD CODE: @views.route('/site')
# OLD CODE: def public_site():
# OLD CODE:     """Marketing landing page for signed-in users - home() bounces them
# OLD CODE:     straight to their dashboard, so this is the only way to see it again
# OLD CODE:     while logged in."""
# OLD CODE:     return render_template("landing.html", **_landing_context())
# OLD CODE:
# OLD CODE:
# OLD CODE: def _credit_referral(application):
# OLD CODE:     """Owe the referrer 10% of the platform's 15% placement fee, once,
# OLD CODE:     the first time an application's fee is actually paid. No-ops if the
# OLD CODE:     hired candidate wasn't referred, or a Referral already exists for this
# OLD CODE:     application (the unique constraint on application_id also guards this)."""
# OLD CODE:     candidate = User.query.get(application.candidate_user_id)
# OLD CODE:     if not candidate or not candidate.referred_by_user_id:
# OLD CODE:         return
# OLD CODE:     if Referral.query.filter_by(application_id=application.id).first():
# OLD CODE:         return
# OLD CODE:
# OLD CODE:     basis_amount, fee_percent = _placement_fee_basis(application, application.job)
# OLD CODE:     if not basis_amount or not fee_percent:
# OLD CODE:         return
# OLD CODE:
# OLD CODE:     platform_fee = basis_amount * fee_percent / 100
# OLD CODE:     commission = round(platform_fee * REFERRAL_COMMISSION_PERCENT / 100)
# OLD CODE:     if commission <= 0:
# OLD CODE:         return
# OLD CODE:
# OLD CODE:     db.session.add(Referral(
# OLD CODE:         referrer_user_id=candidate.referred_by_user_id,
# OLD CODE:         referred_user_id=candidate.id,
# OLD CODE:         application_id=application.id,
# OLD CODE:         commission_usd=commission,
# OLD CODE:     ))
# OLD CODE:
# OLD CODE:
# OLD CODE: @views.route('/stripe/webhook', methods=['POST'])
# OLD CODE: def stripe_webhook():
# OLD CODE:     """Stripe sends checkout.session.completed when a payment link is paid.
# OLD CODE:     We look up the application by metadata and mark fee_paid = True."""
# OLD CODE:     stripe.api_key = current_app.config.get("STRIPE_SECRET_KEY")
# OLD CODE:     webhook_secret = current_app.config.get("STRIPE_WEBHOOK_SECRET")
# OLD CODE:
# OLD CODE:     payload = request.get_data(as_text=False)
# OLD CODE:     sig_header = request.headers.get("Stripe-Signature", "")
# OLD CODE:
# OLD CODE:     try:
# OLD CODE:         if webhook_secret:
# OLD CODE:             event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
# OLD CODE:         else:
# OLD CODE:             event = stripe.Event.construct_from(
# OLD CODE:                 stripe.util.convert_to_stripe_object(request.get_json()),
# OLD CODE:                 stripe.api_key,
# OLD CODE:             )
# OLD CODE:     except (ValueError, stripe.error.SignatureVerificationError):
# OLD CODE:         return "Bad request", 400
# OLD CODE:
# OLD CODE:     if event["type"] == "checkout.session.completed":
# OLD CODE:         session = event["data"]["object"]
# OLD CODE:         metadata = session["metadata"] if "metadata" in session else {}
# OLD CODE:         app_id = metadata["application_id"] if "application_id" in metadata else None
# OLD CODE:         if app_id:
# OLD CODE:             application = Application.query.get(int(app_id))
# OLD CODE:             if application:
# OLD CODE:                 if not application.fee_paid:
# OLD CODE:                     application.fee_paid = True
# OLD CODE:                     _credit_referral(application)
# OLD CODE:                 # Hourly hires check out in subscription mode - capture the
# OLD CODE:                 # subscription id so employer.end_hourly_engagement can
# OLD CODE:                 # cancel it later when the engagement actually ends.
# OLD CODE:                 subscription_id = session.get("subscription")
# OLD CODE:                 if subscription_id and not application.hire_billing_subscription_id:
# OLD CODE:                     application.hire_billing_subscription_id = subscription_id
# OLD CODE:                 db.session.commit()
# OLD CODE:
# OLD CODE:     elif event["type"] == "customer.subscription.deleted":
# OLD CODE:         # Covers cancellations that happen directly in Stripe (not via the
# OLD CODE:         # "End Engagement" button), so the app's state doesn't drift out of
# OLD CODE:         # sync with what's actually being billed.
# OLD CODE:         subscription = event["data"]["object"]
# OLD CODE:         sub_id = subscription.get("id")
# OLD CODE:         if sub_id:
# OLD CODE:             application = Application.query.filter_by(hire_billing_subscription_id=sub_id).first()
# OLD CODE:             if application and not application.hire_engagement_ended_at:
# OLD CODE:                 application.hire_engagement_ended_at = func.now()
# OLD CODE:                 db.session.commit()
# OLD CODE:
# OLD CODE:     return "", 200
# OLD CODE:
# OLD CODE:
# OLD CODE: @views.route('/sitemap.xml')
# OLD CODE: def sitemap():
# OLD CODE:     jobs = Job.query.filter_by(status='open').order_by(Job.created_at.desc()).all()
# OLD CODE:     base = request.host_url.rstrip('/')
# OLD CODE:
# OLD CODE:     def _lastmod(job):
# OLD CODE:         dt = job.created_at
# OLD CODE:         if dt and dt.tzinfo is None:
# OLD CODE:             dt = dt.replace(tzinfo=timezone.utc)
# OLD CODE:         return dt.strftime('%Y-%m-%d') if dt else ''
# OLD CODE:
# OLD CODE:     urls = [
# OLD CODE:         f"<url><loc>{base}/jobs</loc><changefreq>daily</changefreq><priority>0.9</priority></url>",
# OLD CODE:         f"<url><loc>{base}/</loc><changefreq>weekly</changefreq><priority>1.0</priority></url>",
# OLD CODE:     ]
# OLD CODE:     for job in jobs:
# OLD CODE:         loc = f"{base}/jobs/{job.id}"
# OLD CODE:         lm = _lastmod(job)
# OLD CODE:         urls.append(f"<url><loc>{loc}</loc>{'<lastmod>' + lm + '</lastmod>' if lm else ''}<changefreq>weekly</changefreq><priority>0.8</priority></url>")
# OLD CODE:
# OLD CODE:     xml = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join(urls) + '</urlset>'
# OLD CODE:     return Response(xml, mimetype='application/xml')
# OLD CODE:
# OLD CODE:
# OLD CODE: def _resolve_meeting_access(room):
# OLD CODE:     """Returns (application, is_employer) for the current user's relationship
# OLD CODE:     to this meeting room, or aborts 403 if they have none."""
# OLD CODE:     application = Application.query.get_or_404(room.application_id)
# OLD CODE:
# OLD CODE:     if current_user.id == application.candidate_user_id:
# OLD CODE:         return application, False
# OLD CODE:     if current_user.role == 'employer':
# OLD CODE:         job = Job.query.get_or_404(application.job_id)
# OLD CODE:         from .models import CompanyMember
# OLD CODE:         owns = Company.query.filter_by(owner_user_id=current_user.id, id=job.company_id).first()
# OLD CODE:         member = CompanyMember.query.filter_by(user_id=current_user.id, company_id=job.company_id).first()
# OLD CODE:         if not owns and not member:
# OLD CODE:             abort(403)
# OLD CODE:         return application, True
# OLD CODE:     abort(403)
# OLD CODE:
# OLD CODE:
# OLD CODE: @views.route('/meeting/<room_name>')
# OLD CODE: @login_required
# OLD CODE: def join_meeting(room_name):
# OLD CODE:     room = MeetingRoom.query.filter_by(room_name=room_name).first_or_404()
# OLD CODE:     application, is_employer = _resolve_meeting_access(room)
# OLD CODE:     return render_template('meeting_room.html', room=room, application=application, is_employer=is_employer)
# OLD CODE:
# OLD CODE:
# OLD CODE: @views.route('/meeting/<room_name>/recording', methods=['POST'])
# OLD CODE: @login_required
# OLD CODE: def upload_meeting_recording_route(room_name):
# OLD CODE:     """Receives a participant's own local-camera recording of the call (see
# OLD CODE:     meeting_room.html's client-side MediaRecorder), uploaded once they click
# OLD CODE:     'Save & Leave' rather than on every chunk - keeps this to one request per
# OLD CODE:     person per call."""
# OLD CODE:     room = MeetingRoom.query.filter_by(room_name=room_name).first_or_404()
# OLD CODE:     application, is_employer = _resolve_meeting_access(room)
# OLD CODE:
# OLD CODE:     recording = request.files.get('recording')
# OLD CODE:     if not recording or not recording.filename:
# OLD CODE:         return {"error": "No recording provided."}, 400
# OLD CODE:
# OLD CODE:     from video_storage import upload_meeting_recording
# OLD CODE:
# OLD CODE:     try:
# OLD CODE:         path = upload_meeting_recording(
# OLD CODE:             room.id, 'employer' if is_employer else 'candidate', recording.read(),
# OLD CODE:             content_type=recording.content_type or "video/webm",
# OLD CODE:         )
# OLD CODE:     except Exception:
# OLD CODE:         current_app.logger.exception(f"Failed to upload meeting recording for room {room.id}")
# OLD CODE:         return {"error": "Upload failed."}, 502
# OLD CODE:
# OLD CODE:     if is_employer:
# OLD CODE:         room.employer_recording_path = path
# OLD CODE:     else:
# OLD CODE:         room.candidate_recording_path = path
# OLD CODE:     db.session.commit()
# OLD CODE:
# OLD CODE:     if not is_employer:
# OLD CODE:         _notify_company_of_interview_recording(room, application)
# OLD CODE:
# OLD CODE:     return {"status": "saved"}
# OLD CODE:
# OLD CODE:
# OLD CODE: def _notify_company_of_interview_recording(room, application):
# OLD CODE:     """The candidate's side of the interview is the one the employer actually
# OLD CODE:     wants to review - once it's saved, let the whole company know (not just
# OLD CODE:     whoever happened to schedule the room), same as every other company-wide
# OLD CODE:     notification in this app."""
# OLD CODE:     job = application.job
# OLD CODE:     company = job.company
# OLD CODE:     candidate = application.candidate
# OLD CODE:     join_url = external_url('views.join_meeting', room_name=room.room_name)
# OLD CODE:     candidate_name = candidate.first_name or candidate.email
# OLD CODE:
# OLD CODE:     for recipient in _company_recipients(company):
# OLD CODE:         db.session.add(Notification(
# OLD CODE:             user_id=recipient.id,
# OLD CODE:             message=f"{candidate_name}'s interview recording for {job.title} is ready to watch.",
# OLD CODE:             link=url_for('views.join_meeting', room_name=room.room_name),
# OLD CODE:         ))
# OLD CODE:     db.session.commit()
# OLD CODE:
# OLD CODE:     for recipient in _company_recipients(company):
# OLD CODE:         try:
# OLD CODE:             send_branded_email(
# OLD CODE:                 to_email=recipient.email,
# OLD CODE:                 subject=f"Interview recording ready - {candidate_name} / {job.title}",
# OLD CODE:                 heading="Interview recording ready to watch",
# OLD CODE:                 body_html=(
# OLD CODE:                     f"<strong>{candidate_name}</strong>'s interview for <strong>{job.title}</strong> "
# OLD CODE:                     f"has finished, and their recording is ready to watch."
# OLD CODE:                 ),
# OLD CODE:                 plain_text=(
# OLD CODE:                     f"{candidate_name}'s interview for {job.title} has finished, and their "
# OLD CODE:                     f"recording is ready to watch.\n\nWatch it here: {join_url}"
# OLD CODE:                 ),
# OLD CODE:                 cta_label="Watch Recording",
# OLD CODE:                 cta_url=join_url,
# OLD CODE:             )
# OLD CODE:         except Exception:
# OLD CODE:             current_app.logger.exception(f"Failed to send interview-recording-ready email for room {room.id}")
# OLD CODE:
# OLD CODE:
# OLD CODE: @views.route('/meeting/<room_name>/recording/<role>')
# OLD CODE: @login_required
# OLD CODE: def play_meeting_recording(room_name, role):
# OLD CODE:     if role not in ('candidate', 'employer'):
# OLD CODE:         abort(404)
# OLD CODE:
# OLD CODE:     room = MeetingRoom.query.filter_by(room_name=room_name).first_or_404()
# OLD CODE:     _resolve_meeting_access(room)  # any authorized party may view either side's recording
# OLD CODE:
# OLD CODE:     path = room.employer_recording_path if role == 'employer' else room.candidate_recording_path
# OLD CODE:     if not path:
# OLD CODE:         abort(404)
# OLD CODE:
# OLD CODE:     from video_storage import get_signed_meeting_recording_url
# OLD CODE:     return redirect(get_signed_meeting_recording_url(path))
# OLD CODE:
# OLD CODE:
# OLD CODE: @views.route('/terms')
# OLD CODE: def terms():
# OLD CODE:     return render_template('terms.html')
# OLD CODE:
# OLD CODE:
# OLD CODE: @views.route('/privacy')
# OLD CODE: def privacy():
# OLD CODE:     return render_template('privacy.html')
# OLD CODE:
# OLD CODE:
# OLD CODE: @views.route('/robots.txt')
# OLD CODE: def robots():
# OLD CODE:     content = f"User-agent: *\nAllow: /\nDisallow: /employer/\nDisallow: /candidate/\nDisallow: /admin/\nSitemap: {request.host_url.rstrip('/')}/sitemap.xml\n"
# OLD CODE:     return Response(content, mimetype='text/plain')
# ----------------------------------------------------------------
# NEW IMPLEMENTATION - active code starts below
# ----------------------------------------------------------------
import stripe
from flask import Blueprint, render_template, redirect, url_for, request, current_app, Response, abort
from flask_login import current_user, login_required
from datetime import timezone
from sqlalchemy.sql import func

from . import db
from .models import Application, Job, User, Company, MeetingRoom, Referral, Notification, StripeWebhookEvent
from .employer import _placement_fee_basis
from .candidate import _company_recipients
from email_utils import send_branded_email, external_url

REFERRAL_COMMISSION_PERCENT = 10  # referrer's cut of the platform's placement fee, not of the hire's salary

views = Blueprint('views', __name__)

def _landing_context():
    latest_jobs = (Job.query
        .filter_by(status='open')
        .order_by(Job.created_at.desc())
        .limit(8)
        .all())

    job_data = [{"job": job} for job in latest_jobs]

    return {"job_data": job_data}


@views.route('/')
@views.route('/home')
def home():
    if current_user.is_authenticated:
        if current_user.role == 'employer':
            return redirect(url_for('employer.dashboard'))
        return redirect(url_for('candidate.browse_jobs'))

    return render_template("landing.html", **_landing_context())


@views.route('/site')
def public_site():
    """Marketing landing page for signed-in users - home() bounces them
    straight to their dashboard, so this is the only way to see it again
    while logged in."""
    return render_template("landing.html", **_landing_context())


def _credit_referral(application):
    """Owe the referrer 10% of the platform's 15% placement fee, once,
    the first time an application's fee is actually paid. No-ops if the
    hired candidate wasn't referred, or a Referral already exists for this
    application (the unique constraint on application_id also guards this)."""
    candidate = User.query.get(application.candidate_user_id)
    if not candidate or not candidate.referred_by_user_id:
        return
    if Referral.query.filter_by(application_id=application.id).first():
        return

    basis_amount, fee_percent = _placement_fee_basis(application, application.job)
    if not basis_amount or not fee_percent:
        return

    platform_fee = basis_amount * fee_percent / 100
    commission = round(platform_fee * REFERRAL_COMMISSION_PERCENT / 100)
    if commission <= 0:
        return

    db.session.add(Referral(
        referrer_user_id=candidate.referred_by_user_id,
        referred_user_id=candidate.id,
        application_id=application.id,
        commission_usd=commission,
    ))


@views.route('/stripe/webhook', methods=['POST'])
def stripe_webhook():
    """Stripe sends checkout.session.completed when a payment link is paid.
    We look up the application by metadata and mark fee_paid = True."""
    stripe.api_key = current_app.config.get("STRIPE_SECRET_KEY")
    webhook_secret = current_app.config.get("STRIPE_WEBHOOK_SECRET")

    payload = request.get_data(as_text=False)
    sig_header = request.headers.get("Stripe-Signature", "")

    if not webhook_secret:
        current_app.logger.error("Stripe webhook secret is not configured.")
        return "Webhook verification unavailable", 503

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        return "Bad request", 400

    event_id = event.get("id")
    if event_id:
        if StripeWebhookEvent.query.filter_by(event_id=event_id).first():
            return "", 200
        db.session.add(StripeWebhookEvent(event_id=event_id))
        db.session.commit()

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        metadata = session["metadata"] if "metadata" in session else {}
        app_id = metadata["application_id"] if "application_id" in metadata else None
        if app_id:
            application = Application.query.get(int(app_id))
            if application:
                if not application.fee_paid:
                    application.fee_paid = True
                    _credit_referral(application)
                # Hourly hires check out in subscription mode - capture the
                # subscription id so employer.end_hourly_engagement can
                # cancel it later when the engagement actually ends.
                subscription_id = session.get("subscription")
                if subscription_id and not application.hire_billing_subscription_id:
                    application.hire_billing_subscription_id = subscription_id
                db.session.commit()

    elif event["type"] == "customer.subscription.deleted":
        # Covers cancellations that happen directly in Stripe (not via the
        # "End Engagement" button), so the app's state doesn't drift out of
        # sync with what's actually being billed.
        subscription = event["data"]["object"]
        sub_id = subscription.get("id")
        if sub_id:
            application = Application.query.filter_by(hire_billing_subscription_id=sub_id).first()
            if application and not application.hire_engagement_ended_at:
                application.hire_engagement_ended_at = func.now()
                db.session.commit()

    return "", 200


@views.route('/sitemap.xml')
def sitemap():
    jobs = Job.query.filter_by(status='open').order_by(Job.created_at.desc()).all()
    base = request.host_url.rstrip('/')

    def _lastmod(job):
        dt = job.created_at
        if dt and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime('%Y-%m-%d') if dt else ''

    urls = [
        f"<url><loc>{base}/jobs</loc><changefreq>daily</changefreq><priority>0.9</priority></url>",
        f"<url><loc>{base}/</loc><changefreq>weekly</changefreq><priority>1.0</priority></url>",
    ]
    for job in jobs:
        loc = f"{base}/jobs/{job.id}"
        lm = _lastmod(job)
        urls.append(f"<url><loc>{loc}</loc>{'<lastmod>' + lm + '</lastmod>' if lm else ''}<changefreq>weekly</changefreq><priority>0.8</priority></url>")

    xml = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join(urls) + '</urlset>'
    return Response(xml, mimetype='application/xml')


def _resolve_meeting_access(room):
    """Returns (application, is_employer) for the current user's relationship
    to this meeting room, or aborts 403 if they have none."""
    application = Application.query.get_or_404(room.application_id)

    if current_user.id == application.candidate_user_id:
        return application, False
    if current_user.role == 'employer':
        job = Job.query.get_or_404(application.job_id)
        from .models import CompanyMember
        owns = Company.query.filter_by(owner_user_id=current_user.id, id=job.company_id).first()
        member = CompanyMember.query.filter_by(user_id=current_user.id, company_id=job.company_id).first()
        if not owns and not member:
            abort(403)
        return application, True
    abort(403)


@views.route('/meeting/<room_name>')
@login_required
def join_meeting(room_name):
    room = MeetingRoom.query.filter_by(room_name=room_name).first_or_404()
    application, is_employer = _resolve_meeting_access(room)
    return render_template('meeting_room.html', room=room, application=application, is_employer=is_employer)


@views.route('/meeting/<room_name>/recording', methods=['POST'])
@login_required
def upload_meeting_recording_route(room_name):
    """Receives a participant's own local-camera recording of the call (see
    meeting_room.html's client-side MediaRecorder), uploaded once they click
    'Save & Leave' rather than on every chunk - keeps this to one request per
    person per call."""
    room = MeetingRoom.query.filter_by(room_name=room_name).first_or_404()
    application, is_employer = _resolve_meeting_access(room)

    recording = request.files.get('recording')
    if not recording or not recording.filename:
        return {"error": "No recording provided."}, 400

    from video_storage import upload_meeting_recording

    try:
        path = upload_meeting_recording(
            room.id, 'employer' if is_employer else 'candidate', recording.read(),
            content_type=recording.content_type or "video/webm",
        )
    except Exception:
        current_app.logger.exception(f"Failed to upload meeting recording for room {room.id}")
        return {"error": "Upload failed."}, 502

    if is_employer:
        room.employer_recording_path = path
    else:
        room.candidate_recording_path = path
    db.session.commit()

    if not is_employer:
        _notify_company_of_interview_recording(room, application)

    return {"status": "saved"}


def _notify_company_of_interview_recording(room, application):
    """The candidate's side of the interview is the one the employer actually
    wants to review - once it's saved, let the whole company know (not just
    whoever happened to schedule the room), same as every other company-wide
    notification in this app."""
    job = application.job
    company = job.company
    candidate = application.candidate
    join_url = external_url('views.join_meeting', room_name=room.room_name)
    #new change: use both stored name fields in the company notification.
    candidate_name = candidate.full_name or candidate.email

    for recipient in _company_recipients(company):
        db.session.add(Notification(
            user_id=recipient.id,
            message=f"{candidate_name}'s interview recording for {job.title} is ready to watch.",
            link=url_for('views.join_meeting', room_name=room.room_name),
        ))
    db.session.commit()

    for recipient in _company_recipients(company):
        try:
            send_branded_email(
                to_email=recipient.email,
                subject=f"Interview recording ready - {candidate_name} / {job.title}",
                heading="Interview recording ready to watch",
                body_html=(
                    f"<strong>{candidate_name}</strong>'s interview for <strong>{job.title}</strong> "
                    f"has finished, and their recording is ready to watch."
                ),
                plain_text=(
                    f"{candidate_name}'s interview for {job.title} has finished, and their "
                    f"recording is ready to watch.\n\nWatch it here: {join_url}"
                ),
                cta_label="Watch Recording",
                cta_url=join_url,
            )
        except Exception:
            current_app.logger.exception(f"Failed to send interview-recording-ready email for room {room.id}")


@views.route('/meeting/<room_name>/recording/<role>')
@login_required
def play_meeting_recording(room_name, role):
    if role not in ('candidate', 'employer'):
        abort(404)

    room = MeetingRoom.query.filter_by(room_name=room_name).first_or_404()
    _resolve_meeting_access(room)  # any authorized party may view either side's recording

    path = room.employer_recording_path if role == 'employer' else room.candidate_recording_path
    if not path:
        abort(404)

    from video_storage import get_signed_meeting_recording_url
    return redirect(get_signed_meeting_recording_url(path))


@views.route('/terms')
def terms():
    return render_template('terms.html')


@views.route('/privacy')
def privacy():
    return render_template('privacy.html')


@views.route('/robots.txt')
def robots():
    content = f"User-agent: *\nAllow: /\nDisallow: /employer/\nDisallow: /candidate/\nDisallow: /admin/\nSitemap: {request.host_url.rstrip('/')}/sitemap.xml\n"
    return Response(content, mimetype='text/plain')
