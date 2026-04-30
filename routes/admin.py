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
    low_stock_materials = models.get_low_stock_materials()
    low_stock_components = models.get_low_stock_components()
    return render_template("admin/dashboard.html", stats=stats,
                           recent_orders=recent_orders,
                           low_stock_materials=low_stock_materials,
                           low_stock_components=low_stock_components)


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
            if order.get("status") != "placed":
                flash("Advance already requested for this order.", "info")
                return redirect(url_for("admin.order_detail", oid=oid))
            advance = request.form.get("advance_amount", "0")
            shipping = request.form.get("shipping_charge", "0")
            try:
                advance = float(advance)
            except Exception:
                advance = 0
            try:
                shipping = float(shipping)
            except Exception:
                shipping = 0
            # Add shipping to order total
            new_total = float(order.get("total", 0)) + shipping
            update_data = {
                "advance_amount": advance,
                "status": "advance_requested",
                "shipping_charge": shipping,
            }
            if shipping > 0:
                update_data["total"] = new_total
            models.update_order(oid, update_data)
            note = f"Advance of ₹{advance} requested."
            if shipping > 0:
                note += f" Shipping charge: ₹{shipping}."
            models.add_tracking(oid, "advance_requested", note)
            if user:
                final_total = new_total if shipping > 0 else float(order.get("total", 0))
                emails.send_advance_requested(
                    user["email"],
                    {**order, "advance_amount": advance, "shipping_charge": shipping, "total": final_total},
                    upi_id, upi_qr_url, site_url
                )
                models.create_notification(
                    order["user_id"],
                    f"Advance payment of ₹{advance:.0f} requested.",
                    url_for("orders.pay_advance", oid=oid)
                )
            flash("Advance requested and email sent.", "success")

        elif action == "confirm_advance":
            if order.get("status") != "advance_paid":
                flash("This order is not awaiting advance confirmation.", "error")
            else:
                models.update_order(oid, {"status": "advance_confirmed"})
                models.add_tracking(oid, "advance_confirmed", note or "Advance payment verified.")
                if user:
                    emails.send_status_update(user["email"], order, "advance_confirmed", note)
                    models.create_notification(
                        order["user_id"],
                        "Payment confirmed! Crafting begins.",
                        url_for("orders.order_detail", oid=oid)
                    )
                flash("Advance confirmed. Crafting email sent.", "success")

        elif action == "update_status":
            new_status = request.form.get("new_status")
            current_status = order.get("status")
            # Prevent updating to same status (duplicate emails)
            if new_status == current_status:
                flash("Order is already at that status. No changes made.", "info")
            elif new_status in models.ORDER_STATUSES:
                models.update_order(oid, {"status": new_status})
                models.add_tracking(oid, new_status, note or None)
                if user:
                    emails.send_status_update(user["email"], order, new_status, note)
                    models.create_notification(
                        order["user_id"],
                        f"Order status updated: {models.STATUS_LABELS.get(new_status, new_status)}",
                        url_for("orders.order_detail", oid=oid)
                    )
                flash(f"Status updated to {models.STATUS_LABELS.get(new_status, new_status)}.", "success")
            else:
                flash("Invalid status.", "error")

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
    prods = models.get_products(category_id=category_id, search=search or None, listed_only=False)
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


@admin_bp.route("/products/<pid>/toggle-listing", methods=["POST"])
@admin_only
def product_toggle_listing(pid):
    p = models.get_product(pid)
    if p:
        current = p.get("is_listed", True)
        if current is None:
            current = True
        models.update_product(pid, {"is_listed": not current})
        state = "listed" if not current else "unlisted"
        flash(f"Product {state}.", "success")
    return redirect(url_for("admin.products"))


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
        "allow_preorder": req.form.get("allow_preorder") == "on",
        "is_listed": req.form.get("is_listed") == "on",
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
    status = request.args.get("status")
    reqs = models.get_custom_requests_all(status=status)
    counts = {}
    all_r = models.get_custom_requests_all()
    for r in all_r:
        s = r.get("status","new")
        counts[s] = counts.get(s,0) + 1
    return render_template("admin/custom_requests.html",
                           requests=reqs, selected_status=status,
                           counts=counts,
                           status_labels=models.CUSTOM_STATUS_LABELS)


