"""Employer meeting and messaging routes moved from employer.py."""

import json
import logging

from flask import (
    abort, current_app, flash, jsonify, redirect, render_template, request,
    url_for,
)
from flask_login import current_user, login_required

from email_utils import external_url, send_branded_email
from . import db
from .employer import employer, employer_required, get_owned_company
from .models import (
    Application, Job, MeetingProposal, Notification, Message, MeetingRoom,
)

logger = logging.getLogger(__name__)

# Moved from employer.py: schedule_meeting
@employer.route('/employer/applications/<int:application_id>/schedule-meeting', methods=['POST'])
@login_required
@employer_required
def schedule_meeting(application_id):
    company = get_owned_company()
    application = Application.query.get_or_404(application_id)
    job = Job.query.get_or_404(application.job_id)
    if job.company_id != company.id:
        abort(403)

    meeting_type = request.form.get('meeting_type')
    date = request.form.get('date', '').strip()
    time = request.form.get('time', '').strip()
    location_or_url = request.form.get('location_or_url', '').strip()
    notes = request.form.get('notes', '').strip()

    if meeting_type not in ('virtual', 'in_person') or not date or not time or not location_or_url:
        flash("Date, time, and a meeting link or address are required.", "error")
        return redirect(url_for('employer.applicants', job_id=job.id))

    meeting = {"type": meeting_type, "date": date, "time": time, "location_or_url": location_or_url, "notes": notes}
    application.scheduled_meeting = json.dumps(meeting)
    db.session.commit()

    kind_label = "video call" if meeting_type == 'virtual' else "in-person meeting"
    where_label = f"Link: {location_or_url}" if meeting_type == 'virtual' else f"Location: {location_or_url}"
    candidate = application.candidate
    try:
        send_branded_email(
            to_email=candidate.email,
            subject=f"Meeting scheduled - {job.title} at {company.name}",
            heading="A meeting has been scheduled",
            body_html=(
                f"Hi {candidate.first_name or ''},<br><br>"
                f"<strong>{company.name}</strong> would like to meet with you about your application for "
                f"<strong>{job.title}</strong>.<br><br>"
                f"<strong>Type:</strong> {kind_label}<br>"
                f"<strong>Date:</strong> {date}<br>"
                f"<strong>Time:</strong> {time}<br>"
                f"<strong>{'Link' if meeting_type == 'virtual' else 'Location'}:</strong> {location_or_url}"
                + (f"<br><br><strong>Notes:</strong> {notes}" if notes else "")
            ),
            plain_text=(
                f"Hi {candidate.first_name or ''},\n\n"
                f"{company.name} would like to meet with you about your application for {job.title}.\n\n"
                f"Type: {kind_label}\nDate: {date}\nTime: {time}\n{where_label}\n"
                + (f"\nNotes: {notes}\n" if notes else "")
            ),
            cta_label="View My Applications" if meeting_type == 'virtual' else None,
            cta_url=external_url('candidate.dashboard') if meeting_type == 'virtual' else None,
        )
        flash("Meeting scheduled and the candidate has been emailed.", "success")
    except Exception as e:
        print("Meeting email send failed:", e)
        flash("Meeting saved, but the notification email couldn't be sent.", "error")

    return redirect(url_for('employer.applicants', job_id=job.id))

# Moved from employer.py: propose_times
@employer.route('/employer/applications/<int:application_id>/propose-times', methods=['POST'])
@login_required
@employer_required
def propose_times(application_id):
    company = get_owned_company()
    application = Application.query.get_or_404(application_id)
    job = Job.query.get_or_404(application.job_id)
    if job.company_id != company.id:
        abort(403)

    notes = request.form.get('notes', '').strip()
    slots = []
    for i in range(1, 4):
        d = request.form.get(f'date_{i}', '').strip()
        t = request.form.get(f'time_{i}', '').strip()
        if d and t:
            slots.append({'date': d, 'time': t})

    if not slots:
        flash("Add at least one time slot.", "error")
        return redirect(url_for('employer.applicants', job_id=job.id))

    # Cancel any existing pending proposal for this application
    MeetingProposal.query.filter_by(
        application_id=application_id, status='pending'
    ).update({'status': 'expired'})

    proposal = MeetingProposal(
        application_id=application_id,
        employer_user_id=current_user.id,
        slots=json.dumps(slots),
        notes=notes or None,
    )
    db.session.add(proposal)

    candidate = application.candidate
    notif = Notification(
        user_id=candidate.id,
        message=f"{company.name} wants to schedule an interview for {job.title} - pick a time!",
        link=url_for('candidate.interviews'),
    )
    db.session.add(notif)
    db.session.commit()

    try:
        slot_lines = ''.join(
            f"<li><strong>{s['date']}</strong> at {s['time']}</li>" for s in slots
        )
        send_branded_email(
            to_email=candidate.email,
            subject=f"{company.name} wants to schedule an interview - {job.title}",
            heading=f"{company.name} wants to meet you!",
            body_html=(
                f"Hi {candidate.first_name or 'there'},<br><br>"
                f"<strong>{company.name}</strong> would like to schedule a live video interview "
                f"for <strong>{job.title}</strong>. Pick whichever time works best for you:<br><br>"
                f"<ul>{slot_lines}</ul>"
                + (f"<br><strong>Notes:</strong> {notes}<br>" if notes else "")
                + "<br>Click below to choose your slot - the interview room will be created instantly."
            ),
            plain_text=(
                f"Hi {candidate.first_name or 'there'},\n\n"
                f"{company.name} wants to interview you for {job.title}.\n\n"
                "Available times:\n"
                + ''.join(f"  • {s['date']} at {s['time']}\n" for s in slots)
                + (f"\nNotes: {notes}\n" if notes else "")
            ),
            cta_label="Pick a Time",
            cta_url=external_url('candidate.interviews'),
        )
        #new change: show the candidate's combined name in the success message.
        flash(f"Time slots sent to {candidate.full_name or candidate.email}.", "success")
    except Exception:
        flash("Proposal saved - email notification failed.", "error")

    return redirect(url_for('employer.applicants', job_id=job.id))

