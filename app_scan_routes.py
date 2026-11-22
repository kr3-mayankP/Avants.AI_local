"""Routes moved from app.py; registered on the existing Flask app."""

from app import (
    AudioTooLargeError,
    JOB_FIT_VERDICT_SCORE,
    ThreadPoolExecutor,
    VALID_INTERVIEW_LENGTHS,
    _SCAN_PATH_RE,
    _VIDEO_SCAN_JOBS,
    _VIDEO_SCAN_JOBS_MAX,
    app,
    audio_file_extension,
    create_scan_upload_url,
    current_user,
    delete_scan,
    download_scan_to_file,
    extract_audio_for_transcription,
    extract_text_from_file,
    generate_interview_coaching,
    generate_interview_question_preview,
    generate_job_fit_verdict,
    generate_practice_questions,
    httpx,
    json,
    jsonify,
    limiter,
    logger,
    os,
    re,
    render_template,
    request,
    run_interview_turn,
    threading,
    transcribe_audio,
    uuid
)

# Moved from app.py: resumemat_video_upload_url
@app.route('/resume-jobmatch/video-feedback/upload-url', methods=['POST'])
@limiter.limit("30 per hour")
def resumemat_video_upload_url():
    """Hands back a one-time signed URL the browser uploads the raw video
    to directly in Supabase Storage, instead of sending it to this app's own
    /video-feedback route. Needed because large uploads to avants.ai itself
    get rejected at the edge (Render/Cloudflare) well under what a longer
    interview video needs - a direct-to-storage upload bypasses that
    entirely since the big transfer never touches this app's domain."""
    if not current_user.is_authenticated:
        return jsonify({"error": "Please log in to use this feature.", "login_required": True}), 401

    filename = (request.get_json(silent=True) or {}).get('filename') or ''
    ext = audio_file_extension(filename)
    try:
        upload_url, path = create_scan_upload_url(ext)
    except Exception:
        logger.exception("Failed to create a signed video-scan upload URL")
        return jsonify({"error": "Couldn't prepare the upload. Please try again."}), 500

    return jsonify({
        "upload_url": upload_url,
        "path": path,
        "anon_key": os.environ.get("SUPABASE_ANON_KEY"),
    })

