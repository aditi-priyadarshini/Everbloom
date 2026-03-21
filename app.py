import os
from flask import Flask, render_template, request
from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv

load_dotenv()

mail   = Mail()
login  = LoginManager()
csrf   = CSRFProtect()


def create_app():
    app = Flask(__name__)

    app.config.update(
        SECRET_KEY          = os.environ.get("SECRET_KEY", "dev-key"),
        MAIL_SERVER         = "smtp.gmail.com",
        MAIL_PORT           = 587,
        MAIL_USE_TLS        = True,
        MAIL_USERNAME       = os.environ.get("MAIL_USERNAME"),
        MAIL_PASSWORD       = os.environ.get("MAIL_PASSWORD"),
        MAIL_DEFAULT_SENDER = os.environ.get("MAIL_SENDER", os.environ.get("MAIL_USERNAME")),
        STORE_NAME          = os.environ.get("STORE_NAME", "Everbloom"),
        SITE_URL            = os.environ.get("SITE_URL", "http://localhost:5000").rstrip("/"),
        UPI_ID              = os.environ.get("UPI_ID", "yourname@upi"),
        QR_URL              = os.environ.get("QR_URL", ""),
        SUPABASE_URL        = os.environ.get("SUPABASE_URL", ""),
        SUPABASE_KEY        = os.environ.get("SUPABASE_KEY", ""),
        SUPABASE_SERVICE_KEY= os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_KEY", "")),
    )

    mail.init_app(app)
    csrf.init_app(app)
    login.init_app(app)
    login.login_view = "auth.login"
    login.login_message = "Please log in to continue."

    from models import User

    @login.user_loader
    def load_user(uid):
        return User.get(int(uid))

    # Blueprints
    from routes.auth   import bp as auth_bp
    from routes.shop   import bp as shop_bp
    from routes.orders import bp as orders_bp
    from routes.admin  import bp as admin_bp

    app.register_blueprint(shop_bp)
    app.register_blueprint(auth_bp,   url_prefix="/auth")
    app.register_blueprint(orders_bp, url_prefix="/orders")
    app.register_blueprint(admin_bp,  url_prefix="/admin")

    @app.context_processor
    def ctx():
        from flask_login import current_user
        from flask import session
        cart = session.get("cart", {})
        return dict(
            store_name   = app.config["STORE_NAME"],
            cart_count   = sum(i["qty"] for i in cart.values()),
            current_user = current_user,
            config       = app.config,
        )

    @app.errorhandler(404)
    def e404(e): return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def e500(e): return render_template("errors/500.html"), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
