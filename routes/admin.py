from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
import models
import supa
import uuid
import os
from routes.auth import admin_only

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ── Dashboard ─────────────────────────────────────────────

@admin_bp.route("/")
@admin_only
def dashboard():
    stats = models.get_stats()
    recent_orders = models.get_orders(limit=10)
    return render_template("admin/dashboard.html", stats=stats, recent_orders=recent_orders)


# ── Orders ────────────────────────────────────────────────

@admin_bp.route("/orders")
@admin_only
def orders():
    status = request.args.get("status", "")
    if status:
        order_list = models.get_orders(status=status)
    else:
        order_list = models.get_orders()
    return render_template("admin/orders.html", orders=order_list,
                           selected_status=status,
                           statuses=models.ORDER_STATUSES,
                           status_labels=models.STATUS_LABELS)


@admin_bp.route("/orders/<oid>", methods=["GET", "POST"])
@admin_only
def order_detail(oid):
    order = models.get_order(oid)
    if not order:
        flash("Order not found.", "error")
        return redirect(url_for("admin.orders"))
    items = models.get_order_items(oid)
    tracking = models.get_tracking(oid)
    user = models.get_user_by_id(order["user_id"]) if order.get("user_id") else None

    if request.method == "POST":
        action = request.form.get("action")
        note = request.form.get("note", "").strip()
        site_url = os.environ.get("SITE_URL", "http://localhost:5000")
        upi_id = models.get_setting("upi_id")
        upi_qr_url = models.get_setting("upi_qr_url")
        import emails

        if action == "set_advance":
            advance = request.form.get("advance_amount", "0")
            try:
                advance = float(advance)
            except Exception:
                advance = 0
            models.update_order(oid, {"advance_amount": advance, "status": "advance_requested"})
            models.add_tracking(oid, "advance_requested", f"Advance of ₹{advance} requested.")
            if user:
                emails.send_advance_requested(user["email"], {**order, "advance_amount": advance},
                                              upi_id, upi_qr_url, site_url)
                models.create_notification(order["user_id"],
                                           f"Advance payment of ₹{advance} requested.",
                                           url_for("orders.pay_advance", oid=oid))
            flash("Advance requested and email sent.", "success")

        elif action == "confirm_advance":
            models.update_order(oid, {"status": "advance_confirmed"})
            models.add_tracking(oid, "advance_confirmed", note or "Advance payment verified.")
            if user:
                emails.send_status_update(user["email"], order, "advance_confirmed", note)
                models.create_notification(order["user_id"],
                                           "Payment confirmed! Crafting begins.",
                                           url_for("orders.order_detail", oid=oid))
            flash("Advance confirmed.", "success")

        elif action == "update_status":
            new_status = request.form.get("new_status")
            if new_status in models.ORDER_STATUSES:
                models.update_order(oid, {"status": new_status})
                models.add_tracking(oid, new_status, note or None)
                if user:
                    emails.send_status_update(user["email"], order, new_status, note)
                    models.create_notification(order["user_id"],
                                               f"Order status: {models.STATUS_LABELS.get(new_status, new_status)}",
                                               url_for("orders.order_detail", oid=oid))
            flash(f"Status updated to {new_status}.", "success")

        return redirect(url_for("admin.order_detail", oid=oid))

    order = models.get_order(oid)  # refresh
    return render_template("admin/order_detail.html",
                           order=order, items=items, tracking=tracking, user=user,
                           next_status=models.NEXT_STATUS.get(order["status"]),
                           status_labels=models.STATUS_LABELS,
                           statuses=models.ORDER_STATUSES)


# ── Products ──────────────────────────────────────────────

@admin_bp.route("/products")
@admin_only
def products():
    search = request.args.get("q", "")
    category_id = request.args.get("category")
    prods = models.get_products(category_id=category_id, search=search or None)
    categories = models.get_categories()
    return render_template("admin/products.html", products=prods,
                           categories=categories, search=search,
                           selected_category=category_id)


@admin_bp.route("/products/new", methods=["GET", "POST"])
@admin_only
def product_new():
    categories = models.get_categories()
    if request.method == "POST":
        data = _parse_product_form(request)
        product = models.create_product(data)
        if product:
            flash("Product created!", "success")
            return redirect(url_for("admin.products"))
        flash("Error creating product.", "error")
    return render_template("admin/product_form.html", product=None, categories=categories, action="new")


@admin_bp.route("/products/<pid>/edit", methods=["GET", "POST"])
@admin_only
def product_edit(pid):
    product = models.get_product(pid)
    if not product:
        flash("Product not found.", "error")
        return redirect(url_for("admin.products"))
    categories = models.get_categories()
    if request.method == "POST":
        data = _parse_product_form(request, existing=product)
        models.update_product(pid, data)
        flash("Product updated!", "success")
        return redirect(url_for("admin.products"))
    return render_template("admin/product_form.html", product=product,
                           categories=categories, action="edit")


