"""Candidate routes moved from candidate.py."""

from .candidate import (
    Application,
    AudioTooLargeError,
    Job,
    ThreadPoolExecutor,
    abort,
    audio_file_extension,
    candidate,
    current_user,
    extract_audio_for_transcription,
    flash,
    generate_interview_coaching,
    generate_interview_question_preview,
    json,
    jsonify,
    limiter,
    login_required,
    re,
    redirect,
    render_template,
    request,
    run_interview_turn,
    transcribe_audio,
    url_for,
)

# Moved from candidate.py: interview_coaching
@candidate.route('/applications/<int:application_id>/coaching')
@login_required
def interview_coaching(application_id):
    """Post-interview coaching report - private to the candidate."""
    application = Application.query.get_or_404(application_id)
    if application.candidate_user_id != current_user.id:
        abort(403)
    if not application.interview_transcript:
        flash("Complete your AI interview first to unlock the coaching report.", "info")
        return redirect(url_for('candidate.dashboard'))
    job = Job.query.get_or_404(application.job_id)
    secs = job.description_sections or {}
    try:
        coaching = generate_interview_coaching(
            transcript=application.interview_transcript,
            job_title=job.title,
            requirements=secs.get('requirements', ''),
            verdict=application.interview_verdict,
            match_score=application.match_score,
        )
    except Exception:
        flash("Coaching report temporarily unavailable. Please try again.", "error")
        return redirect(url_for('candidate.dashboard'))
    return render_template('interview_coaching.html', application=application, job=job, coaching=coaching)

# Moved from candidate.py: practice_interview
@candidate.route('/jobs/<int:job_id>/practice')
@login_required
def practice_interview(job_id):
    """Practice the AI interview for a job without it counting as your real attempt."""
    if current_user.role != 'candidate':
        abort(403)
    job = Job.query.get_or_404(job_id)
    if job.status != 'open':
        flash("This job is no longer accepting applications.", "info")
        return redirect(url_for('candidate.browse_jobs'))
    return render_template('practice_interview.html', job=job)

# Moved from candidate.py: practice_interview_chat
@candidate.route('/jobs/<int:job_id>/practice-chat', methods=['POST'])
@login_required
@limiter.limit("40 per hour")
def practice_interview_chat(job_id):
    """Stateless practice interview turn - no DB writes, returns coaching at conclusion."""
    job = Job.query.get_or_404(job_id)

    history = json.loads(request.form.get("history", "[]"))
    wrap_up = request.form.get("wrap_up", "false").lower() == "true"
    answer_audio = request.files.get("answer_audio")
    text_answer = (request.form.get("text_answer") or "").strip()

    user_message = text_answer  # text mode takes priority if provided
    if not user_message and answer_audio and answer_audio.filename:
        import tempfile, os as _os
        ext = audio_file_extension(answer_audio.filename)
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(answer_audio.read())
            tmp_path = tmp.name
        # See interview_chat() above for why this runs before transcribing -
        # strips video down to just audio so long answers fit under
        # Whisper's 25MB cap instead of the much smaller ceiling raw video hits.
        audio_path = extract_audio_for_transcription(tmp_path)
        try:
            user_message = transcribe_audio(audio_path)
        except AudioTooLargeError as e:
            return jsonify({"error": str(e)}), 400
        except Exception:
            return jsonify({"error": "Couldn't transcribe your answer. Please try again."}), 500
        finally:
            _os.unlink(tmp_path)
            if audio_path != tmp_path and _os.path.exists(audio_path):
                _os.unlink(audio_path)

    secs = job.description_sections or {}
    coaching = None

    if wrap_up:
        # force_conclude=True guarantees this turn ends in a verdict, not
        # another question - safe to kick off the coaching report
        # immediately instead of waiting for the verdict call to finish
        # first. That serial wait was the main reason "stop early" felt slow.
        transcript_lines = [f"{m.get('role')}: {m.get('content')}" for m in history]
        if user_message:
            transcript_lines.append(f"user: {user_message}")
        full_transcript = "\n".join(transcript_lines)

        with ThreadPoolExecutor(max_workers=2) as pool:
            # Never pass the real employer questions - practice uses generated
            # ones so the actual interview remains a surprise for the candidate.
            reply_future = pool.submit(
                run_interview_turn, job.title, job.description_text, user_message, history,
                force_conclude=True, interview_length=job.interview_length,
                interview_focus=job.interview_focus, interview_questions=None, practice_mode=True,
            )
            coaching_future = pool.submit(
                generate_interview_coaching, transcript=full_transcript, job_title=job.title,
                requirements=secs.get('requirements', ''), verdict=None, match_score=None,
            )
            try:
                reply = reply_future.result()
            except Exception:
                return jsonify({"error": "Failed to get a response. Please try again."}), 500
            try:
                coaching = coaching_future.result()
            except Exception:
                coaching = None
        should_conclude = True
    else:
        try:
            # Never pass the real employer questions - practice uses generated
            # ones so the actual interview remains a surprise for the candidate.
            reply = run_interview_turn(
                job.title, job.description_text, user_message, history, force_conclude=False,
                interview_length=job.interview_length, interview_focus=job.interview_focus,
                interview_questions=None, practice_mode=True,
            )
        except Exception:
            return jsonify({"error": "Failed to get a response. Please try again."}), 500

        verdict_match = re.search(r"Verdict:\s*(Strong Yes|Yes|No|Strong No)", reply, re.IGNORECASE)
        should_conclude = bool(verdict_match)
        if should_conclude:
            transcript_lines = [f"{m.get('role')}: {m.get('content')}" for m in history]
            transcript_lines.append(f"assistant: {reply}")
            full_transcript = "\n".join(transcript_lines)
            try:
                coaching = generate_interview_coaching(
                    transcript=full_transcript,
                    job_title=job.title,
                    requirements=secs.get('requirements', ''),
                    verdict=None,
                    match_score=None,
                )
            except Exception:
                coaching = None

    return jsonify({
        "reply": reply,
        "reply_audio_url": None,
        "transcribed_answer": user_message,
        "text_answer": text_answer,
        "concluded": should_conclude,
        "coaching": coaching,
    })

# Moved from candidate.py: practice_questions
@candidate.route('/jobs/<int:job_id>/practice-questions', methods=['POST'])
@login_required
@limiter.limit("15 per hour")
def practice_questions(job_id):
    """On-demand sample question list for a role, generated fresh each time -
    an alternative to the live back-and-forth practice chat for a candidate
    who'd rather just see what kinds of questions to expect and prepare
    answers on their own time."""
    if current_user.role != 'candidate':
        abort(403)
    job = Job.query.get_or_404(job_id)
    try:
        questions = generate_interview_question_preview(
            job.title, job.description_text,
            interview_length=job.interview_length, interview_focus=job.interview_focus,
        )
    except Exception:
        return jsonify({"error": "Couldn't generate questions right now. Please try again."}), 500
    return jsonify({"questions": questions})

