# ----------------------------------------------------------------
# CHANGE BLOCK: 2026-11-22
# OLD IMPLEMENTATION - commented snapshot from Git HEAD
# ----------------------------------------------------------------
# OLD CODE: from website import create_app, mail, limiter, db
# OLD CODE: from community_stats import resume_total, record_resume_processed
# OLD CODE: from website.candidate import search_jobs_by_text
# OLD CODE: from flask_mail import Message
# OLD CODE: from flask import Flask, render_template, request, jsonify, current_app, Response, flash, redirect, url_for
# OLD CODE: from flask_login import login_required, current_user
# OLD CODE: import openai
# OLD CODE: import httpx
# OLD CODE: import io
# OLD CODE: import json
# OLD CODE: import re
# OLD CODE: import os
# OLD CODE: import logging
# OLD CODE: from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
# OLD CODE: from reportlab.lib.pagesizes import LETTER
# OLD CODE: from reportlab.lib.styles import getSampleStyleSheet
# OLD CODE: from openai._exceptions import RateLimitError, AuthenticationError, APIConnectionError
# OLD CODE: from config import Config
# OLD CODE: from flask_cors import CORS
# OLD CODE: from werkzeug.utils import secure_filename
# OLD CODE: from PIL import Image
# OLD CODE: import pytesseract
# OLD CODE: from flask import send_from_directory
# OLD CODE: import uuid
# OLD CODE: import threading
# OLD CODE: from concurrent.futures import ThreadPoolExecutor
# OLD CODE: from dotenv import load_dotenv
# OLD CODE:
# OLD CODE: from ai_services import (
# OLD CODE:     extract_pdf_text,
# OLD CODE:     extract_docx_text,
# OLD CODE:     extract_text_from_file,
# OLD CODE:     compare_resume_to_job,
# OLD CODE:     generate_summary,
# OLD CODE:     generate_basic_analysis,
# OLD CODE:     generate_resume_from_profile,
# OLD CODE:     run_interview_turn,
# OLD CODE:     transcribe_audio,
# OLD CODE:     extract_audio_for_transcription,
# OLD CODE:     audio_file_extension,
# OLD CODE:     AudioTooLargeError,
# OLD CODE:     generate_interview_question_preview,
# OLD CODE:     generate_interview_coaching,
# OLD CODE:     generate_practice_questions,
# OLD CODE:     generate_job_fit_verdict,
# OLD CODE:     JOB_FIT_VERDICT_SCORE,
# OLD CODE: )
# OLD CODE: from video_storage import create_scan_upload_url, download_scan_to_file, delete_scan
# OLD CODE:
# OLD CODE: #  Load env & config
# OLD CODE: # override=False (the dotenv default) - see website/__init__.py for why this
# OLD CODE: # matters: it must not silently overwrite an env var a caller set on purpose.
# OLD CODE: load_dotenv(override=False)
# OLD CODE: if Config.GOOGLE_APPLICATION_CREDENTIALS:
# OLD CODE:     os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = Config.GOOGLE_APPLICATION_CREDENTIALS
# OLD CODE:
# OLD CODE: # App setup
# OLD CODE: app = create_app()
# OLD CODE: app.config.from_object(Config)
# OLD CODE: CORS(app)
# OLD CODE:
# OLD CODE: # Logging (must come before any function that uses logger)
# OLD CODE: logging.basicConfig(level=logging.INFO)
# OLD CODE: logger = logging.getLogger(__name__)
# OLD CODE:
# OLD CODE: # OpenAI
# OLD CODE: client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
# OLD CODE:
# OLD CODE: # Short-lived handoff for /resume-jobmatch's Post/Redirect/Get flow. Pasted
# OLD CODE: # job descriptions can easily exceed the ~4KB Flask session cookie can hold,
# OLD CODE: # so results are stashed here (keyed by a one-time token in the redirect
# OLD CODE: # URL) instead of in the session. Safe only because gunicorn runs a single
# OLD CODE: # worker (see Procfile) - an in-memory dict wouldn't be shared across
# OLD CODE: # workers if that ever changes.
# OLD CODE: _RESUME_MATCH_CACHE = {}
# OLD CODE: _RESUME_MATCH_CACHE_MAX = 200  # evict oldest if a token is never consumed
# OLD CODE:
# OLD CODE:
# OLD CODE: @app.errorhandler(429)
# OLD CODE: def handle_rate_limit_exceeded(e):
# OLD CODE:     """Flask-Limiter's own default 429 is a plain HTML/text page, not JSON -
# OLD CODE:     every fetch()/XHR-based route in this app (which is most rate-limited
# OLD CODE:     ones) would fail to parse that as JSON and fall back to a generic
# OLD CODE:     "something went wrong" with no indication it was actually a rate limit,
# OLD CODE:     which is exactly what happened debugging the video scan feature: enough
# OLD CODE:     retries in an hour hit this silently. A handful of routes are rate-
# OLD CODE:     limited but driven by a traditional full-page form POST rather than
# OLD CODE:     fetch - those will now render this JSON as plain text on the page
# OLD CODE:     instead of Werkzeug's default error page if someone exceeds their
# OLD CODE:     limit, which is a pre-existing rough edge either way, not a regression."""
# OLD CODE:     return jsonify({"error": "You've made a lot of requests here recently - please wait a bit and try again."}), 429
# OLD CODE:
# OLD CODE:
# OLD CODE: # ══════════════════════════════════════════════════════════════════════════════
# OLD CODE: # Routes
# OLD CODE: # ══════════════════════════════════════════════════════════════════════════════
# OLD CODE:
# OLD CODE: @app.get("/api/community-resume-count")
# OLD CODE: def community_resume_count():
# OLD CODE:     try:
# OLD CODE:         response = jsonify(total=resume_total(db.engine))
# OLD CODE:     except Exception:
# OLD CODE:         logger.exception("Community resume count unavailable")
# OLD CODE:         response = jsonify(error="Count temporarily unavailable")
# OLD CODE:         response.status_code = 503
# OLD CODE:     response.headers["Cache-Control"] = "no-store"
# OLD CODE:     return response
# OLD CODE:
# OLD CODE:
# OLD CODE: def _record_community_resume():
# OLD CODE:     # A metrics failure must not discard a completed analysis for the user.
# OLD CODE:     try:
# OLD CODE:         record_resume_processed(db.engine)
# OLD CODE:     except Exception:
# OLD CODE:         logger.exception("Failed to record completed Community Edition resume")
# OLD CODE:
# OLD CODE:
# OLD CODE: @app.route("/resume-summarizer")
# OLD CODE: def resumesum():
# OLD CODE:     return render_template("resumesum.html")
# OLD CODE:
# OLD CODE:
# OLD CODE: @app.route('/resume-jobmatch', methods=['GET', 'POST'])
# OLD CODE: @limiter.limit("10 per hour", methods=["POST"])
# OLD CODE: def resumemat():
# OLD CODE:     """Resume job-match page - handles both the form display and form submission.
# OLD CODE:
# OLD CODE:     POST redirects back to this same GET route (Post/Redirect/Get) instead of
# OLD CODE:     rendering the result directly, so reloading the results page just re-GETs
# OLD CODE:     it instead of resubmitting the form - which used to re-run the AI call
# OLD CODE:     (burning quota) and drop a duplicate entry into the saved-results list
# OLD CODE:     every time, since the AI's wording differs slightly on each run.
# OLD CODE:     """
# OLD CODE:     def _stash_and_redirect(result, score_value, job_text):
# OLD CODE:         if len(_RESUME_MATCH_CACHE) >= _RESUME_MATCH_CACHE_MAX:
# OLD CODE:             _RESUME_MATCH_CACHE.pop(next(iter(_RESUME_MATCH_CACHE)), None)
# OLD CODE:         token = uuid.uuid4().hex
# OLD CODE:         _RESUME_MATCH_CACHE[token] = {"result": result, "score_value": score_value, "job_text": job_text}
# OLD CODE:         return redirect(url_for('resumemat', rid=token))
# OLD CODE:
# OLD CODE:     if request.method == 'POST':
# OLD CODE:         if not current_user.is_authenticated:
# OLD CODE:             return redirect(url_for('auth.login', next=request.path))
# OLD CODE:
# OLD CODE:         job_text    = request.form.get('job_req', '')
# OLD CODE:         resume_file = request.files.get('resume')
# OLD CODE:
# OLD CODE:         if not job_text.strip() or not resume_file:
# OLD CODE:             return _stash_and_redirect(None, 0, job_text)
# OLD CODE:
# OLD CODE:         resume_bytes = resume_file.read()
# OLD CODE:         resume_file.stream.seek(0)
# OLD CODE:
# OLD CODE:         resume_text = extract_text_from_file(resume_file.filename, resume_bytes)
# OLD CODE:
# OLD CODE:         if not resume_text.strip():
# OLD CODE:             logger.error("Extracted resume text is empty")
# OLD CODE:             return _stash_and_redirect(
# OLD CODE:                 "Resume content could not be read. Please upload a readable PDF, DOCX, or TXT file.",
# OLD CODE:                 0, job_text,
# OLD CODE:             )
# OLD CODE:
# OLD CODE:         try:
# OLD CODE:             result = compare_resume_to_job(job_text, resume_text)
# OLD CODE:         except RateLimitError:
# OLD CODE:             return _stash_and_redirect("Our AI service is busy right now. Please try again in a minute.", 0, job_text)
# OLD CODE:         except AuthenticationError:
# OLD CODE:             logger.error("OpenAI authentication failed in /resume-jobmatch")
# OLD CODE:             return _stash_and_redirect("Something went wrong on our end. Please try again shortly.", 0, job_text)
# OLD CODE:         except Exception as e:
# OLD CODE:             logger.error(f"compare_resume_to_job failed: {str(e)}")
# OLD CODE:             return _stash_and_redirect("We couldn't analyze your resume right now. Please try again shortly.", 0, job_text)
# OLD CODE:
# OLD CODE:         # Persist raw result to disk (optional)
# OLD CODE:         with open("resumemat.txt", "w", encoding="utf-8") as f:
# OLD CODE:             f.write(result)
# OLD CODE:
# OLD CODE:         # Extract numeric score (first number in 0-100 range)
# OLD CODE:         score_value = 0
# OLD CODE:         for num in re.findall(r"\b(\d{1,3})\b", result):
# OLD CODE:             val = int(num)
# OLD CODE:             if 0 <= val <= 100:
# OLD CODE:                 score_value = val
# OLD CODE:                 break
# OLD CODE:
# OLD CODE:         if result and result.strip():
# OLD CODE:             _record_community_resume()
# OLD CODE:         return _stash_and_redirect(result.replace('*', ''), score_value, job_text)
# OLD CODE:
# OLD CODE:     saved = _RESUME_MATCH_CACHE.pop(request.args.get('rid'), None) or {}
# OLD CODE:     return render_template(
# OLD CODE:         'resumemat.html',
# OLD CODE:         result=saved.get('result'),
# OLD CODE:         score_value=saved.get('score_value', 0),
# OLD CODE:         job_text=saved.get('job_text', ''),
# OLD CODE:     )
# OLD CODE:
# OLD CODE:
# OLD CODE: _SCAN_PATH_RE = re.compile(r"^scans/[0-9a-f]{32}\.[a-z0-9]{1,10}$")
# OLD CODE:
# OLD CODE:
# OLD CODE: @app.route('/resume-jobmatch/video-feedback/upload-url', methods=['POST'])
# OLD CODE: @limiter.limit("30 per hour")
# OLD CODE: def resumemat_video_upload_url():
# OLD CODE:     """Hands back a one-time signed URL the browser uploads the raw video
# OLD CODE:     to directly in Supabase Storage, instead of sending it to this app's own
# OLD CODE:     /video-feedback route. Needed because large uploads to avants.ai itself
# OLD CODE:     get rejected at the edge (Render/Cloudflare) well under what a longer
# OLD CODE:     interview video needs - a direct-to-storage upload bypasses that
# OLD CODE:     entirely since the big transfer never touches this app's domain."""
# OLD CODE:     if not current_user.is_authenticated:
# OLD CODE:         return jsonify({"error": "Please log in to use this feature.", "login_required": True}), 401
# OLD CODE:
# OLD CODE:     filename = (request.get_json(silent=True) or {}).get('filename') or ''
# OLD CODE:     ext = audio_file_extension(filename)
# OLD CODE:     try:
# OLD CODE:         upload_url, path = create_scan_upload_url(ext)
# OLD CODE:     except Exception:
# OLD CODE:         logger.exception("Failed to create a signed video-scan upload URL")
# OLD CODE:         return jsonify({"error": "Couldn't prepare the upload. Please try again."}), 500
# OLD CODE:
# OLD CODE:     return jsonify({
# OLD CODE:         "upload_url": upload_url,
# OLD CODE:         "path": path,
# OLD CODE:         "anon_key": os.environ.get("SUPABASE_ANON_KEY"),
# OLD CODE:     })
# OLD CODE:
# OLD CODE:
# OLD CODE: _VIDEO_SCAN_JOBS = {}
# OLD CODE: _VIDEO_SCAN_JOBS_MAX = 200
# OLD CODE:
# OLD CODE:
# OLD CODE: def _process_video_scan_job(job_id, path, job_text, resume_text):
# OLD CODE:     """Runs the full scan pipeline in a background thread - download,
# OLD CODE:     audio extraction, transcription, coaching - so the HTTP request that
# OLD CODE:     kicked it off can return immediately instead of staying open for
# OLD CODE:     however long this takes. A single long-held request is what risked
# OLD CODE:     getting killed by a reverse-proxy timeout somewhere between the
# OLD CODE:     browser and this app (Cloudflare, in front of Render, commonly caps a
# OLD CODE:     single proxied request around 100 seconds) regardless of anything
# OLD CODE:     gunicorn itself is configured to allow."""
# OLD CODE:     import tempfile
# OLD CODE:     with tempfile.NamedTemporaryFile(suffix=os.path.splitext(path)[1], delete=False) as tmp:
# OLD CODE:         tmp_path = tmp.name
# OLD CODE:
# OLD CODE:     # Not persisted anywhere - the temp file, any extracted audio, AND the
# OLD CODE:     # Supabase Storage object itself are all deleted in `finally` below,
# OLD CODE:     # regardless of which path out of this function is taken.
# OLD CODE:     audio_path = tmp_path
# OLD CODE:     try:
# OLD CODE:         try:
# OLD CODE:             download_scan_to_file(path, tmp_path)
# OLD CODE:         except httpx.TimeoutException:
# OLD CODE:             logger.exception("Timed out fetching uploaded video scan from storage")
# OLD CODE:             _VIDEO_SCAN_JOBS[job_id] = {"status": "error", "error": "That video took too long to fetch for processing. Please try again."}
# OLD CODE:             return
# OLD CODE:         except Exception:
# OLD CODE:             logger.exception("Failed to fetch uploaded video scan from storage")
# OLD CODE:             _VIDEO_SCAN_JOBS[job_id] = {"status": "error", "error": "Couldn't find that upload. Please try uploading the video again."}
# OLD CODE:             return
# OLD CODE:
# OLD CODE:         # Strips the video down to just its audio track first - that's what
# OLD CODE:         # actually lets a long recording fit under Whisper's fixed 25MB cap,
# OLD CODE:         # since the picture data (not the speech) is almost all of a video
# OLD CODE:         # file's size. No-ops back to the original file if ffmpeg isn't
# OLD CODE:         # available in this environment.
# OLD CODE:         audio_path = extract_audio_for_transcription(tmp_path)
# OLD CODE:
# OLD CODE:         try:
# OLD CODE:             transcript = transcribe_audio(audio_path)
# OLD CODE:         except AudioTooLargeError as e:
# OLD CODE:             _VIDEO_SCAN_JOBS[job_id] = {"status": "error", "error": str(e)}
# OLD CODE:             return
# OLD CODE:         except Exception:
# OLD CODE:             logger.exception("Video interview transcription failed")
# OLD CODE:             _VIDEO_SCAN_JOBS[job_id] = {"status": "error", "error": "Couldn't transcribe that video. Please try again."}
# OLD CODE:             return
# OLD CODE:
# OLD CODE:         if not transcript.strip():
# OLD CODE:             _VIDEO_SCAN_JOBS[job_id] = {"status": "error", "error": "Couldn't make out any speech in that video. Try again with clear audio."}
# OLD CODE:             return
# OLD CODE:
# OLD CODE:         # Whether what they SAID fits the job, as distinct from how well
# OLD CODE:         # they said it (that's the coaching report below) - only makes
# OLD CODE:         # sense when a job description was actually provided. Non-fatal if
# OLD CODE:         # it fails: the coaching report alone is still useful on its own.
# OLD CODE:         job_fit = None
# OLD CODE:         if job_text:
# OLD CODE:             try:
# OLD CODE:                 job_fit = generate_job_fit_verdict(transcript, job_text)
# OLD CODE:             except Exception:
# OLD CODE:                 logger.exception("Job fit verdict generation failed - continuing without it")
# OLD CODE:
# OLD CODE:         try:
# OLD CODE:             coaching = generate_interview_coaching(
# OLD CODE:                 transcript=transcript,
# OLD CODE:                 job_title="this role",
# OLD CODE:                 requirements=job_text or "General interview performance.",
# OLD CODE:                 verdict=job_fit.get("verdict") if job_fit else None,
# OLD CODE:                 match_score=None,
# OLD CODE:                 resume=resume_text,
# OLD CODE:             )
# OLD CODE:         except Exception:
# OLD CODE:             logger.exception("Video interview coaching report failed")
# OLD CODE:             _VIDEO_SCAN_JOBS[job_id] = {"status": "error", "error": "Transcribed your video, but couldn't generate the feedback report. Please try again."}
# OLD CODE:             return
# OLD CODE:
# OLD CODE:         # The headline number shown to the candidate - weighted mostly
# OLD CODE:         # toward whether their answer actually fit the job (70%), with
# OLD CODE:         # communication style as a smaller factor (30%). Communication
# OLD CODE:         # Score alone is graded harshly by design (most real answers score
# OLD CODE:         # well under 75), so leading with it as THE score made a candidate
# OLD CODE:         # whose answer was genuinely relevant look bad overall just for not
# OLD CODE:         # being maximally polished. Falls back to communication score alone
# OLD CODE:         # when there's no job description to judge fit against.
# OLD CODE:         if job_fit and job_fit.get("verdict") in JOB_FIT_VERDICT_SCORE:
# OLD CODE:             overall_score = round(JOB_FIT_VERDICT_SCORE[job_fit["verdict"]] * 0.7 + coaching["communication_score"] * 0.3)
# OLD CODE:         else:
# OLD CODE:             overall_score = coaching["communication_score"]
# OLD CODE:
# OLD CODE:         _VIDEO_SCAN_JOBS[job_id] = {
# OLD CODE:             "status": "done",
# OLD CODE:             "transcript": transcript,
# OLD CODE:             "coaching": coaching,
# OLD CODE:             "job_fit": job_fit,
# OLD CODE:             "overall_score": overall_score,
# OLD CODE:         }
# OLD CODE:     except Exception:
# OLD CODE:         logger.exception(f"Unexpected error processing video scan job {job_id}")
# OLD CODE:         _VIDEO_SCAN_JOBS[job_id] = {"status": "error", "error": "Something went wrong analyzing your video. Please try again."}
# OLD CODE:     finally:
# OLD CODE:         os.unlink(tmp_path)
# OLD CODE:         if audio_path != tmp_path and os.path.exists(audio_path):
# OLD CODE:             os.unlink(audio_path)
# OLD CODE:         delete_scan(path)
# OLD CODE:
# OLD CODE:
# OLD CODE: @app.route('/resume-jobmatch/video-feedback', methods=['POST'])
# OLD CODE: @limiter.limit("15 per hour")
# OLD CODE: def resumemat_video_feedback():
# OLD CODE:     """Kicks off scanning a video already uploaded straight to Supabase
# OLD CODE:     Storage (via the signed URL from resumemat_video_upload_url above) in a
# OLD CODE:     background thread and returns a job id immediately - poll
# OLD CODE:     resumemat_video_feedback_status below for the result. Takes a storage
# OLD CODE:     path, not the video itself."""
# OLD CODE:     if not current_user.is_authenticated:
# OLD CODE:         return jsonify({"error": "Please log in to use this feature.", "login_required": True}), 401
# OLD CODE:
# OLD CODE:     # multipart, not JSON - the optional resume file needs a file field, and
# OLD CODE:     # Flask can't mix a file upload into a JSON body.
# OLD CODE:     path = request.form.get('path') or ''
# OLD CODE:     if not _SCAN_PATH_RE.match(path):
# OLD CODE:         return jsonify({"error": "Missing or invalid upload reference. Please upload the video again."}), 400
# OLD CODE:
# OLD CODE:     job_text = (request.form.get('job_req') or '').strip()
# OLD CODE:
# OLD CODE:     resume_text = None
# OLD CODE:     resume_file = request.files.get('resume')
# OLD CODE:     if resume_file and resume_file.filename:
# OLD CODE:         try:
# OLD CODE:             resume_text = extract_text_from_file(resume_file.filename, resume_file.read()).strip() or None
# OLD CODE:         except Exception:
# OLD CODE:             logger.exception("Resume extraction failed for video scan - continuing without it")
# OLD CODE:
# OLD CODE:     if len(_VIDEO_SCAN_JOBS) >= _VIDEO_SCAN_JOBS_MAX:
# OLD CODE:         _VIDEO_SCAN_JOBS.pop(next(iter(_VIDEO_SCAN_JOBS)), None)
# OLD CODE:     job_id = uuid.uuid4().hex
# OLD CODE:     _VIDEO_SCAN_JOBS[job_id] = {"status": "processing"}
# OLD CODE:     threading.Thread(target=_process_video_scan_job, args=(job_id, path, job_text, resume_text), daemon=True).start()
# OLD CODE:
# OLD CODE:     return jsonify({"job_id": job_id}), 202
# OLD CODE:
# OLD CODE:
# OLD CODE: @app.route('/resume-jobmatch/video-feedback/status/<job_id>')
# OLD CODE: def resumemat_video_feedback_status(job_id):
# OLD CODE:     """Polled every couple seconds by the browser while a scan is running -
# OLD CODE:     each request is a trivial in-memory dict lookup, so none of them can
# OLD CODE:     ever time out the way the single long-held request this replaced could."""
# OLD CODE:     if not current_user.is_authenticated:
# OLD CODE:         return jsonify({"error": "Please log in to use this feature."}), 401
# OLD CODE:     job = _VIDEO_SCAN_JOBS.get(job_id)
# OLD CODE:     if not job:
# OLD CODE:         return jsonify({"error": "Unknown or expired job."}), 404
# OLD CODE:     return jsonify(job)
# OLD CODE:
# OLD CODE:
# OLD CODE: @app.route('/resume-jobmatch/video-feedback/questions', methods=['POST'])
# OLD CODE: @limiter.limit("15 per hour")
# OLD CODE: def resumemat_practice_questions():
# OLD CODE:     """10 tailored practice questions shown beside the video scan's results
# OLD CODE:     once a scan completes - reuses whatever job description/resume context
# OLD CODE:     is on the page rather than asking for it twice."""
# OLD CODE:     if not current_user.is_authenticated:
# OLD CODE:         return jsonify({"error": "Please log in to use this feature.", "login_required": True}), 401
# OLD CODE:
# OLD CODE:     job_text = (request.form.get('job_req') or '').strip()
# OLD CODE:     if not job_text:
# OLD CODE:         return jsonify({"error": "Add a job description first."}), 400
# OLD CODE:
# OLD CODE:     resume_text = None
# OLD CODE:     resume_file = request.files.get('resume')
# OLD CODE:     if resume_file and resume_file.filename:
# OLD CODE:         try:
# OLD CODE:             resume_text = extract_text_from_file(resume_file.filename, resume_file.read()).strip() or None
# OLD CODE:         except Exception:
# OLD CODE:             logger.exception("Resume extraction failed for practice questions - continuing without it")
# OLD CODE:
# OLD CODE:     try:
# OLD CODE:         questions = generate_practice_questions(job_text, resume=resume_text)
# OLD CODE:     except Exception:
# OLD CODE:         logger.exception("Practice question generation failed")
# OLD CODE:         return jsonify({"error": "Couldn't generate questions right now. Please try again."}), 500
# OLD CODE:
# OLD CODE:     return jsonify({"questions": questions})
# OLD CODE:
# OLD CODE:
# OLD CODE: VALID_INTERVIEW_LENGTHS = ("short", "standard", "thorough")
# OLD CODE:
# OLD CODE:
# OLD CODE: @app.route("/practice-interview-hub")
# OLD CODE: def practice_interview_hub():
# OLD CODE:     """Community Edition standalone practice interview - not tied to any job
# OLD CODE:     posting or application. Anyone can build a practice session either from
# OLD CODE:     an AI-generated question set (paste a job description) or from their own
# OLD CODE:     manually-written requirements/questions. Page itself is open to everyone;
# OLD CODE:     actually running a session (below) requires login since it costs AI calls."""
# OLD CODE:     return render_template("practice_hub.html")
# OLD CODE:
# OLD CODE:
# OLD CODE: @app.route("/practice-interview-hub/chat", methods=["POST"])
# OLD CODE: @limiter.limit("40 per hour")
# OLD CODE: def practice_hub_chat():
# OLD CODE:     """Stateless practice interview turn for the standalone hub - mirrors
# OLD CODE:     candidate.practice_interview_chat but takes the role/description/
# OLD CODE:     questions straight from the request instead of a Job row, since this
# OLD CODE:     session isn't tied to any job posting."""
# OLD CODE:     if not current_user.is_authenticated:
# OLD CODE:         return jsonify({"error": "Please log in to start a practice interview.", "login_required": True}), 401
# OLD CODE:
# OLD CODE:     title = (request.form.get("title") or "Practice Interview").strip()[:200]
# OLD CODE:     description = (request.form.get("description") or "").strip()
# OLD CODE:     requirements_raw = request.form.get("requirements") or ""
# OLD CODE:     manual_questions = [q.strip() for q in requirements_raw.splitlines() if q.strip()][:15] or None
# OLD CODE:     interview_length = request.form.get("interview_length") or "standard"
# OLD CODE:     if interview_length not in VALID_INTERVIEW_LENGTHS:
# OLD CODE:         interview_length = "standard"
# OLD CODE:     interview_focus = (request.form.get("interview_focus") or "").strip()[:2000] or None
# OLD CODE:
# OLD CODE:     history = json.loads(request.form.get("history", "[]"))
# OLD CODE:     wrap_up = request.form.get("wrap_up", "false").lower() == "true"
# OLD CODE:     answer_audio = request.files.get("answer_audio")
# OLD CODE:     text_answer = (request.form.get("text_answer") or "").strip()
# OLD CODE:
# OLD CODE:     user_message = text_answer  # text mode takes priority if provided
# OLD CODE:     if not user_message and answer_audio and answer_audio.filename:
# OLD CODE:         import tempfile
# OLD CODE:         with tempfile.NamedTemporaryFile(suffix=audio_file_extension(answer_audio.filename), delete=False) as tmp:
# OLD CODE:             tmp.write(answer_audio.read())
# OLD CODE:             tmp_path = tmp.name
# OLD CODE:         # Strips video down to just audio before Whisper - lets a long
# OLD CODE:         # answer fit under its 25MB cap instead of the much smaller ceiling
# OLD CODE:         # raw video hits. No-ops back to tmp_path if ffmpeg isn't available.
# OLD CODE:         audio_path = extract_audio_for_transcription(tmp_path)
# OLD CODE:         try:
# OLD CODE:             user_message = transcribe_audio(audio_path)
# OLD CODE:         except AudioTooLargeError as e:
# OLD CODE:             return jsonify({"error": str(e)}), 400
# OLD CODE:         except Exception:
# OLD CODE:             return jsonify({"error": "Couldn't transcribe your answer. Please try again."}), 500
# OLD CODE:         finally:
# OLD CODE:             os.unlink(tmp_path)
# OLD CODE:             if audio_path != tmp_path and os.path.exists(audio_path):
# OLD CODE:                 os.unlink(audio_path)
# OLD CODE:
# OLD CODE:     coaching = None
# OLD CODE:     if wrap_up:
# OLD CODE:         # force_conclude=True guarantees this turn ends in a verdict, not
# OLD CODE:         # another question - so it's safe to kick off the coaching report
# OLD CODE:         # immediately instead of waiting to see the reply first. Coaching
# OLD CODE:         # generation was the single biggest contributor to how long "stop
# OLD CODE:         # early" took, since it used to run only after the verdict call
# OLD CODE:         # finished rather than alongside it.
# OLD CODE:         transcript_lines = [f"{m.get('role')}: {m.get('content')}" for m in history]
# OLD CODE:         if user_message:
# OLD CODE:             transcript_lines.append(f"user: {user_message}")
# OLD CODE:         full_transcript = "\n".join(transcript_lines)
# OLD CODE:
# OLD CODE:         with ThreadPoolExecutor(max_workers=2) as pool:
# OLD CODE:             reply_future = pool.submit(
# OLD CODE:                 run_interview_turn, title, description, user_message, history,
# OLD CODE:                 force_conclude=True, interview_length=interview_length,
# OLD CODE:                 interview_focus=interview_focus, interview_questions=manual_questions,
# OLD CODE:                 practice_mode=True,
# OLD CODE:             )
# OLD CODE:             coaching_future = pool.submit(
# OLD CODE:                 generate_interview_coaching, transcript=full_transcript, job_title=title,
# OLD CODE:                 requirements=description or requirements_raw, verdict=None, match_score=None,
# OLD CODE:             )
# OLD CODE:             try:
# OLD CODE:                 reply = reply_future.result()
# OLD CODE:             except Exception:
# OLD CODE:                 return jsonify({"error": "Failed to get a response. Please try again."}), 500
# OLD CODE:             try:
# OLD CODE:                 coaching = coaching_future.result()
# OLD CODE:             except Exception:
# OLD CODE:                 coaching = None
# OLD CODE:         should_conclude = True
# OLD CODE:     else:
# OLD CODE:         try:
# OLD CODE:             reply = run_interview_turn(
# OLD CODE:                 title, description, user_message, history, force_conclude=False,
# OLD CODE:                 interview_length=interview_length, interview_focus=interview_focus,
# OLD CODE:                 interview_questions=manual_questions, practice_mode=True,
# OLD CODE:             )
# OLD CODE:         except Exception:
# OLD CODE:             return jsonify({"error": "Failed to get a response. Please try again."}), 500
# OLD CODE:
# OLD CODE:         verdict_match = re.search(r"Verdict:\s*(Strong Yes|Yes|No|Strong No)", reply, re.IGNORECASE)
# OLD CODE:         should_conclude = bool(verdict_match)
# OLD CODE:         if should_conclude:
# OLD CODE:             transcript_lines = [f"{m.get('role')}: {m.get('content')}" for m in history]
# OLD CODE:             transcript_lines.append(f"assistant: {reply}")
# OLD CODE:             full_transcript = "\n".join(transcript_lines)
# OLD CODE:             try:
# OLD CODE:                 coaching = generate_interview_coaching(
# OLD CODE:                     transcript=full_transcript,
# OLD CODE:                     job_title=title,
# OLD CODE:                     requirements=description or requirements_raw,
# OLD CODE:                     verdict=None,
# OLD CODE:                     match_score=None,
# OLD CODE:                 )
# OLD CODE:             except Exception:
# OLD CODE:                 coaching = None
# OLD CODE:
# OLD CODE:     return jsonify({
# OLD CODE:         "reply": reply,
# OLD CODE:         "transcribed_answer": user_message,
# OLD CODE:         "text_answer": text_answer,
# OLD CODE:         "concluded": should_conclude,
# OLD CODE:         "coaching": coaching,
# OLD CODE:     })
# OLD CODE:
# OLD CODE:
# OLD CODE: @app.route("/practice-interview-hub/questions", methods=["POST"])
# OLD CODE: @limiter.limit("15 per hour")
# OLD CODE: def practice_hub_questions():
# OLD CODE:     """On-demand sample question list for the standalone hub's AI-generated
# OLD CODE:     mode, same idea as candidate.practice_questions but built from the
# OLD CODE:     title/description the visitor typed in rather than an existing Job row."""
# OLD CODE:     if not current_user.is_authenticated:
# OLD CODE:         return jsonify({"error": "Please log in to generate questions.", "login_required": True}), 401
# OLD CODE:
# OLD CODE:     title = (request.form.get("title") or "").strip()
# OLD CODE:     description = (request.form.get("description") or "").strip()
# OLD CODE:     if not title or not description:
# OLD CODE:         return jsonify({"error": "Add a job title and description first."}), 400
# OLD CODE:     interview_length = request.form.get("interview_length") or "standard"
# OLD CODE:     if interview_length not in VALID_INTERVIEW_LENGTHS:
# OLD CODE:         interview_length = "standard"
# OLD CODE:     interview_focus = (request.form.get("interview_focus") or "").strip() or None
# OLD CODE:
# OLD CODE:     try:
# OLD CODE:         questions = generate_interview_question_preview(
# OLD CODE:             title, description, interview_length=interview_length, interview_focus=interview_focus,
# OLD CODE:         )
# OLD CODE:     except Exception:
# OLD CODE:         return jsonify({"error": "Couldn't generate questions right now. Please try again."}), 500
# OLD CODE:     return jsonify({"questions": questions})
# OLD CODE:
# OLD CODE:
# OLD CODE: @app.route("/generate-profile-resume", methods=["POST"])
# OLD CODE: @login_required
# OLD CODE: @limiter.limit("10 per hour")
# OLD CODE: def generate_profile_resume():
# OLD CODE:     """Build a resume from pasted LinkedIn profile text for candidates without one."""
# OLD CODE:     data = request.get_json() or {}
# OLD CODE:     linkedin_url = data.get("linkedin_url", "").strip()
# OLD CODE:     profile_text = data.get("profile_text", "").strip()
# OLD CODE:
# OLD CODE:     if not profile_text:
# OLD CODE:         return jsonify({"error": "Paste your LinkedIn About/Experience/Education content first."}), 400
# OLD CODE:
# OLD CODE:     try:
# OLD CODE:         resume_text = generate_resume_from_profile(linkedin_url, profile_text)
# OLD CODE:         return jsonify({"status": "success", "resume_text": resume_text})
# OLD CODE:     except RateLimitError:
# OLD CODE:         return jsonify({"error": "AI service is busy. Please try again shortly."}), 429
# OLD CODE:     except AuthenticationError:
# OLD CODE:         return jsonify({"error": "API authentication failed."}), 500
# OLD CODE:     except Exception as e:
# OLD CODE:         logger.error(f"Profile resume generation failed: {str(e)}")
# OLD CODE:         return jsonify({"error": "Failed to generate resume. Please try again."}), 500
# OLD CODE:
# OLD CODE:
# OLD CODE: @app.route("/export/profile-resume-pdf", methods=["POST"])
# OLD CODE: def export_profile_resume_pdf():
# OLD CODE:     data = request.get_json() or {}
# OLD CODE:     resume_text = (data.get("resume_text") or "").strip()
# OLD CODE:     if not resume_text:
# OLD CODE:         return "No resume content provided", 400
# OLD CODE:
# OLD CODE:     buffer = io.BytesIO()
# OLD CODE:     doc = SimpleDocTemplate(buffer, pagesize=LETTER)
# OLD CODE:     styles = getSampleStyleSheet()
# OLD CODE:     story = [
# OLD CODE:         Paragraph("<b>Resume</b>", styles["Title"]),
# OLD CODE:         Spacer(1, 12),
# OLD CODE:     ]
# OLD CODE:     for paragraph in resume_text.split("\n\n"):
# OLD CODE:         clean = paragraph.strip().replace("\n", "<br/>")
# OLD CODE:         if clean:
# OLD CODE:             story.append(Paragraph(clean, styles["Normal"]))
# OLD CODE:             story.append(Spacer(1, 6))
# OLD CODE:
# OLD CODE:     doc.build(story)
# OLD CODE:     buffer.seek(0)
# OLD CODE:     return Response(
# OLD CODE:         buffer,
# OLD CODE:         mimetype="application/pdf",
# OLD CODE:         headers={"Content-Disposition": "attachment; filename=generated_resume.pdf"},
# OLD CODE:     )
# OLD CODE:
# OLD CODE:
# OLD CODE: @app.route("/uploads", methods=["POST"])
# OLD CODE: @login_required
# OLD CODE: @limiter.limit("10 per hour")
# OLD CODE: def upload_resume():
# OLD CODE:     """Handle resume uploads for the summariser page."""
# OLD CODE:     logger.info("Upload endpoint hit")
# OLD CODE:
# OLD CODE:     if "file" not in request.files:
# OLD CODE:         return jsonify({"error": "No file uploaded"}), 400
# OLD CODE:
# OLD CODE:     file = request.files["file"]
# OLD CODE:     if file.filename == "":
# OLD CODE:         return jsonify({"error": "Empty filename"}), 400
# OLD CODE:
# OLD CODE:     filename = secure_filename(file.filename)
# OLD CODE:     ext      = filename.lower()
# OLD CODE:     filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
# OLD CODE:
# OLD CODE:     try:
# OLD CODE:         file.save(filepath)
# OLD CODE:         with open(filepath, "rb") as f:
# OLD CODE:             file_stream = io.BytesIO(f.read())
# OLD CODE:
# OLD CODE:         if ext.endswith(".pdf"):
# OLD CODE:             text = extract_pdf_text(file_stream)
# OLD CODE:         elif ext.endswith(".docx"):
# OLD CODE:             text = extract_docx_text(file_stream)
# OLD CODE:         elif ext.endswith(".txt"):
# OLD CODE:             text = file_stream.getvalue().decode("utf-8")
# OLD CODE:         elif ext.endswith((".png", ".jpg", ".jpeg", ".bmp", ".tiff")):
# OLD CODE:             text = pytesseract.image_to_string(Image.open(file_stream))
# OLD CODE:         else:
# OLD CODE:             return jsonify({"error": "Unsupported file type"}), 400
# OLD CODE:
# OLD CODE:         if not text.strip():
# OLD CODE:             return jsonify({"status": "partial", "error": "File appears empty or unreadable",
# OLD CODE:                             **generate_basic_analysis(text)}), 200
# OLD CODE:
# OLD CODE:         logger.info(f"Extracted {len(text)} characters")
# OLD CODE:
# OLD CODE:         try:
# OLD CODE:             text_summary = generate_summary(text)
# OLD CODE:             if text_summary and text_summary.strip():
# OLD CODE:                 _record_community_resume()
# OLD CODE:             return jsonify({"status": "success", "text_summary": text_summary, "analysis_type": "AI"})
# OLD CODE:         except RateLimitError:
# OLD CODE:             return jsonify({"status": "rate_limited", "error": "api_rate_limited",
# OLD CODE:                             "retry_after": 60, "analysis_type": "basic",
# OLD CODE:                             **generate_basic_analysis(text)}), 429
# OLD CODE:         except AuthenticationError:
# OLD CODE:             return jsonify({"status": "error", "error": "api_authentication_failed",
# OLD CODE:                             "analysis_type": "basic", **generate_basic_analysis(text)}), 500
# OLD CODE:         except Exception as e:
# OLD CODE:             logger.error(f"OpenAI API failed: {str(e)}")
# OLD CODE:             return jsonify({"status": "partial", "error": "AI analysis unavailable",
# OLD CODE:                             "analysis_type": "basic", **generate_basic_analysis(text)}), 200
# OLD CODE:
# OLD CODE:     except Exception as e:
# OLD CODE:         logger.error(f"Unexpected error in /upload: {str(e)}", exc_info=True)
# OLD CODE:         return jsonify({"error": "Internal server error"}), 500
# OLD CODE:
# OLD CODE:     finally:
# OLD CODE:         if os.path.exists(filepath):
# OLD CODE:             try:
# OLD CODE:                 os.remove(filepath)
# OLD CODE:             except Exception as e:
# OLD CODE:                 logger.error(f"Failed to delete temp file: {str(e)}")
# OLD CODE:
# OLD CODE:
# OLD CODE: def _matching_jobs_payload(user_message):
# OLD CODE:     """Cheap keyword-matched open jobs for a chat message, serialized for the
# OLD CODE:     frontend to render as clickable links alongside the AI's reply."""
# OLD CODE:     jobs = search_jobs_by_text(user_message)
# OLD CODE:     return [
# OLD CODE:         {
# OLD CODE:             "id": job.id,
# OLD CODE:             "title": job.title,
# OLD CODE:             "company": job.company.name if job.company else "Company",
# OLD CODE:             "location": job.location,
# OLD CODE:             "url": url_for("candidate.job_detail", job_id=job.id),
# OLD CODE:         }
# OLD CODE:         for job in jobs
# OLD CODE:     ]
# OLD CODE:
# OLD CODE:
# OLD CODE: @app.route("/resume-chat", methods=["POST"])
# OLD CODE: @login_required
# OLD CODE: @limiter.limit("30 per hour")
# OLD CODE: def resume_chat():
# OLD CODE:     """Chat endpoint - resume coaching powered by GPT-4o."""
# OLD CODE:     data = request.get_json()
# OLD CODE:     if not data:
# OLD CODE:         return jsonify({"error": "No data provided"}), 400
# OLD CODE:
# OLD CODE:     user_message    = data.get("message", "").strip()
# OLD CODE:     job_description = data.get("job_description", "").strip()
# OLD CODE:     resume_analysis = data.get("resume_analysis", "").strip()
# OLD CODE:     history         = data.get("history", [])
# OLD CODE:
# OLD CODE:     if not user_message:
# OLD CODE:         return jsonify({"error": "No message provided"}), 400
# OLD CODE:
# OLD CODE:     context_block = ""
# OLD CODE:     if job_description:
# OLD CODE:         context_block += f"\n=== JOB DESCRIPTION ===\n{job_description[:2000]}\n"
# OLD CODE:     if resume_analysis:
# OLD CODE:         context_block += f"\n=== MATCH ANALYSIS ===\n{resume_analysis[:2000]}\n"
# OLD CODE:
# OLD CODE:     system_prompt = (
# OLD CODE:         "You are an expert career coach and resume advisor. "
# OLD CODE:         "Your role is to give the candidate actionable tips and guidance so they can improve their own resume - "
# OLD CODE:         "not to write or rewrite it for them."
# OLD CODE:         + (f"\n\nYou have the following context:\n{context_block}" if context_block else "")
# OLD CODE:         + "\n\nGuidelines:\n"
# OLD CODE:         "- Give specific, honest tips: explain WHAT is weak and WHY, and HOW to fix it - but do not write the fix.\n"
# OLD CODE:         "- NEVER write, rewrite, or generate resume bullets, summaries, job descriptions, or any resume content on behalf of the candidate. "
# OLD CODE:         "If asked to write a section or bullet, decline and instead explain what makes a strong version of that content so they can write it themselves.\n"
# OLD CODE:         "- Do not produce text the candidate could copy-paste directly into their resume. "
# OLD CODE:         "The goal is to coach their thinking and writing, not to do it for them.\n"
# OLD CODE:         "- Be honest about gaps and weaknesses, and encouraging about genuine strengths.\n"
# OLD CODE:         "- Keep advice concrete and easy to act on - suggest structure, keywords, specificity, or metrics they should add.\n"
# OLD CODE:         "- Politely redirect anything unrelated to resume improvement or career advice."
# OLD CODE:     )
# OLD CODE:
# OLD CODE:     messages = [{"role": "system", "content": system_prompt}]
# OLD CODE:     for msg in history[-20:]:
# OLD CODE:         if msg.get("role") in ("user", "assistant") and msg.get("content"):
# OLD CODE:             messages.append({"role": msg["role"], "content": msg["content"]})
# OLD CODE:     messages.append({"role": "user", "content": user_message})
# OLD CODE:
# OLD CODE:     try:
# OLD CODE:         response = client.chat.completions.create(
# OLD CODE:             model="gpt-4o",
# OLD CODE:             messages=messages,
# OLD CODE:             max_tokens=800,
# OLD CODE:             temperature=0.7,
# OLD CODE:         )
# OLD CODE:         return jsonify({
# OLD CODE:             "reply": response.choices[0].message.content.strip(),
# OLD CODE:             "matching_jobs": _matching_jobs_payload(user_message),
# OLD CODE:         })
# OLD CODE:     except Exception as e:
# OLD CODE:         logger.error(f"Resume chat API error: {str(e)}")
# OLD CODE:         return jsonify({"error": "Failed to get a response. Please try again."}), 500
# OLD CODE:
# OLD CODE:
# OLD CODE: SITE_HELP_SYSTEM_PROMPT = """You are the Avants AI site guide - a help assistant embedded on every page of the \
# OLD CODE: Avants AI hiring platform. Your only job is helping people (candidates, employers, or visitors who haven't signed \
# OLD CODE: up yet) understand how to use the site and what things mean. You are not a career coach or a general chatbot.
# OLD CODE:
# OLD CODE: === WHAT AVANTS AI IS ===
# OLD CODE: An AI-powered hiring platform. Candidates apply to jobs, complete a real AI voice interview, and get an instant \
# OLD CODE: resume match score. Employers post jobs and every applicant is automatically resume-scored and voice-interviewed \
# OLD CODE: by AI before the employer reviews anyone, producing a ranked shortlist instead of a pile of resumes.
# OLD CODE:
# OLD CODE: === FOR CANDIDATES ===
# OLD CODE: - Browse Jobs: search/filter open roles by keyword, category, work type (Remote/Hybrid/On-site), and city.
# OLD CODE: - Apply: upload a resume (or build one from pasted LinkedIn text via AI) - get an instant 0-100 AI match score \
# OLD CODE: against the job before submitting.
# OLD CODE: - AI Interview: after applying, complete a structured voice interview tailored to that specific role. The AI asks \
# OLD CODE: follow-up questions and issues a verdict (Strong Yes/Yes/No/Strong No) employers see. Can be saved and resumed \
# OLD CODE: later, but only submitted once.
# OLD CODE: - Dashboard: track all applications, message employers, see interview status.
# OLD CODE: - If rejected: candidates may get AI coaching feedback and a personalized skills-gap roadmap.
# OLD CODE: - If hired: the employer enters the actual compensation figure; the candidate must confirm it's accurate (or \
# OLD CODE: dispute it if it's wrong) before anything is finalized.
# OLD CODE: - Community Edition (free, no application needed, open to everyone including employers): a standalone Resume Job \
# OLD CODE: Match tool (paste a job description + resume, get a score), a Resume Summarizer, and a Practice Interview Hub - \
# OLD CODE: a mock AI interview built either from a pasted job description (AI generates the questions) or from your own \
# OLD CODE: manually-typed requirements/questions, not tied to any real job posting or application. All three live under the \
# OLD CODE: "Resume Tools" menu; running an actual practice session or resume tool requires being logged in even though \
# OLD CODE: browsing the page doesn't.
# OLD CODE: - Earn: a separate paid marketplace where professionals rank, rate, fact-check, or write AI training data for \
# OLD CODE: money, unrelated to job hunting.
# OLD CODE:
# OLD CODE: === FOR EMPLOYERS ===
# OLD CODE: - Sign up with a company work email (personal providers like Gmail aren't accepted for employer accounts).
# OLD CODE: - Post a job for free - AI can help structure the description.
# OLD CODE: - Every applicant is automatically screened: resume-scored and voice-interviewed by AI before the employer sees \
# OLD CODE: anything.
# OLD CODE: - Review a ranked pipeline: match scores, AI interview verdicts and transcripts, schedule video or in-person \
# OLD CODE: meetings, message candidates, advance/reject with one click.
# OLD CODE: - To hire: mark the candidate "Hired" and enter their actual compensation (salary or hourly rate) - this is what \
# OLD CODE: the placement fee is based on, not whatever salary was posted on the job listing. The candidate must then confirm \
# OLD CODE: that figure before the fee invoice fires.
# OLD CODE: - Placement fee: 15% of first-year compensation, due within 30 days of the candidate's confirmed start date. \
# OLD CODE: Hourly hires bill this monthly for as long as the engagement stays active instead of one lump sum. Candidates are \
# OLD CODE: never charged anything.
# OLD CODE: - Hired/Rejected decisions are final once confirmed and can't be reversed by the employer afterward (only the \
# OLD CODE: hire's compensation figure can still be corrected).
# OLD CODE: - Employers can close a job (stops new applications, keeps history) or delete it outright only if it has zero \
# OLD CODE: applicants.
# OLD CODE: - Full rules live at /for-employers and the binding Employer Platform Agreement is Section 12 of /terms.
# OLD CODE:
# OLD CODE: === GENERAL ===
# OLD CODE: - A language switcher (top nav) machine-translates any page.
# OLD CODE: - Pricing, fees, and legal terms are covered on /terms and /for-employers - point people there for exact figures \
# OLD CODE: rather than guessing if you're unsure.
# OLD CODE:
# OLD CODE: Guidelines:
# OLD CODE: - Be concise and concrete. Tell people exactly where to click/go (e.g. "Browse Jobs in the top nav", "your \
# OLD CODE: Dashboard").
# OLD CODE: - If asked something outside what you know about this site (general career advice, coding help, anything \
# OLD CODE: unrelated to Avants AI), politely say that's outside what you can help with here and redirect to what you can \
# OLD CODE: help with.
# OLD CODE: - Never invent features, prices, or policies you're not sure about - say you're not certain and point to /terms, \
# OLD CODE: /for-employers, or /faq instead of guessing.
# OLD CODE: - You cannot see which page the person is currently on or their account details - ask if it would help clarify \
# OLD CODE: your answer."""
# OLD CODE:
# OLD CODE:
# OLD CODE: @app.route("/site-help-chat", methods=["POST"])
# OLD CODE: @limiter.limit("30 per hour")
# OLD CODE: def site_help_chat():
# OLD CODE:     """Site-wide help chat - explains how Avants AI works and where to find things.
# OLD CODE:     Deliberately not @login_required so logged-out visitors can ask questions too."""
# OLD CODE:     data = request.get_json()
# OLD CODE:     if not data:
# OLD CODE:         return jsonify({"error": "No data provided"}), 400
# OLD CODE:
# OLD CODE:     user_message = data.get("message", "").strip()
# OLD CODE:     history = data.get("history", [])
# OLD CODE:
# OLD CODE:     if not user_message:
# OLD CODE:         return jsonify({"error": "No message provided"}), 400
# OLD CODE:
# OLD CODE:     messages = [{"role": "system", "content": SITE_HELP_SYSTEM_PROMPT}]
# OLD CODE:     for msg in history[-20:]:
# OLD CODE:         if msg.get("role") in ("user", "assistant") and msg.get("content"):
# OLD CODE:             messages.append({"role": msg["role"], "content": msg["content"]})
# OLD CODE:     messages.append({"role": "user", "content": user_message})
# OLD CODE:
# OLD CODE:     try:
# OLD CODE:         response = client.chat.completions.create(
# OLD CODE:             model="gpt-4o",
# OLD CODE:             messages=messages,
# OLD CODE:             max_tokens=500,
# OLD CODE:             temperature=0.4,
# OLD CODE:         )
# OLD CODE:         return jsonify({
# OLD CODE:             "reply": response.choices[0].message.content.strip(),
# OLD CODE:             "matching_jobs": _matching_jobs_payload(user_message),
# OLD CODE:         })
# OLD CODE:     except Exception as e:
# OLD CODE:         logger.error(f"Site help chat API error: {str(e)}")
# OLD CODE:         return jsonify({"error": "Failed to get a response. Please try again."}), 500
# OLD CODE:
# OLD CODE:
# OLD CODE: def _google_tts_credentials():
# OLD CODE:     """Explicit credentials built from GOOGLE_CREDENTIALS_JSON (the service
# OLD CODE:     account key pasted as a plain env var), if set. Preferred over
# OLD CODE:     GOOGLE_APPLICATION_CREDENTIALS's file-path/Secret-File mounting, which
# OLD CODE:     has repeatedly failed to actually land the file on disk in production.
# OLD CODE:     Returns None to fall back to the default file-based lookup."""
# OLD CODE:     raw = os.environ.get("GOOGLE_CREDENTIALS_JSON")
# OLD CODE:     if not raw:
# OLD CODE:         return None
# OLD CODE:     from google.oauth2 import service_account
# OLD CODE:     info = json.loads(raw)
# OLD CODE:     return service_account.Credentials.from_service_account_info(info)
# OLD CODE:
# OLD CODE:
# OLD CODE: @app.route("/speak", methods=["POST"])
# OLD CODE: @login_required
# OLD CODE: @limiter.limit("20 per hour")
# OLD CODE: def speak_summary():
# OLD CODE:     from google.cloud import texttospeech
# OLD CODE:     from google.auth.exceptions import DefaultCredentialsError
# OLD CODE:     data         = request.get_json()
# OLD CODE:     summary_text = data.get("text", "").strip()
# OLD CODE:
# OLD CODE:     if not summary_text:
# OLD CODE:         return jsonify({"error": "No summary text provided"}), 400
# OLD CODE:
# OLD CODE:     try:
# OLD CODE:         audio_folder = app.config["AUDIO_FOLDER"]
# OLD CODE:         filename = f"{uuid.uuid4()}.mp3"
# OLD CODE:         filepath = os.path.join(audio_folder, filename)
# OLD CODE:
# OLD CODE:         credentials = _google_tts_credentials()
# OLD CODE:         tts_client = (
# OLD CODE:             texttospeech.TextToSpeechClient(credentials=credentials)
# OLD CODE:             if credentials else texttospeech.TextToSpeechClient()
# OLD CODE:         )
# OLD CODE:         input_text  = texttospeech.SynthesisInput(text=summary_text)
# OLD CODE:         voice_name  = data.get("voice", "en-US-Wavenet-D")
# OLD CODE:         voice       = texttospeech.VoiceSelectionParams(
# OLD CODE:             language_code="en-US",
# OLD CODE:             name=voice_name,
# OLD CODE:             ssml_gender=texttospeech.SsmlVoiceGender.MALE,
# OLD CODE:         )
# OLD CODE:         audio_config = texttospeech.AudioConfig(
# OLD CODE:             audio_encoding=texttospeech.AudioEncoding.MP3,
# OLD CODE:             speaking_rate=float(data.get("speed", 1.2)),
# OLD CODE:         )
# OLD CODE:         tts_response = tts_client.synthesize_speech(
# OLD CODE:             input=input_text, voice=voice, audio_config=audio_config
# OLD CODE:         )
# OLD CODE:         with open(filepath, "wb") as out:
# OLD CODE:             out.write(tts_response.audio_content)
# OLD CODE:
# OLD CODE:         return jsonify({"audio_url": f"/audio/{filename}"})
# OLD CODE:     except DefaultCredentialsError as e:
# OLD CODE:         logger.error(f"Google TTS credentials not configured: {str(e)}")
# OLD CODE:         return jsonify({"error": "Text-to-speech isn't configured on the server (missing Google credentials)."}), 500
# OLD CODE:     except Exception as e:
# OLD CODE:         logger.error(f"Google TTS error: {str(e)}", exc_info=True)
# OLD CODE:         return jsonify({"error": "Audio generation failed. Please try again."}), 500
# OLD CODE:
# OLD CODE:
# OLD CODE: @app.route("/audio/<filename>")
# OLD CODE: def serve_audio(filename):
# OLD CODE:     return send_from_directory(app.config["AUDIO_FOLDER"], filename)
# OLD CODE:
# OLD CODE:
# OLD CODE: @app.route("/export/summary-pdf", methods=["POST"])
# OLD CODE: @login_required
# OLD CODE: def export_summary_pdf():
# OLD CODE:     data    = request.get_json()
# OLD CODE:     summary = (data or {}).get("summary", "").strip()
# OLD CODE:     if not summary:
# OLD CODE:         return "No summary provided", 400
# OLD CODE:
# OLD CODE:     # Strip voice-name lines
# OLD CODE:     voice_names = ["Alex", "Rose", "Linda", "Tom"]
# OLD CODE:     lines   = [l for l in summary.split("\n") if l.strip() not in voice_names]
# OLD CODE:     summary = "\n".join(lines).strip()
# OLD CODE:
# OLD CODE:     buffer = io.BytesIO()
# OLD CODE:     doc    = SimpleDocTemplate(buffer, pagesize=LETTER)
# OLD CODE:     styles = getSampleStyleSheet()
# OLD CODE:     story  = [
# OLD CODE:         Paragraph("<b>Resume Summary</b>", styles["Title"]),
# OLD CODE:         Spacer(1, 12),
# OLD CODE:     ]
# OLD CODE:     for paragraph in summary.split("\n\n"):
# OLD CODE:         clean = paragraph.strip().replace("\n", "<br/>")
# OLD CODE:         if clean:
# OLD CODE:             story.append(Paragraph(clean, styles["Normal"]))
# OLD CODE:             story.append(Spacer(1, 6))
# OLD CODE:
# OLD CODE:     doc.build(story)
# OLD CODE:     buffer.seek(0)
# OLD CODE:     return Response(
# OLD CODE:         buffer,
# OLD CODE:         mimetype="application/pdf",
# OLD CODE:         headers={"Content-Disposition": "attachment; filename=resume_summary.pdf"},
# OLD CODE:     )
# OLD CODE:
# OLD CODE:
# OLD CODE: @app.route("/faq")
# OLD CODE: def faq():
# OLD CODE:     return render_template("faq.html")
# OLD CODE:
# OLD CODE:
# OLD CODE: @app.route("/for-employers")
# OLD CODE: def for_employers():
# OLD CODE:     return render_template("for_employers.html")
# OLD CODE:
# OLD CODE:
# OLD CODE: @app.route("/terms")
# OLD CODE: def terms():
# OLD CODE:     return render_template("terms.html")
# OLD CODE:
# OLD CODE:
# OLD CODE: @app.route("/privacy")
# OLD CODE: def privacy():
# OLD CODE:     return render_template("privacy.html")
# OLD CODE:
# OLD CODE:
# OLD CODE: @app.route("/contact", methods=["GET", "POST"])
# OLD CODE: @limiter.limit("20 per hour", key_func=lambda: "contact-global", methods=["POST"])
# OLD CODE: @limiter.limit("5 per hour", methods=["POST"])
# OLD CODE: @limiter.limit("20 per hour", methods=["POST"], key_func=lambda: "contact-global")
# OLD CODE: def contact():
# OLD CODE:     if request.method == "POST":
# OLD CODE:         name = request.form.get("name", "").strip()
# OLD CODE:         email = request.form.get("email", "").strip()
# OLD CODE:         message = request.form.get("message", "").strip()
# OLD CODE:         honeypot = request.form.get("website", "").strip()
# OLD CODE:         not_robot = request.form.get("not_robot")
# OLD CODE:
# OLD CODE:         if honeypot:
# OLD CODE:             # Bot filled in the hidden field - pretend it worked so it doesn't
# OLD CODE:             # adjust its behavior, but skip sending anything.
# OLD CODE:             flash("Thanks for reaching out! Your message has been sent.", "success")
# OLD CODE:             return redirect(url_for("contact"))
# OLD CODE:
# OLD CODE:         if not name or not email or not message:
# OLD CODE:             flash("All fields are required.", "error")
# OLD CODE:             return render_template("contact.html")
# OLD CODE:
# OLD CODE:         if not not_robot:
# OLD CODE:             flash("Please confirm you're not a robot.", "error")
# OLD CODE:             return render_template("contact.html")
# OLD CODE:
# OLD CODE:         try:
# OLD CODE:             # Notify us only; no auto-reply is sent to the sender
# OLD CODE:             msg = Message(
# OLD CODE:                 subject=f"Contact form: {name}",
# OLD CODE:                 recipients=["bazarirhythm@gmail.com"],
# OLD CODE:                 reply_to=email,
# OLD CODE:                 body=f"From: {name} <{email}>\n\n{message}",
# OLD CODE:             )
# OLD CODE:             mail.send(msg)
# OLD CODE:
# OLD CODE:             flash("Thanks for reaching out! Your message has been sent.", "success")
# OLD CODE:         except Exception as e:
# OLD CODE:             logger.error(f"Contact form send failed: {str(e)}")
# OLD CODE:             flash("Couldn't send your message right now. Please try again shortly.", "error")
# OLD CODE:             return render_template("contact.html")
# OLD CODE:
# OLD CODE:         return redirect(url_for("contact"))
# OLD CODE:
# OLD CODE:     return render_template("contact.html")
# OLD CODE:
# OLD CODE:
# OLD CODE: @app.route("/health")
# OLD CODE: def health_check():
# OLD CODE:     return jsonify({
# OLD CODE:         "status": "healthy",
# OLD CODE:         "services": {
# OLD CODE:             "openai": "enabled" if Config.OPENAI_API_KEY else "disabled",
# OLD CODE:             "storage": {
# OLD CODE:                 "upload_folder": os.path.exists(app.config["UPLOAD_FOLDER"]),
# OLD CODE:                 "audio_folder":  os.path.exists(app.config["AUDIO_FOLDER"]),
# OLD CODE:             },
# OLD CODE:         },
# OLD CODE:     })
# OLD CODE:
# OLD CODE:
# OLD CODE: if __name__ == '__main__':
# OLD CODE:     port = int(os.environ.get("PORT", 8080))
# OLD CODE:     app.run(host="0.0.0.0", port=port, debug=True)
# ----------------------------------------------------------------
# NEW IMPLEMENTATION - active code starts below
# ----------------------------------------------------------------
from website import create_app, mail, limiter, db
from community_stats import resume_total, record_resume_processed
from website.candidate import search_jobs_by_text
from flask_mail import Message
from flask import Flask, render_template, request, jsonify, current_app, Response, flash, redirect, url_for
from flask_login import login_required, current_user
#import openai
import httpx
import io
import json
import re
import os
import logging
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from openai._exceptions import RateLimitError, AuthenticationError, APIConnectionError
from config import Config
from flask_cors import CORS
from werkzeug.utils import secure_filename
from PIL import Image
import pytesseract
from flask import send_from_directory
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

