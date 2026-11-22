"""Routes moved from app.py; registered on the existing Flask app."""

from app import (
    AuthenticationError,
    LETTER,
    Paragraph,
    RateLimitError,
    Response,
    SimpleDocTemplate,
    Spacer,
    app,
    generate_resume_from_profile,
    getSampleStyleSheet,
    io,
    jsonify,
    limiter,
    logger,
    login_required,
    request
)

# Moved from app.py: generate_profile_resume
@app.route("/generate-profile-resume", methods=["POST"])
@login_required
@limiter.limit("10 per hour")
def generate_profile_resume():
    """Build a resume from pasted LinkedIn profile text for candidates without one."""
    data = request.get_json() or {}
    linkedin_url = data.get("linkedin_url", "").strip()
    profile_text = data.get("profile_text", "").strip()

    if not profile_text:
        return jsonify({"error": "Paste your LinkedIn About/Experience/Education content first."}), 400

    try:
        resume_text = generate_resume_from_profile(linkedin_url, profile_text)
        return jsonify({"status": "success", "resume_text": resume_text})
    except RateLimitError:
        return jsonify({"error": "AI service is busy. Please try again shortly."}), 429
    except AuthenticationError:
        return jsonify({"error": "API authentication failed."}), 500
    except Exception as e:
        logger.error(f"Profile resume generation failed: {str(e)}")
        return jsonify({"error": "Failed to generate resume. Please try again."}), 500

# Moved from app.py: export_profile_resume_pdf
@app.route("/export/profile-resume-pdf", methods=["POST"])
def export_profile_resume_pdf():
    data = request.get_json() or {}
    resume_text = (data.get("resume_text") or "").strip()
    if not resume_text:
        return "No resume content provided", 400

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=LETTER)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("<b>Resume</b>", styles["Title"]),
        Spacer(1, 12),
    ]
    for paragraph in resume_text.split("\n\n"):
        clean = paragraph.strip().replace("\n", "<br/>")
        if clean:
            story.append(Paragraph(clean, styles["Normal"]))
            story.append(Spacer(1, 6))

    doc.build(story)
    buffer.seek(0)
    return Response(
        buffer,
        mimetype="application/pdf",
        headers={"Content-Disposition": "attachment; filename=generated_resume.pdf"},
    )

