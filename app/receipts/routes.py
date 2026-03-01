import json
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, current_app, abort)
from app import db
from app.models import Receipt, ReceiptStatus, YnabLink, SplitProposal
from app.receipts.service import (import_receipt_file, allowed_file,
                                   get_ynab_candidates, build_split_proposal,
                                   apply_split_to_ynab)

receipts_bp = Blueprint('receipts', __name__, url_prefix='/receipts')


@receipts_bp.route('/')
def list_receipts():
    status_filter = request.args.get('status')
    merchant_filter = request.args.get('merchant')
    query = Receipt.query.order_by(Receipt.created_at.desc())
    if status_filter:
        try:
            query = query.filter_by(status=ReceiptStatus[status_filter])
        except KeyError:
            pass
    if merchant_filter:
        query = query.filter(Receipt.merchant.ilike(f'%{merchant_filter}%'))
    receipts = query.all()
    return render_template('receipts/list.html', receipts=receipts,
                           status_filter=status_filter, merchant_filter=merchant_filter)


@receipts_bp.route('/import', methods=['GET', 'POST'])
def import_receipts():
    if request.method == 'POST':
        files = request.files.getlist('files')
        if not files or all(f.filename == '' for f in files):
            flash('No files selected.', 'warning')
            return redirect(request.url)

        imported = 0
        errors = []
        for f in files:
            if f.filename == '':
                continue
            if not allowed_file(f.filename):
                errors.append(f'{f.filename}: unsupported file type')
                continue
            try:
                import_receipt_file(f)
                imported += 1
            except Exception as e:
                errors.append(f'{f.filename}: {e}')

        if imported:
            flash(f'Successfully imported {imported} receipt(s).', 'success')
        for err in errors:
            flash(err, 'danger')
        return redirect(url_for('receipts.list_receipts'))

    return render_template('receipts/import.html')


@receipts_bp.route('/<receipt_id>')
def receipt_detail(receipt_id):
    receipt = Receipt.query.get_or_404(receipt_id)
    return render_template('receipts/detail.html', receipt=receipt)


@receipts_bp.route('/<receipt_id>/match', methods=['GET', 'POST'])
def match_receipt(receipt_id):
    receipt = Receipt.query.get_or_404(receipt_id)
    if request.method == 'POST':
        ynab_txn_id = request.form.get('ynab_transaction_id')
        if not ynab_txn_id:
            flash('No transaction selected.', 'warning')
            return redirect(request.url)
        
        if ynab_txn_id == 'no_match':
            receipt.status = ReceiptStatus.needs_review
            db.session.commit()
            flash('Marked as no match.', 'info')
            return redirect(url_for('receipts.receipt_detail', receipt_id=receipt_id))

        # Check for duplicate
        existing = YnabLink.query.filter_by(ynab_transaction_id=ynab_txn_id).first()
        if existing and existing.receipt_id != receipt_id:
            flash('This YNAB transaction is already linked to another receipt.', 'danger')
            return redirect(request.url)

        # Save/update link
        link = YnabLink.query.filter_by(receipt_id=receipt_id).first()
        if not link:
            link = YnabLink(receipt_id=receipt_id)
            db.session.add(link)

        from app.models import Settings
        settings = Settings.get_instance()
        link.ynab_budget_id = settings.ynab_budget_id
        link.ynab_account_id = settings.ynab_account_id
        link.ynab_transaction_id = ynab_txn_id

        # Store amount/date from form
        amount_str = request.form.get('matched_amount_cents')
        if amount_str:
            link.matched_amount_cents = int(amount_str)
        date_str = request.form.get('matched_date')
        if date_str:
            from datetime import date
            try:
                link.matched_date = date.fromisoformat(date_str)
            except ValueError:
                pass
        confidence_str = request.form.get('match_confidence')
        if confidence_str:
            link.match_confidence = float(confidence_str)

        receipt.status = ReceiptStatus.matched
        db.session.commit()
        flash('Transaction matched!', 'success')
        return redirect(url_for('receipts.propose_split', receipt_id=receipt_id))

    candidates = get_ynab_candidates(receipt)
    return render_template('receipts/match.html', receipt=receipt, candidates=candidates)


@receipts_bp.route('/<receipt_id>/propose-split', methods=['GET', 'POST'])
def propose_split(receipt_id):
    receipt = Receipt.query.get_or_404(receipt_id)
    link = YnabLink.query.filter_by(receipt_id=receipt_id).first()
    if not link:
        flash('Please match a YNAB transaction first.', 'warning')
        return redirect(url_for('receipts.match_receipt', receipt_id=receipt_id))

    if request.method == 'POST':
        # User submitted edited splits
        split_data = []
        categories = request.form.getlist('category[]')
        amounts = request.form.getlist('amount_dollars[]')
        ynab_cats = request.form.getlist('ynab_category_id[]')
        for i, cat in enumerate(categories):
            try:
                amount_cents = int(float(amounts[i]) * 100)
            except (ValueError, IndexError):
                amount_cents = 0
            split_data.append({
                'category': cat,
                'amount_cents': amount_cents,
                'ynab_category_id': ynab_cats[i] if i < len(ynab_cats) else None,
            })

        proposal = SplitProposal.query.filter_by(receipt_id=receipt_id).first()
        if not proposal:
            proposal = SplitProposal(receipt_id=receipt_id)
            db.session.add(proposal)
        proposal.ynab_transaction_id = link.ynab_transaction_id
        proposal.proposal_json = json.dumps(split_data)
        db.session.commit()
        return redirect(url_for('receipts.confirm_split', receipt_id=receipt_id))

    splits = build_split_proposal(receipt)
    return render_template('receipts/propose_split.html', receipt=receipt, splits=splits, link=link)


@receipts_bp.route('/<receipt_id>/confirm', methods=['GET', 'POST'])
def confirm_split(receipt_id):
    receipt = Receipt.query.get_or_404(receipt_id)
    proposal = SplitProposal.query.filter_by(receipt_id=receipt_id).first()
    if not proposal:
        flash('No split proposal found.', 'warning')
        return redirect(url_for('receipts.propose_split', receipt_id=receipt_id))

    splits = json.loads(proposal.proposal_json) if proposal.proposal_json else []
    link = YnabLink.query.filter_by(receipt_id=receipt_id).first()

    if request.method == 'POST':
        success, resp = apply_split_to_ynab(receipt, splits, proposal.ynab_transaction_id)
        if success:
            flash('Split applied to YNAB successfully!', 'success')
            return redirect(url_for('receipts.receipt_detail', receipt_id=receipt_id))
        else:
            flash(f'Failed to apply split: {resp}', 'danger')

    return render_template('receipts/confirm.html', receipt=receipt, splits=splits,
                           proposal=proposal, link=link)
