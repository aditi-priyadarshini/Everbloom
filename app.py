"""
app.py — Flask application factory.
Vercel runs this file directly via @vercel/python.
"""
import os
from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv

load_dotenv()

from emails import mail

login_manager = LoginManager()
csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)

    # ── Config ────────────────────────────────────────────────
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    # Mail
    app.config["MAIL_SERVER"]         = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    app.config["MAIL_PORT"]           = int(os.environ.get("MAIL_PORT", 587))
    app.config["MAIL_USE_TLS"]        = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    app.config["MAIL_USERNAME"]       = os.environ.get("MAIL_USERNAME")
    app.config["MAIL_PASSWORD"]       = os.environ.get("MAIL_PASSWORD")
    app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_DEFAULT_SENDER", "Everbloom <noreply@everbloom.store>")

    # Store
    app.config["STORE_NAME"] = os.environ.get("STORE_NAME", "Everbloom")
    app.config["SITE_URL"]   = os.environ.get("SITE_URL", "http://localhost:5000").rstrip("/")
    app.config["UPI_ID"]     = os.environ.get("UPI_ID", "yourname@upi")

    # ── Extensions ────────────────────────────────────────────
    mail.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to continue."
    login_manager.login_message_category = "info"

    # ── User loader ───────────────────────────────────────────
    from models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.get(int(user_id))

    # ── Blueprints ────────────────────────────────────────────
    from routes.shop   import shop_bp
    from routes.auth   import auth_bp
    from routes.admin  import admin_bp
    from routes.orders import orders_bp

    app.register_blueprint(shop_bp)
    app.register_blueprint(auth_bp,    url_prefix="/auth")
    app.register_blueprint(admin_bp,   url_prefix="/admin")
    app.register_blueprint(orders_bp,  url_prefix="/orders")

    # ── Context processors ────────────────────────────────────
    @app.context_processor
    def globals():
        from flask_login import current_user
        from flask import session
        cart = session.get("cart", {})
        cart_count = sum(i["qty"] for i in cart.values())
        return dict(
            store_name=app.config["STORE_NAME"],
            cart_count=cart_count,
            current_user=current_user,
            config=app.config,
        )

    # ── Error handlers ────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        from flask import render_template
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        from flask import render_template
        return render_template("errors/500.html"), 500

    # ── DB init route (hit once after deploy) ─────────────────
    @app.route("/_init")
    def init_db_route():
        """
        GET /_init  — creates all tables and seeds categories.
        Protect this in production by checking a secret header or deleting after first use.
        """
        secret = request_secret()
        if secret and secret != os.environ.get("INIT_SECRET", ""):
            from flask import abort
            abort(403)
        from db import init_db
        init_db()
        return "✓ Database initialised", 200

    return app


def request_secret():
    from flask import request
    return request.args.get("secret") or request.headers.get("X-Init-Secret")


# ── Vercel entrypoint ─────────────────────────────────────────────────────────
app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
