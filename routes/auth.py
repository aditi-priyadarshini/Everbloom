from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from models import User
from emails import send_welcome

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("shop.home"))
    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))
        user = User.get_by_email(email)
        if user and user.check_password(password):
            login_user(user, remember=remember)
            nxt = request.args.get("next")
            return redirect(nxt or url_for("shop.home"))
        flash("Invalid email or password.", "error")
    return render_template("auth/login.html")


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("shop.home"))
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email     = request.form.get("email", "").strip().lower()
        phone     = request.form.get("phone", "").strip()
        password  = request.form.get("password", "")
        confirm   = request.form.get("confirm_password", "")
        if not all([full_name, email, password]):
            flash("Please fill in all required fields.", "error")
        elif len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        elif User.get_by_email(email):
            flash("An account with this email already exists.", "error")
        else:
            uid = User.create(full_name, email, phone, password)
            if uid:
                user = User.get(uid)
                login_user(user)
                try:
                    send_welcome({"full_name": full_name, "email": email})
                except Exception:
                    pass
                flash("Account created! Welcome to Everbloom 🌸", "success")
                return redirect(url_for("shop.home"))
    return render_template("auth/signup.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.pop("cart", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("shop.home"))


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        User.update_profile(
            current_user.id,
            request.form.get("full_name", "").strip() or current_user.full_name,
            request.form.get("phone", "").strip(),
            request.form.get("address", "").strip(),
        )
        flash("Profile updated.", "success")
        return redirect(url_for("auth.profile"))
    return render_template("auth/profile.html")
