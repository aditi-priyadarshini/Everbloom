from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import models
import supa
import uuid
from routes.auth import login_required

orders_bp = Blueprint("orders", __name__, url_prefix="/orders")

BUCKET = "everbloom"


@orders_bp.route("/")
@login_required
def orders_list():
    orders = models.get_orders(user_id=session["user_id"])
    # Also fetch this user's custom requests that haven't been converted yet
    all_custom = models.get_custom_requests()
    custom_requests = [r for r in all_custom
                       if str(r.get("user_id", "")) == session["user_id"]
                       and r.get("status") not in ("accepted", "rejected")]
    return render_template("shop/orders.html", orders=orders, custom_requests=custom_requests)


@orders_bp.route("/<oid>")
@login_required
def order_detail(oid):
    order = models.get_order(oid)
    if not order or str(order["user_id"]) != session["user_id"]:
        flash("Order not found.", "error")
        return redirect(url_for("orders.orders_list"))
    items = models.get_order_items(oid)
    tracking = models.get_tracking(oid)
    return render_template("shop/order_detail.html",
                           order=order, items=items, tracking=tracking)


@orders_bp.route("/<oid>/track")
@login_required
def track(oid):
    order = models.get_order(oid)
    if not order or str(order["user_id"]) != session["user_id"]:
        flash("Order not found.", "error")
        return redirect(url_for("orders.orders_list"))
    tracking = models.get_tracking(oid)
    return render_template("shop/track.html", order=order, tracking=tracking)


@orders_bp.route("/<oid>/pay-advance", methods=["GET", "POST"])
@login_required
def pay_advance(oid):
    order = models.get_order(oid)
    if not order or str(order["user_id"]) != session["user_id"]:
        flash("Order not found.", "error")
        return redirect(url_for("orders.orders_list"))
    if order["status"] != "advance_requested":
        flash("No advance payment required at this time.", "info")
        return redirect(url_for("orders.order_detail", oid=oid))

    upi_id = models.get_setting("upi_id")
    upi_qr_url = models.get_setting("upi_qr_url")

    if request.method == "POST":
        screenshot = request.files.get("screenshot")
        if screenshot and screenshot.filename:
            safe_name = screenshot.filename.replace(" ", "_")
            path = f"payments/{uuid.uuid4()}-{safe_name}"
            url = supa.upload_file(BUCKET, path, screenshot.read(),
                                   screenshot.content_type or "image/jpeg")
            if url:
                models.update_order(oid, {
                    "payment_screenshot_url": url,
                    "status": "advance_paid"
                })
                models.add_tracking(oid, "advance_paid",
                                    "Customer uploaded payment screenshot.")
                models.create_notification(
                    session["user_id"],
                    "Payment screenshot uploaded. Awaiting confirmation.",
                    url_for("orders.order_detail", oid=oid)
                )
                flash("Screenshot uploaded! We'll confirm your payment shortly.", "success")
                return redirect(url_for("orders.order_detail", oid=oid))
            else:
                flash("Upload failed — check Supabase Storage bucket 'everbloom' exists and is Public.", "error")
        else:
            flash("Please select a screenshot to upload.", "error")

    return render_template("shop/pay_advance.html",
                           order=order, upi_id=upi_id, upi_qr_url=upi_qr_url)
