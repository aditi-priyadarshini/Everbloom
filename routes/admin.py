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
    import sys
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
    data["flash_sale_ends_at"] = flash_ends if flash_ends else None

    # Handle image uploads
    images = list((existing or {}).get("images") or [])
    files = req.files.getlist("images")
    for f in files:
        if not f or not f.filename:
            continue
        try:
            file_bytes = f.read()
            if not file_bytes:
                continue
            safe_name = f.filename.replace(" ", "_").replace("/", "_")
            path = f"products/{uuid.uuid4()}-{safe_name}"
            content_type = f.content_type or "image/jpeg"
            url = supa.upload_file("everbloom", path, file_bytes, content_type)
            if url:
                images.append(url)
                print(f"[upload OK] {url}", file=sys.stderr)
            else:
                flash(f"Image '{f.filename}' failed — check bucket 'everbloom' exists and is Public in Supabase Storage.", "error")
        except Exception as e:
            print(f"[upload EXCEPTION] {e}", file=sys.stderr)
            flash(f"Upload error: {e}", "error")

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


# ── Analytics ─────────────────────────────────────────────

@admin_bp.route("/analytics")
@admin_only
def analytics():
    stats = models.get_stats()
    all_orders = models.get_orders()
    low_stock = models.get_low_stock_products(threshold=5)
    return render_template("admin/analytics.html", stats=stats,
                           all_orders=all_orders, low_stock=low_stock)


@admin_bp.route("/analytics/export")
@admin_only
def export_orders():
    import csv, io
    all_orders = models.get_orders()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Order ID", "Customer", "Phone", "Address", "Total",
                     "Advance", "Coupon", "Discount", "Status", "Date"])
    for o in all_orders:
        writer.writerow([
            o["id"][:8].upper(), o.get("name", ""), o.get("phone", ""),
            o.get("address", ""), o.get("total", ""), o.get("advance_amount", ""),
            o.get("coupon_code", ""), o.get("discount_amount", ""),
            o.get("status", ""), o.get("created_at", "")[:10]
        ])
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=everbloom_orders.csv"}
    )


# ── Gift Cards ────────────────────────────────────────────

@admin_bp.route("/gift-cards")
@admin_only
def gift_cards():
    cards = models.get_all_gift_cards()
    return render_template("admin/gift_cards.html", cards=cards)


@admin_bp.route("/gift-cards/new", methods=["POST"])
@admin_only
def gift_card_new():
    import random, string
    code = request.form.get("code", "").strip().upper()
    if not code:
        code = "GIFT-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    models.create_gift_card({
        "code": code,
        "amount": float(request.form.get("amount", 500)),
        "issued_to": request.form.get("issued_to", ""),
        "expires_at": request.form.get("expires_at") or None,
    })
    flash(f"Gift card {code} created!", "success")
    return redirect(url_for("admin.gift_cards"))


@admin_bp.route("/gift-cards/<gid>/delete", methods=["POST"])
@admin_only
def gift_card_delete(gid):
    models.delete_gift_card(gid)
    flash("Gift card deleted.", "success")
    return redirect(url_for("admin.gift_cards"))


# ── Returns ───────────────────────────────────────────────

@admin_bp.route("/returns")
@admin_only
def returns():
    status = request.args.get("status", "")
    ret_list = models.get_returns(status=status or None)
    return render_template("admin/returns.html", returns=ret_list, selected_status=status)


@admin_bp.route("/returns/<rid>", methods=["GET", "POST"])
@admin_only
def return_detail(rid):
    ret = models.get_return(rid)
    if not ret:
        flash("Return not found.", "error")
        return redirect(url_for("admin.returns"))
    if request.method == "POST":
        models.update_return(rid, {
            "status": request.form.get("status"),
            "admin_note": request.form.get("admin_note", ""),
        })
        flash("Return updated.", "success")
        return redirect(url_for("admin.return_detail", rid=rid))
    order = models.get_order(ret["order_id"]) if ret.get("order_id") else None
    return render_template("admin/return_detail.html", ret=ret, order=order)


# ── Artisans ──────────────────────────────────────────────

@admin_bp.route("/artisans")
@admin_only
def artisans():
    artisan_list = models.get_artisans(active_only=False)
    return render_template("admin/artisans.html", artisans=artisan_list)


@admin_bp.route("/artisans/new", methods=["GET", "POST"])
@admin_only
def artisan_new():
    if request.method == "POST":
        image_url = None
        img = request.files.get("image")
        if img and img.filename:
            path = f"artisans/{uuid.uuid4()}-{img.filename}"
            image_url = supa.upload_file("everbloom", path, img.read(), img.content_type)
        models.create_artisan({
            "name": request.form.get("name", ""),
            "bio": request.form.get("bio", ""),
            "location": request.form.get("location", ""),
            "speciality": request.form.get("speciality", ""),
            "instagram": request.form.get("instagram", ""),
            "image_url": image_url,
            "active": request.form.get("active") == "on",
        })
        flash("Artisan added!", "success")
        return redirect(url_for("admin.artisans"))
    return render_template("admin/artisan_form.html", artisan=None)


