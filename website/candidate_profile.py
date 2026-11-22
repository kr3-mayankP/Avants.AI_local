"""Candidate routes moved from candidate.py."""

from .candidate import (
    Application,
    CandidateProfile,
    Company,
    Job,
    LETTER,
    Notification,
    Paragraph,
    Response,
    SIMILAR_JOB_POOL,
    SUGGESTION_JOB_POOL,
    SimpleDocTemplate,
    Spacer,
    User,
    _notify_employers_of_open_to_work,
    abort,
    candidate,
    current_user,
    db,
    find_similar_jobs,
    generate_resume_from_profile,
    getSampleStyleSheet,
    io,
    jsonify,
    limiter,
    login_required,
    render_template,
    request,
    suggest_jobs_for_profile,
    url_for,
)

# Moved from candidate.py: profile
@candidate.route('/profile')
@login_required
def profile():
    candidate_profile = CandidateProfile.query.filter_by(user_id=current_user.id).first()
    return render_template("profile.html", profile=candidate_profile)

# Moved from candidate.py: save_profile
@candidate.route('/profile/save', methods=['POST'])
@login_required
def save_profile():
    data = request.get_json() or {}

    first_name = (data.get('first_name') or '').strip()
    last_name = (data.get('last_name') or '').strip()   #new change for last name
    if first_name:
        current_user.first_name = first_name
    if last_name:                               #new change for last name
        current_user.last_name = last_name      #new change for last name

    candidate_profile = CandidateProfile.query.filter_by(user_id=current_user.id).first()
    if not candidate_profile:
        candidate_profile = CandidateProfile(user_id=current_user.id)
        db.session.add(candidate_profile)

    was_open_to_work = candidate_profile.open_to_work

    candidate_profile.headline       = (data.get('headline') or '').strip() or None
    candidate_profile.linkedin_url   = (data.get('linkedin_url') or '').strip() or None
    candidate_profile.target_roles   = (data.get('target_roles') or '').strip() or None
    candidate_profile.skills         = (data.get('skills') or '').strip() or None
    candidate_profile.work_preference = (data.get('work_preference') or '').strip() or None
    candidate_profile.availability   = (data.get('availability') or '').strip() or None
    candidate_profile.years_experience = (data.get('years_experience') or '').strip() or None
    candidate_profile.location       = (data.get('location') or '').strip() or None
    candidate_profile.open_to_work   = bool(data.get('open_to_work', False))

    resume_text = (data.get('resume_text') or '').strip()
    if resume_text:
        candidate_profile.resume_text = resume_text

    db.session.commit()

    if candidate_profile.open_to_work and not was_open_to_work:
        _notify_employers_of_open_to_work(candidate_profile)
        db.session.commit()

    return jsonify({"status": "success"})

# Moved from candidate.py: generate_profile_resume
@candidate.route('/profile/generate-resume', methods=['POST'])
@login_required
@limiter.limit("15 per hour")
def generate_profile_resume():
    """Intake pasted LinkedIn profile content and turn it into a structured resume."""
    data = request.get_json() or {}
    linkedin_url = (data.get('linkedin_url') or '').strip()
    profile_text = (data.get('profile_text') or '').strip()

    if not profile_text:
        return jsonify({"error": "Paste your LinkedIn About/Experience/Education content first."}), 400

    try:
        resume_text = generate_resume_from_profile(linkedin_url, profile_text)
    except Exception:
        return jsonify({"error": "Failed to generate resume. Please try again."}), 500

    return jsonify({"resume_text": resume_text})

# Moved from candidate.py: public_profile
@candidate.route('/candidates/<int:user_id>')
def public_profile(user_id):
    from .models import User
    user = User.query.get_or_404(user_id)
    prof = CandidateProfile.query.filter_by(user_id=user_id).first_or_404()
    if not prof.open_to_work:
        abort(404)

    # employer invite-to-apply logic
    employer_jobs = []
    if current_user.is_authenticated and current_user.role == 'employer':
        from .models import Company
        company = Company.query.filter_by(owner_user_id=current_user.id).first()
        if company:
            employer_jobs = Job.query.filter_by(company_id=company.id, status='open').all()

    return render_template("candidate_public.html", profile=prof, user=user, employer_jobs=employer_jobs)

