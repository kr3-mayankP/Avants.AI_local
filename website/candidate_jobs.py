"""Candidate routes moved from candidate.py."""

from .candidate import (
    Application,
    COUNTRIES,
    CandidateProfile,
    CompanyMember,
    JOB_CATEGORIES,
    Job,
    SavedJob,
    _extract_score,
    abort,
    candidate,
    compare_resume_to_job,
    current_user,
    datetime,
    db,
    extract_text_from_file,
    flash,
    func,
    json,
    jsonify,
    limiter,
    login_required,
    or_,
    redirect,
    render_template,
    request,
    timedelta,
    url_for,
)

# Moved from candidate.py: browse_jobs
@candidate.route('/jobs')
def browse_jobs():
    query = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    location = request.args.get('location', '').strip()
    city = request.args.get('city', '').strip()
    sort = request.args.get('sort', 'newest').strip()

    jobs_query = Job.query.filter_by(status='open')
    if query:
        jobs_query = jobs_query.filter(
            or_(Job.title.ilike(f"%{query}%"), Job.description.ilike(f"%{query}%"))
        )
    if category in JOB_CATEGORIES:
        jobs_query = jobs_query.filter_by(category=category)
    if location:
        jobs_query = jobs_query.filter(Job.location.ilike(f"{location}%"))
    if city:
        # City isn't its own column - Hybrid/On-site postings store it appended
        # to location as "Hybrid - New York, NY" (see employer.post_job), so
        # match it as a substring rather than a separate field.
        jobs_query = jobs_query.filter(Job.location.ilike(f"%{city}%"))

    if sort == 'priority':
        applicant_count_subq = (
            db.session.query(func.count(Application.id))
            .filter(Application.job_id == Job.id)
            .correlate(Job)
            .scalar_subquery()
        )
        jobs_query = jobs_query.order_by(applicant_count_subq.desc())
    elif sort == 'trending':
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_count_subq = (
            db.session.query(func.count(Application.id))
            .filter(Application.job_id == Job.id, Application.created_at >= week_ago)
            .correlate(Job)
            .scalar_subquery()
        )
        jobs_query = jobs_query.order_by(recent_count_subq.desc())
    elif sort == 'pay':
        jobs_query = jobs_query.order_by(Job.salary_usd.desc().nullslast())
    else:
        jobs_query = jobs_query.order_by(Job.created_at.desc())

    jobs = jobs_query.all()

    # Distinct cities actually in use, for the city filter's suggestions -
    # parsed from the "<work type> - <city>" format post_job.html stores
    # (e.g. "Hybrid - New York, NY"); plain "Remote (Worldwide)"/"On-site"
    # values with no " - " have no city to extract.
    all_locations = {
        loc for (loc,) in Job.query.filter_by(status='open')
        .filter(Job.location.isnot(None)).with_entities(Job.location).distinct().all()
    }
    available_cities = sorted({
        loc.split(' - ', 1)[1].strip() for loc in all_locations if ' - ' in loc
    })

    applied_job_ids = set()
    saved_job_ids = set()
    if current_user.is_authenticated and current_user.role == 'candidate':
        applied_job_ids = {
            a.job_id for a in Application.query.filter_by(
                candidate_user_id=current_user.id, withdrawn=False
            ).with_entities(Application.job_id).all()
        }
        saved_job_ids = {
            s.job_id for s in SavedJob.query.filter_by(user_id=current_user.id).with_entities(SavedJob.job_id).all()
        }

    return render_template(
        "jobs_browse.html",
        jobs=jobs,
        query=query,
        category=category,
        location=location,
        city=city,
        sort=sort,
        categories=JOB_CATEGORIES,
        locations=["Remote (Worldwide)", "Remote (US Only)", "Hybrid", "On-site"],
        available_cities=available_cities,
        applied_job_ids=applied_job_ids,
        saved_job_ids=saved_job_ids,
    )

# Moved from candidate.py: job_detail
@candidate.route('/jobs/<int:job_id>')
def job_detail(job_id):
    job = Job.query.get_or_404(job_id)
    existing = (
        Application.query.filter_by(job_id=job.id, candidate_user_id=current_user.id).first()
        if current_user.is_authenticated else None
    )

    # Compute live rank for this candidate
    rank = None
    total_applicants = 0
    percentile = None
    if existing and not existing.withdrawn and existing.match_score is not None:
        all_apps = (
            Application.query.filter_by(job_id=job.id, withdrawn=False)
            .with_entities(Application.match_score)
            .all()
        )
        scores = sorted([a.match_score or 0 for a in all_apps], reverse=True)
        total_applicants = len(scores)
        my_score = existing.match_score
        rank = next((i + 1 for i, s in enumerate(scores) if s <= my_score), total_applicants)
        percentile = round((total_applicants - rank) / total_applicants * 100) if total_applicants > 1 else 100

    is_saved = (
        SavedJob.query.filter_by(user_id=current_user.id, job_id=job.id).first() is not None
        if current_user.is_authenticated else False
    )

    is_own_posting = False
    if current_user.is_authenticated and current_user.role == 'employer':
        is_owner = job.company.owner_user_id == current_user.id
        is_member = CompanyMember.query.filter_by(company_id=job.company_id, user_id=current_user.id).first() is not None
        is_own_posting = is_owner or is_member

    return render_template("job_detail.html", job=job, existing=existing,
                           rank=rank, total_applicants=total_applicants, percentile=percentile,
                           is_saved=is_saved, is_own_posting=is_own_posting)

