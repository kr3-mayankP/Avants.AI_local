"""Candidate routes moved from candidate.py."""

from .candidate import (
    Application,
    AudioTooLargeError,
    Job,
    Notification,
    _audio_dir_for_application,
    _can_access_application_audio,
    abort,
    analyze_ai_likelihood,
    candidate,
    create_interview_answer_upload_url,
    current_user,
    db,
    download_interview_answer_to_file,
    extract_audio_for_transcription,
    get_signed_video_url,
    httpx,
    json,
    jsonify,
    limiter,
    logger,
    login_required,
    os,
    re,
    redirect,
    render_template,
    request,
    run_interview_turn,
    send_from_directory,
    synthesize_speech,
    transcribe_audio,
    url_for,
    uuid,
)

# Moved from candidate.py: interview
@candidate.route('/jobs/<int:job_id>/apply/<int:application_id>/interview')
@login_required
def interview(job_id, application_id):
    application = Application.query.get_or_404(application_id)
    if application.candidate_user_id != current_user.id:
        abort(403)
    job = Job.query.get_or_404(job_id)
    already_done = bool(application.interview_transcript)
    saved_session = None
    if not already_done and application.interview_saved_session:
        try:
            saved_session = json.loads(application.interview_saved_session)
        except (ValueError, TypeError):
            pass
    return render_template("ai_interview.html", job=job, application=application,
                           already_done=already_done, saved_session=saved_session)

# Moved from candidate.py: save_interview_session
@candidate.route('/jobs/<int:job_id>/apply/<int:application_id>/save-session', methods=['POST'])
@login_required
def save_interview_session(job_id, application_id):
    application = Application.query.get_or_404(application_id)
    if application.candidate_user_id != current_user.id:
        abort(403)
    data = request.get_json() or {}
    history = data.get('history', [])
    application.interview_saved_session = json.dumps(history)
    db.session.commit()
    return jsonify({'status': 'saved'})

# Moved from candidate.py: interview_answer_upload_url
@candidate.route('/jobs/<int:job_id>/apply/<int:application_id>/interview-answer-upload-url', methods=['POST'])
@login_required
@limiter.limit("120 per hour")
def interview_answer_upload_url(job_id, application_id):
    """Hands back a one-time signed URL the browser uploads a recorded
    answer to directly in Supabase Storage, instead of sending it through
    this app's own /interview-chat route. Needed because large uploads to
    avants.ai itself get rejected at the edge well under what a longer
    answer needs - a direct-to-storage upload bypasses that entirely since
    the big transfer never touches this app's domain."""
    application = Application.query.get_or_404(application_id)
    if application.candidate_user_id != current_user.id:
        abort(403)

    audio_log = json.loads(application.interview_audio_log) if application.interview_audio_log else []
    turn_number = len(audio_log) + 1
    content_type = (request.get_json(silent=True) or {}).get('content_type') or 'video/webm'

    try:
        upload_url, path = create_interview_answer_upload_url(application_id, turn_number, content_type)
    except Exception:
        logger.exception(f"Failed to create a signed interview-answer upload URL for application {application_id}")
        return jsonify({"error": "Couldn't prepare the upload. Please try again."}), 500

    return jsonify({
        "upload_url": upload_url,
        "path": path,
        "anon_key": os.environ.get("SUPABASE_ANON_KEY"),
    })

