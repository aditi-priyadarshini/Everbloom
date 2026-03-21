from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from models import User
from emails import mail_welcome

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("shop.home"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        pw    = request.form.get("password", "")
        user  = User.by_email(email)
        if user and user.check_password(pw):
            login_user(user, remember=bool(request.form.get("remember")))
            return redirect(url_for("shop.home"))
        flash("Invalid email or password.", "error")
    return render_template("auth/login.html")


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("shop.home"))
    if request.method == "POST":
        name    = request.form.get("full_name", "").strip()
        email   = request.form.get("email", "").strip().lower()
        phone   = request.form.get("phone", "").strip()
        pw      = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        if not name or not email or not pw:
            flash("Please fill in all required fields.", "error")
        elif len(pw) < 8:
            flash("Password must be at least 8 characters.", "error")
        elif pw != confirm:
            flash("Passwords do not match.", "error")
        elif User.by_email(email):
            flash("An account with this email already exists.", "error")
        else:
            uid = User.create(name, email, phone, pw)
            if uid:
                login_user(User.get(uid))
                try: mail_welcome(name, email)
                except: pass
                flash("Welcome to Everbloom! 🌿", "success")
                return redirect(url_for("shop.home"))
    return render_template("auth/signup.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.pop("cart", None)
    return redirect(url_for("shop.home"))


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        User.update(
            current_user.id,
            request.form.get("full_name", "").strip() or current_user.full_name,
            request.form.get("phone", "").strip(),
            request.form.get("address", "").strip(),
        )
        flash("Profile updated.", "success")
        return redirect(url_for("auth.profile"))
    return render_template("auth/profile.html")
