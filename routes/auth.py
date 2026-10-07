import os
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import models
import emails
import secrets

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("auth.login", next=request.full_path))
        return f(*args, **kwargs)
    return decorated


def admin_only(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Admin access required.", "error")
            return redirect(url_for("shop.index"))
        return f(*args, **kwargs)
    return decorated


# ── Signup ────────────────────────────────────────────────

@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if session.get("user_id"):
        return redirect(url_for("shop.index"))
    error = None
    if request.method == "POST":
        name  = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if models.get_user_by_email(email):
            flash("If registration is available for this email, check your inbox for the next step.", "success")
            return redirect(url_for("auth.login"))
        elif len(password) < 10:
            error = "Password must be at least 10 characters."
        else:
            pw_hash = generate_password_hash(password, method="pbkdf2:sha256")
            user = models.create_user(email, pw_hash, name)
            if user:
                # Send verification email
                token = models.create_auth_token(user["id"], "verify_email", hours=24)
                site_url = os.environ.get("SITE_URL", "http://localhost:5000").rstrip("/")
                verify_url = f"{site_url}/auth/verify-email/{token}"
                emails.send_verify_email(email, name, verify_url)
                flash("Account created! Please check your email to verify your account before logging in.", "success")
                return redirect(url_for("auth.login"))
            error = "Could not create account. Check your Supabase connection."
    return render_template("auth/signup.html", error=error)


# ── Verify Email ──────────────────────────────────────────

@auth_bp.route("/verify-email/<token>")
def verify_email(token):
    t = models.get_auth_token(token, "verify_email")
    if not t:
        flash("This verification link is invalid or has expired. Please sign up again or request a new link.", "error")
        return redirect(url_for("auth.signup"))
    models.verify_user_email(t["user_id"])
    models.use_auth_token(t["id"])
    flash("Email verified! You can now log in.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/resend-verification", methods=["GET", "POST"])
def resend_verification():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = models.get_user_by_email(email)
        if user and not user.get("email_verified"):
            token = models.create_auth_token(user["id"], "verify_email", hours=24)
            site_url = os.environ.get("SITE_URL", "http://localhost:5000").rstrip("/")
            verify_url = f"{site_url}/auth/verify-email/{token}"
            emails.send_verify_email(email, user.get("name", ""), verify_url)
        # Always show success to prevent email enumeration
        flash("If that email exists and is unverified, we've sent a new verification link.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/resend_verification.html")


# ── Login ─────────────────────────────────────────────────

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("shop.index"))
    error = None
    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = models.get_user_by_email(email)
        if user and user.get("password_hash") and check_password_hash(user["password_hash"], password):
            # Block unverified users (skip check for admins)
            if not user.get("email_verified") and not user.get("is_admin"):
                flash("Please verify your email before logging in. "
                      "Check your inbox or ", "error")
                return render_template("auth/login.html",
                                       error=None,
                                       show_resend=True,
                                       resend_email=email)
            session.permanent = True   # use PERMANENT_SESSION_LIFETIME (15 days)
            session["user_id"]   = str(user["id"])
            session["user_name"] = user.get("name", "")
            session["is_admin"]  = user.get("is_admin", False)
            next_url = request.args.get("next")
            return redirect(safe_next(next_url))
        error = "Invalid email or password."
    return render_template("auth/login.html", error=error, show_resend=False)


# ── Forgot Password ───────────────────────────────────────

@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user  = models.get_user_by_email(email)
        if user:
            token = models.create_auth_token(user["id"], "reset_password", hours=1)
            site_url = os.environ.get("SITE_URL", "http://localhost:5000").rstrip("/")
            reset_url = f"{site_url}/auth/reset-password/{token}"
            emails.send_password_reset(email, user.get("name", ""), reset_url)
        # Always success to prevent email enumeration
        flash("If that email is registered, you'll receive a password reset link shortly.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot_password.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    t = models.get_auth_token(token, "reset_password")
    if not t:
        flash("This reset link is invalid or has expired. Please request a new one.", "error")
        return redirect(url_for("auth.forgot_password"))
    error = None
    if request.method == "POST":
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm_password", "")
        if len(password) < 6:
            error = "Password must be at least 10 characters."
        elif password != confirm:
            error = "Passwords do not match."
        else:
            pw_hash = generate_password_hash(password, method="pbkdf2:sha256")
            models.update_user(t["user_id"], {"password_hash": pw_hash})
            models.use_auth_token(t["id"])
            flash("Password reset successfully! Please log in.", "success")
            return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html", token=token, error=error)


# ── Google OAuth ─────────────────────────────────────────

@auth_bp.route("/google/login")
def google_login():
    from app import oauth
    redirect_uri = url_for("auth.google_callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route("/google/callback")
def google_callback():
    from app import oauth
    try:
        token = oauth.google.authorize_access_token()
        user_info = token.get("userinfo")
        if not user_info:
            flash("Google sign-in failed. Please try again.", "error")
            return redirect(url_for("auth.login"))

        email = user_info.get("email", "").lower()
        name  = user_info.get("name", "")

        if not email or not user_info.get("email_verified"):
            flash("Could not verify your email with Google.", "error")
            return redirect(url_for("auth.login"))

        # Find or create user
        user = models.get_user_by_email(email)
        if not user:
            # Create account — random password since they use Google
            pw_hash = generate_password_hash(secrets.token_urlsafe(32), method="pbkdf2:sha256")
            user = models.create_user(email, pw_hash, name)
            if user:
                models.verify_user_email(user["id"])  # auto-verified via Google
                try:
                    emails.send_welcome(email, name)
                except Exception:
                    pass

        if not user:
            flash("Could not create account. Please try again.", "error")
            return redirect(url_for("auth.login"))

        session.permanent = True
        session["user_id"]   = str(user["id"])
        session["user_name"] = user.get("name") or name
        session["is_admin"]  = user.get("is_admin", False)

        # Mark as verified if not already
        if not user.get("email_verified"):
            models.verify_user_email(user["id"])

        flash(f"Welcome, {session['user_name']}!", "success")
        next_url = request.args.get("next")
        return redirect(safe_next(next_url))

    except Exception as e:
        import sys
        print(f"[Google OAuth error] {type(e).__name__}", file=sys.stderr)
        flash("Google sign-in failed. Please try again or use email.", "error")
        return redirect(url_for("auth.login"))


# ── Logout ────────────────────────────────────────────────

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("shop.index"))


# ── Profile ───────────────────────────────────────────────

@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = models.get_user_by_id(session["user_id"])
    success = None
    if request.method == "POST":
        data = {
            "name":    request.form.get("name", "").strip(),
            "phone":   request.form.get("phone", "").strip(),
            "address": request.form.get("address", "").strip(),
        }
        models.update_user(session["user_id"], data)
        session["user_name"] = data["name"]
        success = "Profile updated!"
        user = models.get_user_by_id(session["user_id"])
    return render_template("auth/profile.html", user=user, success=success)


def safe_next(target):
    from urllib.parse import urlsplit
    if target and target.startswith('/') and not target.startswith('//') and not urlsplit(target).netloc and '\\' not in target:
        return target
    return url_for('shop.index')
