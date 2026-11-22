"""Routes moved from app.py; registered on the existing Flask app."""

from app import (
    Config,
    LETTER,
    Message,
    Paragraph,
    Response,
    SITE_HELP_SYSTEM_PROMPT,
    SimpleDocTemplate,
    Spacer,
    app,
    #client,
    flash,
    getSampleStyleSheet,
    io,
    json,
    jsonify,
    limiter,
    logger,
    login_required,
    mail,
    os,
    redirect,
    render_template,
    request,
    search_jobs_by_text,
    send_from_directory,
    url_for,
    uuid
)
from _ai_service_common import openrouter_client

# Moved from app.py: _matching_jobs_payload
def _matching_jobs_payload(user_message):
    """Cheap keyword-matched open jobs for a chat message, serialized for the
    frontend to render as clickable links alongside the AI's reply."""
    jobs = search_jobs_by_text(user_message)
    return [
        {
            "id": job.id,
            "title": job.title,
            "company": job.company.name if job.company else "Company",
            "location": job.location,
            "url": url_for("candidate.job_detail", job_id=job.id),
        }
        for job in jobs
    ]

# Moved from app.py: resume_chat
@app.route("/resume-chat", methods=["POST"])
@login_required
@limiter.limit("30 per hour")
def resume_chat():
    """Chat endpoint - resume coaching powered by GPT-4o."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    user_message    = data.get("message", "").strip()
    job_description = data.get("job_description", "").strip()
    resume_analysis = data.get("resume_analysis", "").strip()
    history         = data.get("history", [])

    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    context_block = ""
    if job_description:
        context_block += f"\n=== JOB DESCRIPTION ===\n{job_description[:2000]}\n"
    if resume_analysis:
        context_block += f"\n=== MATCH ANALYSIS ===\n{resume_analysis[:2000]}\n"

    system_prompt = (
        "You are an expert career coach and resume advisor. "
        "Your role is to give the candidate actionable tips and guidance so they can improve their own resume - "
        "not to write or rewrite it for them."
        + (f"\n\nYou have the following context:\n{context_block}" if context_block else "")
        + "\n\nGuidelines:\n"
        "- Give specific, honest tips: explain WHAT is weak and WHY, and HOW to fix it - but do not write the fix.\n"
        "- NEVER write, rewrite, or generate resume bullets, summaries, job descriptions, or any resume content on behalf of the candidate. "
        "If asked to write a section or bullet, decline and instead explain what makes a strong version of that content so they can write it themselves.\n"
        "- Do not produce text the candidate could copy-paste directly into their resume. "
        "The goal is to coach their thinking and writing, not to do it for them.\n"
        "- Be honest about gaps and weaknesses, and encouraging about genuine strengths.\n"
        "- Keep advice concrete and easy to act on - suggest structure, keywords, specificity, or metrics they should add.\n"
        "- Politely redirect anything unrelated to resume improvement or career advice."
    )

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history[-20:]:
        if msg.get("role") in ("user", "assistant") and msg.get("content"):
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    try:
        #response = client.chat.completions.create(
        response = openrouter_client.chat.completions.create(
            #model="gpt-4o",
            model=Config.OPENROUTER_CHAT_MODEL,
            messages=messages,
            max_tokens=800,
            temperature=0.7,
        )
        return jsonify({
            "reply": response.choices[0].message.content.strip(),
            "matching_jobs": _matching_jobs_payload(user_message),
        })
    except Exception as e:
        logger.error(f"Resume chat API error: {str(e)}")
        return jsonify({"error": "Failed to get a response. Please try again."}), 500

# Moved from app.py: site_help_chat
@app.route("/site-help-chat", methods=["POST"])
@limiter.limit("30 per hour")
def site_help_chat():
    """Site-wide help chat - explains how Avants AI works and where to find things.
    Deliberately not @login_required so logged-out visitors can ask questions too."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    user_message = data.get("message", "").strip()
    history = data.get("history", [])

    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    messages = [{"role": "system", "content": SITE_HELP_SYSTEM_PROMPT}]
    for msg in history[-20:]:
        if msg.get("role") in ("user", "assistant") and msg.get("content"):
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    try:
        #response = client.chat.completions.create(
        response = openrouter_client.chat.completions.create(
            #model="gpt-4o",
            model=Config.OPENROUTER_CHAT_MODEL,
            messages=messages,
            max_tokens=500,
            temperature=0.4,
        )
        return jsonify({
            "reply": response.choices[0].message.content.strip(),
            "matching_jobs": _matching_jobs_payload(user_message),
        })
    except Exception as e:
        logger.error(f"Site help chat API error: {str(e)}")
        return jsonify({"error": "Failed to get a response. Please try again."}), 500

# Moved from app.py: _google_tts_credentials
def _google_tts_credentials():
    """Explicit credentials built from GOOGLE_CREDENTIALS_JSON (the service
    account key pasted as a plain env var), if set. Preferred over
    GOOGLE_APPLICATION_CREDENTIALS's file-path/Secret-File mounting, which
    has repeatedly failed to actually land the file on disk in production.
    Returns None to fall back to the default file-based lookup."""
    raw = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if not raw:
        return None
    from google.oauth2 import service_account
    info = json.loads(raw)
    return service_account.Credentials.from_service_account_info(info)

