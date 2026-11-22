"""Routes moved from admin.py."""

from .admin import (
    ContractorProfile,
    EARN_DOMAINS,
    EarnTask,
    Feedback,
    FeedbackInsight,
    Referral,
    Response,
    TaskSubmission,
    User,
    _require_admin,
    admin_bp,
    analyze_platform_feedback,
    current_app,
    db,
    flash,
    json,
    logger,
    login_required,
    redirect,
    render_template,
    request,
    shape_submission,
    stripe,
    url_for,
)

# Moved from admin.py: feedback
@admin_bp.route('/admin/feedback')
@login_required
def feedback():
    _require_admin()
    entries = Feedback.query.order_by(Feedback.created_at.desc()).all()
    avg_rating = round(sum(f.rating for f in entries) / len(entries), 1) if entries else None
    latest_insight = FeedbackInsight.query.order_by(FeedbackInsight.generated_at.desc()).first()
    recommendations = json.loads(latest_insight.recommendations) if latest_insight and latest_insight.recommendations else []
    return render_template('admin_feedback.html',
        entries=entries, avg_rating=avg_rating, insight=latest_insight, recommendations=recommendations)

# Moved from admin.py: analyze_feedback
@admin_bp.route('/admin/feedback/analyze', methods=['POST'])
@login_required
def analyze_feedback():
    _require_admin()
    entries = Feedback.query.order_by(Feedback.created_at.desc()).limit(200).all()
    if not entries:
        flash("No feedback to analyze yet.", "error")
        return redirect(url_for('admin_bp.feedback'))

    rows = [{"role": f.role, "context": f.context, "rating": f.rating, "comment": f.comment} for f in entries]
    try:
        result = analyze_platform_feedback(rows)
    except Exception as e:
        logger.exception("Feedback analysis failed")
        flash(f"AI analysis failed: {e}", "error")
        return redirect(url_for('admin_bp.feedback'))

    insight = FeedbackInsight(
        summary=result["summary"],
        recommendations=json.dumps(result["recommendations"]),
        feedback_count=len(entries),
    )
    db.session.add(insight)
    db.session.commit()
    flash("Feedback analyzed.", "success")
    return redirect(url_for('admin_bp.feedback'))

# Moved from admin.py: create_task
@admin_bp.route('/admin/tasks/new', methods=['GET', 'POST'])
@login_required
def create_task():
    _require_admin()
    if request.method == 'POST':
        task_type = request.form.get('task_type', 'ranking')
        selected_domains = request.form.getlist('required_domains')
        valid_domains = [d for d in selected_domains if d in EARN_DOMAINS]
        try:
            min_responses = max(1, int(request.form.get('min_responses', 3)))
        except (ValueError, TypeError):
            min_responses = 3
        task = EarnTask(
            title=request.form.get('title', '').strip(),
            description=request.form.get('description', '').strip(),
            task_type=task_type,
            domain=request.form.get('domain', '').strip() or None,
            required_domains=json.dumps(valid_domains) if valid_domains else None,
            min_responses=min_responses,
            pay_cents=int(float(request.form.get('pay_dollars', '5')) * 100),
            estimated_minutes=int(request.form.get('estimated_minutes', 5)),
            option_a=request.form.get('option_a', '').strip() or None,
            option_b=request.form.get('option_b', '').strip() or None,
            content=request.form.get('content', '').strip() or None,
            status='open',
        )
        db.session.add(task)
        db.session.commit()
        flash("Task created.", "success")
        return redirect(url_for('admin_bp.dashboard'))
    return render_template('admin_task_form.html', earn_domains=EARN_DOMAINS)

# Moved from admin.py: close_task
@admin_bp.route('/admin/tasks/<int:task_id>/close', methods=['POST'])
@login_required
def close_task(task_id):
    _require_admin()
    task = EarnTask.query.get_or_404(task_id)
    task.status = 'closed'
    db.session.commit()
    flash("Task closed.", "success")
    return redirect(url_for('admin_bp.dashboard'))

