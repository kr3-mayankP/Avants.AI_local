"""Candidate routes moved from candidate.py."""

from .candidate import (
    Application,
    CandidateProfile,
    Feedback,
    MeetingProposal,
    MeetingRoom,
    Notification,
    abort,
    candidate,
    current_user,
    db,
    external_url,
    flash,
    generate_skills_roadmap,
    json,
    login_required,
    redirect,
    render_template,
    request,
    send_branded_email,
    url_for,
)

# Moved from candidate.py: dashboard
@candidate.route('/candidate/dashboard')
@login_required
def dashboard():
    applications = (
        Application.query.filter_by(candidate_user_id=current_user.id)
        .order_by(Application.created_at.desc())
        .all()
    )
    meetings = {
        app.id: json.loads(app.scheduled_meeting) if app.scheduled_meeting else None
        for app in applications
    }

    # Lazily generate skills roadmap for low-scoring applications that don't have one yet
    roadmaps_generated = False
    for app in applications:
        if (app.match_score is not None and app.match_score < 65
                and not app.skills_roadmap and app.status != 'hired'):
            try:
                secs = app.job.description_sections or {}
                steps = generate_skills_roadmap(
                    job_title=app.job.title,
                    match_explanation=app.match_explanation or '',
                    match_score=app.match_score,
                    requirements=secs.get('requirements', ''),
                )
                app.skills_roadmap = json.dumps(steps)
                roadmaps_generated = True
            except Exception:
                pass
    if roadmaps_generated:
        db.session.commit()

    # Parse roadmaps for template
    roadmaps = {}
    for app in applications:
        if app.skills_roadmap:
            try:
                roadmaps[app.id] = json.loads(app.skills_roadmap)
            except Exception:
                pass

    candidate_profile = CandidateProfile.query.filter_by(user_id=current_user.id).first()
    has_profile = bool(candidate_profile and (candidate_profile.resume_text or '').strip())

    from datetime import date as _date
    today = _date.today().isoformat()
    app_ids = [a.id for a in applications]
    try:
        upcoming_interviews = (
            MeetingRoom.query
            .filter(MeetingRoom.application_id.in_(app_ids))
            .filter(MeetingRoom.scheduled_date >= today)
            .order_by(MeetingRoom.scheduled_date, MeetingRoom.scheduled_time)
            .all()
        ) if app_ids else []
        pending_proposals = (
            MeetingProposal.query
            .filter(MeetingProposal.application_id.in_(app_ids))
            .filter_by(status='pending')
            .count()
        ) if app_ids else 0
    except Exception:
        db.session.rollback()
        upcoming_interviews = []
        pending_proposals = 0

    given_feedback = {
        (f.application_id, f.context)
        for f in Feedback.query.filter_by(user_id=current_user.id).filter(Feedback.application_id.in_(app_ids)).all()
    } if app_ids else set()

    # One feedback prompt per application - prefer the resolution prompt over
    # the interview one if both would apply, since it's the more final moment.
    feedback_prompts = {}
    for app in applications:
        if app.status in ('hired', 'rejected') and (app.id, 'application_resolved') not in given_feedback:
            feedback_prompts[app.id] = 'application_resolved'
        elif app.interview_verdict and app.interview_verdict != 'Pending' and (app.id, 'interview_completed') not in given_feedback:
            feedback_prompts[app.id] = 'interview_completed'

    return render_template(
        "candidate_dashboard.html",
        applications=applications,
        meetings=meetings,
        has_profile=has_profile,
        roadmaps=roadmaps,
        upcoming_interviews=upcoming_interviews,
        pending_proposals=pending_proposals,
        feedback_prompts=feedback_prompts,
    )

