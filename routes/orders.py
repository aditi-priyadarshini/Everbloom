from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import models
import supa
import uuid
from routes.auth import login_required

orders_bp = Blueprint("orders", __name__, url_prefix="/orders")


@orders_bp.route("/")
@login_required
def orders_list():
    orders = models.get_orders(user_id=session["user_id"])
    return render_template("shop/orders.html", orders=orders)


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


@orders_bp.route("/<oid>/detail")
@login_required
def order_detail(oid):
    order = models.get_order(oid)
    if not order or str(order["user_id"]) != session["user_id"]:
        flash("Order not found.", "error")
        return redirect(url_for("orders.orders_list"))
    items = models.get_order_items(oid)
    return render_template("shop/order_detail.html", order=order, items=items)


@orders_bp.route("/<oid>/return", methods=["GET", "POST"])
@login_required
def request_return(oid):
    order = models.get_order(oid)
    if not order or str(order["user_id"]) != session["user_id"]:
        flash("Order not found.", "error")
        return redirect(url_for("orders.orders_list"))
    if order["status"] != "delivered":
        flash("Returns are only available for delivered orders.", "info")
        return redirect(url_for("orders.order_detail", oid=oid))

    if request.method == "POST":
        image_url = None
        img = request.files.get("image")
        if img and img.filename:
            path = f"returns/{uuid.uuid4()}-{img.filename}"
            image_url = supa.upload_file("products", path, img.read(), img.content_type)
        models.create_return({
            "order_id": oid,
            "user_id": session["user_id"],
            "reason": request.form.get("reason", ""),
            "description": request.form.get("description", ""),
            "image_url": image_url,
        })
        flash("Return request submitted. We'll review it shortly.", "success")
        return redirect(url_for("orders.order_detail", oid=oid))

    return render_template("shop/return_request.html", order=order)
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
            path = f"payments/{uuid.uuid4()}-{screenshot.filename}"
            url = supa.upload_file("products", path, screenshot.read(), screenshot.content_type)
            if url:
                models.update_order(oid, {"payment_screenshot_url": url, "status": "advance_paid"})
                models.add_tracking(oid, "advance_paid", "Customer uploaded payment screenshot.")
                models.create_notification(session["user_id"],
                                           "Payment screenshot uploaded. Awaiting confirmation.",
                                           url_for("orders.order_detail", oid=oid))
                flash("Screenshot uploaded! We'll confirm your payment shortly.", "success")
                return redirect(url_for("orders.order_detail", oid=oid))
        flash("Please upload a screenshot.", "error")

    return render_template("shop/pay_advance.html",
                           order=order, upi_id=upi_id, upi_qr_url=upi_qr_url)
