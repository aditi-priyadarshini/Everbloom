import os
from flask import Flask

# Keep only Flask itself as a mandatory module-level dependency. Optional Flask
# extensions are imported inside create_app() so a packaging/configuration issue
# produces our diagnostic fallback app instead of an opaque Vercel invocation crash.
mail = None
csrf = None
oauth = None


def create_app():
    global mail, csrf, oauth

    from dotenv import load_dotenv
    load_dotenv()
    from flask_mail import Mail
    from flask_wtf.csrf import CSRFProtect
    from authlib.integrations.flask_client import OAuth

    mail = Mail()
    csrf = CSRFProtect()
    oauth = OAuth()

    app = Flask(
        __name__,
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
        static_url_path="/static",
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
    )
    secret = os.environ.get("SECRET_KEY")
    production = bool(os.environ.get("VERCEL")) or os.environ.get("APP_ENV") == "production"
    if production and (not secret or len(secret) < 32 or secret == "dev-secret-change-me"):
        raise RuntimeError("A strong SECRET_KEY is required in production")

    # Prefer the service-role credential for the migrated/RLS-hardened schema, but
    # preserve compatibility with legacy deployments long enough to boot and show
    # a useful application response. Once migrations 002/010 are applied, the
    # service-role key is required for database access.
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")
    legacy_key = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
    if production and not (service_key or legacy_key):
        raise RuntimeError("A Supabase backend credential is required in production")
    if production and not service_key:
        app.logger.warning(
            "SUPABASE_SERVICE_ROLE_KEY is not configured; using the legacy Supabase key. "
            "Configure the service-role key before applying the RLS-hardened migrations."
        )

    # Shared Redis is recommended on serverless deployments, but absence of Redis
    # must not take the entire storefront offline. memory:// provides per-instance
    # protection as a safe availability fallback until shared storage is configured.
    rate_limit_storage = os.environ.get("RATELIMIT_STORAGE_URI") or "memory://"
    if production and rate_limit_storage == "memory://":
        app.logger.warning(
            "RATELIMIT_STORAGE_URI is not configured; using per-instance memory rate limiting. "
            "Configure shared Redis for distributed production enforcement."
        )

    app.secret_key = secret or __import__('secrets').token_hex(32)

    # Keep users logged in for 15 days
    from datetime import timedelta
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=15)
    app.config["SESSION_COOKIE_SECURE"]   = bool(production)
    app.config["SESSION_COOKIE_HTTPONLY"] = True    # No JS access
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"  # CSRF protection
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 86400
    app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
    app.config["APPLICATION_ROOT"] = "/"
    app.config["PREFERRED_URL_SCHEME"] = "https"

    # Dependency-free health probe. If this returns 200 on Vercel, the Flask
    # runtime and application factory completed successfully.
    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "service": "everbloom"}, 200

    # Zoho Mail SMTP
    mail_user = os.environ.get("MAIL_USERNAME", "")
    mail_pass = os.environ.get("MAIL_PASSWORD", "")
    app.config["MAIL_SERVER"]         = "smtp.zoho.in"
    app.config["MAIL_PORT"]           = 465
    app.config["MAIL_USE_TLS"]        = False
    app.config["MAIL_USE_SSL"]        = True
    app.config["MAIL_USERNAME"]       = mail_user
    app.config["MAIL_PASSWORD"]       = mail_pass
    app.config["MAIL_DEFAULT_SENDER"] = ("Everbloom", mail_user)
    app.config["MAIL_SUPPRESS_SEND"]  = False

    # Rate limiting is a defense-in-depth feature. It must never prevent the
    # storefront from booting on a serverless deployment if the optional
    # extension/storage backend is unavailable.
    limiter = None
    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address
        limiter = Limiter(
            get_remote_address,
            app=app,
            storage_uri=rate_limit_storage,
            default_limits=[],
            swallow_errors=True,
            in_memory_fallback_enabled=True,
        )
    except Exception as exc:
        app.logger.exception("Rate limiter initialization failed; continuing without rate limiting: %s", exc)

    mail.init_app(app)
    csrf.init_app(app)
    oauth.init_app(app)

    # Google OAuth
    oauth.register(
        name="google",
        client_id=os.environ.get("GOOGLE_CLIENT_ID", ""),
        client_secret=os.environ.get("GOOGLE_CLIENT_SECRET", ""),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

    from routes.auth import auth_bp
    from routes.shop import shop_bp
    from routes.orders import orders_bp
    from routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(shop_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(admin_bp)
    from routes.shop import inject_cart
    app.context_processor(inject_cart)

    if limiter is not None:
        for endpoint in ['auth.login','auth.signup','auth.forgot_password','auth.resend_verification','shop.checkout','shop.custom_order','shop.submit_review','shop.newsletter']:
            view = app.view_functions.get(endpoint)
            if view is not None:
                app.view_functions[endpoint] = limiter.limit(
                    '10 per minute; 100 per hour', methods=['POST']
                )(view)

    import models
    app.jinja_env.globals.update(
        discounted_price=models.discounted_price,
        is_flash_active=models.is_flash_active,
        status_index=models.status_index,
        ORDER_STATUSES=models.ORDER_STATUSES,
        STATUS_LABELS=models.STATUS_LABELS,
        SITE_URL=os.environ.get("SITE_URL", "http://localhost:5000"),
        get_setting=models.get_setting,
    )

    from flask import render_template, request, session, abort
    from werkzeug.exceptions import HTTPException
    from services.commerce import availability
    @app.template_filter('phone_digits')
    def phone_digits(value):
        import re
        digits=re.sub(r'\D','',value or '')
        if len(digits)==10: digits='91'+digits
        return digits if 8<=len(digits)<=15 else ''

    app.jinja_env.globals.update(availability=availability, category_name=lambda cid: next((c['name'] for c in getattr(__import__('flask').g, 'nav_categories', []) if str(c['id']) == str(cid)), 'Handmade'))

    @app.errorhandler(Exception)
    def safe_error(error):
        code = error.code if isinstance(error, HTTPException) else 500
        if code == 500:
            app.logger.exception("Request failed")
        return render_template('errors/error.html', code=code), code

    @app.before_request
    def guard_admin():
        if request.path.startswith('/admin'):
            user = models.get_user_by_id(session['user_id']) if session.get('user_id') else None
            if not user or not user.get('is_admin'):
                abort(403)

    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        if production:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        if request.path.startswith(('/admin','/orders','/checkout','/auth')):
            response.headers['Cache-Control'] = 'no-store'
        return response

    return app


# Vercel requires a TOP-LEVEL WSGI variable named `app` (or `application`).
# Do not hide that assignment inside try/except: Vercel's build-time entrypoint
# detector will otherwise reject the deployment before Python is invoked.
def _build_wsgi_app():
    try:
        return create_app()
    except Exception as startup_error:
        import logging
        logging.exception("Everbloom failed during application startup")

        fallback_app = Flask(__name__)
        fallback_app.config["STARTUP_ERROR"] = (
            f"{type(startup_error).__name__}: {startup_error}"
        )

        @fallback_app.route("/", defaults={"path": ""})
        @fallback_app.route("/<path:path>")
        def startup_failure(path):
            from flask import Response
            message = (
                "Everbloom could not start.\n\n"
                + fallback_app.config["STARTUP_ERROR"]
                + "\n\nCheck the Vercel environment variables and function logs, then redeploy."
            )
            return Response(message, status=503, mimetype="text/plain")

        return fallback_app


# These assignments MUST remain at module scope for Vercel Python detection.
app = _build_wsgi_app()
application = app


if __name__ == "__main__":
    app.run(debug=True)
