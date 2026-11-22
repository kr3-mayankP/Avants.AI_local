"""Routes moved from admin.py."""

from .admin import (
    Application,
    Company,
    CompanyInvite,
    CompanyMember,
    ContractorProfile,
    DeletedJob,
    EarnTask,
    EmployerSubscription,
    Job,
    MeetingProposal,
    MeetingRoom,
    Message,
    Referral,
    SavedJob,
    TaskSubmission,
    User,
    _cascade_delete_jobs,
    _require_admin,
    admin_bp,
    db,
    flash,
    json,
    login_required,
    redirect,
    render_template,
    request,
    url_for,
)

# Moved from admin.py: dashboard
@admin_bp.route('/admin')
@login_required
def dashboard():
    _require_admin()
    tasks = EarnTask.query.order_by(EarnTask.created_at.desc()).all()
    total_submissions = TaskSubmission.query.count()
    total_paid = db.session.query(db.func.sum(TaskSubmission.earnings_cents))\
        .filter_by(paid_out=False).scalar() or 0

    platform_stats = {
        "total_users": User.query.count(),
        "total_candidates": User.query.filter_by(role='candidate').count(),
        "total_employers": User.query.filter_by(role='employer').count(),
        "total_companies": Company.query.count(),
        "total_jobs": Job.query.count(),
        "total_applications": Application.query.count(),
        "total_interviews": Application.query.filter(Application.interview_verdict.isnot(None)).count(),
    }

    return render_template('admin_dashboard.html',
        tasks=tasks,
        total_submissions=total_submissions,
        total_pending_payout=total_paid,
        platform_stats=platform_stats,
    )

# Moved from admin.py: companies
@admin_bp.route('/admin/companies')
@login_required
def companies():
    _require_admin()
    all_companies = Company.query.order_by(Company.created_at.desc()).all()
    owner_ids = [c.owner_user_id for c in all_companies]
    owners = {u.id: u for u in User.query.filter(User.id.in_(owner_ids)).all()} if owner_ids else {}
    job_counts = dict(
        db.session.query(Job.company_id, db.func.count(Job.id)).group_by(Job.company_id).all()
    )
    member_counts = dict(
        db.session.query(CompanyMember.company_id, db.func.count(CompanyMember.id))
        .group_by(CompanyMember.company_id).all()
    )
    return render_template('admin_companies.html',
        companies=all_companies, owners=owners, job_counts=job_counts, member_counts=member_counts)

# Moved from admin.py: company_detail
@admin_bp.route('/admin/companies/<int:company_id>')
@login_required
def company_detail(company_id):
    _require_admin()
    company = Company.query.get_or_404(company_id)
    owner = User.query.get(company.owner_user_id)
    members = (
        db.session.query(User, CompanyMember)
        .join(CompanyMember, CompanyMember.user_id == User.id)
        .filter(CompanyMember.company_id == company_id)
        .all()
    )
    jobs = Job.query.filter_by(company_id=company_id).order_by(Job.created_at.desc()).all()
    application_counts = dict(
        db.session.query(Application.job_id, db.func.count(Application.id))
        .filter(Application.job_id.in_([j.id for j in jobs]))
        .group_by(Application.job_id).all()
    ) if jobs else {}
    deleted_jobs = (
        DeletedJob.query
        .filter_by(company_id=company_id, restored_job_id=None)
        .order_by(DeletedJob.created_at.desc())
        .all()
    )

    # Flag any member whose email has another account under a different
    # case (e.g. the case-sensitivity bug fixed in auth.py) - lets the admin
    # spot and clean these up right from this page.
    duplicate_ids = set()
    for user, _ in members:
        if User.query.filter(db.func.lower(User.email) == user.email.lower(), User.id != user.id).first():
            duplicate_ids.add(user.id)

    return render_template('admin_company_detail.html',
        company=company, owner=owner, members=members, jobs=jobs, application_counts=application_counts,
        deleted_jobs=deleted_jobs, duplicate_ids=duplicate_ids)

# Moved from admin.py: delete_job
@admin_bp.route('/admin/jobs/<int:job_id>/delete', methods=['POST'])
@login_required
def delete_job(job_id):
    """Admin override of employer.delete_job() - that route refuses to delete
    a job once it has applicants (pushing the employer to close it instead,
    to preserve candidate history). This force-deletes it and everything
    under it: applications, meeting rooms, messages, feedback."""
    _require_admin()
    job = Job.query.get_or_404(job_id)
    company_id = job.company_id
    title = job.title
    applicant_count = Application.query.filter_by(job_id=job.id).count()

    _cascade_delete_jobs([job.id])
    db.session.commit()

    suffix = f" and {applicant_count} application{'s' if applicant_count != 1 else ''}" if applicant_count else ""
    flash(f'Deleted "{title}"{suffix}.', 'success')
    return redirect(url_for('admin_bp.company_detail', company_id=company_id))

