import os
import json
import re
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import current_app

from app import db
from app.models import Receipt, ReceiptItem, ReceiptStatus, Settings, YnabLink, SplitProposal, AuditLog, Rule, PatternType
from app.receipts.parsing import extract_text
from app.parsers import detect_parser
from app.ynab_client import YnabClient, find_matching_transactions


def allowed_file(filename: str) -> bool:
    allowed = current_app.config.get('ALLOWED_EXTENSIONS', {'pdf', 'html', 'htm', 'txt'})
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


def import_receipt_file(file_storage) -> Receipt:
    """Store file, extract text, parse, save to DB."""
    filename = secure_filename(file_storage.filename)
    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)

    # Add UUID prefix to avoid collisions
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    file_path = os.path.join(upload_folder, unique_name)
    file_storage.save(file_path)

    text = extract_text(file_path, filename)
    parser, confidence = detect_parser(text, filename)
    parsed = parser.parse(text, filename)

    status = ReceiptStatus.imported
    if parsed.confidence < 0.4:
        status = ReceiptStatus.needs_review

    receipt = Receipt(
        merchant=parsed.merchant,
        purchase_datetime=parsed.purchase_datetime,
        subtotal=parsed.subtotal,
        tax=parsed.tax,
        total=parsed.total,
        currency=parsed.currency,
        source_filename=filename,
        stored_path=file_path,
        extracted_text=text,
        parse_confidence=parsed.confidence,
        status=status,
    )
    db.session.add(receipt)
    db.session.flush()  # get receipt.id

    for item in parsed.items:
        ri = ReceiptItem(
            receipt_id=receipt.id,
            description_raw=item.description_raw,
            description_normalized=item.description_normalized,
            quantity=item.quantity,
            unit_price_cents=item.unit_price_cents,
            total_price_cents=item.total_price_cents,
        )
        db.session.add(ri)

    db.session.commit()

    # Apply rules to items
    apply_rules_to_receipt(receipt)

    return receipt


def apply_rules_to_receipt(receipt: Receipt):
    """Apply categorization rules to all items of a receipt."""
    rules = Rule.query.filter_by(enabled=True).order_by(Rule.priority).all()
    for item in receipt.items:
        for rule in rules:
            if rule.merchant and rule.merchant.lower() not in (receipt.merchant or '').lower():
                continue
            desc = item.description_normalized or item.description_raw or ''
            matched = False
            if rule.pattern_type == PatternType.contains:
                matched = rule.pattern_value.lower() in desc.lower()
            elif rule.pattern_type == PatternType.regex:
                try:
                    matched = bool(re.search(rule.pattern_value, desc, re.IGNORECASE))
                except re.error:
                    pass
            if matched:
                item.category_suggestion = rule.suggested_subcategory
                item.rule_hit = rule.pattern_value
                break
    db.session.commit()


def get_ynab_candidates(receipt: Receipt):
    """Fetch YNAB transactions and return top matches for this receipt."""
    settings = Settings.get_instance()
    if not settings.ynab_budget_id:
        return []
    token = _decrypt_token(settings.ynab_access_token_enc)
    if not token:
        return []
    client = YnabClient(token)
    since_date = None
    if receipt.purchase_datetime:
        from datetime import timedelta
        d = receipt.purchase_datetime.date() - timedelta(days=7)
        since_date = d.isoformat()
    try:
        transactions = client.get_transactions(
            settings.ynab_budget_id,
            settings.ynab_account_id,
            since_date=since_date,
        )
    except Exception:
        return []
    return find_matching_transactions(receipt, transactions)


def build_split_proposal(receipt: Receipt):
    """Build a split proposal from receipt items grouped by category."""
    groups = {}
    for item in receipt.items:
        cat = item.category_suggestion or 'Uncategorized'
        if cat not in groups:
            groups[cat] = {'category': cat, 'amount_cents': 0, 'items': []}
        groups[cat]['amount_cents'] += item.total_price_cents
        groups[cat]['items'].append(item.description_normalized or item.description_raw)

    splits = list(groups.values())
    total = sum(s['amount_cents'] for s in splits)

    # Adjust for tax/rounding: add to last group
    if splits and receipt.total and total != receipt.total:
        splits[-1]['amount_cents'] += (receipt.total - total)

    return splits


def apply_split_to_ynab(receipt: Receipt, split_lines: list, ynab_transaction_id: str):
    """Apply split to YNAB. Returns (success, response_json)."""
    settings = Settings.get_instance()
    token = _decrypt_token(settings.ynab_access_token_enc)
    client = YnabClient(token)

    # Build subtransactions
    subtransactions = []
    for line in split_lines:
        subtransactions.append({
            'amount': -(line['amount_cents'] * 10),  # YNAB milliunits, negative for outflow
            'memo': line.get('category', ''),
            'category_id': line.get('ynab_category_id'),
        })

    request_data = {'subtransactions': subtransactions}
    request_json = json.dumps(request_data)

    try:
        resp = client.update_transaction(settings.ynab_budget_id, ynab_transaction_id, request_data)
        response_json = json.dumps(resp)
        success = True
    except Exception as e:
        response_json = json.dumps({'error': str(e)})
        success = False

    audit = AuditLog(
        action='YNAB_SPLIT_APPLIED',
        receipt_id=receipt.id,
        ynab_transaction_id=ynab_transaction_id,
        request_json=request_json,
        response_json=response_json,
    )
    db.session.add(audit)

    if success:
        receipt.status = ReceiptStatus.applied

    db.session.commit()
    return success, response_json


def _decrypt_token(enc_token: str) -> str:
    """Decrypt a stored token. Returns plaintext or empty string."""
    if not enc_token:
        return ''
    enc_key = current_app.config.get('ENCRYPTION_KEY', '')
    if not enc_key:
        return enc_token  # store as plaintext if no key configured
    try:
        from cryptography.fernet import Fernet
        f = Fernet(enc_key.encode() if isinstance(enc_key, str) else enc_key)
        return f.decrypt(enc_token.encode()).decode()
    except Exception:
        return enc_token


def encrypt_token(plaintext: str) -> str:
    """Encrypt a token for storage."""
    if not plaintext:
        return ''
    enc_key = current_app.config.get('ENCRYPTION_KEY', '')
    if not enc_key:
        return plaintext
    try:
        from cryptography.fernet import Fernet
        f = Fernet(enc_key.encode() if isinstance(enc_key, str) else enc_key)
        return f.encrypt(plaintext.encode()).decode()
    except Exception:
        return plaintext
