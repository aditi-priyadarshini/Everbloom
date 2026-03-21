import os
from flask import Flask
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect

mail = Mail()
csrf = CSRFProtect()


def create_app():
    app = Flask(
        __name__,
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
        static_url_path="/static",
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
    )
    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
    app.config["APPLICATION_ROOT"] = "/"
    app.config["PREFERRED_URL_SCHEME"] = "https"

    # Zoho Mail SMTP
    mail_user = os.environ.get("MAIL_USERNAME", "")
    mail_pass = os.environ.get("MAIL_PASSWORD", "")
    app.config["MAIL_SERVER"]         = "smtp.zoho.com"
    app.config["MAIL_PORT"]           = 465
    app.config["MAIL_USE_TLS"]        = False
    app.config["MAIL_USE_SSL"]        = True
    app.config["MAIL_USERNAME"]       = mail_user
    app.config["MAIL_PASSWORD"]       = mail_pass
    app.config["MAIL_DEFAULT_SENDER"] = ("Everbloom", mail_user)
    app.config["MAIL_SUPPRESS_SEND"]  = False

    mail.init_app(app)
    csrf.init_app(app)

    from routes.auth import auth_bp
    from routes.shop import shop_bp
    from routes.orders import orders_bp
    from routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(shop_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(admin_bp)

    import models
    app.jinja_env.globals.update(
        discounted_price=models.discounted_price,
        is_flash_active=models.is_flash_active,
        status_index=models.status_index,
        ORDER_STATUSES=models.ORDER_STATUSES,
        STATUS_LABELS=models.STATUS_LABELS,
        SITE_URL=os.environ.get("SITE_URL", "http://localhost:5000"),
    )

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