# Moved from candidate.py: accept_slot
@candidate.route('/candidate/proposals/<int:proposal_id>/accept', methods=['POST'])
@login_required
def accept_slot(proposal_id):
    from daily_utils import create_room as _create_room
    from flask import current_app

    proposal = MeetingProposal.query.get_or_404(proposal_id)
    application = Application.query.get_or_404(proposal.application_id)
    if application.candidate_user_id != current_user.id:
        abort(403)
    if proposal.status != 'pending':
        flash("This scheduling request is no longer active.", "error")
        return redirect(url_for('candidate.interviews'))

    slot_index = request.form.get('slot')
    slots = json.loads(proposal.slots)
    try:
        slot = slots[int(slot_index)]
    except (TypeError, IndexError, ValueError):
        flash("Please select a time slot.", "error")
        return redirect(url_for('candidate.interviews'))

    api_key = current_app.config.get('DAILY_API_KEY')
    if not api_key:
        flash("Video rooms are not configured yet - contact support.", "error")
        return redirect(url_for('candidate.interviews'))

    try:
        room_data = _create_room(api_key)
    except Exception as e:
        flash(f"Could not create room: {e}", "error")
        return redirect(url_for('candidate.interviews'))

    room = MeetingRoom(
        application_id=application.id,
        employer_user_id=proposal.employer_user_id,
        room_name=room_data['name'],
        room_url=room_data['url'],
        scheduled_date=slot['date'],
        scheduled_time=slot['time'],
        notes=proposal.notes,
    )
    db.session.add(room)

    proposal.status = 'accepted'
    proposal.accepted_slot = json.dumps(slot)

    join_url = external_url('views.join_meeting', room_name=room_data['name'])
    application.scheduled_meeting = json.dumps({
        'type': 'virtual', 'date': slot['date'], 'time': slot['time'],
        'location_or_url': join_url, 'notes': proposal.notes or '', 'in_app': True,
    })

    employer = proposal.employer
    #new change: use both stored name fields in interview confirmation messages.
    candidate_name = current_user.full_name or current_user.email
    notif = Notification(
        user_id=employer.id,
        message=f"{candidate_name} confirmed {slot['date']} at {slot['time']} for {application.job.title}.",
        link=url_for('employer.employer_meetings'),
    )
    db.session.add(notif)
    db.session.commit()

    try:
        send_branded_email(
            to_email=employer.email,
            subject=f"Interview confirmed - {application.job.title}",
            heading="Interview time confirmed",
            body_html=(
                f"<strong>{candidate_name}</strong> has confirmed "
                f"<strong>{slot['date']}</strong> at <strong>{slot['time']}</strong> "
                f"for <strong>{application.job.title}</strong>.<br><br>"
                "The interview room is ready."
            ),
            plain_text=(
                f"{candidate_name} confirmed the interview:\n"
                f"Job: {application.job.title}\nDate: {slot['date']}\nTime: {slot['time']}\n\nJoin: {join_url}\n"
            ),
            cta_label="Join Interview Room",
            cta_url=join_url,
        )
    except Exception:
        pass

    flash(f"Interview confirmed for {slot['date']} at {slot['time']}. The room is ready!", "success")
    return redirect(url_for('candidate.interviews'))

# Moved from candidate.py: interviews
@candidate.route('/candidate/interviews')
@login_required
def interviews():
    """Candidate-facing page showing all their scheduled meetings."""
    from datetime import date as _date
    applications = Application.query.filter_by(candidate_user_id=current_user.id).all()
    app_ids = [a.id for a in applications]
    app_map = {a.id: a for a in applications}

    rooms = (
        MeetingRoom.query
        .filter(MeetingRoom.application_id.in_(app_ids))
        .order_by(MeetingRoom.scheduled_date.asc(), MeetingRoom.scheduled_time.asc())
        .all()
    )

    today = _date.today().isoformat()
    upcoming = [r for r in rooms if (r.scheduled_date or '') >= today]
    past     = [r for r in rooms if (r.scheduled_date or '') < today]

    pending_proposals = (
        MeetingProposal.query
        .filter(MeetingProposal.application_id.in_(app_ids))
        .filter_by(status='pending')
        .order_by(MeetingProposal.created_at.desc())
        .all()
    ) if app_ids else []

    return render_template(
        'candidate_interviews.html',
        upcoming=upcoming,
        past=past,
        app_map=app_map,
        pending_proposals=pending_proposals,
    )

# Moved from candidate.py: submit_platform_feedback
@candidate.route('/applications/<int:application_id>/platform-feedback', methods=['POST'])
@login_required
def submit_platform_feedback(application_id):
    application = Application.query.get_or_404(application_id)
    if application.candidate_user_id != current_user.id:
        abort(403)

    context = request.form.get('context', '')
    if context not in ('interview_completed', 'application_resolved'):
        flash("Something went wrong - please try again.", "error")
        return redirect(request.referrer or url_for('candidate.dashboard'))

    rating = request.form.get('rating', type=int)
    if not rating or rating < 1 or rating > 5:
        flash("Please select a rating from 1 to 5.", "error")
        return redirect(request.referrer or url_for('candidate.dashboard'))

    comment = (request.form.get('comment') or '').strip()

    existing = Feedback.query.filter_by(
        user_id=current_user.id, application_id=application_id, context=context
    ).first()
    if not existing:
        db.session.add(Feedback(
            user_id=current_user.id,
            application_id=application_id,
            role='candidate',
            context=context,
            rating=rating,
            comment=comment or None,
        ))
        db.session.commit()

    flash("Thanks for the feedback!", "success")
    return redirect(request.referrer or url_for('candidate.dashboard'))