# Moved from employer.py: messages_json
@employer.route('/employer/applications/<int:application_id>/messages.json')
@login_required
@employer_required
def messages_json(application_id):
    company = get_owned_company()
    application = Application.query.get_or_404(application_id)
    job = Job.query.get_or_404(application.job_id)
    if job.company_id != company.id:
        abort(403)

    # Mark unread messages (from candidate) as read
    Message.query.filter_by(application_id=application_id, read=False).filter(
        Message.sender_user_id != current_user.id
    ).update({"read": True})
    db.session.commit()

    msgs = Message.query.filter_by(application_id=application_id).order_by(Message.created_at).all()
    return jsonify([{
        "id": m.id,
        "body": m.body,
        #new change: provide the sender's combined name to the messaging UI.
        "sender_name": m.sender.full_name or m.sender.email,
        "is_mine": m.sender_user_id == current_user.id,
        "time": m.created_at.strftime("%b %d, %H:%M") if m.created_at else "",
    } for m in msgs])

# Moved from employer.py: send_message
@employer.route('/employer/applications/<int:application_id>/message', methods=['POST'])
@login_required
@employer_required
def send_message(application_id):
    company = get_owned_company()
    application = Application.query.get_or_404(application_id)
    job = Job.query.get_or_404(application.job_id)
    if job.company_id != company.id:
        abort(403)

    body = (request.json or {}).get('body', '').strip() if request.is_json else request.form.get('body', '').strip()
    if not body:
        return jsonify({"error": "Message body is required"}), 400

    msg = Message(application_id=application_id, sender_user_id=current_user.id, body=body)
    db.session.add(msg)

    # Notify candidate
    candidate = application.candidate
    notif = Notification(
        user_id=candidate.id,
        message=f"New message from {company.name} about your {job.title} application.",
        link=url_for('candidate.dashboard'),
    )
    db.session.add(notif)
    db.session.commit()

    return jsonify({
        "id": msg.id,
        "body": msg.body,
        #new change: provide the sender's combined name to the messaging UI.
        "sender_name": current_user.full_name or current_user.email,
        "is_mine": True,
        "time": msg.created_at.strftime("%b %d, %H:%M") if msg.created_at else "",
    })

