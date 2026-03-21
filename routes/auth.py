from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import models
import emails

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("auth.login", next=request.url))
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


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("shop.index"))
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = models.get_user_by_email(email)
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = str(user["id"])
            session["user_name"] = user.get("name", "")
            session["is_admin"] = user.get("is_admin", False)
            next_url = request.args.get("next")
            return redirect(next_url if next_url else url_for("shop.index"))
        error = "Invalid email or password."
    return render_template("auth/login.html", error=error)


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if session.get("user_id"):
        return redirect(url_for("shop.index"))
    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if models.get_user_by_email(email):
            error = "An account with this email already exists."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        else:
            pw_hash = generate_password_hash(password, method="pbkdf2:sha256")
            user = models.create_user(email, pw_hash, name)
            if user:
                session["user_id"] = str(user["id"])
                session["user_name"] = user.get("name", "")
                session["is_admin"] = False
                emails.send_welcome(email, name)
                return redirect(url_for("shop.index"))
            error = "Could not create account. Please try again."
    return render_template("auth/signup.html", error=error)


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("shop.index"))


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = models.get_user_by_id(session["user_id"])
    success = None
    if request.method == "POST":
        data = {
            "name": request.form.get("name", "").strip(),
            "phone": request.form.get("phone", "").strip(),
            "address": request.form.get("address", "").strip(),
        }
        models.update_user(session["user_id"], data)
        session["user_name"] = data["name"]
        success = "Profile updated!"
        user = models.get_user_by_id(session["user_id"])
    return render_template("auth/profile.html", user=user, success=success)