# Moved from admin.py: export_task
@admin_bp.route('/admin/tasks/<int:task_id>/export')
@login_required
def export_task(task_id):
    _require_admin()
    task = EarnTask.query.get_or_404(task_id)
    submissions = TaskSubmission.query.filter_by(task_id=task_id).all()

    lines = []
    for sub in submissions:
        record = shape_submission(task, sub)
        if record:
            lines.append(json.dumps(record))

    output = "\n".join(lines)
    filename = f"task_{task_id}_{task.task_type}.jsonl"
    return Response(
        output,
        mimetype="application/x-ndjson",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

# Moved from admin.py: task_submissions
@admin_bp.route('/admin/tasks/<int:task_id>')
@login_required
def task_submissions(task_id):
    _require_admin()
    task = EarnTask.query.get_or_404(task_id)
    submissions = TaskSubmission.query.filter_by(task_id=task_id)\
        .order_by(TaskSubmission.created_at.desc()).all()
    consensus = json.loads(task.consensus_answer) if task.consensus_answer else None
    return render_template('admin_task_submissions.html',
        task=task, submissions=submissions, consensus=consensus)

# Moved from admin.py: payouts
@admin_bp.route('/admin/payouts')
@login_required
def payouts():
    _require_admin()
    rows = (
        db.session.query(User, ContractorProfile,
                         db.func.sum(TaskSubmission.earnings_cents).label('pending_cents'))
        .join(TaskSubmission, TaskSubmission.user_id == User.id)
        .outerjoin(ContractorProfile, ContractorProfile.user_id == User.id)
        .filter(TaskSubmission.paid_out == False)
        .group_by(User.id, ContractorProfile.id)
        .having(db.func.sum(TaskSubmission.earnings_cents) > 0)
        .all()
    )
    total_pending = sum(r.pending_cents for r in rows)
    return render_template('admin_payouts.html', rows=rows, total_pending=total_pending)

# Moved from admin.py: pay_user
@admin_bp.route('/admin/payouts/pay/<int:user_id>', methods=['POST'])
@login_required
def pay_user(user_id):
    _require_admin()
    stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
    if not stripe.api_key:
        flash("Stripe is not configured.", "error")
        return redirect(url_for('admin_bp.payouts'))

    contractor = ContractorProfile.query.filter_by(user_id=user_id).first_or_404()
    if not contractor.stripe_account_id or not contractor.payout_enabled:
        flash("This worker hasn't completed Stripe payout setup.", "error")
        return redirect(url_for('admin_bp.payouts'))

    unpaid = TaskSubmission.query.filter_by(user_id=user_id, paid_out=False).all()
    amount = sum(s.earnings_cents for s in unpaid)

    if amount < 50:   # Stripe minimum is $0.50
        flash("Pending amount is below the $0.50 minimum transfer threshold.", "error")
        return redirect(url_for('admin_bp.payouts'))

    try:
        stripe.Transfer.create(
            amount=amount,
            currency='usd',
            destination=contractor.stripe_account_id,
            idempotency_key=f"payout_user_{user_id}_batch_{sum(s.id for s in unpaid)}",
        )
        for sub in unpaid:
            sub.paid_out = True
        db.session.commit()
        #new change: display the contractor's combined name in payout notices.
        worker_name = contractor.user.full_name or contractor.user.email
        flash(f"Paid ${amount / 100:.2f} to {worker_name}.", "success")
    except stripe.error.StripeError as e:
        logger.exception("Stripe transfer failed for user %s", user_id)
        flash(f"Transfer failed: {e.user_message}", "error")

    return redirect(url_for('admin_bp.payouts'))

# Moved from admin.py: referrals
@admin_bp.route('/admin/referrals')
@login_required
def referrals():
    _require_admin()
    rows = (
        Referral.query
        .filter_by(status='owed')
        .order_by(Referral.created_at.desc())
        .all()
    )
    paid_rows = (
        Referral.query
        .filter_by(status='paid')
        .order_by(Referral.paid_at.desc())
        .limit(50)
        .all()
    )
    total_owed = sum(r.commission_usd for r in rows)
    return render_template('admin_referrals.html', rows=rows, paid_rows=paid_rows, total_owed=total_owed)

# Moved from admin.py: mark_referral_paid
@admin_bp.route('/admin/referrals/<int:referral_id>/mark-paid', methods=['POST'])
@login_required
def mark_referral_paid(referral_id):
    _require_admin()
    referral = Referral.query.get_or_404(referral_id)
    referral.status = 'paid'
    referral.paid_at = db.func.now()
    db.session.commit()
    #new change: display the referrer's combined name in the admin confirmation.
    flash(f"Marked ${referral.commission_usd:,} referral payout to {referral.referrer.full_name or referral.referrer.email} as paid.", "success")
    return redirect(url_for('admin_bp.referrals'))