@admin_bp.route("/custom-requests/<rid>", methods=["GET"])
@admin_only
def custom_request_detail(rid):
    req_obj = models.get_custom_request(rid)
    if not req_obj:
        flash("Request not found.", "error")
        return redirect(url_for("admin.custom_requests"))
    email_log = models.get_email_log("custom_request", rid)
    categories = models.get_categories()
    all_products = models.get_products(listed_only=False)
    linked_product = None
    if req_obj.get("linked_product_id"):
        linked_product = models.get_product(str(req_obj["linked_product_id"]))
    converted_order = None
    if req_obj.get("converted_order_id"):
        converted_order = models.get_order(str(req_obj["converted_order_id"]))
    return render_template("admin/custom_request_detail.html",
                           req=req_obj, email_log=email_log,
                           categories=categories, all_products=all_products,
                           linked_product=linked_product,
                           converted_order=converted_order,
                           status_labels=models.CUSTOM_STATUS_LABELS)


@admin_bp.route("/custom-requests/<rid>/convert", methods=["POST"])
@admin_only
def custom_request_convert(rid):
    """Admin manually converts request to real order."""
    price = request.form.get("agreed_price", "0")
    note  = request.form.get("note", "").strip()
    try:
        price = float(price)
    except Exception:
        price = 0
    if price <= 0:
        flash("Please enter a valid agreed price.", "error")
        return redirect(url_for("admin.custom_request_detail", rid=rid))
    order, err = models.convert_custom_to_order(rid, price, note)
    if err:
        flash(f"Error: {err}", "error")
    else:
        req = models.get_custom_request(rid)
        user_id = req.get("user_id") if req else None
        if user_id:
            models.create_notification(user_id,
                f"Your custom order has been confirmed! Total: ₹{price:.0f}",
                url_for("orders.order_detail", oid=order["id"]))
        import emails, os
        site_url = os.environ.get("SITE_URL","http://localhost:5000")
        if req and req.get("email"):
            emails.send_custom_accepted(req["email"], req.get("name",""),
                                        order["id"], site_url)
        flash(f"Order created successfully! Order #{str(order['id'])[:7].upper()}", "success")
    return redirect(url_for("admin.custom_request_detail", rid=rid))


@admin_bp.route("/custom-requests/<rid>/note", methods=["POST"])
@admin_only
def custom_request_add_note(rid):
    note = request.form.get("note","").strip()
    if note:
        models.add_custom_internal_note(rid, note)
        flash("Note added.", "success")
    return redirect(url_for("admin.custom_request_detail", rid=rid))


@admin_bp.route("/custom-requests/<rid>/status", methods=["POST"])
@admin_only
def custom_request_status(rid):
    status = request.form.get("status")
    if status in models.CUSTOM_STATUSES:
        models.update_custom_request(rid, {"status": status})
        flash("Status updated.", "success")
    return redirect(url_for("admin.custom_request_detail", rid=rid))


@admin_bp.route("/custom-requests/<rid>/email", methods=["POST"])
@admin_only
def custom_request_email(rid):
    import emails
    req = models.get_custom_request(rid)
    if not req:
        flash("Request not found.", "error")
        return redirect(url_for("admin.custom_requests"))
    subject = request.form.get("subject","").strip()
    message = request.form.get("message","").strip()
    if subject and message:
        emails.send_manual_email(req["email"], subject, message)
        models.log_email(req["email"], subject, message,
                         session["user_id"], "custom_request", rid)
        flash("Email sent!", "success")
    return redirect(url_for("admin.custom_request_detail", rid=rid))


@admin_bp.route("/custom-requests/<rid>/create-product", methods=["POST"])
@admin_only
def custom_request_create_product(rid):
    req = models.get_custom_request(rid)
    if not req:
        flash("Request not found.", "error")
        return redirect(url_for("admin.custom_requests"))
    title       = request.form.get("title","").strip()
    price       = float(request.form.get("price",0) or 0)
    category_id = request.form.get("category_id") or None
    stock       = int(request.form.get("stock",0) or 0)
    description = request.form.get("description","").strip()
    is_listed   = request.form.get("is_listed") == "on"
    images = [req["reference_image_url"]] if req.get("reference_image_url") else []
    product = models.create_product({
        "title": title, "price": price, "category_id": category_id,
        "stock": stock, "description": description, "is_listed": is_listed,
        "images": images, "crafting_days": int(req.get("quoted_days") or 14),
    })
    if product:
        models.update_custom_request(str(req["id"]),{
            "linked_product_id": str(product["id"]),
            "listed_in_shop": is_listed,
        })
        flash(f"Product '{title}' created and linked!", "success")
    else:
        flash("Could not create product.", "error")
    return redirect(url_for("admin.custom_request_detail", rid=rid))