# Moved from candidate.py: interview_chat
@candidate.route('/jobs/<int:job_id>/apply/<int:application_id>/interview-chat', methods=['POST'])
@login_required
@limiter.limit("60 per hour")
def interview_chat(job_id, application_id):
    application = Application.query.get_or_404(application_id)
    if application.candidate_user_id != current_user.id:
        abort(403)
    job = Job.query.get_or_404(job_id)

    history = json.loads(request.form.get("history", "[]"))
    wrap_up = request.form.get("wrap_up", "false").lower() == "true"
    video_path_uploaded = request.form.get("video_path") or None
    has_video = request.form.get("has_video", "false").lower() == "true"

    audio_log = json.loads(application.interview_audio_log) if application.interview_audio_log else []
    audio_dir = _audio_dir_for_application(application_id)

    user_message = ""
    if video_path_uploaded:
        # The browser already uploaded the recording directly to Supabase
        # Storage (see interview_answer_upload_url above) - this is just a
        # throwaway local copy of that same file for transcription. The
        # permanent recording candidates/employers play back later is the
        # direct-to-storage upload itself, never touched by anything below.
        ext = os.path.splitext(video_path_uploaded)[1] or ".webm"
        tmp_path = os.path.join(audio_dir, f"_tmp_{uuid.uuid4().hex}{ext}")

        try:
            download_interview_answer_to_file(video_path_uploaded, tmp_path)
        except httpx.TimeoutException:
            logger.exception(f"Timed out fetching uploaded interview answer for application {application_id}")
            return jsonify({"error": "That answer took too long to fetch for processing. Please try again."}), 400
        except Exception:
            logger.exception(f"Failed to fetch uploaded interview answer for application {application_id}")
            return jsonify({"error": "Couldn't find your uploaded answer. Please try again."}), 400

        # Strips the video down to just its audio track before Whisper -
        # the picture data (not the speech) is almost all of a video
        # answer's size, so this is what actually lets a long recording fit
        # under Whisper's fixed 25MB cap instead of the roughly-a-minute
        # ceiling raw video hit before. No-ops back to tmp_path if ffmpeg
        # isn't available.
        audio_path = extract_audio_for_transcription(tmp_path)
        try:
            user_message = transcribe_audio(audio_path)
        except AudioTooLargeError as e:
            os.remove(tmp_path)
            if audio_path != tmp_path and os.path.exists(audio_path):
                os.remove(audio_path)
            return jsonify({"error": str(e)}), 400
        except Exception:
            os.remove(tmp_path)
            if audio_path != tmp_path and os.path.exists(audio_path):
                os.remove(audio_path)
            return jsonify({"error": "Couldn't transcribe your answer. Please try again."}), 500
        os.remove(tmp_path)
        if audio_path != tmp_path and os.path.exists(audio_path):
            os.remove(audio_path)

        audio_log.append({
            "role": "user", "text": user_message,
            "video_path": video_path_uploaded, "has_video": has_video,
        })

    try:
        interview_questions = json.loads(job.interview_questions) if job.interview_questions else None
        reply = run_interview_turn(
            job.title, job.description_text, user_message, history, force_conclude=wrap_up,
            interview_length=job.interview_length, interview_focus=job.interview_focus,
            interview_questions=interview_questions,
        )
    except Exception:
        return jsonify({"error": "Failed to get a response. Please try again."}), 500

    verdict_match = re.search(r"Verdict:\s*(Strong Yes|Yes|No|Strong No)", reply, re.IGNORECASE)
    should_conclude = bool(verdict_match) or wrap_up

    if wrap_up and not verdict_match:
        # The model was told to conclude but didn't return a parseable verdict
        # line - retry once with the same context before falling back to
        # "Pending", so a single off-format reply doesn't permanently strand
        # this application with no usable grade (see job_applicants.html's
        # "interviewing"-styled Pending badge for how that's surfaced).
        logger.warning(f"Interview conclude for application {application_id} returned no parseable verdict on first try - retrying")
        try:
            retry_reply = run_interview_turn(
                job.title, job.description_text, user_message, history, force_conclude=True,
                interview_length=job.interview_length, interview_focus=job.interview_focus,
                interview_questions=interview_questions,
            )
            retry_match = re.search(r"Verdict:\s*(Strong Yes|Yes|No|Strong No)", retry_reply, re.IGNORECASE)
            if retry_match:
                reply, verdict_match = retry_reply, retry_match
        except Exception:
            logger.exception(f"Verdict retry failed for application {application_id}")
        if not verdict_match:
            logger.error(f"Application {application_id} concluded with no parseable verdict after retry - grading falls back to resume-only")

    question_filename = f"q_{len(audio_log) + 1}.mp3"
    try:
        synthesize_speech(reply, os.path.join(audio_dir, question_filename))
        reply_audio_url = url_for('candidate.application_audio', application_id=application_id, filename=question_filename)
    except Exception:
        reply_audio_url = None

    audio_log.append({"role": "assistant", "text": reply, "audio_filename": question_filename if reply_audio_url else None})
    application.interview_audio_log = json.dumps(audio_log)

    if should_conclude:
        transcript_lines = [f"{m.get('role')}: {m.get('content')}" for m in history]
        transcript_lines.append(f"assistant: {reply}")
        application.interview_transcript = "\n".join(transcript_lines)
        application.interview_saved_session = None  # clear saved session on completion
        verdict = verdict_match.group(1).title() if verdict_match else "Pending"
        application.interview_verdict = verdict
        application.status = 'interviewing'
        try:
            ai_result = analyze_ai_likelihood(application.interview_transcript, job.title)
            application.ai_likelihood = json.dumps(ai_result)
        except Exception:
            pass

        if current_user.notifications_enabled:
            job = Job.query.get(job_id)
            positive = "Yes" in verdict
            notif = Notification(
                user_id=current_user.id,
                message=(
                    f"Your AI interview for {job.title} is complete - verdict: {verdict}."
                    if positive else
                    f"Your AI interview for {job.title} is complete. The employer will review your result."
                ),
                link=url_for('candidate.dashboard', _external=False),
            )
            db.session.add(notif)

    db.session.commit()

    return jsonify({
        "reply": reply,
        "reply_audio_url": reply_audio_url,
        "transcribed_answer": user_message,
        "concluded": should_conclude,
    })

# Moved from candidate.py: application_audio
@candidate.route('/applications/<int:application_id>/audio/<filename>')
@login_required
def application_audio(application_id, filename):
    application = Application.query.get_or_404(application_id)
    if not _can_access_application_audio(application):
        abort(403)
    return send_from_directory(_audio_dir_for_application(application_id), filename)

# Moved from candidate.py: application_video
@candidate.route('/applications/<int:application_id>/interview-video/<int:log_index>')
@login_required
def application_video(application_id, log_index):
    """Redirects to a freshly-generated signed URL for a recorded answer,
    rather than storing/exposing the signed URL itself - those expire, and
    regenerating one per request means it's never stale."""
    application = Application.query.get_or_404(application_id)
    if not _can_access_application_audio(application):
        abort(403)
    log = json.loads(application.interview_audio_log) if application.interview_audio_log else []
    if log_index < 0 or log_index >= len(log) or not log[log_index].get('video_path'):
        abort(404)
    try:
        signed_url = get_signed_video_url(log[log_index]['video_path'])
    except Exception:
        logger.exception(f"Failed to generate signed video URL for application {application_id}")
        abort(502)
    return redirect(signed_url)