# Moved from candidate.py: toggle_save_job
@candidate.route('/jobs/<int:job_id>/save', methods=['POST'])
@login_required
def toggle_save_job(job_id):
    job = Job.query.get_or_404(job_id)
    saved = SavedJob.query.filter_by(user_id=current_user.id, job_id=job.id).first()
    if saved:
        db.session.delete(saved)
        db.session.commit()
        return jsonify({"saved": False})
    db.session.add(SavedJob(user_id=current_user.id, job_id=job.id))
    db.session.commit()
    return jsonify({"saved": True})

# Moved from candidate.py: apply
@candidate.route('/jobs/<int:job_id>/apply', methods=['GET'])
@login_required
def apply(job_id):
    if current_user.role != 'candidate':
        abort(403)
    job = Job.query.get_or_404(job_id)

    existing = Application.query.filter_by(job_id=job.id, candidate_user_id=current_user.id).first()
    if existing:
        flash("You've already applied to this job.", "error")
        return redirect(url_for('candidate.job_detail', job_id=job.id))

    profile = CandidateProfile.query.filter_by(user_id=current_user.id).first()
    saved_resume_text = (profile.resume_text or '').strip() if profile else ''

    return render_template("apply.html", job=job, countries=COUNTRIES, saved_resume_text=saved_resume_text or None)

# Moved from candidate.py: extract_resume_text
@candidate.route('/extract-resume-text', methods=['POST'])
@login_required
@limiter.limit("20 per hour")
def extract_resume_text():
    """Pull text out of an uploaded resume file - used by the apply wizard's
    first step before the candidate moves on to checking their match score."""
    resume_file = request.files.get('resume')
    if not resume_file or not resume_file.filename:
        return jsonify({"error": "No file uploaded."}), 400

    resume_text = extract_text_from_file(resume_file.filename, resume_file.read())
    if not resume_text.strip():
        return jsonify({"error": "Couldn't read that file. Try a different PDF, DOCX, or TXT."}), 400

    return jsonify({"resume_text": resume_text})

# Moved from candidate.py: preview_match
@candidate.route('/jobs/<int:job_id>/preview-match', methods=['POST'])
@login_required
@limiter.limit("20 per hour")
def preview_match(job_id):
    """Score a resume against the job WITHOUT creating an application - lets
    the candidate revise their resume and re-check as many times as they want
    before committing to a submission."""
    job = Job.query.get_or_404(job_id)
    data = request.get_json() or {}
    resume_text = (data.get('resume_text') or '').strip()

    if not resume_text:
        return jsonify({"error": "Add your resume content first."}), 400

    try:
        result = compare_resume_to_job(job.description_text, resume_text)
    except Exception:
        return jsonify({"error": "Failed to score your resume. Please try again."}), 500

    score = _extract_score(result)
    return jsonify({"score": score, "explanation": result.replace('*', '')})

# Moved from candidate.py: submit_application
@candidate.route('/jobs/<int:job_id>/apply', methods=['POST'])
@login_required
@limiter.limit("10 per hour")
def submit_application(job_id):
    if current_user.role != 'candidate':
        abort(403)
    job = Job.query.get_or_404(job_id)

    existing = Application.query.filter_by(job_id=job.id, candidate_user_id=current_user.id).first()
    if existing:
        return jsonify({"error": "You've already applied to this job."}), 400

    data = request.get_json() or {}
    resume_text = (data.get('resume_text') or '').strip()
    work_authorization = data.get('work_authorization')

    if not resume_text:
        return jsonify({"error": "Add your resume content first."}), 400

    try:
        result = compare_resume_to_job(job.description_text, resume_text)
    except Exception as e:
        return jsonify({"error": "Resume analysis failed - please try again."}), 500

    score = _extract_score(result)

    try:
        application = Application(
            job_id=job.id,
            candidate_user_id=current_user.id,
            resume_text=resume_text,
            work_authorization=json.dumps(work_authorization) if work_authorization else None,
            match_score=score,
            match_explanation=result.replace('*', ''),
        )
        db.session.add(application)

        try:
            profile = CandidateProfile.query.filter_by(user_id=current_user.id).first()
            if not profile:
                profile = CandidateProfile(user_id=current_user.id)
                db.session.add(profile)
            profile.resume_text = resume_text
        except Exception:
            db.session.rollback()

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Could not save your application - please try again."}), 500

    return jsonify({
        "redirect_url": url_for('candidate.apply_next_steps', job_id=job.id, application_id=application.id)
    })

# Moved from candidate.py: apply_next_steps
@candidate.route('/jobs/<int:job_id>/apply/<int:application_id>/next')
@login_required
def apply_next_steps(job_id, application_id):
    application = Application.query.get_or_404(application_id)
    if application.candidate_user_id != current_user.id:
        abort(403)
    job = Job.query.get_or_404(job_id)
    return render_template("apply_next_steps.html", job=job, application=application)

