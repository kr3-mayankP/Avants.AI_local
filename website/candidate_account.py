"""Candidate routes moved from candidate.py."""

from .candidate import (
    Application,
    CandidateProfile,
    Company,
    Job,
    Message,
    Notification,
    SavedJob,
    User,
    _company_recipients,
    abort,
    candidate,
    current_user,
    db,
    delete_interview_videos,
    external_url,
    flash,
    func,
    jsonify,
    login_required,
    redirect,
    render_template,
    request,
    send_branded_email,
    url_for,
)

# Moved from candidate.py: withdraw_application
@candidate.route('/applications/<int:application_id>/withdraw', methods=['POST'])
@login_required
def withdraw_application(application_id):
    application = Application.query.get_or_404(application_id)
    if application.candidate_user_id != current_user.id:
        abort(403)
    if application.status == 'hired':
        flash("You can't withdraw from a position you've already been hired for.", "error")
        return redirect(url_for('candidate.dashboard'))
    application.withdrawn = True
    db.session.commit()
    flash("Application withdrawn.", "success")
    return redirect(url_for('candidate.dashboard'))

# Moved from candidate.py: confirm_hire
@candidate.route('/applications/<int:application_id>/confirm-hire', methods=['POST'])
@login_required
def confirm_hire(application_id):
    """Candidate-side verification that a hire actually happened - the employer's
    placement fee invoice only fires after this, not the moment they click 'hired'."""
    application = Application.query.get_or_404(application_id)
    if application.candidate_user_id != current_user.id:
        abort(403)
    if application.status != 'hired':
        abort(400)

    if not application.candidate_confirmed_hire:
        application.candidate_confirmed_hire = True
        application.hire_confirmed_at = func.now()
        application.hire_salary_disputed = False  # confirming clears any earlier dispute
        db.session.commit()

        job = Job.query.get(application.job_id)
        company = Company.query.get(job.company_id)
        employer_user = User.query.get(company.owner_user_id)

        for recipient in _company_recipients(company):
            db.session.add(Notification(
                user_id=recipient.id,
                #new change: include both name fields in hire notifications.
                message=f"{current_user.full_name or current_user.email} confirmed their hire for {job.title}.",
                link=url_for('employer.applicants', job_id=job.id),
            ))
        db.session.commit()

        if employer_user:
            from .employer_billing import send_hire_fee_invoice
            send_hire_fee_invoice(application, job, company, current_user, employer_user)

    flash("Thanks for confirming! We've let the employer know.", "success")
    return redirect(url_for('candidate.dashboard'))

# Moved from candidate.py: dispute_hire
@candidate.route('/applications/<int:application_id>/dispute-hire', methods=['POST'])
@login_required
def dispute_hire(application_id):
    """Candidate says the compensation the employer entered isn't accurate.
    Flags the application instead of confirming - the placement fee invoice
    stays on hold until the employer corrects it and the candidate confirms."""
    application = Application.query.get_or_404(application_id)
    if application.candidate_user_id != current_user.id:
        abort(403)
    if application.status != 'hired':
        abort(400)

    application.hire_salary_disputed = True
    application.candidate_confirmed_hire = False
    application.hire_confirmed_at = None

    from .employer import _save_hire_evidence
    evidence_filename = _save_hire_evidence(application.id, request.files.get('hire_evidence'))
    if evidence_filename:
        application.hire_evidence_filename = evidence_filename

    db.session.commit()

    job = Job.query.get(application.job_id)
    company = Company.query.get(job.company_id)

    for recipient in _company_recipients(company):
        db.session.add(Notification(
            user_id=recipient.id,
            #new change: include both name fields in dispute notifications.
            message=f"{current_user.full_name or current_user.email} disputed the hire compensation for {job.title} - the placement fee invoice is on hold.",
            link=url_for('employer.applicants', job_id=job.id),
        ))
    db.session.commit()

    for recipient in _company_recipients(company):
        try:
            send_branded_email(
                to_email=recipient.email,
                subject=f"Hire compensation disputed - {job.title}",
                heading="Candidate flagged the compensation figure",
                body_html=(
                    #new change: show the candidate's full name in the dispute email.
                    f"<strong>{current_user.full_name or current_user.email}</strong> says the compensation entered for their hire as "
                    f"<strong>{job.title}</strong> isn't accurate. The placement fee invoice is on hold until you "
                    f"correct it and they re-confirm."
                ),
                plain_text=(
                    f"{current_user.full_name or current_user.email} disputed the hire compensation for {job.title}. "
                    f"The placement fee invoice is on hold until you correct it and they re-confirm."
                ),
                cta_label="Review Applicant",
                cta_url=external_url('employer.applicants', job_id=job.id),
            )
        except Exception as e:
            print("Dispute notification email failed:", e)

    flash("We've flagged this for the employer to review. The placement fee won't be invoiced until it's corrected.", "info")
    return redirect(url_for('candidate.dashboard'))

