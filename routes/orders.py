from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import Order, Tracking, Notification, STATUS_KEYS, STATUS_LABELS, STATUS_ICONS, ORDER_STATUSES
import storage

orders_bp = Blueprint("orders", __name__)

ALLOWED = {"png", "jpg", "jpeg", "webp", "gif"}


@orders_bp.route("/")
@login_required
def my_orders():
    orders = Order.list_for_customer(current_user.id)
    # Attach items summary per order
    for o in orders:
        o["items"] = Order.items(o["id"])
    return render_template("shop/orders.html", orders=orders,
                           STATUS_LABELS=STATUS_LABELS, STATUS_ICONS=STATUS_ICONS,
                           STATUS_KEYS=STATUS_KEYS)


@orders_bp.route("/<int:order_id>/track")
@login_required
def track(order_id):
    order = Order.get_for_customer(order_id, current_user.id)
    if not order:
        flash("Order not found.", "error")
        return redirect(url_for("orders.my_orders"))
    events   = Tracking.list(order_id)
    items    = Order.items(order_id)
    event_map = {e["status"]: e for e in events}
    return render_template("shop/track.html",
                           order=order, events=events, items=items,
                           event_map=event_map,
                           STATUS_KEYS=STATUS_KEYS, STATUS_LABELS=STATUS_LABELS,
                           STATUS_ICONS=STATUS_ICONS, ORDER_STATUSES=ORDER_STATUSES)


@orders_bp.route("/<int:order_id>/pay-advance", methods=["GET", "POST"])
@login_required
def pay_advance(order_id):
    order = Order.get_for_customer(order_id, current_user.id)
    if not order or order["status"] != "advance_requested":
        flash("No advance payment is required for this order right now.", "info")
        return redirect(url_for("orders.track", order_id=order_id))

    if request.method == "POST":
        file = request.files.get("proof")
        if not file or not file.filename:
            flash("Please upload your payment screenshot.", "error")
            return render_template("shop/pay_advance.html", order=order)
        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext not in ALLOWED:
            flash("Please upload a valid image (JPG, PNG, etc.)", "error")
            return render_template("shop/pay_advance.html", order=order)

        # Upload to Supabase Storage
        proof_url = storage.upload_payment_proof(file, order_id, "advance")
        if not proof_url:
            flash("Upload failed. Please try again.", "error")
            return render_template("shop/pay_advance.html", order=order)

        Order.set_advance_proof(order_id, proof_url)
        Tracking.add(order_id, "advance_paid",
                     "Customer uploaded advance payment screenshot. Awaiting admin confirmation.",
                     current_user.id)
        Notification.add(current_user.id, order_id,
                         "Payment Screenshot Uploaded 💳",
                         "Your advance screenshot has been submitted. We'll confirm shortly.")
        flash("Payment screenshot uploaded! We'll confirm it shortly.", "success")
        return redirect(url_for("orders.track", order_id=order_id))

    return render_template("shop/pay_advance.html", order=order)