# Moved from app.py: speak_summary
@app.route("/speak", methods=["POST"])
@login_required
@limiter.limit("20 per hour")
def speak_summary():
    from google.cloud import texttospeech
    from google.auth.exceptions import DefaultCredentialsError
    data         = request.get_json()
    summary_text = data.get("text", "").strip()

    if not summary_text:
        return jsonify({"error": "No summary text provided"}), 400

    try:
        audio_folder = app.config["AUDIO_FOLDER"]
        filename = f"{uuid.uuid4()}.mp3"
        filepath = os.path.join(audio_folder, filename)

        credentials = _google_tts_credentials()
        tts_client = (
            texttospeech.TextToSpeechClient(credentials=credentials)
            if credentials else texttospeech.TextToSpeechClient()
        )
        input_text  = texttospeech.SynthesisInput(text=summary_text)
        voice_name  = data.get("voice", "en-US-Wavenet-D")
        voice       = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name=voice_name,
            ssml_gender=texttospeech.SsmlVoiceGender.MALE,
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=float(data.get("speed", 1.2)),
        )
        tts_response = tts_client.synthesize_speech(
            input=input_text, voice=voice, audio_config=audio_config
        )
        with open(filepath, "wb") as out:
            out.write(tts_response.audio_content)

        return jsonify({"audio_url": f"/audio/{filename}"})
    except DefaultCredentialsError as e:
        logger.error(f"Google TTS credentials not configured: {str(e)}")
        return jsonify({"error": "Text-to-speech isn't configured on the server (missing Google credentials)."}), 500
    except Exception as e:
        logger.error(f"Google TTS error: {str(e)}", exc_info=True)
        return jsonify({"error": "Audio generation failed. Please try again."}), 500

# Moved from app.py: serve_audio
@app.route("/audio/<filename>")
def serve_audio(filename):
    return send_from_directory(app.config["AUDIO_FOLDER"], filename)

# Moved from app.py: export_summary_pdf
@app.route("/export/summary-pdf", methods=["POST"])
@login_required
def export_summary_pdf():
    data    = request.get_json()
    summary = (data or {}).get("summary", "").strip()
    if not summary:
        return "No summary provided", 400

    # Strip voice-name lines
    voice_names = ["Alex", "Rose", "Linda", "Tom"]
    lines   = [l for l in summary.split("\n") if l.strip() not in voice_names]
    summary = "\n".join(lines).strip()

    buffer = io.BytesIO()
    doc    = SimpleDocTemplate(buffer, pagesize=LETTER)
    styles = getSampleStyleSheet()
    story  = [
        Paragraph("<b>Resume Summary</b>", styles["Title"]),
        Spacer(1, 12),
    ]
    for paragraph in summary.split("\n\n"):
        clean = paragraph.strip().replace("\n", "<br/>")
        if clean:
            story.append(Paragraph(clean, styles["Normal"]))
            story.append(Spacer(1, 6))

    doc.build(story)
    buffer.seek(0)
    return Response(
        buffer,
        mimetype="application/pdf",
        headers={"Content-Disposition": "attachment; filename=resume_summary.pdf"},
    )

# Moved from app.py: faq
@app.route("/faq")
def faq():
    return render_template("faq.html")

# Moved from app.py: for_employers
@app.route("/for-employers")
def for_employers():
    return render_template("for_employers.html")

# Moved from app.py: terms
@app.route("/terms")
def terms():
    return render_template("terms.html")

# Moved from app.py: privacy
@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

# Moved from app.py: contact
@app.route("/contact", methods=["GET", "POST"])
@limiter.limit("20 per hour", key_func=lambda: "contact-global", methods=["POST"])
@limiter.limit("5 per hour", methods=["POST"])
@limiter.limit("20 per hour", methods=["POST"], key_func=lambda: "contact-global")
def contact():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        message = request.form.get("message", "").strip()
        honeypot = request.form.get("website", "").strip()
        not_robot = request.form.get("not_robot")

        if honeypot:
            # Bot filled in the hidden field - pretend it worked so it doesn't
            # adjust its behavior, but skip sending anything.
            flash("Thanks for reaching out! Your message has been sent.", "success")
            return redirect(url_for("contact"))

        if not name or not email or not message:
            flash("All fields are required.", "error")
            return render_template("contact.html")

        if not not_robot:
            flash("Please confirm you're not a robot.", "error")
            return render_template("contact.html")

        try:
            # Notify us only; no auto-reply is sent to the sender
            msg = Message(
                subject=f"Contact form: {name}",
                recipients=["bazarirhythm@gmail.com"],
                reply_to=email,
                body=f"From: {name} <{email}>\n\n{message}",
            )
            mail.send(msg)

            flash("Thanks for reaching out! Your message has been sent.", "success")
        except Exception as e:
            logger.error(f"Contact form send failed: {str(e)}")
            flash("Couldn't send your message right now. Please try again shortly.", "error")
            return render_template("contact.html")

        return redirect(url_for("contact"))

    return render_template("contact.html")

# Moved from app.py: health_check
@app.route("/health")
def health_check():
    return jsonify({
        "status": "healthy",
        "services": {
            "openai": "enabled" if Config.OPENAI_API_KEY else "disabled",
            "storage": {
                "upload_folder": os.path.exists(app.config["UPLOAD_FOLDER"]),
                "audio_folder":  os.path.exists(app.config["AUDIO_FOLDER"]),
            },
        },
    })