@admin_bp.route("/artisans/<aid>/edit", methods=["GET", "POST"])
@admin_only
def artisan_edit(aid):
    artisan = models.get_artisan(aid)
    if not artisan:
        return redirect(url_for("admin.artisans"))
    if request.method == "POST":
        data = {
            "name": request.form.get("name", ""),
            "bio": request.form.get("bio", ""),
            "location": request.form.get("location", ""),
            "speciality": request.form.get("speciality", ""),
            "instagram": request.form.get("instagram", ""),
            "active": request.form.get("active") == "on",
        }
        img = request.files.get("image")
        if img and img.filename:
            path = f"artisans/{uuid.uuid4()}-{img.filename}"
            url = supa.upload_file("everbloom", path, img.read(), img.content_type)
            if url:
                data["image_url"] = url
        models.update_artisan(aid, data)
        flash("Artisan updated!", "success")
        return redirect(url_for("admin.artisans"))
    return render_template("admin/artisan_form.html", artisan=artisan)


@admin_bp.route("/artisans/<aid>/delete", methods=["POST"])
@admin_only
def artisan_delete(aid):
    models.delete_artisan(aid)
    flash("Artisan deleted.", "success")
    return redirect(url_for("admin.artisans"))


# ── FAQs ──────────────────────────────────────────────────

@admin_bp.route("/faqs")
@admin_only
def faqs():
    faq_list = models.get_all_faqs()
    return render_template("admin/faqs.html", faqs=faq_list)


@admin_bp.route("/faqs/new", methods=["POST"])
@admin_only
def faq_new():
    models.create_faq({
        "question": request.form.get("question", ""),
        "answer": request.form.get("answer", ""),
        "category": request.form.get("category", "general"),
        "sort_order": int(request.form.get("sort_order", 0)),
        "active": True,
    })
    flash("FAQ added!", "success")
    return redirect(url_for("admin.faqs"))


@admin_bp.route("/faqs/<fid>/delete", methods=["POST"])
@admin_only
def faq_delete(fid):
    models.delete_faq(fid)
    flash("FAQ deleted.", "success")
    return redirect(url_for("admin.faqs"))


# ── Broadcast Email ───────────────────────────────────────

@admin_bp.route("/broadcast", methods=["GET", "POST"])
@admin_only
def broadcast():
    broadcasts = models.get_broadcasts()
    if request.method == "POST":
        subject = request.form.get("subject", "")
        body = request.form.get("body", "")
        all_users = models.get_all_users()
        customers = [u for u in all_users if not u.get("is_admin") and u.get("email")]
        import emails as email_mod
        sent = 0
        for u in customers:
            try:
                email_mod._send(u["email"], subject,
                    f'<div style="font-family:Georgia,serif;max-width:560px;margin:0 auto;">'
                    f'<h2 style="color:#5c3d3d;">Everbloom</h2>{body}'
                    f'<p style="color:#999;font-size:12px;margin-top:2rem;">You received this because you have an account with Everbloom.</p>'
                    f'</div>')
                sent += 1
            except Exception:
                pass
        models.log_broadcast(subject, body, sent)
        flash(f"Email sent to {sent} customers!", "success")
        return redirect(url_for("admin.broadcast"))
    return render_template("admin/broadcast.html", broadcasts=broadcasts)


# ── Variants (inline via product form) ───────────────────

@admin_bp.route("/products/<pid>/variants/add", methods=["POST"])
@admin_only
def variant_add(pid):
    models.create_variant({
        "product_id": pid,
        "name": request.form.get("name", ""),
        "value": request.form.get("value", ""),
        "price_modifier": float(request.form.get("price_modifier", 0)),
        "stock": int(request.form.get("stock", 0)),
    })
    flash("Variant added!", "success")
    return redirect(url_for("admin.product_edit", pid=pid))


@admin_bp.route("/variants/<vid>/delete", methods=["POST"])
@admin_only
def variant_delete(vid):
    pid = request.form.get("product_id")
    models.delete_variant(vid)
    flash("Variant deleted.", "success")
    return redirect(url_for("admin.product_edit", pid=pid))


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
            url = supa.upload_file("everbloom", path, qr_file.read(), qr_file.content_type)
            if url:
                models.set_setting("upi_qr_url", url)
        flash("Settings saved!", "success")
        return redirect(url_for("admin.settings"))
    upi_id = models.get_setting("upi_id")
    upi_qr_url = models.get_setting("upi_qr_url")
    return render_template("admin/settings.html", upi_id=upi_id, upi_qr_url=upi_qr_url)