@admin_bp.route("/custom-requests/<rid>/link-product", methods=["POST"])
@admin_only
def custom_request_link_product(rid):
    product_id = request.form.get("product_id","").strip()
    if product_id:
        models.update_custom_request(rid, {"linked_product_id": product_id})
        flash("Product linked!", "success")
    return redirect(url_for("admin.custom_request_detail", rid=rid))


@admin_bp.route("/custom-requests/<rid>/unlink", methods=["POST"])
@admin_only
def custom_request_unlink(rid):
    models.update_custom_request(rid, {"linked_product_id": None})
    flash("Product unlinked.", "success")
    return redirect(url_for("admin.custom_request_detail", rid=rid))


# ── Order Delete ──────────────────────────────────────────


# ── Analytics ─────────────────────────────────────────────

@admin_bp.route("/analytics")
@admin_only
def analytics():
    stats = models.get_stats()
    all_orders = models.get_orders()
    try:
        low_stock = models.get_low_stock_products(threshold=5)
    except Exception:
        low_stock = []
    try:
        mfg_analytics = models.get_manufacturing_analytics()
    except Exception:
        mfg_analytics = {"total_runs": 0, "total_waste_cost": 0, "avg_waste_pct": 0,
                         "monthly_waste": {}, "monthly_qty": {}, "recent_logs": [], "total_qty_made": 0}
    try:
        low_stock_materials = models.get_low_stock_materials()
        low_stock_components = models.get_low_stock_components()
    except Exception:
        low_stock_materials = []
        low_stock_components = []
    return render_template("admin/analytics.html", stats=stats,
                           all_orders=all_orders, low_stock=low_stock,
                           mfg=mfg_analytics,
                           low_stock_materials=low_stock_materials,
                           low_stock_components=low_stock_components)


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
    try:
        cards = models.get_all_gift_cards()
    except Exception:
        cards = []
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
    try:
        ret_list = models.get_returns(status=status or None)
    except Exception:
        ret_list = []
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
    try:
        artisan_list = models.get_artisans(active_only=False)
    except Exception:
        artisan_list = []
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
    try:
        faq_list = models.get_all_faqs()
    except Exception:
        faq_list = []
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
        for key in ["upi_id", "whatsapp_number", "instagram_handle", "store_name", "store_tagline"]:
            val = request.form.get(key, "").strip()
            if val:
                models.set_setting(key, val)
        qr_file = request.files.get("upi_qr")
        if qr_file and qr_file.filename:
            path = f"settings/upi_qr_{uuid.uuid4()}.png"
            url = supa.upload_file("everbloom", path, qr_file.read(), qr_file.content_type)
            if url:
                models.set_setting("upi_qr_url", url)
        flash("Settings saved!", "success")
        return redirect(url_for("admin.settings"))
    s = models.get_all_settings()
    return render_template("admin/settings.html", s=s)


# ── Email Templates ───────────────────────────────────────

TEMPLATE_LABELS = {
    "order_placed":      "Order Placed",
    "advance_requested": "Advance Payment Request",
    "advance_confirmed": "Advance Confirmed / Crafting Begins",
    "crafting":          "Crafting in Progress",
    "quality_check":     "Quality Check",
    "shipped":           "Order Shipped",
    "delivered":         "Order Delivered",
    "cancelled":         "Order Cancelled",
    "welcome":           "Welcome Email",
    "custom_request":    "Custom Order Request Received",
}

