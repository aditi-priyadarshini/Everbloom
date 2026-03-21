from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import Order, Tracking, Notification, STATUSES, STATUS_KEYS, STATUS_LABELS, STATUS_ICONS
import supa, time

bp = Blueprint("orders", __name__)
ALLOWED = {"png", "jpg", "jpeg", "webp", "gif"}


@bp.route("/")
@login_required
def my_orders():
    orders = Order.for_customer(current_user.id)
    for o in orders:
        o["items"] = Order.items(o["id"])
    return render_template("shop/orders.html", orders=orders,
                           STATUS_LABELS=STATUS_LABELS, STATUS_ICONS=STATUS_ICONS, STATUS_KEYS=STATUS_KEYS)


@bp.route("/<int:oid>/track")
@login_required
def track(oid):
    o = Order.get_for_customer(oid, current_user.id)
    if not o: flash("Order not found.", "error"); return redirect(url_for("orders.my_orders"))
    events    = Tracking.for_order(oid)
    items     = Order.items(oid)
    event_map = {e["status"]: e for e in events}
    return render_template("shop/track.html", o=o, events=events, items=items,
                           event_map=event_map, STATUSES=STATUSES,
                           STATUS_LABELS=STATUS_LABELS, STATUS_ICONS=STATUS_ICONS, STATUS_KEYS=STATUS_KEYS)


@bp.route("/<int:oid>/pay-advance", methods=["GET", "POST"])
@login_required
def pay_advance(oid):
    o = Order.get_for_customer(oid, current_user.id)
    if not o or o["status"] != "advance_requested":
        flash("No advance payment required right now.", "info")
        return redirect(url_for("orders.track", oid=oid))
    if request.method == "POST":
        f = request.files.get("proof")
        if not f or not f.filename:
            flash("Please select a payment screenshot.", "error")
            return render_template("shop/pay_advance.html", o=o)
        ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
        if ext not in ALLOWED:
            flash("Please upload an image file (JPG, PNG, etc.)", "error")
            return render_template("shop/pay_advance.html", o=o)
        url = supa.upload_image(f, "payment-proofs", f"{oid}/advance_{int(time.time())}")
        if not url:
            flash("Upload failed. Please try again.", "error")
            return render_template("shop/pay_advance.html", o=o)
        Order.set_advance_proof(oid, url)
        Tracking.add(oid, "advance_paid", "Customer uploaded payment screenshot.")
        Notification.add(current_user.id, oid, "Screenshot Uploaded 💳",
                         "Payment screenshot submitted. We'll confirm shortly!")
        flash("Screenshot uploaded! We'll confirm your payment soon.", "success")
        return redirect(url_for("orders.track", oid=oid))
    return render_template("shop/pay_advance.html", o=o)
