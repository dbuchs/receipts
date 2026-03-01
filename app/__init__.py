import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()

def create_app(config_name=None):
    app = Flask(__name__, instance_relative_config=True)
    
    # Load config
    if config_name == 'testing':
        app.config.from_object('app.config.TestingConfig')
    else:
        app.config.from_object('app.config.Config')
    
    # Ensure instance folder exists
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Register blueprints
    from app.receipts.routes import receipts_bp
    from app.rules.routes import rules_bp
    from app.settings.routes import settings_bp
    
    app.register_blueprint(receipts_bp)
    app.register_blueprint(rules_bp)
    app.register_blueprint(settings_bp)
    
    # Dashboard route
    from flask import render_template
    from app.models import Receipt, ReceiptStatus
    
    @app.route('/')
    def dashboard():
        counts = {
            'imported': Receipt.query.filter_by(status=ReceiptStatus.imported).count(),
            'needs_review': Receipt.query.filter_by(status=ReceiptStatus.needs_review).count(),
            'matched': Receipt.query.filter_by(status=ReceiptStatus.matched).count(),
            'applied': Receipt.query.filter_by(status=ReceiptStatus.applied).count(),
        }
        return render_template('dashboard.html', counts=counts)
    
    return app