TEMPLATE_VARS = {
    "order_placed":      ["{{name}}", "{{order_id}}", "{{total}}"],
    "advance_requested": ["{{name}}", "{{order_id}}", "{{advance_amount}}", "{{upi_id}}", "{{pay_link}}", "{{total}}", "{{shipping_charge}}"],
    "advance_confirmed": ["{{name}}", "{{order_id}}"],
    "crafting":          ["{{name}}", "{{order_id}}"],
    "quality_check":     ["{{name}}", "{{order_id}}"],
    "shipped":           ["{{name}}", "{{order_id}}"],
    "delivered":         ["{{name}}", "{{order_id}}", "{{balance}}"],
    "cancelled":         ["{{name}}", "{{order_id}}"],
    "welcome":           ["{{name}}"],
    "custom_request":    ["{{name}}"],
}


@admin_bp.route("/email-templates")
@admin_only
def email_templates():
    templates = models.get_email_templates()
    tmap = {t["key"]: t for t in templates}
    return render_template("admin/email_templates.html",
                           templates=tmap,
                           labels=TEMPLATE_LABELS,
                           template_vars=TEMPLATE_VARS)


@admin_bp.route("/email-templates/<key>", methods=["GET", "POST"])
@admin_only
def email_template_edit(key):
    if key not in TEMPLATE_LABELS:
        flash("Template not found.", "error")
        return redirect(url_for("admin.email_templates"))

    template = models.get_email_template(key)
    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        body_html = request.form.get("body_html", "").strip()
        models.save_email_template(key, subject, body_html)
        flash("Template saved!", "success")
        return redirect(url_for("admin.email_template_edit", key=key))

    return render_template("admin/email_template_edit.html",
                           key=key,
                           label=TEMPLATE_LABELS[key],
                           template=template,
                           vars=TEMPLATE_VARS.get(key, []))


# ── Manual email from order detail ────────────────────────

@admin_bp.route("/orders/<oid>/email", methods=["POST"])
@admin_only
def order_send_email(oid):
    import emails
    order = models.get_order(oid)
    if not order:
        flash("Order not found.", "error")
        return redirect(url_for("admin.orders"))
    user = models.get_user_by_id(order["user_id"]) if order.get("user_id") else None
    if not user:
        flash("No customer email found.", "error")
        return redirect(url_for("admin.order_detail", oid=oid))

    subject = request.form.get("subject", "").strip()
    message = request.form.get("message", "").strip()

    emails.send_manual_email(user["email"], subject, message)
    models.log_email(user["email"], subject, message,
                     session["user_id"], "order", oid)
    flash("Email sent to customer!", "success")
    return redirect(url_for("admin.order_detail", oid=oid))


# ═══════════════════════════════════════════════════════════
# RAW MATERIAL INVENTORY
# ═══════════════════════════════════════════════════════════

@admin_bp.route("/inventory")
@admin_only
def inventory():
    materials = models.get_raw_materials()
    low_stock = models.get_low_stock_materials()
    return render_template("admin/inventory.html",
                           materials=materials, low_stock=low_stock)


@admin_bp.route("/inventory/new", methods=["POST"])
@admin_only
def inventory_new():
    data = {
        "name":          request.form.get("name", "").strip(),
        "unit":          request.form.get("unit", "units").strip(),
        "current_stock": float(request.form.get("current_stock", 0)),
        "reorder_level": float(request.form.get("reorder_level", 0)),
        "cost_per_unit": float(request.form.get("cost_per_unit", 0)),
        "supplier":      request.form.get("supplier", "").strip(),
        "notes":         request.form.get("notes", "").strip(),
    }
    models.create_raw_material(data)
    flash("Material added!", "success")
    return redirect(url_for("admin.inventory"))


@admin_bp.route("/inventory/<int:mid>/edit", methods=["POST"])
@admin_only
def inventory_edit(mid):
    data = {
        "name":          request.form.get("name", "").strip(),
        "unit":          request.form.get("unit", "units").strip(),
        "reorder_level": float(request.form.get("reorder_level", 0)),
        "cost_per_unit": float(request.form.get("cost_per_unit", 0)),
        "supplier":      request.form.get("supplier", "").strip(),
        "notes":         request.form.get("notes", "").strip(),
    }
    models.update_raw_material(mid, data)
    flash("Material updated!", "success")
    return redirect(url_for("admin.inventory"))


@admin_bp.route("/inventory/<int:mid>/delete", methods=["POST"])
@admin_only
def inventory_delete(mid):
    models.delete_raw_material(mid)
    flash("Material deleted.", "success")
    return redirect(url_for("admin.inventory"))