# Moved from app.py: _process_video_scan_job
def _process_video_scan_job(job_id, path, job_text, resume_text):
    """Runs the full scan pipeline in a background thread - download,
    audio extraction, transcription, coaching - so the HTTP request that
    kicked it off can return immediately instead of staying open for
    however long this takes. A single long-held request is what risked
    getting killed by a reverse-proxy timeout somewhere between the
    browser and this app (Cloudflare, in front of Render, commonly caps a
    single proxied request around 100 seconds) regardless of anything
    gunicorn itself is configured to allow."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=os.path.splitext(path)[1], delete=False) as tmp:
        tmp_path = tmp.name

    # Not persisted anywhere - the temp file, any extracted audio, AND the
    # Supabase Storage object itself are all deleted in `finally` below,
    # regardless of which path out of this function is taken.
    audio_path = tmp_path
    try:
        try:
            download_scan_to_file(path, tmp_path)
        except httpx.TimeoutException:
            logger.exception("Timed out fetching uploaded video scan from storage")
            _VIDEO_SCAN_JOBS[job_id] = {"status": "error", "error": "That video took too long to fetch for processing. Please try again."}
            return
        except Exception:
            logger.exception("Failed to fetch uploaded video scan from storage")
            _VIDEO_SCAN_JOBS[job_id] = {"status": "error", "error": "Couldn't find that upload. Please try uploading the video again."}
            return

        # Strips the video down to just its audio track first - that's what
        # actually lets a long recording fit under Whisper's fixed 25MB cap,
        # since the picture data (not the speech) is almost all of a video
        # file's size. No-ops back to the original file if ffmpeg isn't
        # available in this environment.
        audio_path = extract_audio_for_transcription(tmp_path)

        try:
            transcript = transcribe_audio(audio_path)
        except AudioTooLargeError as e:
            _VIDEO_SCAN_JOBS[job_id] = {"status": "error", "error": str(e)}
            return
        except Exception:
            logger.exception("Video interview transcription failed")
            _VIDEO_SCAN_JOBS[job_id] = {"status": "error", "error": "Couldn't transcribe that video. Please try again."}
            return

        if not transcript.strip():
            _VIDEO_SCAN_JOBS[job_id] = {"status": "error", "error": "Couldn't make out any speech in that video. Try again with clear audio."}
            return

        # Whether what they SAID fits the job, as distinct from how well
        # they said it (that's the coaching report below) - only makes
        # sense when a job description was actually provided. Non-fatal if
        # it fails: the coaching report alone is still useful on its own.
        job_fit = None
        if job_text:
            try:
                job_fit = generate_job_fit_verdict(transcript, job_text)
            except Exception:
                logger.exception("Job fit verdict generation failed - continuing without it")

        try:
            coaching = generate_interview_coaching(
                transcript=transcript,
                job_title="this role",
                requirements=job_text or "General interview performance.",
                verdict=job_fit.get("verdict") if job_fit else None,
                match_score=None,
                resume=resume_text,
            )
        except Exception:
            logger.exception("Video interview coaching report failed")
            _VIDEO_SCAN_JOBS[job_id] = {"status": "error", "error": "Transcribed your video, but couldn't generate the feedback report. Please try again."}
            return

        # The headline number shown to the candidate - weighted mostly
        # toward whether their answer actually fit the job (70%), with
        # communication style as a smaller factor (30%). Communication
        # Score alone is graded harshly by design (most real answers score
        # well under 75), so leading with it as THE score made a candidate
        # whose answer was genuinely relevant look bad overall just for not
        # being maximally polished. Falls back to communication score alone
        # when there's no job description to judge fit against.
        if job_fit and job_fit.get("verdict") in JOB_FIT_VERDICT_SCORE:
            overall_score = round(JOB_FIT_VERDICT_SCORE[job_fit["verdict"]] * 0.7 + coaching["communication_score"] * 0.3)
        else:
            overall_score = coaching["communication_score"]

        _VIDEO_SCAN_JOBS[job_id] = {
            "status": "done",
            "transcript": transcript,
            "coaching": coaching,
            "job_fit": job_fit,
            "overall_score": overall_score,
        }
    except Exception:
        logger.exception(f"Unexpected error processing video scan job {job_id}")
        _VIDEO_SCAN_JOBS[job_id] = {"status": "error", "error": "Something went wrong analyzing your video. Please try again."}
    finally:
        os.unlink(tmp_path)
        if audio_path != tmp_path and os.path.exists(audio_path):
            os.unlink(audio_path)
        delete_scan(path)

# Moved from app.py: resumemat_video_feedback
@app.route('/resume-jobmatch/video-feedback', methods=['POST'])
@limiter.limit("15 per hour")
def resumemat_video_feedback():
    """Kicks off scanning a video already uploaded straight to Supabase
    Storage (via the signed URL from resumemat_video_upload_url above) in a
    background thread and returns a job id immediately - poll
    resumemat_video_feedback_status below for the result. Takes a storage
    path, not the video itself."""
    if not current_user.is_authenticated:
        return jsonify({"error": "Please log in to use this feature.", "login_required": True}), 401

    # multipart, not JSON - the optional resume file needs a file field, and
    # Flask can't mix a file upload into a JSON body.
    path = request.form.get('path') or ''
    if not _SCAN_PATH_RE.match(path):
        return jsonify({"error": "Missing or invalid upload reference. Please upload the video again."}), 400

    job_text = (request.form.get('job_req') or '').strip()

    resume_text = None
    resume_file = request.files.get('resume')
    if resume_file and resume_file.filename:
        try:
            resume_text = extract_text_from_file(resume_file.filename, resume_file.read()).strip() or None
        except Exception:
            logger.exception("Resume extraction failed for video scan - continuing without it")

    if len(_VIDEO_SCAN_JOBS) >= _VIDEO_SCAN_JOBS_MAX:
        _VIDEO_SCAN_JOBS.pop(next(iter(_VIDEO_SCAN_JOBS)), None)
    job_id = uuid.uuid4().hex
    _VIDEO_SCAN_JOBS[job_id] = {"status": "processing"}
    threading.Thread(target=_process_video_scan_job, args=(job_id, path, job_text, resume_text), daemon=True).start()

    return jsonify({"job_id": job_id}), 202

# Moved from app.py: resumemat_video_feedback_status
@app.route('/resume-jobmatch/video-feedback/status/<job_id>')
def resumemat_video_feedback_status(job_id):
    """Polled every couple seconds by the browser while a scan is running -
    each request is a trivial in-memory dict lookup, so none of them can
    ever time out the way the single long-held request this replaced could."""
    if not current_user.is_authenticated:
        return jsonify({"error": "Please log in to use this feature."}), 401
    job = _VIDEO_SCAN_JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Unknown or expired job."}), 404
    return jsonify(job)

# Moved from app.py: resumemat_practice_questions
@app.route('/resume-jobmatch/video-feedback/questions', methods=['POST'])
@limiter.limit("15 per hour")
def resumemat_practice_questions():
    """10 tailored practice questions shown beside the video scan's results
    once a scan completes - reuses whatever job description/resume context
    is on the page rather than asking for it twice."""
    if not current_user.is_authenticated:
        return jsonify({"error": "Please log in to use this feature.", "login_required": True}), 401

    job_text = (request.form.get('job_req') or '').strip()
    if not job_text:
        return jsonify({"error": "Add a job description first."}), 400

    resume_text = None
    resume_file = request.files.get('resume')
    if resume_file and resume_file.filename:
        try:
            resume_text = extract_text_from_file(resume_file.filename, resume_file.read()).strip() or None
        except Exception:
            logger.exception("Resume extraction failed for practice questions - continuing without it")

    try:
        questions = generate_practice_questions(job_text, resume=resume_text)
    except Exception:
        logger.exception("Practice question generation failed")
        return jsonify({"error": "Couldn't generate questions right now. Please try again."}), 500

    return jsonify({"questions": questions})

# Moved from app.py: practice_interview_hub
@app.route("/practice-interview-hub")
def practice_interview_hub():
    """Community Edition standalone practice interview - not tied to any job
    posting or application. Anyone can build a practice session either from
    an AI-generated question set (paste a job description) or from their own
    manually-written requirements/questions. Page itself is open to everyone;
    actually running a session (below) requires login since it costs AI calls."""
    return render_template("practice_hub.html")

# Moved from app.py: practice_hub_chat
@app.route("/practice-interview-hub/chat", methods=["POST"])
@limiter.limit("40 per hour")
def practice_hub_chat():
    """Stateless practice interview turn for the standalone hub - mirrors
    candidate.practice_interview_chat but takes the role/description/
    questions straight from the request instead of a Job row, since this
    session isn't tied to any job posting."""
    if not current_user.is_authenticated:
        return jsonify({"error": "Please log in to start a practice interview.", "login_required": True}), 401

    title = (request.form.get("title") or "Practice Interview").strip()[:200]
    description = (request.form.get("description") or "").strip()
    requirements_raw = request.form.get("requirements") or ""
    manual_questions = [q.strip() for q in requirements_raw.splitlines() if q.strip()][:15] or None
    interview_length = request.form.get("interview_length") or "standard"
    if interview_length not in VALID_INTERVIEW_LENGTHS:
        interview_length = "standard"
    interview_focus = (request.form.get("interview_focus") or "").strip()[:2000] or None

    history = json.loads(request.form.get("history", "[]"))
    wrap_up = request.form.get("wrap_up", "false").lower() == "true"
    answer_audio = request.files.get("answer_audio")
    text_answer = (request.form.get("text_answer") or "").strip()

    user_message = text_answer  # text mode takes priority if provided
    if not user_message and answer_audio and answer_audio.filename:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=audio_file_extension(answer_audio.filename), delete=False) as tmp:
            tmp.write(answer_audio.read())
            tmp_path = tmp.name
        # Strips video down to just audio before Whisper - lets a long
        # answer fit under its 25MB cap instead of the much smaller ceiling
        # raw video hits. No-ops back to tmp_path if ffmpeg isn't available.
        audio_path = extract_audio_for_transcription(tmp_path)
        try:
            user_message = transcribe_audio(audio_path)
        except AudioTooLargeError as e:
            return jsonify({"error": str(e)}), 400
        except Exception:
            return jsonify({"error": "Couldn't transcribe your answer. Please try again."}), 500
        finally:
            os.unlink(tmp_path)
            if audio_path != tmp_path and os.path.exists(audio_path):
                os.unlink(audio_path)

    coaching = None
    if wrap_up:
        # force_conclude=True guarantees this turn ends in a verdict, not
        # another question - so it's safe to kick off the coaching report
        # immediately instead of waiting to see the reply first. Coaching
        # generation was the single biggest contributor to how long "stop
        # early" took, since it used to run only after the verdict call
        # finished rather than alongside it.
        transcript_lines = [f"{m.get('role')}: {m.get('content')}" for m in history]
        if user_message:
            transcript_lines.append(f"user: {user_message}")
        full_transcript = "\n".join(transcript_lines)

        with ThreadPoolExecutor(max_workers=2) as pool:
            reply_future = pool.submit(
                run_interview_turn, title, description, user_message, history,
                force_conclude=True, interview_length=interview_length,
                interview_focus=interview_focus, interview_questions=manual_questions,
                practice_mode=True,
            )
            coaching_future = pool.submit(
                generate_interview_coaching, transcript=full_transcript, job_title=title,
                requirements=description or requirements_raw, verdict=None, match_score=None,
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
            reply = run_interview_turn(
                title, description, user_message, history, force_conclude=False,
                interview_length=interview_length, interview_focus=interview_focus,
                interview_questions=manual_questions, practice_mode=True,
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
                    job_title=title,
                    requirements=description or requirements_raw,
                    verdict=None,
                    match_score=None,
                )
            except Exception:
                coaching = None

    return jsonify({
        "reply": reply,
        "transcribed_answer": user_message,
        "text_answer": text_answer,
        "concluded": should_conclude,
        "coaching": coaching,
    })

# Moved from app.py: practice_hub_questions
@app.route("/practice-interview-hub/questions", methods=["POST"])
@limiter.limit("15 per hour")
def practice_hub_questions():
    """On-demand sample question list for the standalone hub's AI-generated
    mode, same idea as candidate.practice_questions but built from the
    title/description the visitor typed in rather than an existing Job row."""
    if not current_user.is_authenticated:
        return jsonify({"error": "Please log in to generate questions.", "login_required": True}), 401

    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip()
    if not title or not description:
        return jsonify({"error": "Add a job title and description first."}), 400
    interview_length = request.form.get("interview_length") or "standard"
    if interview_length not in VALID_INTERVIEW_LENGTHS:
        interview_length = "standard"
    interview_focus = (request.form.get("interview_focus") or "").strip() or None

    try:
        questions = generate_interview_question_preview(
            title, description, interview_length=interview_length, interview_focus=interview_focus,
        )
    except Exception:
        return jsonify({"error": "Couldn't generate questions right now. Please try again."}), 500
    return jsonify({"questions": questions})