from ai_services import (
    extract_pdf_text,
    extract_docx_text,
    extract_text_from_file,
    compare_resume_to_job,
    generate_summary,
    generate_basic_analysis,
    generate_resume_from_profile,
    run_interview_turn,
    transcribe_audio,
    extract_audio_for_transcription,
    audio_file_extension,
    AudioTooLargeError,
    generate_interview_question_preview,
    generate_interview_coaching,
    generate_practice_questions,
    generate_job_fit_verdict,
    JOB_FIT_VERDICT_SCORE,
)
from video_storage import create_scan_upload_url, download_scan_to_file, delete_scan

#  Load env & config
# override=False (the dotenv default) - see website/__init__.py for why this
# matters: it must not silently overwrite an env var a caller set on purpose.
load_dotenv(override=False)
if Config.GOOGLE_APPLICATION_CREDENTIALS:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = Config.GOOGLE_APPLICATION_CREDENTIALS

# App setup
app = create_app()
app.config.from_object(Config)
cors_origins = [
    origin.strip().rstrip('/')
    for origin in os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        f"{Config.PUBLIC_BASE_URL},http://127.0.0.1:5000,http://localhost:5000",
    ).split(',')
    if origin.strip()
]
CORS(app, resources={r"/api/*": {"origins": cors_origins}}, supports_credentials=False)

