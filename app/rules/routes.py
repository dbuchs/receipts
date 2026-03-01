from flask import Blueprint, render_template, request, redirect, url_for, flash
from app import db
from app.models import Rule, PatternType
from app.rules.service import test_rule

rules_bp = Blueprint('rules', __name__, url_prefix='/rules')


@rules_bp.route('/')
def list_rules():
    rules = Rule.query.order_by(Rule.priority).all()
    return render_template('rules/list.html', rules=rules)


@rules_bp.route('/new', methods=['GET', 'POST'])
def new_rule():
    if request.method == 'POST':
        rule = Rule(
            merchant=request.form.get('merchant') or None,
            pattern_type=PatternType[request.form.get('pattern_type', 'contains')],
            pattern_value=request.form.get('pattern_value', ''),
            suggested_subcategory=request.form.get('suggested_subcategory', ''),
            ynab_category_id=request.form.get('ynab_category_id') or None,
            priority=int(request.form.get('priority', 100)),
            enabled=bool(request.form.get('enabled')),
        )
        db.session.add(rule)
        db.session.commit()
        flash('Rule created.', 'success')
        return redirect(url_for('rules.list_rules'))
    return render_template('rules/form.html', rule=None, action='New')


@rules_bp.route('/<rule_id>/edit', methods=['GET', 'POST'])
def edit_rule(rule_id):
    rule = Rule.query.get_or_404(rule_id)
    if request.method == 'POST':
        rule.merchant = request.form.get('merchant') or None
        rule.pattern_type = PatternType[request.form.get('pattern_type', 'contains')]
        rule.pattern_value = request.form.get('pattern_value', '')
        rule.suggested_subcategory = request.form.get('suggested_subcategory', '')
        rule.ynab_category_id = request.form.get('ynab_category_id') or None
        rule.priority = int(request.form.get('priority', 100))
        rule.enabled = bool(request.form.get('enabled'))
        db.session.commit()
        flash('Rule updated.', 'success')
        return redirect(url_for('rules.list_rules'))
    return render_template('rules/form.html', rule=rule, action='Edit')


@rules_bp.route('/<rule_id>/delete', methods=['POST'])
def delete_rule(rule_id):
    rule = Rule.query.get_or_404(rule_id)
    db.session.delete(rule)
    db.session.commit()
    flash('Rule deleted.', 'success')
    return redirect(url_for('rules.list_rules'))


@rules_bp.route('/test', methods=['POST'])
def test_rule_endpoint():
    pattern_type = request.form.get('pattern_type', 'contains')
    pattern_value = request.form.get('pattern_value', '')
    test_text = request.form.get('test_text', '')
    rule = Rule(
        pattern_type=PatternType[pattern_type],
        pattern_value=pattern_value,
        suggested_subcategory='',
    )
    matched = test_rule(rule, test_text)
    return {'matched': matched}
