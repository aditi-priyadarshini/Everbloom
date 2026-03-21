import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)

    # ── Config ────────────────────────────────────────────────────
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-me')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///everbloom.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Mail
    app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'Everbloom <noreply@everbloom.store>')

    # Uploads
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, os.environ.get('UPLOAD_FOLDER', 'static/uploads'))
    app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_CONTENT_LENGTH', 5 * 1024 * 1024))

    # Store info (accessible in templates)
    app.config['STORE_NAME'] = os.environ.get('STORE_NAME', 'Everbloom')
    app.config['SITE_URL'] = os.environ.get('SITE_URL', 'http://localhost:5000')
    app.config['UPI_ID'] = os.environ.get('UPI_ID', 'yourname@upi')
    app.config['ADMIN_EMAIL'] = os.environ.get('ADMIN_EMAIL', '')

    # ── Ensure upload dirs exist ───────────────────────────────────
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'products'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'payments'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'qr'), exist_ok=True)

    # ── Extensions ────────────────────────────────────────────────
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to continue.'
    login_manager.login_message_category = 'info'

    # ── Blueprints ────────────────────────────────────────────────
    from routes.shop import shop_bp
    from routes.auth import auth_bp
    from routes.admin import admin_bp
    from routes.orders import orders_bp

    app.register_blueprint(shop_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(orders_bp, url_prefix='/orders')

    # ── Template globals ──────────────────────────────────────────
    @app.context_processor
    def inject_globals():
        from flask_login import current_user
        from flask import session
        cart = session.get('cart', {})
        cart_count = sum(item['qty'] for item in cart.values())
        return dict(
            store_name=app.config['STORE_NAME'],
            cart_count=cart_count,
            current_user=current_user,
        )

    # ── Error handlers ────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        from flask import render_template
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        from flask import render_template
        return render_template('errors/500.html'), 500

    # ── Create DB tables ──────────────────────────────────────────
    with app.app_context():
        db.create_all()
        _seed_categories()

    return app


def _seed_categories():
    from models import Category
    if Category.query.count() == 0:
        cats = [
            Category(name='Paintings',  slug='paintings',  icon='🎨', description='Original hand-painted artworks'),
            Category(name='Pottery',    slug='pottery',    icon='🏺', description='Handcrafted clay and ceramic pieces'),
            Category(name='Jewelry',    slug='jewelry',    icon='💍', description='Artisan-made jewelry and accessories'),
            Category(name='DIY Kits',   slug='diy-kits',   icon='🧰', description='Complete craft kits for home creation'),
            Category(name='Textiles',   slug='textiles',   icon='🧵', description='Handwoven and embroidered fabrics'),
            Category(name='Sculptures', slug='sculptures', icon='🗿', description='Three-dimensional art pieces'),
        ]
        db.session.add_all(cats)
        db.session.commit()


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