# Logging (must come before any function that uses logger)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OpenAI
#client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY")) new change

# Short-lived handoff for /resume-jobmatch's Post/Redirect/Get flow. Pasted
# job descriptions can easily exceed the ~4KB Flask session cookie can hold,
# so results are stashed here (keyed by a one-time token in the redirect
# URL) instead of in the session. Safe only because gunicorn runs a single
# worker (see Procfile) - an in-memory dict wouldn't be shared across
# workers if that ever changes.
_RESUME_MATCH_CACHE = {}
_RESUME_MATCH_CACHE_MAX = 200  # evict oldest if a token is never consumed


@app.errorhandler(429)
def handle_rate_limit_exceeded(e):
    """Flask-Limiter's own default 429 is a plain HTML/text page, not JSON -
    every fetch()/XHR-based route in this app (which is most rate-limited
    ones) would fail to parse that as JSON and fall back to a generic
    "something went wrong" with no indication it was actually a rate limit,
    which is exactly what happened debugging the video scan feature: enough
    retries in an hour hit this silently. A handful of routes are rate-
    limited but driven by a traditional full-page form POST rather than
    fetch - those will now render this JSON as plain text on the page
    instead of Werkzeug's default error page if someone exceeds their
    limit, which is a pre-existing rough edge either way, not a regression."""
    return jsonify({"error": "You've made a lot of requests here recently - please wait a bit and try again."}), 429


