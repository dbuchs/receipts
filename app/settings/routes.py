from flask import Blueprint, render_template, request, redirect, url_for, flash
from app import db
from app.models import Settings
from app.receipts.service import encrypt_token, _decrypt_token

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')


@settings_bp.route('/', methods=['GET', 'POST'])
def index():
    settings = Settings.get_instance()
    if request.method == 'POST':
        settings.ynab_budget_id = request.form.get('ynab_budget_id') or None
        settings.ynab_account_id = request.form.get('ynab_account_id') or None
        settings.default_currency = request.form.get('default_currency', 'USD')

        token = request.form.get('ynab_access_token', '').strip()
        if token:
            settings.ynab_access_token_enc = encrypt_token(token)

        db.session.commit()
        flash('Settings saved.', 'success')
        return redirect(url_for('settings.index'))

    # Decrypt for display (show masked)
    token_set = bool(settings.ynab_access_token_enc)
    return render_template('settings/index.html', settings=settings, token_set=token_set)