# Moved from candidate.py: invite_candidate
@candidate.route('/candidates/<int:user_id>/invite', methods=['POST'])
@login_required
def invite_candidate(user_id):
    from .models import User, Company
    if current_user.role != 'employer':
        return jsonify({"error": "Employers only"}), 403
    target_user = User.query.get_or_404(user_id)
    job_id = request.get_json(silent=True, force=True).get('job_id') if request.data else None

    company = Company.query.filter_by(owner_user_id=current_user.id).first()
    company_name = company.name if company else "An employer"
    job = Job.query.get(job_id) if job_id else None
    msg = f"{company_name} is interested in your profile"
    link = url_for('candidate.job_detail', job_id=job.id) if job else url_for('employer.company_page', company_id=company.id) if company else None
    if job:
        msg += f" and invited you to apply for {job.title}"
    db.session.add(Notification(user_id=target_user.id, message=msg + ".", link=link))
    db.session.commit()
    return jsonify({"status": "invited"})

# Moved from candidate.py: download_profile_resume
@candidate.route('/profile/resume.pdf')
@login_required
def download_profile_resume():
    candidate_profile = CandidateProfile.query.filter_by(user_id=current_user.id).first()
    if not candidate_profile or not (candidate_profile.resume_text or '').strip():
        abort(404)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=LETTER)
    styles = getSampleStyleSheet()
    story = [Paragraph("<b>Resume</b>", styles["Title"]), Spacer(1, 12)]
    for paragraph in candidate_profile.resume_text.split("\n\n"):
        clean = paragraph.strip().replace("\n", "<br/>")
        if clean:
            story.append(Paragraph(clean, styles["Normal"]))
            story.append(Spacer(1, 6))

    doc.build(story)
    buffer.seek(0)
    return Response(
        buffer,
        mimetype="application/pdf",
        headers={"Content-Disposition": "attachment; filename=resume.pdf"},
    )

# Moved from candidate.py: suggested_jobs
@candidate.route('/profile/suggested-jobs')
@login_required
@limiter.limit("30 per hour")
def suggested_jobs():
    """AI-ranked open jobs/companies on the platform that fit this candidate's profile."""
    candidate_profile = CandidateProfile.query.filter_by(user_id=current_user.id).first()
    if not candidate_profile or not (candidate_profile.resume_text or '').strip():
        return jsonify({"suggestions": []})

    already_applied_ids = {
        app.job_id for app in Application.query.filter_by(candidate_user_id=current_user.id).all()
    }
    open_jobs = (
        Job.query.filter_by(status='open')
        .order_by(Job.created_at.desc())
        .limit(SUGGESTION_JOB_POOL)
        .all()
    )
    open_jobs = [job for job in open_jobs if job.id not in already_applied_ids]
    if not open_jobs:
        return jsonify({"suggestions": []})

    jobs_payload = [
        {
            "id": job.id,
            "title": job.title,
            "company": job.company.name,
            "category": job.category,
            "description": job.description_text,
        }
        for job in open_jobs
    ]

    try:
        ranked = suggest_jobs_for_profile(candidate_profile.resume_text, candidate_profile.target_roles, jobs_payload)
    except Exception:
        return jsonify({"error": "Failed to generate suggestions. Please try again."}), 500

    jobs_by_id = {job.id: job for job in open_jobs}
    suggestions = []
    for item in ranked[:8]:
        job = jobs_by_id.get(item["job_id"])
        if not job:
            continue
        suggestions.append({
            "job_id": job.id,
            "title": job.title,
            "company": job.company.name,
            "score": item["score"],
            "reason": item["reason"],
            "url": url_for('candidate.job_detail', job_id=job.id),
        })

    return jsonify({"suggestions": suggestions})

# Moved from candidate.py: similar_jobs
@candidate.route('/jobs/<int:job_id>/similar')
def similar_jobs(job_id):
    """AI-powered similar jobs based on role title + description, not category."""
    current_job = Job.query.get_or_404(job_id)

    other_jobs = (
        Job.query.filter(Job.status == 'open', Job.id != job_id)
        .order_by(Job.created_at.desc())
        .limit(SIMILAR_JOB_POOL)
        .all()
    )
    if not other_jobs:
        return jsonify({"similar": []})

    current_payload = {
        "id": current_job.id,
        "title": current_job.title,
        "description": current_job.description_text,
    }
    others_payload = [
        {
            "id": j.id,
            "title": j.title,
            "company": j.company.name,
            "description": j.description_text,
        }
        for j in other_jobs
    ]

    try:
        ranked = find_similar_jobs(current_payload, others_payload)
    except Exception:
        return jsonify({"similar": []})

    jobs_by_id = {j.id: j for j in other_jobs}
    similar = []
    for item in ranked:
        job = jobs_by_id.get(item["job_id"])
        if not job:
            continue
        similar.append({
            "job_id": job.id,
            "title": job.title,
            "company": job.company.name,
            "similarity": item["similarity"],
            "reason": item["reason"],
            "url": url_for('candidate.job_detail', job_id=job.id),
            "salary": None,
        })

    return jsonify({"similar": similar})