# ══════════════════════════════════════════════════════════════════════════════
# Routes
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/community-resume-count")
def community_resume_count():
    try:
        response = jsonify(total=resume_total(db.engine))
    except Exception:
        logger.exception("Community resume count unavailable")
        response = jsonify(error="Count temporarily unavailable")
        response.status_code = 503
    response.headers["Cache-Control"] = "no-store"
    return response


def _record_community_resume():
    # A metrics failure must not discard a completed analysis for the user.
    try:
        record_resume_processed(db.engine)
    except Exception:
        logger.exception("Failed to record completed Community Edition resume")


@app.route("/resume-summarizer")
def resumesum():
    return render_template("resumesum.html")


@app.route('/resume-jobmatch', methods=['GET', 'POST'])
@limiter.limit("10 per hour", methods=["POST"])
def resumemat():
    """Resume job-match page - handles both the form display and form submission.

    POST redirects back to this same GET route (Post/Redirect/Get) instead of
    rendering the result directly, so reloading the results page just re-GETs
    it instead of resubmitting the form - which used to re-run the AI call
    (burning quota) and drop a duplicate entry into the saved-results list
    every time, since the AI's wording differs slightly on each run.
    """
    def _stash_and_redirect(result, score_value, job_text):
        if len(_RESUME_MATCH_CACHE) >= _RESUME_MATCH_CACHE_MAX:
            _RESUME_MATCH_CACHE.pop(next(iter(_RESUME_MATCH_CACHE)), None)
        token = uuid.uuid4().hex
        _RESUME_MATCH_CACHE[token] = {"result": result, "score_value": score_value, "job_text": job_text}
        return redirect(url_for('resumemat', rid=token))

    if request.method == 'POST':
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=request.path))

        job_text    = request.form.get('job_req', '')
        resume_file = request.files.get('resume')

        if not job_text.strip() or not resume_file:
            return _stash_and_redirect(None, 0, job_text)

        resume_bytes = resume_file.read()
        resume_file.stream.seek(0)

        resume_text = extract_text_from_file(resume_file.filename, resume_bytes)

        if not resume_text.strip():
            logger.error("Extracted resume text is empty")
            return _stash_and_redirect(
                "Resume content could not be read. Please upload a readable PDF, DOCX, or TXT file.",
                0, job_text,
            )

        try:
            result = compare_resume_to_job(job_text, resume_text)
        except RateLimitError:
            return _stash_and_redirect("Our AI service is busy right now. Please try again in a minute.", 0, job_text)
        except AuthenticationError:
            logger.error("OpenAI authentication failed in /resume-jobmatch")
            return _stash_and_redirect("Something went wrong on our end. Please try again shortly.", 0, job_text)
        except Exception as e:
            logger.error(f"compare_resume_to_job failed: {str(e)}")
            return _stash_and_redirect("We couldn't analyze your resume right now. Please try again shortly.", 0, job_text)

        # Persist raw result to disk (optional)
        with open("resumemat.txt", "w", encoding="utf-8") as f:
            f.write(result)

        # Extract numeric score (first number in 0-100 range)
        score_value = 0
        for num in re.findall(r"\b(\d{1,3})\b", result):
            val = int(num)
            if 0 <= val <= 100:
                score_value = val
                break

        if result and result.strip():
            _record_community_resume()
        return _stash_and_redirect(result.replace('*', ''), score_value, job_text)

    saved = _RESUME_MATCH_CACHE.pop(request.args.get('rid'), None) or {}
    return render_template(
        'resumemat.html',
        result=saved.get('result'),
        score_value=saved.get('score_value', 0),
        job_text=saved.get('job_text', ''),
    )