@admin_bp.route("/products/<pid>/delete", methods=["POST"])
@admin_only
def product_delete(pid):
    models.delete_product(pid)
    flash("Product deleted.", "success")
    return redirect(url_for("admin.products"))


def _parse_product_form(req, existing=None):
    import datetime
    data = {
        "title": req.form.get("title", "").strip(),
        "description": req.form.get("description", "").strip(),
        "price": float(req.form.get("price", 0)),
        "discount_percent": int(req.form.get("discount_percent", 0)),
        "stock": int(req.form.get("stock", 0)),
        "category_id": req.form.get("category_id") or None,
        "featured": req.form.get("featured") == "on",
        "is_flash_sale": req.form.get("is_flash_sale") == "on",
        "crafting_days": int(req.form.get("crafting_days", 7)),
    }
    flash_ends = req.form.get("flash_sale_ends_at", "")
    if flash_ends:
        data["flash_sale_ends_at"] = flash_ends
    else:
        data["flash_sale_ends_at"] = None

    # Handle image uploads
    images = list((existing or {}).get("images") or [])
    files = req.files.getlist("images")
    for f in files:
        if f and f.filename:
            path = f"products/{uuid.uuid4()}-{f.filename}"
            url = supa.upload_file("products", path, f.read(), f.content_type)
            if url:
                images.append(url)

    # Remove images
    remove_indices = req.form.getlist("remove_image")
    for idx in remove_indices:
        try:
            images.pop(int(idx))
        except Exception:
            pass

    data["images"] = images
    return data


# ── Customers ─────────────────────────────────────────────

@admin_bp.route("/customers")
@admin_only
def customers():
    all_users = models.get_all_users()
    customers_only = [u for u in all_users if not u.get("is_admin")]
    return render_template("admin/customers.html", customers=customers_only)


# ── Coupons ───────────────────────────────────────────────

@admin_bp.route("/coupons")
@admin_only
def coupons():
    all_coupons = models.get_all_coupons()
    return render_template("admin/coupons.html", coupons=all_coupons)


@admin_bp.route("/coupons/new", methods=["POST"])
@admin_only
def coupon_new():
    data = {
        "code": request.form.get("code", "").strip().upper(),
        "discount_percent": int(request.form.get("discount_percent", 10)),
        "max_uses": int(request.form.get("max_uses", 100)),
        "expires_at": request.form.get("expires_at") or None,
        "active": True,
    }
    models.create_coupon(data)
    flash("Coupon created!", "success")
    return redirect(url_for("admin.coupons"))


@admin_bp.route("/coupons/<cid>/toggle", methods=["POST"])
@admin_only
def coupon_toggle(cid):
    coupons_list = models.get_all_coupons()
    coupon = next((c for c in coupons_list if str(c["id"]) == str(cid)), None)
    if coupon:
        models.update_coupon(cid, {"active": not coupon["active"]})
    return redirect(url_for("admin.coupons"))


@admin_bp.route("/coupons/<cid>/delete", methods=["POST"])
@admin_only
def coupon_delete(cid):
    models.delete_coupon(cid)
    flash("Coupon deleted.", "success")
    return redirect(url_for("admin.coupons"))


# ── Custom Requests ───────────────────────────────────────

@admin_bp.route("/custom-requests")
@admin_only
def custom_requests():
    status = request.args.get("status", "")
    reqs = models.get_custom_requests(status=status or None)
    return render_template("admin/custom_requests.html", requests=reqs, selected_status=status)


@admin_bp.route("/custom-requests/<rid>", methods=["GET", "POST"])
@admin_only
def custom_request_detail(rid):
    req_obj = models.get_custom_request(rid)
    if not req_obj:
        flash("Request not found.", "error")
        return redirect(url_for("admin.custom_requests"))
    if request.method == "POST":
        status = request.form.get("status")
        note = request.form.get("admin_note", "")
        models.update_custom_request(rid, {"status": status, "admin_note": note})
        flash("Request updated.", "success")
        return redirect(url_for("admin.custom_request_detail", rid=rid))
    return render_template("admin/custom_request_detail.html", req=req_obj)


# ── Settings ─────────────────────────────────────────────

@admin_bp.route("/settings", methods=["GET", "POST"])
@admin_only
def settings():
    if request.method == "POST":
        upi_id = request.form.get("upi_id", "").strip()
        models.set_setting("upi_id", upi_id)
        qr_file = request.files.get("upi_qr")
        if qr_file and qr_file.filename:
            path = f"settings/upi_qr_{uuid.uuid4()}.png"
            url = supa.upload_file("products", path, qr_file.read(), qr_file.content_type)
            if url:
                models.set_setting("upi_qr_url", url)
        flash("Settings saved!", "success")
        return redirect(url_for("admin.settings"))
    upi_id = models.get_setting("upi_id")
    upi_qr_url = models.get_setting("upi_qr_url")
    return render_template("admin/settings.html", upi_id=upi_id, upi_qr_url=upi_qr_url)