# Moved from employer.py: create_meeting_room
@employer.route('/employer/applications/<int:application_id>/meeting/create', methods=['POST'])
@login_required
@employer_required
def create_meeting_room(application_id):
    from daily_utils import create_room
    company = get_owned_company()
    application = Application.query.get_or_404(application_id)
    job = Job.query.get_or_404(application.job_id)
    if job.company_id != company.id:
        abort(403)

    date = request.form.get('date', '').strip()
    time_ = request.form.get('time', '').strip()
    notes = request.form.get('notes', '').strip()

    if not date or not time_:
        flash("Date and time are required.", "error")
        return redirect(url_for('employer.applicants', job_id=job.id))

    api_key = current_app.config.get('DAILY_API_KEY')
    if not api_key:
        flash("Daily.co API key is not configured.", "error")
        return redirect(url_for('employer.applicants', job_id=job.id))

    try:
        room_data = create_room(api_key)
    except Exception as e:
        logger.exception("Daily.co room creation failed")
        flash(f"Could not create meeting room: {e}", "error")
        return redirect(url_for('employer.applicants', job_id=job.id))

    room = MeetingRoom(
        application_id=application_id,
        employer_user_id=current_user.id,
        room_name=room_data['name'],
        room_url=room_data['url'],
        scheduled_date=date,
        scheduled_time=time_,
        notes=notes or None,
    )
    db.session.add(room)

    join_url = external_url('views.join_meeting', room_name=room_data['name'])
    application.scheduled_meeting = json.dumps({
        "type": "virtual",
        "date": date,
        "time": time_,
        "location_or_url": join_url,
        "notes": notes,
        "in_app": True,
    })
    db.session.commit()

    candidate = application.candidate

    # In-app notification (shows in the bell)
    notif = Notification(
        user_id=candidate.id,
        message=f"{company.name} wants to meet you! Interview scheduled for {job.title} on {date} at {time_}.",
        link=url_for('candidate.interviews'),
    )
    db.session.add(notif)
    db.session.commit()

    # Email
    try:
        send_branded_email(
            to_email=candidate.email,
            subject=f"{company.name} wants to interview you - {job.title}",
            heading=f"{company.name} wants to meet you!",
            body_html=(
                f"Hi {candidate.first_name or 'there'},<br><br>"
                f"Great news - <strong>{company.name}</strong> has scheduled a live video interview "
                f"with you for <strong>{job.title}</strong>.<br><br>"
                f"<strong>Date:</strong> {date}<br>"
                f"<strong>Time:</strong> {time_}<br>"
                + (f"<strong>Notes:</strong> {notes}<br>" if notes else "")
                + "<br>The interview takes place directly on Avants - no Zoom needed. "
                "Click the button below when it's time."
            ),
            plain_text=(
                f"Hi {candidate.first_name or 'there'},\n\n"
                f"{company.name} has scheduled a live interview for {job.title}.\n\n"
                f"Date: {date}\nTime: {time_}\n"
                + (f"Notes: {notes}\n" if notes else "")
                + f"\nJoin here: {join_url}\n"
            ),
            cta_label="Join Interview",
            cta_url=join_url,
        )
        flash("Interview room created - candidate notified by email and in-app.", "success")
    except Exception:
        flash("Interview room created and candidate notified in-app (email failed).", "error")

    return redirect(url_for('employer.applicants', job_id=job.id))

# Moved from employer.py: employer_meetings
@employer.route('/employer/meetings')
@login_required
@employer_required
def employer_meetings():
    company = get_owned_company()
    jobs = Job.query.filter_by(company_id=company.id).all()
    job_ids = [j.id for j in jobs]
    job_map = {j.id: j for j in jobs}

    rooms = (
        MeetingRoom.query
        .join(Application, Application.id == MeetingRoom.application_id)
        .filter(Application.job_id.in_(job_ids))
        .order_by(MeetingRoom.created_at.desc())
        .all()
    )

    candidate_map = {}
    for room in rooms:
        app = room.application
        if app.candidate_user_id not in candidate_map:
            candidate_map[app.candidate_user_id] = app.candidate

    from datetime import date as _date
    return render_template(
        'employer_meetings.html',
        company=company,
        rooms=rooms,
        job_map=job_map,
        candidate_map=candidate_map,
        now_date=_date.today().isoformat(),
    )

# Moved from employer.py: room_recordings
@employer.route('/employer/meetings/<int:room_id>/recordings')
@login_required
@employer_required
def room_recordings(room_id):
    from daily_utils import get_recordings
    company = get_owned_company()
    room = MeetingRoom.query.get_or_404(room_id)
    job = Job.query.get_or_404(room.application.job_id)
    if job.company_id != company.id:
        abort(403)

    api_key = current_app.config.get('DAILY_API_KEY')
    if not api_key:
        return jsonify({"error": "Daily.co not configured"}), 503
    try:
        recordings = get_recordings(api_key, room.room_name)
        return jsonify(recordings)
    except Exception as e:
        logger.exception("Failed to fetch recordings for room %s", room.room_name)
        return jsonify({"error": str(e)}), 502

# Moved from employer.py: recording_link
@employer.route('/employer/meetings/<int:room_id>/recording/<recording_id>/link')
@login_required
@employer_required
def recording_link(room_id, recording_id):
    from daily_utils import get_recording_link
    company = get_owned_company()
    room = MeetingRoom.query.get_or_404(room_id)
    job = Job.query.get_or_404(room.application.job_id)
    if job.company_id != company.id:
        abort(403)

    api_key = current_app.config.get('DAILY_API_KEY')
    if not api_key:
        return jsonify({"error": "Daily.co not configured"}), 503
    try:
        link = get_recording_link(api_key, recording_id)
        return jsonify({"download_link": link})
    except Exception as e:
        logger.exception("Failed to get recording link %s", recording_id)
        return jsonify({"error": str(e)}), 502