_SCAN_PATH_RE = re.compile(r"^scans/[0-9a-f]{32}\.[a-z0-9]{1,10}$")




_VIDEO_SCAN_JOBS = {}
_VIDEO_SCAN_JOBS_MAX = 200










VALID_INTERVIEW_LENGTHS = ("short", "standard", "thorough")












@app.route("/uploads", methods=["POST"])
@login_required
@limiter.limit("10 per hour")
def upload_resume():
    """Handle resume uploads for the summariser page."""
    logger.info("Upload endpoint hit")

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    filename = secure_filename(file.filename)
    ext      = filename.lower()
    if ext.rsplit('.', 1)[-1] not in {'pdf', 'docx', 'txt'}:
        return jsonify({"error": "Unsupported file type"}), 400
    file.stream.seek(0, os.SEEK_END)
    size = file.stream.tell()
    file.stream.seek(0)
    if size <= 0 or size > Config.MAX_FILE_SIZE:
        return jsonify({"error": "File is empty or exceeds the 5 MB limit"}), 400
    safe_name = f"{uuid.uuid4().hex}{os.path.splitext(filename)[1].lower()}"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], safe_name)

    try:
        file.save(filepath)
        with open(filepath, "rb") as f:
            file_stream = io.BytesIO(f.read())

        if ext.endswith(".pdf"):
            text = extract_pdf_text(file_stream)
        elif ext.endswith(".docx"):
            text = extract_docx_text(file_stream)
        elif ext.endswith(".txt"):
            text = file_stream.getvalue().decode("utf-8")
        elif ext.endswith((".png", ".jpg", ".jpeg", ".bmp", ".tiff")):
            text = pytesseract.image_to_string(Image.open(file_stream))
        else:
            return jsonify({"error": "Unsupported file type"}), 400

        if not text.strip():
            return jsonify({"status": "partial", "error": "File appears empty or unreadable",
                            **generate_basic_analysis(text)}), 200

        logger.info(f"Extracted {len(text)} characters")

        try:
            text_summary = generate_summary(text)
            if text_summary and text_summary.strip():
                _record_community_resume()
            return jsonify({"status": "success", "text_summary": text_summary, "analysis_type": "AI"})
        except RateLimitError:
            return jsonify({"status": "rate_limited", "error": "api_rate_limited",
                            "retry_after": 60, "analysis_type": "basic",
                            **generate_basic_analysis(text)}), 429
        except AuthenticationError:
            return jsonify({"status": "error", "error": "api_authentication_failed",
                            "analysis_type": "basic", **generate_basic_analysis(text)}), 500
        except Exception as e:
            logger.error(f"OpenAI API failed: {str(e)}")
            return jsonify({"status": "partial", "error": "AI analysis unavailable",
                            "analysis_type": "basic", **generate_basic_analysis(text)}), 200

    except Exception as e:
        logger.error(f"Unexpected error in /upload: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

    finally:
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as e:
                logger.error(f"Failed to delete temp file: {str(e)}")






SITE_HELP_SYSTEM_PROMPT = """You are the Avants AI site guide - a help assistant embedded on every page of the \
Avants AI hiring platform. Your only job is helping people (candidates, employers, or visitors who haven't signed \
up yet) understand how to use the site and what things mean. You are not a career coach or a general chatbot.

=== WHAT AVANTS AI IS ===
An AI-powered hiring platform. Candidates apply to jobs, complete a real AI voice interview, and get an instant \
resume match score. Employers post jobs and every applicant is automatically resume-scored and voice-interviewed \
by AI before the employer reviews anyone, producing a ranked shortlist instead of a pile of resumes.

=== FOR CANDIDATES ===
- Browse Jobs: search/filter open roles by keyword, category, work type (Remote/Hybrid/On-site), and city.
- Apply: upload a resume (or build one from pasted LinkedIn text via AI) - get an instant 0-100 AI match score \
against the job before submitting.
- AI Interview: after applying, complete a structured voice interview tailored to that specific role. The AI asks \
follow-up questions and issues a verdict (Strong Yes/Yes/No/Strong No) employers see. Can be saved and resumed \
later, but only submitted once.
- Dashboard: track all applications, message employers, see interview status.
- If rejected: candidates may get AI coaching feedback and a personalized skills-gap roadmap.
- If hired: the employer enters the actual compensation figure; the candidate must confirm it's accurate (or \
dispute it if it's wrong) before anything is finalized.
- Community Edition (free, no application needed, open to everyone including employers): a standalone Resume Job \
Match tool (paste a job description + resume, get a score), a Resume Summarizer, and a Practice Interview Hub - \
a mock AI interview built either from a pasted job description (AI generates the questions) or from your own \
manually-typed requirements/questions, not tied to any real job posting or application. All three live under the \
"Resume Tools" menu; running an actual practice session or resume tool requires being logged in even though \
browsing the page doesn't.
- Earn: a separate paid marketplace where professionals rank, rate, fact-check, or write AI training data for \
money, unrelated to job hunting.

=== FOR EMPLOYERS ===
- Sign up with a company work email (personal providers like Gmail aren't accepted for employer accounts).
- Post a job for free - AI can help structure the description.
- Every applicant is automatically screened: resume-scored and voice-interviewed by AI before the employer sees \
anything.
- Review a ranked pipeline: match scores, AI interview verdicts and transcripts, schedule video or in-person \
meetings, message candidates, advance/reject with one click.
- To hire: mark the candidate "Hired" and enter their actual compensation (salary or hourly rate) - this is what \
the placement fee is based on, not whatever salary was posted on the job listing. The candidate must then confirm \
that figure before the fee invoice fires.
- Placement fee: 15% of first-year compensation, due within 30 days of the candidate's confirmed start date. \
Hourly hires bill this monthly for as long as the engagement stays active instead of one lump sum. Candidates are \
never charged anything.
- Hired/Rejected decisions are final once confirmed and can't be reversed by the employer afterward (only the \
hire's compensation figure can still be corrected).
- Employers can close a job (stops new applications, keeps history) or delete it outright only if it has zero \
applicants.
- Full rules live at /for-employers and the binding Employer Platform Agreement is Section 12 of /terms.

=== GENERAL ===
- A language switcher (top nav) machine-translates any page.
- Pricing, fees, and legal terms are covered on /terms and /for-employers - point people there for exact figures \
rather than guessing if you're unsure.

Guidelines:
- Be concise and concrete. Tell people exactly where to click/go (e.g. "Browse Jobs in the top nav", "your \
Dashboard").
- If asked something outside what you know about this site (general career advice, coding help, anything \
unrelated to Avants AI), politely say that's outside what you can help with here and redirect to what you can \
help with.
- Never invent features, prices, or policies you're not sure about - say you're not certain and point to /terms, \
/for-employers, or /faq instead of guessing.
- You cannot see which page the person is currently on or their account details - ask if it would help clarify \
your answer."""

























# Load route modules after app and shared services are initialized.
import sys
if __name__ == "__main__":
    sys.modules.setdefault("app", sys.modules[__name__])
from app_scan_routes import (
    resumemat_video_upload_url, _process_video_scan_job, resumemat_video_feedback,
    resumemat_video_feedback_status, resumemat_practice_questions, practice_interview_hub,
    practice_hub_chat, practice_hub_questions,
)
from app_resume_routes import generate_profile_resume, export_profile_resume_pdf
from app_site_routes import (
    site_help_chat, _google_tts_credentials, speak_summary, serve_audio,
    export_summary_pdf, faq, for_employers, terms, privacy, contact, health_check,
    _matching_jobs_payload, resume_chat,
)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host="127.0.0.1", port=port, debug=False)