# Moved from admin.py: restore_job
@admin_bp.route('/admin/deleted-jobs/<int:history_id>/restore', methods=['POST'])
@login_required
def restore_job(history_id):
    """Recreates the job listing from its DeletedJob snapshot. Note this only
    brings back the listing itself - applications/messages/videos that were
    cascade-deleted alongside it are gone for good."""
    _require_admin()
    entry = DeletedJob.query.get_or_404(history_id)
    if entry.restored_job_id:
        flash("That job was already restored.", "error")
        return redirect(url_for('admin_bp.company_detail', company_id=entry.company_id))
    if not Company.query.get(entry.company_id):
        flash("Can't restore - the company this job belonged to was also deleted.", "error")
        return redirect(url_for('admin_bp.companies'))

    data = json.loads(entry.snapshot)
    job = Job(company_id=entry.company_id, **data)
    db.session.add(job)
    db.session.flush()
    entry.restored_job_id = job.id
    db.session.commit()
    flash(f'"{job.title}" restored.', 'success')
    return redirect(url_for('admin_bp.company_detail', company_id=entry.company_id))

# Moved from admin.py: remove_member
@admin_bp.route('/admin/companies/<int:company_id>/members/<int:user_id>/remove', methods=['POST'])
@login_required
def remove_member(company_id, user_id):
    """Removes a CompanyMember (team member) from a company. Can't touch the
    owner this way - ownership isn't a CompanyMember row, it's Company.owner_user_id."""
    _require_admin()
    Company.query.get_or_404(company_id)
    member = CompanyMember.query.filter_by(company_id=company_id, user_id=user_id).first_or_404()
    db.session.delete(member)
    db.session.commit()
    flash("Member removed.", "success")
    return redirect(url_for('admin_bp.company_detail', company_id=company_id))

# Moved from admin.py: set_company_owner
@admin_bp.route('/admin/companies/<int:company_id>/set-owner', methods=['POST'])
@login_required
def set_company_owner(company_id):
    """Transfers ownership of a company to a different existing user -
    admin-only, since ownership controls billing, who can invite/remove team
    members, and who signed the Employer Platform Agreement. There's no
    self-serve way to do this otherwise (owner_user_id is only ever set once,
    at company creation). The previous owner is kept on as a regular team
    member rather than losing access outright."""
    _require_admin()
    company = Company.query.get_or_404(company_id)

    email = (request.form.get('email') or '').strip().lower()
    if not email:
        flash("Enter an email address.", "error")
        return redirect(url_for('admin_bp.company_detail', company_id=company_id))

    new_owner = User.query.filter(db.func.lower(User.email) == email).first()
    if not new_owner:
        flash(f"No account found for {email}.", "error")
        return redirect(url_for('admin_bp.company_detail', company_id=company_id))

    if new_owner.id == company.owner_user_id:
        flash(f"{new_owner.email} already owns this company.", "error")
        return redirect(url_for('admin_bp.company_detail', company_id=company_id))

    old_owner_id = company.owner_user_id

    # The owner is tracked exclusively via Company.owner_user_id, never also
    # as a CompanyMember - drop any existing membership row for the incoming
    # owner so they're not double-counted.
    CompanyMember.query.filter_by(company_id=company.id, user_id=new_owner.id).delete()

    new_owner.role = 'employer'
    company.owner_user_id = new_owner.id

    if not CompanyMember.query.filter_by(company_id=company.id, user_id=old_owner_id).first():
        db.session.add(CompanyMember(company_id=company.id, user_id=old_owner_id))

    db.session.commit()
    flash(f"{new_owner.email} is now the owner of {company.name}. The previous owner was kept on as a team member.", "success")
    return redirect(url_for('admin_bp.company_detail', company_id=company_id))