@admin_bp.route("/inventory/<int:mid>/purchase", methods=["POST"])
@admin_only
def inventory_purchase(mid):
    qty      = float(request.form.get("quantity", 0))
    cpu      = float(request.form.get("cost_per_unit", 0))
    supplier = request.form.get("supplier", "").strip()
    note     = request.form.get("note", "").strip()
    if qty > 0:
        models.add_expenditure({
            "material_id":   mid,
            "quantity":      qty,
            "cost_per_unit": cpu,
            "total_cost":    round(qty * cpu, 2),
            "supplier":      supplier,
            "note":          note,
        })
        flash(f"Stock updated! Added {qty} units.", "success")
    return redirect(url_for("admin.inventory"))


@admin_bp.route("/inventory/<int:mid>")
@admin_only
def inventory_detail(mid):
    material = models.get_raw_material(mid)
    if not material:
        flash("Material not found.", "error")
        return redirect(url_for("admin.inventory"))
    expenditures = models.get_expenditures(mid)
    return render_template("admin/inventory_detail.html",
                           material=material, expenditures=expenditures)


# ═══════════════════════════════════════════════════════════
# PRODUCT COST BUILDER
# ═══════════════════════════════════════════════════════════

@admin_bp.route("/product-costs")
@admin_only
def product_costs():
    products = models.get_products(listed_only=False)
    return render_template("admin/product_costs.html", products=products)




# ═══════════════════════════════════════════════════════════
# COMPONENTS (SEMI-FINISHED GOODS)
# ═══════════════════════════════════════════════════════════

COMPONENT_ICONS = ["🔧","🪵","🎨","🖼️","🏺","🧱","🪡","🧵","🪢","⚙️","🔩","🪣","📦","🎭","🗿","💎","🪨","🌿","🍃","🌸"]

@admin_bp.route("/components")
@admin_only
def components():
    comps = models.get_components()
    materials = models.get_raw_materials()
    low = models.get_low_stock_components()
    return render_template("admin/components.html",
                           components=comps, materials=materials,
                           low_stock=low, icons=COMPONENT_ICONS)

@admin_bp.route("/components/new", methods=["POST"])
@admin_only
def component_new():
    data = {
        "name":          request.form.get("name", "").strip(),
        "unit":          request.form.get("unit", "pieces"),
        "current_stock": float(request.form.get("current_stock", 0)),
        "reorder_level": float(request.form.get("reorder_level", 0)),
        "icon":          request.form.get("icon", "🔧"),
        "notes":         request.form.get("notes", "").strip(),
    }
    models.create_component(data)
    flash("Component added!", "success")
    return redirect(url_for("admin.components"))

@admin_bp.route("/components/<int:cid>", methods=["GET", "POST"])
@admin_only
def component_detail(cid):
    comp = models.get_component(cid)
    if not comp:
        flash("Component not found.", "error")
        return redirect(url_for("admin.components"))
    materials = models.get_raw_materials()
    bom = models.get_component_bom(cid)
    cost = models.calculate_component_cost(cid)
    log = supa.select("manufacture_log", {"component_id": f"eq.{cid}"}, order="manufactured_at.desc")

    if request.method == "POST":
        action = request.form.get("action")
        if action == "save_bom":
            mat_ids = request.form.getlist("material_id[]")
            qtys    = request.form.getlist("quantity_used[]")
            models.save_component_bom(cid, [
                {"material_id": m, "quantity_used": q}
                for m, q in zip(mat_ids, qtys)
            ])
            # Also update icon/notes
            models.update_component(cid, {
                "icon":  request.form.get("icon", comp.get("icon","🔧")),
                "notes": request.form.get("notes", "").strip(),
                "reorder_level": float(request.form.get("reorder_level", 0)),
            })
            flash("Component BOM saved!", "success")
        elif action == "manufacture":
            qty   = float(request.form.get("quantity", 1))
            notes = request.form.get("notes", "").strip()
            wastage_pct = float(request.form.get("wastage_percent", 0) or 0)
            ok, errors = models.manufacture_component(cid, qty, notes, wastage_percent=wastage_pct)
            if ok:
                waste_msg = f" ({wastage_pct}% wastage applied)" if wastage_pct > 0 else ""
                flash(f"Manufactured {qty} × {comp['name']}. Stock updated!{waste_msg}", "success")
            else:
                for e in errors:
                    flash(e, "error")
        elif action == "edit":
            models.update_component(cid, {
                "name":  request.form.get("name", comp["name"]).strip(),
                "unit":  request.form.get("unit", comp["unit"]),
                "icon":  request.form.get("icon", comp.get("icon","🔧")),
                "reorder_level": float(request.form.get("reorder_level", 0)),
                "notes": request.form.get("notes", "").strip(),
            })
            flash("Component updated!", "success")
        return redirect(url_for("admin.component_detail", cid=cid))

    comp = models.get_component(cid)
    bom  = models.get_component_bom(cid)
    cost = models.calculate_component_cost(cid)
    return render_template("admin/component_detail.html",
                           comp=comp, materials=materials, bom=bom,
                           cost=cost, log=log, icons=COMPONENT_ICONS)

