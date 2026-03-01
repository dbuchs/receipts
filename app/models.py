import uuid
import enum
from datetime import datetime, date
from app import db


class ReceiptStatus(enum.Enum):
    imported = 'imported'
    needs_review = 'needs_review'
    matched = 'matched'
    applied = 'applied'


class PatternType(enum.Enum):
    contains = 'contains'
    regex = 'regex'


def _uuid():
    return str(uuid.uuid4())


class Receipt(db.Model):
    __tablename__ = 'receipt'
    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    merchant = db.Column(db.String(100), nullable=True)
    purchase_datetime = db.Column(db.DateTime, nullable=True)
    subtotal = db.Column(db.Integer, default=0)   # cents
    tax = db.Column(db.Integer, default=0)         # cents
    total = db.Column(db.Integer, default=0)       # cents
    currency = db.Column(db.String(3), default='USD')
    source_filename = db.Column(db.String(255))
    stored_path = db.Column(db.String(500))
    extracted_text = db.Column(db.Text)
    parse_confidence = db.Column(db.Float, default=0.0)
    status = db.Column(db.Enum(ReceiptStatus), default=ReceiptStatus.imported)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship('ReceiptItem', backref='receipt', lazy=True, cascade='all, delete-orphan')
    ynab_link = db.relationship('YnabLink', backref='receipt', lazy=True, uselist=False, cascade='all, delete-orphan')
    split_proposals = db.relationship('SplitProposal', backref='receipt', lazy=True, cascade='all, delete-orphan')
    audit_logs = db.relationship('AuditLog', backref='receipt', lazy=True, cascade='all, delete-orphan')

    @property
    def total_dollars(self):
        return self.total / 100.0 if self.total else 0.0

    @property
    def subtotal_dollars(self):
        return self.subtotal / 100.0 if self.subtotal else 0.0

    @property
    def tax_dollars(self):
        return self.tax / 100.0 if self.tax else 0.0


class ReceiptItem(db.Model):
    __tablename__ = 'receipt_item'
    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    receipt_id = db.Column(db.String(36), db.ForeignKey('receipt.id'), nullable=False)
    description_raw = db.Column(db.String(500))
    description_normalized = db.Column(db.String(500))
    quantity = db.Column(db.Float, nullable=True)
    unit_price_cents = db.Column(db.Integer, nullable=True)
    total_price_cents = db.Column(db.Integer, default=0)
    category_suggestion = db.Column(db.String(100), nullable=True)
    rule_hit = db.Column(db.String(100), nullable=True)

    @property
    def total_price_dollars(self):
        return self.total_price_cents / 100.0 if self.total_price_cents else 0.0


class YnabLink(db.Model):
    __tablename__ = 'ynab_link'
    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    receipt_id = db.Column(db.String(36), db.ForeignKey('receipt.id'), nullable=False, unique=True)
    ynab_budget_id = db.Column(db.String(100))
    ynab_account_id = db.Column(db.String(100))
    ynab_transaction_id = db.Column(db.String(100), unique=True)
    matched_amount_cents = db.Column(db.Integer)
    matched_date = db.Column(db.Date, nullable=True)
    match_confidence = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SplitProposal(db.Model):
    __tablename__ = 'split_proposal'
    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    receipt_id = db.Column(db.String(36), db.ForeignKey('receipt.id'), nullable=False)
    ynab_transaction_id = db.Column(db.String(100))
    proposal_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditLog(db.Model):
    __tablename__ = 'audit_log'
    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    action = db.Column(db.String(100))
    receipt_id = db.Column(db.String(36), db.ForeignKey('receipt.id'), nullable=True)
    ynab_transaction_id = db.Column(db.String(100), nullable=True)
    request_json = db.Column(db.Text, nullable=True)
    response_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Rule(db.Model):
    __tablename__ = 'rule'
    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    merchant = db.Column(db.String(100), nullable=True)
    pattern_type = db.Column(db.Enum(PatternType), default=PatternType.contains)
    pattern_value = db.Column(db.String(500))
    suggested_subcategory = db.Column(db.String(100))
    ynab_category_id = db.Column(db.String(100), nullable=True)
    priority = db.Column(db.Integer, default=100)
    enabled = db.Column(db.Boolean, default=True)


class Settings(db.Model):
    __tablename__ = 'settings'
    id = db.Column(db.Integer, primary_key=True)
    ynab_access_token_enc = db.Column(db.Text, nullable=True)
    ynab_refresh_token_enc = db.Column(db.Text, nullable=True)
    ynab_budget_id = db.Column(db.String(100), nullable=True)
    ynab_account_id = db.Column(db.String(100), nullable=True)
    default_currency = db.Column(db.String(3), default='USD')

    @staticmethod
    def get_instance():
        s = Settings.query.first()
        if s is None:
            s = Settings()
            db.session.add(s)
            db.session.commit()
        return s