# Moved from candidate.py: notifications
@candidate.route('/notifications')
@login_required
def notifications():
    notifs = (
        Notification.query.filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(30)
        .all()
    )
    unread = sum(1 for n in notifs if not n.read)
    return jsonify({
        "notifications": [
            {
                "id": n.id,
                "message": n.message,
                "link": n.link,
                "read": n.read,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in notifs
        ],
        "unread_count": unread,
        "notifications_enabled": current_user.notifications_enabled,
    })

# Moved from candidate.py: mark_notifications_read
@candidate.route('/notifications/read-all', methods=['POST'])
@login_required
def mark_notifications_read():
    Notification.query.filter_by(user_id=current_user.id, read=False).update({"read": True})
    db.session.commit()
    return jsonify({"status": "ok"})

# Moved from candidate.py: notification_preferences
@candidate.route('/notifications/preferences', methods=['POST'])
@login_required
def notification_preferences():
    data = request.get_json() or {}
    current_user.notifications_enabled = bool(data.get("enabled", True))
    db.session.commit()
    return jsonify({"notifications_enabled": current_user.notifications_enabled})

# Moved from candidate.py: candidate_messages_json
@candidate.route('/candidate/applications/<int:application_id>/messages.json')
@login_required
def candidate_messages_json(application_id):
    application = Application.query.get_or_404(application_id)
    if application.candidate_user_id != current_user.id:
        abort(403)

    # Mark employer messages as read
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

# Moved from candidate.py: candidate_send_message
@candidate.route('/candidate/applications/<int:application_id>/message', methods=['POST'])
@login_required
def candidate_send_message(application_id):
    application = Application.query.get_or_404(application_id)
    if application.candidate_user_id != current_user.id:
        abort(403)

    body = (request.json or {}).get('body', '').strip() if request.is_json else request.form.get('body', '').strip()
    if not body:
        return jsonify({"error": "Message body is required"}), 400

    msg = Message(application_id=application_id, sender_user_id=current_user.id, body=body)
    db.session.add(msg)

    # Notify employer
    job = application.job
    employer_company = job.company
    owner = db.session.get(type(current_user), employer_company.owner_user_id)
    if owner:
        notif = Notification(
            user_id=owner.id,
            #new change: use the candidate's full name in the message notification.
            message=f"{current_user.full_name or current_user.email} sent a message about their {job.title} application.",
            link=url_for('employer.applicants', job_id=job.id),
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

# Moved from candidate.py: delete_account
@candidate.route('/account/delete', methods=['GET', 'POST'])
@login_required
def delete_account():
    if current_user.role != 'candidate':
        abort(403)

    if request.method == 'POST':
        confirm = request.form.get('confirm', '').strip().lower()
        if confirm != 'delete my account':
            flash("Type exactly 'delete my account' to confirm.", "error")
            return render_template('delete_account.html')

        user = current_user
        from flask_login import logout_user as _logout

        # Wipe personal data from all applications
        apps = Application.query.filter_by(candidate_user_id=user.id).all()
        for app in apps:
            delete_interview_videos(app.id)
            app.resume_text = '[deleted]'
            app.interview_transcript = None
            app.interview_audio_log = None
            app.work_authorization = None
            app.match_explanation = None
            app.skills_roadmap = None
            app.interview_saved_session = None

        # Delete profile
        profile = CandidateProfile.query.filter_by(user_id=user.id).first()
        if profile:
            db.session.delete(profile)

        # Delete notifications, saved jobs, messages
        Notification.query.filter_by(user_id=user.id).delete()
        SavedJob.query.filter_by(user_id=user.id).delete()
        Message.query.filter_by(sender_user_id=user.id).delete()

        # Anonymise the user record
        user.first_name = 'Deleted'
        #new change: remove the surname too when anonymising a deleted account.
        user.last_name = None
        user.email = f'deleted_{user.id}@deleted.invalid'
        user.password = None
        user.email_verified = False

        db.session.commit()
        _logout()
        flash("Your account and personal data have been deleted.", "success")
        return redirect(url_for('views.home'))

    return render_template('delete_account.html')