@admin_bp.route("/components/<int:cid>/delete", methods=["POST"])
@admin_only
def component_delete(cid):
    models.delete_component(cid)
    flash("Component deleted.", "success")
    return redirect(url_for("admin.components"))


# ── Update product cost detail to use new BOM ─────────────

@admin_bp.route("/product-costs/<pid>", methods=["GET", "POST"])
@admin_only
def product_cost_detail(pid):
    product = models.get_product(pid)
    if not product:
        flash("Product not found.", "error")
        return redirect(url_for("admin.product_costs"))
    materials  = models.get_raw_materials()
    components = models.get_components()

    if request.method == "POST":
        models.save_product_cost(pid, {
            "labour_cost":    float(request.form.get("labour_cost", 0)),
            "overhead_cost":  float(request.form.get("overhead_cost", 0)),
            "margin_percent": float(request.form.get("margin_percent", 30)),
            "notes":          request.form.get("notes", "").strip(),
        })
        item_types  = request.form.getlist("item_type[]")
        mat_ids     = request.form.getlist("material_id[]")
        comp_ids    = request.form.getlist("component_id[]")
        qtys        = request.form.getlist("quantity_used[]")
        bom_items = []
        for i, itype in enumerate(item_types):
            qty = float(qtys[i]) if i < len(qtys) else 0
            if itype == "material":
                mid = mat_ids[i] if i < len(mat_ids) else ""
                bom_items.append({"item_type": "material", "material_id": mid, "component_id": None, "quantity_used": qty})
            elif itype == "component":
                cid_val = comp_ids[i] if i < len(comp_ids) else ""
                bom_items.append({"item_type": "component", "material_id": None, "component_id": cid_val, "quantity_used": qty})
        models.save_product_bom(pid, bom_items)
        flash("Cost breakdown saved!", "success")
        return redirect(url_for("admin.product_cost_detail", pid=pid))

    product_cost   = models.get_product_cost(pid)
    product_bom    = models.get_product_bom(pid)
    cost_breakdown = models.calculate_product_bom_cost(pid)
    return render_template("admin/product_cost_detail.html",
                           product=product, materials=materials,
                           components=components, product_cost=product_cost,
                           product_bom=product_bom, cost_breakdown=cost_breakdown)


# ── Order Requirements Panel ──────────────────────────────

@admin_bp.route("/orders/<oid>/requirements")
@admin_only
def order_requirements(oid):
    order = models.get_order(oid)
    if not order:
        flash("Order not found.", "error")
        return redirect(url_for("admin.orders"))
    items = models.get_order_items(oid)
    reqs  = models.calculate_order_requirements(oid)
    reqs_with_status = models.check_requirements_availability(reqs)
    all_available = all(r["is_available"] for r in reqs_with_status)
    return render_template("admin/order_requirements.html",
                           order=order, items=items,
                           requirements=reqs_with_status,
                           all_available=all_available)


@admin_bp.route("/orders/<oid>/deduct-stock", methods=["POST"])
@admin_only
def order_deduct_stock(oid):
    order = models.get_order(oid)
    if not order:
        flash("Order not found.", "error")
        return redirect(url_for("admin.orders"))
    models.deduct_order_materials(oid)
    models.add_tracking(oid, order["status"], "Inventory deducted for this order.")
    flash("Stock deducted from inventory!", "success")
    return redirect(url_for("admin.order_requirements", oid=oid))