# Moved from admin.py: delete_duplicate_user
@admin_bp.route('/admin/users/<int:user_id>/delete-duplicate', methods=['POST'])
@login_required
def delete_duplicate_user(user_id):
    """Deletes a User row that is a confirmed duplicate of another account
    with the same email (case-insensitive) - e.g. left over from the
    case-sensitivity bug fixed in auth.py, where a mismatched-case lookup
    created a second, disconnected account instead of matching the first.
    Refuses unless there's a sibling account with the same email AND this
    row has zero data anywhere else in the app, so it can never silently
    discard someone's real applications, profile, or history."""
    _require_admin()
    user = User.query.get_or_404(user_id)

    sibling = User.query.filter(
        db.func.lower(User.email) == user.email.lower(), User.id != user.id
    ).first()
    if not sibling:
        flash(f"No other account shares {user.email} - not a confirmed duplicate, refusing to delete.", "error")
        return redirect(request.referrer or url_for('admin_bp.dashboard'))

    from .models import CandidateProfile

    blockers = []
    if Company.query.filter_by(owner_user_id=user.id).first():
        blockers.append("owns a company")
    if CandidateProfile.query.filter_by(user_id=user.id).first():
        blockers.append("has a candidate profile")
    if Application.query.filter_by(candidate_user_id=user.id).first():
        blockers.append("has applications")
    if SavedJob.query.filter_by(user_id=user.id).first():
        blockers.append("has saved jobs")
    if Referral.query.filter_by(referrer_user_id=user.id).first():
        blockers.append("has referrals made")
    if Referral.query.filter_by(referred_user_id=user.id).first():
        blockers.append("was referred by someone")
    if TaskSubmission.query.filter_by(user_id=user.id).first():
        blockers.append("has Earn task submissions")
    if ContractorProfile.query.filter_by(user_id=user.id).first():
        blockers.append("has a contractor profile")
    if MeetingProposal.query.filter_by(employer_user_id=user.id).first():
        blockers.append("has meeting proposals")
    if Message.query.filter_by(sender_user_id=user.id).first():
        blockers.append("has sent messages")
    if MeetingRoom.query.filter_by(employer_user_id=user.id).first():
        blockers.append("has meeting rooms")
    if CompanyInvite.query.filter_by(invited_by_user_id=user.id).first():
        blockers.append("sent invites")
    if DeletedJob.query.filter_by(deleted_by_user_id=user.id).first():
        blockers.append("deleted a job")
    if User.query.filter_by(referred_by_user_id=user.id).first():
        blockers.append("referred other users")

    if blockers:
        flash(f"Refusing to delete {user.email} - this account {', '.join(blockers)}. Not a clean duplicate.", "error")
        return redirect(request.referrer or url_for('admin_bp.dashboard'))

    CompanyMember.query.filter_by(user_id=user.id).delete()
    from .models import Notification
    Notification.query.filter_by(user_id=user.id).delete()
    email = user.email
    db.session.delete(user)
    db.session.commit()

    flash(f"Deleted duplicate account {email} (id={user_id}).", "success")
    return redirect(request.referrer or url_for('admin_bp.dashboard'))

# Moved from admin.py: add_member
@admin_bp.route('/admin/companies/<int:company_id>/members/add', methods=['POST'])
@login_required
def add_member(company_id):
    """Adds an existing user to a company as a team member, promoting them to
    role='employer' first if they signed up as a candidate. Exists because
    there's no self-serve way for a candidate account to become an employer
    once the email is already registered - e.g. someone at a company that
    already has a hub picked 'candidate' at signup by mistake."""
    _require_admin()
    company = Company.query.get_or_404(company_id)

    email = (request.form.get('email') or '').strip().lower()
    if not email:
        flash("Enter an email address.", "error")
        return redirect(url_for('admin_bp.company_detail', company_id=company_id))

    user = User.query.filter(db.func.lower(User.email) == email).first()
    if not user:
        flash(f"No account found for {email}.", "error")
        return redirect(url_for('admin_bp.company_detail', company_id=company_id))

    if user.id == company.owner_user_id:
        flash(f"{user.email} already owns this company.", "error")
        return redirect(url_for('admin_bp.company_detail', company_id=company_id))

    if CompanyMember.query.filter_by(company_id=company.id, user_id=user.id).first():
        flash(f"{user.email} is already a team member.", "error")
        return redirect(url_for('admin_bp.company_detail', company_id=company_id))

    if user.role != 'employer':
        user.role = 'employer'

    db.session.add(CompanyMember(company_id=company.id, user_id=user.id))
    CompanyInvite.query.filter_by(company_id=company.id, email=email, used=False).update({"used": True})
    db.session.commit()

    flash(f"{user.email} added to {company.name}.", "success")
    return redirect(url_for('admin_bp.company_detail', company_id=company_id))

# Moved from admin.py: delete_company
@admin_bp.route('/admin/companies/<int:company_id>/delete', methods=['POST'])
@login_required
def delete_company(company_id):
    """Full cascade delete - every job, application, meeting, message,
    feedback entry, team membership, subscription, and pending invite under
    this company. The owner's User account itself is untouched (Company.
    owner_user_id points at User, not the reverse). Requires typing the
    exact company name to confirm, given the blast radius."""
    _require_admin()
    company = Company.query.get_or_404(company_id)

    confirm_name = (request.form.get('confirm_name') or '').strip()
    if confirm_name != company.name:
        flash("Company name didn't match what you typed - nothing was deleted.", "error")
        return redirect(url_for('admin_bp.company_detail', company_id=company_id))

    job_ids = [j.id for j in Job.query.filter_by(company_id=company.id).all()]
    _cascade_delete_jobs(job_ids)
    CompanyMember.query.filter_by(company_id=company.id).delete(synchronize_session=False)
    EmployerSubscription.query.filter_by(company_id=company.id).delete(synchronize_session=False)
    CompanyInvite.query.filter_by(company_id=company.id).delete(synchronize_session=False)

    name = company.name
    db.session.delete(company)
    db.session.commit()
    flash(f'Deleted company "{name}" and everything under it.', 'success')
    return redirect(url_for('admin_bp.companies'))

