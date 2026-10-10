from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
import models
import supa
import uuid
import os
from routes.auth import admin_only
from services.commerce import availability as models_availability, MODES, PAYMENT_STATUSES, FULFILMENT_STATUSES, money

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _saved(result, label):
    """A database rejection must never produce a green success toast."""
    ok = result is not None and result is not False and result != []
    flash(f'{label} saved.' if ok else f'Could not save {label.lower()}. Check backend logs and migrations.',
          'success' if ok else 'error')
    return ok


def _number(name, default=0, minimum=0):
    """Validate untrusted admin numeric forms; avoid unhandled ValueError/500s."""
    from decimal import Decimal, InvalidOperation
    try:
        value = Decimal(request.form.get(name) or str(default))
        if not value.is_finite() or value < minimum:
            raise ValueError
    except (InvalidOperation, ValueError):
        raise ValueError(f'Enter a valid {name.replace("_", " ")}.')
    return float(value)


def _refresh_catalogue():
    from services.cache import invalidate
    invalidate('public_catalogue')


@admin_bp.errorhandler(ValueError)
@admin_bp.errorhandler(supa.SupabaseError)
def admin_action_error(error):
    """Show actionable failures instead of redirecting into a generic 500 page."""
    if request.method == 'POST':
        from urllib.parse import urlsplit
        referer = request.referrer or ''
        target = referer if urlsplit(referer).netloc == request.host else url_for('admin.dashboard')
        flash(error.admin_detail if isinstance(error, supa.SupabaseError) else str(error), 'error')
        return redirect(target)
    from flask import current_app
    current_app.logger.warning('Admin backend operation failed: %s', error)
    return render_template('errors/error.html', code=503), 503


@admin_bp.route('/system-health')
@admin_only
def system_health():
    """Read-only diagnostics to expose missing migrations/permissions in production."""
    checks = [
        ('Store settings', 'settings', 'key,value'),
        ('Product creation schema', 'products', 'id,title,description,price,discount_percent,stock,category_id,featured,is_flash_sale,flash_sale_ends_at,allow_preorder,is_listed,crafting_days,images,availability_mode,accepting_orders,lead_time_min,lead_time_max,max_order_quantity,sale_price,personalization_fields,slug,image_alt_texts'),
        ('Product collections linkage', 'collection_products', 'collection_id,product_id'),
        ('Product occasions linkage', 'product_occasions', 'occasion_id,product_id'),
        ('Categories', 'categories', 'id,active'),
        ('Collections', 'collections', 'id,slug,active'),
        ('Occasions', 'occasions', 'id,slug,active'),
        ('Orders', 'orders', 'id,email,tracking_token,internal_notes,payment_status,fulfilment_status'),
        ('Custom order items', 'order_items', 'id,order_id,product_id,availability_mode,personalization'),
        ('Custom order tracking', 'tracking', 'id,order_id,status,note'),
        ('Custom orders', 'custom_requests', 'id,status,linked_product_id,quoted_price,converted_order_id'),
        ('Gift cards', 'gift_cards', 'id,issued_to,balance'),
        ('Inventory', 'raw_materials', 'id,active'),
        ('Components', 'components', 'id,active'),
        ('Reviews', 'reviews', 'id,visible'),
        ('Artisans', 'artisans', 'id,speciality,instagram'),
        ('FAQs', 'faqs', 'id,category'),
        ('Product costs', 'product_costs', 'id,notes'),
        ('Audit log', 'audit_log', 'id,actor_id'),
        ('Testimonials', 'testimonials', 'id,active'),
    ]
    results = []
    for label, table, fields in checks:
        try:
            supa.probe_table(table, fields)
            results.append({'name':label, 'ok':True, 'detail':'Table and required columns reachable'})
        except (supa.SupabaseError, ValueError) as error:
            results.append({'name':label, 'ok':False, 'detail':error.admin_detail if isinstance(error, supa.SupabaseError) else str(error)})
    for bucket, visibility in [('everbloom', True), ('payment-receipts', False)]:
        try:
            supa.probe_bucket(bucket, expected_public=visibility)
            results.append({'name': f'Storage: {bucket}', 'ok': True,
                            'detail': 'Bucket exists with correct privacy'})
        except supa.SupabaseError as error:
            results.append({'name': f'Storage: {bucket}', 'ok': False,
                            'detail': error.admin_detail})
    return render_template('admin/system_health.html', checks=results,
                           configured=bool(os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_SERVICE_KEY')))


# ── Dashboard ─────────────────────────────────────────────

@admin_bp.route("/")
@admin_only
def dashboard():
    all_orders = models.get_orders()
    stats = models.get_stats(all_orders=all_orders)
    recent_orders = all_orders[:10]
    from datetime import date
    today=date.today().isoformat()
    ops={'today_orders':sum(1 for o in all_orders if (o.get('created_at') or '').startswith(today)),
         'month_revenue':sum(float(o.get('total') or 0) for o in all_orders if o.get('status')=='delivered' and (o.get('created_at') or '').startswith(today[:7])),
         'pending_payments':sum(1 for o in all_orders if o.get('payment_status')=='advance_submitted'),
         'custom_pending':sum(1 for r in models.get_custom_requests() if r.get('status') not in ('converted','closed','rejected')),
         'due_orders':sorted([o for o in all_orders if o.get('preferred_delivery_date') and o.get('status') not in ('cancelled','delivered')],key=lambda o:o['preferred_delivery_date'])[:10]}
    low_stock_materials = models.get_low_stock_materials()
    low_stock_components = models.get_low_stock_components()
    return render_template("admin/dashboard.html", stats=stats,
                           recent_orders=recent_orders, ops=ops,
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
    query=request.args.get('q','').strip().casefold()
    if query: order_list=[o for o in order_list if query in ' '.join(str(o.get(k) or '') for k in ('id','name','email','phone')).casefold()]
    if request.args.get('payment'): order_list=[o for o in order_list if o.get('payment_status')==request.args['payment']]
    if request.args.get('fulfilment'): order_list=[o for o in order_list if o.get('fulfilment_status')==request.args['fulfilment']]
    return render_template("admin/orders.html", orders=order_list, payment_statuses=PAYMENT_STATUSES, fulfilment_statuses=FULFILMENT_STATUSES,
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
    user = models.get_user_by_id(order["user_id"]) if order.get("user_id") else ({"email":order["email"]} if order.get("email") else None)

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
            if advance < 0 or shipping < 0 or advance > float(order.get('total',0)) + shipping:
                flash('Advance and shipping must be nonnegative; advance cannot exceed the total.','error')
                return redirect(url_for('admin.order_detail',oid=oid))
            # Add shipping to order total
            new_total = float(order.get("total", 0)) + shipping
            update_data = {
                "advance_amount": advance,
                "status": "advance_requested",
                "shipping_charge": shipping,
            }
            if shipping > 0:
                update_data["total"] = new_total
            update_data["payment_status"] = "advance_requested"
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
                    order.get("user_id"),
                    f"Advance payment of ₹{advance:.0f} requested.",
                    url_for("orders.pay_advance", oid=oid)
                )
            flash('Advance request saved. Verify outbound email in SMTP logs.', 'success')

        elif action == "confirm_advance":
            if order.get("status") != "advance_paid":
                flash("This order is not awaiting advance confirmation.", "error")
            else:
                models.update_order(oid, {"status": "advance_confirmed", "payment_status":"advance_verified", "fulfilment_status":"confirmed"})
                models.add_tracking(oid, "advance_confirmed", note or "Advance payment verified.")
                if user:
                    emails.send_status_update(user["email"], order, "advance_confirmed", note)
                    models.create_notification(
                        order.get("user_id"),
                        "Payment confirmed! Crafting begins.",
                        url_for("orders.order_detail", oid=oid)
                    )
                flash('Advance confirmed. Verify outbound email in SMTP logs.', 'success')

        elif action == 'internal_note':
            existing=order.get('internal_notes') or ''
            models.update_order(oid, {'internal_notes':(existing+'\n'+request.form.get('internal_note','').strip())[-20000:]})
            flash('Internal note saved.','success')

        elif action == 'commerce_status':
            payment = request.form.get('payment_status')
            fulfilment = request.form.get('fulfilment_status')
            if payment not in PAYMENT_STATUSES or fulfilment not in FULFILMENT_STATUSES:
                flash('Invalid payment or fulfilment state.', 'error')
            else:
                try:
                    if fulfilment == 'cancelled': models.delete_order(oid)
                    else:
                        models.update_order(oid, {'payment_status':payment,'fulfilment_status':fulfilment})
                        if fulfilment != order.get('fulfilment_status'):
                            models.add_tracking(oid,fulfilment,note or None)
                    flash('Order updated.', 'success')
                except ValueError as error: flash(str(error),'error')

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
                        order.get("user_id"),
                        f"Order status updated: {models.STATUS_LABELS.get(new_status, new_status)}",
                        url_for("orders.order_detail", oid=oid)
                    )
                flash(f"Status updated to {models.STATUS_LABELS.get(new_status, new_status)}.", "success")
            else:
                flash("Invalid status.", "error")

        return redirect(url_for("admin.order_detail", oid=oid))

    order = models.get_order(oid)  # refresh
    if order.get("payment_screenshot_url"):
        order["payment_screenshot_url"] = supa.receipt_url(order["payment_screenshot_url"])
    return render_template("admin/order_detail.html",
                           order=order, items=items, tracking=tracking, user=user,
                           next_status=models.NEXT_STATUS.get(order["status"]),
                           status_labels=models.STATUS_LABELS,
                           statuses=models.ORDER_STATUSES, payment_statuses=PAYMENT_STATUSES, fulfilment_statuses=FULFILMENT_STATUSES)


# ── Products ──────────────────────────────────────────────

@admin_bp.route("/products")
@admin_only
def products():
    search = request.args.get("q", "")
    category_id = request.args.get("category")
    prods = models.get_products(category_id=category_id, search=search or None, listed_only=False)
    mode=request.args.get('availability','')
    if mode: prods=[p for p in prods if models_availability(p)['mode']==mode]
    visibility=request.args.get('visibility','')
    if visibility in ('published','hidden'): prods=[p for p in prods if models_availability(p)['published']==(visibility=='published')]
    if request.args.get('stock')=='empty': prods=[p for p in prods if int(p.get('stock') or 0)==0]
    categories = models.get_categories()
    return render_template("admin/products.html", products=prods,
                           categories=categories, search=search,
                           selected_category=category_id)


@admin_bp.route("/products/new", methods=["GET", "POST"])
@admin_only
def product_new():
    categories = models.get_categories()
    if request.method == 'POST':
        try:
            data = _parse_product_form(request)
            if not data['title'] or data['price'] <= 0:
                raise ValueError('A title and a positive price are required.')
            product = models.create_product(data)
            if not product: raise ValueError('Supabase did not create this product.')
            _refresh_catalogue()
            try:
                _save_memberships(product['id'])
            except (ValueError, supa.SupabaseError) as exc:
                # Product INSERT has committed; don't invite a duplicate retry.
                flash('Product created, but collection/occasion linking failed: ' +
                      (exc.admin_detail if isinstance(exc, supa.SupabaseError) else str(exc)) +
                      '. Open this product and retry saving its links.', 'error')
                return redirect(url_for('admin.product_edit', pid=product['id']))
            flash('Product created!', 'success')
            return redirect(url_for('admin.products'))
        except (ValueError, supa.SupabaseError) as exc:
            flash(exc.admin_detail if isinstance(exc, supa.SupabaseError) else str(exc), 'error')
    return render_template('admin/product_form.html', product=None,
                           categories=categories, action='new', **_catalog_editor_context())


@admin_bp.route("/products/<pid>/edit", methods=["GET", "POST"])
@admin_only
def product_edit(pid):
    product = models.get_product(pid)
    if not product:
        flash('Product not found.', 'error')
        return redirect(url_for('admin.products'))
    categories = models.get_categories()
    if request.method == 'POST':
        try:
            data = _parse_product_form(request, existing=product)
            if not data['title'] or data['price'] <= 0:
                raise ValueError('A title and a positive price are required.')
            if not models.update_product(pid, data):
                raise ValueError('Supabase did not update the product.')
            _save_memberships(pid)
            _refresh_catalogue()
            flash('Product updated!', 'success')
            return redirect(url_for('admin.products'))
        except (ValueError, supa.SupabaseError) as exc:
            flash(exc.admin_detail if isinstance(exc, supa.SupabaseError) else str(exc), 'error')
    return render_template('admin/product_form.html', product=product,
                           categories=categories, action='edit', variants=models.get_variants(pid),
                           **_catalog_editor_context(pid))


@admin_bp.route("/products/<pid>/toggle-listing", methods=["POST"])
@admin_only
def product_toggle_listing(pid):
    p = models.get_product(pid)
    if p:
        current = p.get("is_listed", True)
        if current is None:
            current = True
        if _saved(models.update_product(pid, {"is_listed": not current}), 'Product visibility'):
            _refresh_catalogue()
    return redirect(url_for("admin.products"))


@admin_bp.route("/products/<pid>/delete", methods=["POST"])
@admin_only
def product_delete(pid):
    if _saved(models.delete_product(pid), 'Product archive'):
        _refresh_catalogue()
    return redirect(url_for("admin.products"))


def _parse_product_form(req, existing=None):
    import json, re
    mode = req.form.get('availability_mode','READY_TO_SHIP')
    if mode not in MODES: raise ValueError('Choose a valid availability mode.')
    fields = json.loads(req.form.get('personalization_fields','[]') or '[]')
    if not isinstance(fields,list) or len(fields)>12: raise ValueError('Use at most 12 personalization fields.')
    for field in fields:
        if not isinstance(field,dict) or not re.fullmatch(r'[a-z][a-z0-9_]{0,39}',field.get('name','')): raise ValueError('Personalization field names must use lowercase letters and underscores.')
    data = {
        'availability_mode':mode,
        'accepting_orders':req.form.get('accepting_orders') == 'on',
        'lead_time_min':max(0,int(req.form.get('lead_time_min') or 0)),
        'lead_time_max':max(0,int(req.form.get('lead_time_max') or req.form.get('crafting_days') or 7)),
        'max_order_quantity':max(1,min(99,int(req.form.get('max_order_quantity') or 99))),
        'sale_price':float(money(req.form['sale_price'])) if req.form.get('sale_price') else None,
        'personalization_fields':fields,
        'slug':req.form.get('slug','').strip() or re.sub(r'[^a-z0-9]+','-',req.form.get('title','').lower()).strip('-'),
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
    try:
        remove_indices = sorted({int(index) for index in req.form.getlist("remove_image")}, reverse=True)
    except ValueError:
        raise ValueError("Invalid image selection.")
    if any(index < 0 or index >= len(images) for index in remove_indices):
        raise ValueError("Invalid image selection.")
    files = req.files.getlist("images")
    if len(images)-len(remove_indices)+len([f for f in files if f.filename])>12: raise ValueError("Use at most 12 product images.")
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
            if not url:
                raise ValueError(f"Image '{f.filename}' failed to upload. Verify the Supabase Storage bucket 'everbloom'.")
            images.append(url)
        except (ValueError, supa.SupabaseError) as error:
            raise ValueError(f"Image '{f.filename}': {error}") from error

    # Remove images from highest index first to preserve indices.
    for index in remove_indices:
        images.pop(index)

    original = list((existing or {}).get("images") or [])
    ordering = req.form.getlist("image_order")
    try:
        indices = [int(index) for index in ordering] if ordering else list(range(len(original)))
    except ValueError:
        raise ValueError("Invalid image order.")
    if sorted(indices) != list(range(len(original))):
        raise ValueError("Invalid image order.")
    removed = set(remove_indices)
    kept_indices = [index for index in indices if index not in removed]
    uploaded = images[len(original)-len(removed):]
    images = [original[index] for index in kept_indices] + uploaded
    previous_alt = (existing or {}).get('image_alt_texts') or []
    data['image_alt_texts'] = [
        req.form.get('image_alt_'+str(index), previous_alt[index] if index < len(previous_alt) else data['title']).strip()[:300] or data['title']
        for index in kept_indices
    ] + [data['title']] * len(uploaded)
    data["images"] = images
    return data


# ── Customers ─────────────────────────────────────────────

@admin_bp.route("/customers")
@admin_only
def customers():
    all_users = models.get_all_users()
    customers_only = [u for u in all_users if not u.get("is_admin")]
    query=request.args.get("q", "").strip().casefold()
    if query: customers_only=[u for u in customers_only if query in " ".join(str(u.get(k) or "") for k in ("name", "email", "phone")).casefold()]
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
    code = request.form.get('code', '').strip().upper()
    percent = _number('discount_percent', 10, 0)
    uses = _number('max_uses', 100, 1)
    if not code or percent > 100 or not percent.is_integer() or not uses.is_integer():
        raise ValueError('Enter a coupon code, a discount from 0–100%, and a whole-number usage limit.')
    data = {
        "code": code,
        "discount_percent": int(percent),
        "max_uses": int(uses),
        "usage_limit": int(uses),
        "expires_at": request.form.get("expires_at") or None,
        "active": True,
    }
    _saved(models.create_coupon(data), "Coupon")
    return redirect(url_for("admin.coupons"))


@admin_bp.route("/coupons/<cid>/toggle", methods=["POST"])
@admin_only
def coupon_toggle(cid):
    coupons_list = models.get_all_coupons()
    coupon = next((c for c in coupons_list if str(c["id"]) == str(cid)), None)
    if coupon:
        _saved(models.update_coupon(cid, {"active": not coupon["active"]}), "Coupon visibility")
    return redirect(url_for("admin.coupons"))


@admin_bp.route("/coupons/<cid>/delete", methods=["POST"])
@admin_only
def coupon_delete(cid):
    _saved(models.delete_coupon(cid), "Coupon archive")
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
    # Keep the submitted decimal string intact, rather than floating-point
    # rounding money before models.convert_custom_to_order validates it.
    order, err = models.convert_custom_to_order(rid, price, note)
    if err:
        flash(f"Error: {err}", "error")
    else:
        # The RPC transaction has committed. Optional notifications must never
        # make a completed order appear to have failed (inviting duplicate retries).
        flash(f"Order created successfully! Order #{str(order['id'])[:7].upper()}", "success")
        try:
            req = models.get_custom_request(rid)
        except (supa.SupabaseError, ValueError):
            from flask import current_app
            current_app.logger.warning('Order conversion succeeded; custom request notification lookup failed')
            req = None
        if req and req.get('user_id'):
            try:
                models.create_notification(req['user_id'],
                    f"Your custom order has been confirmed! Total: ₹{float(order['total']):.2f}",
                    url_for('orders.order_detail', oid=order['id']))
            except (supa.SupabaseError, ValueError):
                from flask import current_app
                current_app.logger.warning('Order conversion succeeded; in-app notification failed')
                flash('Order saved, but the in-app notification could not be delivered.', 'error')
        if req and req.get('email'):
            import emails
            try:
                sent = emails.send_custom_accepted(req['email'], req.get('name',''),
                                                   order['id'], os.environ.get('SITE_URL', 'http://localhost:5000'))
                if not sent:
                    flash('Order saved, but confirmation email was not sent.', 'error')
            except Exception:
                from flask import current_app
                current_app.logger.exception('Order conversion succeeded; confirmation email failed')
                flash('Order saved, but confirmation email failed. You can contact the customer manually.', 'error')
    return redirect(url_for("admin.custom_request_detail", rid=rid))


@admin_bp.route("/custom-requests/<rid>/note", methods=["POST"])
@admin_only
def custom_request_add_note(rid):
    note = request.form.get("note","").strip()
    if note:
        _saved(models.add_custom_internal_note(rid, note), 'Internal note')
    return redirect(url_for("admin.custom_request_detail", rid=rid))


@admin_bp.route("/custom-requests/<rid>/status", methods=["POST"])
@admin_only
def custom_request_status(rid):
    status = request.form.get("status")
    req = models.get_custom_request(rid)
    if not req:
        flash("Custom request not found.", "error")
    elif status not in models.CUSTOM_STATUSES:
        flash("Invalid custom request status.", "error")
    elif status == "converted" and not req.get("converted_order_id"):
        flash("Use Create Order to convert this request; changing the status alone does not create an order.", "error")
    elif req.get("converted_order_id") and status not in ("converted", "closed"):
        flash("This request already has an order and cannot be reverted to a pre-order status.", "error")
    elif not models.update_custom_request(rid, {"status": status}):
        flash("Could not update request status.", "error")
    else:
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
    if subject and message and req.get('email'):
        sent = emails.send_manual_email(req['email'], subject, message)
        if sent:
            try:
                models.log_email(req['email'], subject, message,
                                 session['user_id'], 'custom_request', rid)
            except supa.SupabaseError:
                from flask import current_app
                current_app.logger.exception('Custom request email sent, audit log failed')
            flash('Email sent.', 'success')
        else:
            flash('Email not sent. Verify the SMTP configuration and logs.', 'error')
    else:
        flash('Recipient email, subject and message are required.', 'error')
    return redirect(url_for("admin.custom_request_detail", rid=rid))


@admin_bp.route("/custom-requests/<rid>/create-product", methods=["POST"])
@admin_only
def custom_request_create_product(rid):
    req = models.get_custom_request(rid)
    if not req:
        flash("Request not found.", "error")
        return redirect(url_for("admin.custom_requests"))
    title       = request.form.get("title","").strip()
    price = _number('price', minimum=0.01)
    stock_number = _number('stock', minimum=0)
    if stock_number != int(stock_number):
        raise ValueError('Stock must be a whole number.')
    stock = int(stock_number)
    if not title:
        raise ValueError('A product title is required.')
    category_id = request.form.get('category_id') or None
    if category_id and not models.get_category(category_id):
        raise ValueError('The selected category no longer exists.')
    description = request.form.get("description","").strip()
    is_listed = request.form.get('is_listed') == 'on'
    images = [req["reference_image_url"]] if req.get("reference_image_url") else []
    product = models.create_product({
        "title": title, "price": price, "category_id": category_id,
        "stock": stock, "description": description, "is_listed": is_listed,
        "availability_mode":"READY_TO_SHIP" if stock>0 else "MADE_TO_ORDER",
        "images": images, "crafting_days": int(req.get("quoted_days") or 14),
    })
    if product:
        # The product already exists. Do not suggest retrying its creation if
        # a later link write fails (that would create duplicates).
        try:
            linked = models.update_custom_request(str(req['id']), {
                'linked_product_id': str(product['id']),
                'listed_in_shop': is_listed,
            })
            if not linked:
                raise ValueError('The custom request did not accept the new product link.')
        except (ValueError, supa.SupabaseError) as error:
            flash(f'Product created, but linking failed: {error}. Find it in Products and retry linking.', 'error')
            return redirect(url_for('admin.custom_request_detail', rid=rid))
        # If order already exists, update its order item to link to this product
        if req.get("converted_order_id"):
            oid = str(req["converted_order_id"])
            items = models.get_order_items(oid)
            if items:
                # Update first item to link to the product
                import supa as supa_mod
                try:
                    changed = supa_mod.update('order_items',
                        {'order_id': f'eq.{oid}', 'is_custom': 'eq.true'},
                        {'product_id': str(product['id']), 'title': title,
                         'image_url': images[0] if images else ''})
                    if not changed:
                        flash('Product created and linked; the converted order item could not be updated.', 'error')
                except supa.SupabaseError as error:
                    flash(f'Product created and linked; updating the converted order item failed: {error.admin_detail}', 'error')
        _refresh_catalogue()
        flash(f"Product '{title}' created and linked to this request.", 'success')
    else:
        flash("Could not create product.", "error")
    return redirect(url_for("admin.custom_request_detail", rid=rid))


@admin_bp.route("/custom-requests/<rid>/link-product", methods=["POST"])
@admin_only
def custom_request_link_product(rid):
    product_id = request.form.get("product_id","").strip()
    if not product_id:
        flash("Please select a product.", "error")
        return redirect(url_for("admin.custom_request_detail", rid=rid))

    req = models.get_custom_request(rid)
    if not req:
        raise ValueError('Custom request not found.')
    product = models.get_product(product_id)
    if not product:
        raise ValueError('Selected product does not exist. Refresh and try again.')
    if not models.update_custom_request(rid, {'linked_product_id': product_id}):
        raise ValueError('Could not link the selected product.')
    # Preserve unrelated order lines: only touch the custom item associated
    # with this converted request.
    if req and product and req.get("converted_order_id"):
        oid = str(req["converted_order_id"])
        items = models.get_order_items(oid)
        img = (product.get('images') or [''])[0]
        if items:
            # Update existing item
            import supa as supa_mod
            updated = supa_mod.update('order_items',
                {'order_id': f'eq.{oid}', 'is_custom': 'eq.true'},
                {'product_id': product_id, 'title': product['title'], 'image_url': img})
            if not updated:
                flash('Request linked, but no converted custom order line could be updated.', 'error')
        else:
            # No items yet — create one
            models.create_order_item({
                "order_id":   oid,
                "product_id": product_id,
                "title":      product["title"],
                "price":      float(product.get("price", req.get("quoted_price") or 0)),
                "quantity":   1,
                "image_url":  img,
            })

    flash(f"Linked to '{product['title'] if product else product_id}'! Order items updated.", "success")
    return redirect(url_for("admin.custom_request_detail", rid=rid))


@admin_bp.route("/custom-requests/<rid>/unlink", methods=["POST"])
@admin_only
def custom_request_unlink(rid):
    _saved(models.update_custom_request(rid, {'linked_product_id': None}), 'Product unlink')
    return redirect(url_for("admin.custom_request_detail", rid=rid))


# ── Order Delete ──────────────────────────────────────────


# ── Analytics ─────────────────────────────────────────────

@admin_bp.route("/analytics")
@admin_only
def analytics():
    all_orders = models.get_orders()
    stats = models.get_stats(all_orders=all_orders)
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
    import secrets, string
    code = request.form.get("code", "").strip().upper()
    if not code:
        code = "GIFT-" + "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(12))
    result = models.create_gift_card({
        "code": code,
        "amount": _number('amount', 500, 0.01),
        "issued_to": request.form.get("issued_to", ""),
        "expires_at": request.form.get("expires_at") or None,
    })
    _saved(result, "Gift card")
    return redirect(url_for("admin.gift_cards"))


@admin_bp.route("/gift-cards/<gid>/delete", methods=["POST"])
@admin_only
def gift_card_delete(gid):
    _saved(models.delete_gift_card(gid), "Gift card deletion")
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
        result = models.update_return(rid, {
            "status": request.form.get("status"),
            "admin_note": request.form.get("admin_note", ""),
        })
        _saved(result, "Return")
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
        result = models.create_artisan({
            "name": request.form.get("name", ""),
            "bio": request.form.get("bio", ""),
            "location": request.form.get("location", ""),
            "speciality": request.form.get("speciality", ""),
            "instagram": request.form.get("instagram", ""),
            "image_url": image_url,
            "active": request.form.get("active") == "on",
        })
        if _saved(result, "Artisan"): _refresh_catalogue()
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
        if _saved(models.update_artisan(aid, data), "Artisan"): _refresh_catalogue()
        return redirect(url_for("admin.artisans"))
    return render_template("admin/artisan_form.html", artisan=artisan)


@admin_bp.route("/artisans/<aid>/delete", methods=["POST"])
@admin_only
def artisan_delete(aid):
    if _saved(models.delete_artisan(aid), "Artisan archive"): _refresh_catalogue()
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
    result = models.create_faq({
        "question": request.form.get("question", ""),
        "answer": request.form.get("answer", ""),
        "category": request.form.get("category", "general"),
        "sort_order": int(request.form.get("sort_order", 0)),
        "active": True,
    })
    _saved(result, "FAQ")
    return redirect(url_for("admin.faqs"))


@admin_bp.route("/faqs/<fid>/delete", methods=["POST"])
@admin_only
def faq_delete(fid):
    _saved(models.delete_faq(fid), "FAQ deletion")
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
                delivered = email_mod._send(u["email"], subject,
                    f'<div style="font-family:Georgia,serif;max-width:560px;margin:0 auto;">'
                    f'<h2 style="color:#5c3d3d;">Everbloom</h2>{body}'
                    f'<p style="color:#999;font-size:12px;margin-top:2rem;">You received this because you have an account with Everbloom.</p>'
                    f'</div>')
                sent += int(bool(delivered))
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
    result = models.create_variant({
        "product_id": pid,
        "name": request.form.get("name", ""),
        "value": request.form.get("value", ""),
        "price_modifier": float(request.form.get("price_modifier", 0)),
        "stock": int(request.form.get("stock", 0)),
    })
    if _saved(result, "Variant"): _refresh_catalogue()
    return redirect(url_for("admin.product_edit", pid=pid))


@admin_bp.route("/variants/<vid>/delete", methods=["POST"])
@admin_only
def variant_delete(vid):
    pid = request.form.get("product_id")
    if _saved(models.delete_variant(vid), "Variant deletion"): _refresh_catalogue()
    return redirect(url_for("admin.product_edit", pid=pid))


# ── Settings ─────────────────────────────────────────────

@admin_bp.route("/settings", methods=["GET", "POST"])
@admin_only
def settings():
    if request.method == "POST":
        keys = ["upi_id", "whatsapp_number", "instagram_handle", "store_name", "store_tagline", "business_email", "business_phone", "business_address", "announcement", "hero_eyebrow", "hero_headline", "hero_body", "hero_image", "hero_mobile_image", "hero_primary_label", "hero_secondary_label", "brand_story", "story_headline", "custom_headline", "custom_body", "footer_text", "processing_buffer", "policy_shipping", "policy_returns", "policy_privacy", "policy_terms"]
        values = {key: request.form.get(key, '').strip() for key in keys}
        try:
            _number('processing_buffer', minimum=0)
            qr_file = request.files.get('upi_qr')
            if qr_file and qr_file.filename:
                values['upi_qr_url'] = supa.upload_file('everbloom',
                    f'settings/upi_qr_{uuid.uuid4()}.png', qr_file.read(), qr_file.content_type)
                if not values['upi_qr_url']:
                    raise ValueError('QR code upload failed.')
            _saved(models.save_settings(values), 'Store settings')
        except (ValueError, supa.SupabaseError) as error:
            flash(str(error), 'error')
        return redirect(url_for('admin.settings'))
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
        _saved(models.save_email_template(key, subject, body_html), "Email template")
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
    user = models.get_user_by_id(order["user_id"]) if order.get("user_id") else ({"email":order["email"]} if order.get("email") else None)
    if not user:
        flash("No customer email found.", "error")
        return redirect(url_for("admin.order_detail", oid=oid))

    subject = request.form.get("subject", "").strip()
    message = request.form.get("message", "").strip()

    sent = emails.send_manual_email(user["email"], subject, message)
    if sent:
        try:
            models.log_email(user['email'], subject, message,
                             session['user_id'], 'order', oid)
        except supa.SupabaseError:
            from flask import current_app
            current_app.logger.exception('Order email sent but email log write failed')
    flash('Email sent to customer.' if sent else 'Email could not be delivered. Check SMTP configuration.', 'success' if sent else 'error')
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
    _saved(models.create_raw_material(data), "Material")
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
    _saved(models.update_raw_material(mid, data), "Material")
    return redirect(url_for("admin.inventory"))


@admin_bp.route("/inventory/<int:mid>/delete", methods=["POST"])
@admin_only
def inventory_delete(mid):
    _saved(models.delete_raw_material(mid), "Material archive")
    return redirect(url_for("admin.inventory"))


@admin_bp.route("/inventory/<int:mid>/purchase", methods=["POST"])
@admin_only
def inventory_purchase(mid):
    qty      = float(request.form.get("quantity", 0))
    cpu      = float(request.form.get("cost_per_unit", 0))
    supplier = request.form.get("supplier", "").strip()
    note     = request.form.get("note", "").strip()
    if qty > 0:
        received = models.add_expenditure({
            "material_id":   mid,
            "quantity":      qty,
            "cost_per_unit": cpu,
            "total_cost":    round(qty * cpu, 2),
            "supplier":      supplier,
            "note":          note,
        })
        flash(f"Received {qty} units." if received else "Receiving failed. Stock was not changed.", "success" if received else "error")
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
    _saved(models.create_component(data), "Component")
    return redirect(url_for("admin.components"))

@admin_bp.route("/components/<int:cid>", methods=["GET", "POST"])
@admin_only
def component_detail(cid):
    comp = models.get_component(cid)
    if not comp:
        flash("Component not found.", "error")
        return redirect(url_for("admin.components"))
    materials = models.get_raw_materials()
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
            result = models.update_component(cid, {
                "icon":  request.form.get("icon", comp.get("icon","🔧")),
                "notes": request.form.get("notes", "").strip(),
                "reorder_level": float(request.form.get("reorder_level", 0)),
            })
            _saved(result, 'Component recipe')
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
            result = models.update_component(cid, {
                "name":  request.form.get("name", comp["name"]).strip(),
                "unit":  request.form.get("unit", comp["unit"]),
                "icon":  request.form.get("icon", comp.get("icon","🔧")),
                "reorder_level": float(request.form.get("reorder_level", 0)),
                "notes": request.form.get("notes", "").strip(),
            })
            _saved(result, 'Component')
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
    _saved(models.delete_component(cid), "Component archive")
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
        if not models.save_product_cost(pid, {
            "labour_cost":    float(request.form.get("labour_cost", 0)),
            "overhead_cost":  float(request.form.get("overhead_cost", 0)),
            "margin_percent": float(request.form.get("margin_percent", 30)),
            "notes":          request.form.get("notes", "").strip(),
        }):
            raise ValueError('Could not save the product cost fields.')
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
        if not models.save_product_bom(pid, bom_items):
            raise ValueError('Could not save the product recipe.')
        flash("Cost breakdown saved!", "success")
        return redirect(url_for("admin.product_cost_detail", pid=pid))

    product_cost   = models.get_product_cost(pid)
    product_bom    = models.get_product_bom(pid)
    cost_breakdown = models.calculate_product_bom_cost(
        pid, bom=product_bom, pc=product_cost, materials=materials, components=components)
    return render_template("admin/product_cost_detail.html",
                           product=product, materials=materials,
                           components=components, product_cost=product_cost,
                           product_bom=product_bom, cost_breakdown=cost_breakdown, capacity=models.manufacturable_quantity(pid))


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
    try:
        models.deduct_order_materials(oid)
    except (ValueError, supa.SupabaseError) as error:
        flash(str(error), 'error')
        return redirect(url_for('admin.order_requirements',oid=oid))
    models.add_tracking(oid, order["status"], "Inventory deducted for this order.")
    flash("Stock deducted from inventory!", "success")
    return redirect(url_for("admin.order_requirements", oid=oid))


# ── Legacy alias — old templates may reference this ───────
@admin_bp.route("/custom-requests/<rid>/quote", methods=["POST"])
@admin_only
def custom_request_quote(rid):
    req=models.get_custom_request(rid)
    if not req or req.get('converted_order_id'):
        flash('This request cannot be quoted.','error')
        return redirect(url_for('admin.custom_requests'))
    try:
        amount=money(request.form.get('quoted_price'))
        if amount<=0: raise ValueError('Enter a positive quote.')
        from datetime import datetime,timezone
        import emails
        payload={'quoted_price':float(amount),'quoted_days':max(1,int(request.form.get('quoted_days') or 7)),'quote_message':request.form.get('quote_message','').strip()[:2000],'quote_sent_at':datetime.now(timezone.utc).isoformat(),'status':'quoted'}
        if not models.update_custom_request(rid,payload): raise ValueError('Could not save the quote.')
        track_url=url_for('shop.custom_order_track',token=req['tracking_token'],_external=True)
        sent=emails.send_custom_quote(req['email'],req['name'],{**req,**payload},track_url,track_url)
        flash('Quote saved and emailed.' if sent else 'Quote saved. Email delivery failed; share the request tracking link manually.','success' if sent else 'error')
    except ValueError as error: flash(str(error),'error')
    return redirect(url_for('admin.custom_request_detail',rid=rid))


# ── Order Delete ──────────────────────────────────────────

@admin_bp.route("/orders/<oid>/delete", methods=["POST"])
@admin_only
def order_delete(oid):
    order = models.get_order(oid)
    if not order:
        flash("Order not found.", "error")
        return redirect(url_for("admin.orders"))
    force = request.form.get("force") == "1"
    safe = order.get("status") in ["placed", "cancelled"]
    if not safe and not force:
        flash("Cancel the order first before deleting.", "error")
        return redirect(url_for("admin.order_detail", oid=oid))
    if _saved(models.delete_order(oid), 'Order cancellation'):
        _refresh_catalogue()
    return redirect(url_for("admin.orders"))


@admin_bp.after_request
def audit_admin_action(response):
    if request.method == 'POST' and response.status_code < 400 and session.get('user_id'):
        try:
            supa.insert('audit_log', {'actor_id':session['user_id'], 'action':request.endpoint,
                                      'entity':'admin_request', 'entity_id':str(request.view_args or {}),
                                      'metadata':{'http_status':response.status_code}})
        except supa.SupabaseError:
            # Audit is operational telemetry. Missing migration 002 must never
            # convert a successful mutation into a misleading HTTP 500.
            from flask import current_app
            current_app.logger.exception('Admin audit write failed; check migration 002')
    return response


@admin_bp.route('/stock-movements')
@admin_only
def stock_movements():
    return render_template('admin/stock_movements.html', movements=supa.select('inventory_movements',order='created_at.desc',limit=200))


@admin_bp.route('/audit-log')
@admin_only
def audit_log():
    return render_template('admin/audit_log.html', entries=supa.select('audit_log',order='created_at.desc',limit=200))

MERCHANDISING = {'categories':'Categories','collections':'Collections','occasions':'Occasions','testimonials':'Testimonials'}

@admin_bp.route('/merchandising/<kind>', methods=['GET','POST'])
@admin_only
def merchandising(kind):
    from flask import abort
    import re
    if kind not in MERCHANDISING: abort(404)
    if request.method=='POST':
        action=request.form.get('action','create')
        entry_id=request.form.get('entry_id')
        if action in ('edit','archive','restore'):
            entries=supa.select(kind, {'id':'eq.'+str(entry_id)})
            if not entries:
                flash('Entry not found.','error')
                return redirect(url_for('admin.merchandising',kind=kind))
            if action in ('archive','restore'):
                saved=supa.update(kind, {'id':'eq.'+str(entry_id)}, {'active':action=='restore'})
            else:
                name=request.form.get('name','').strip()[:150]
                if not name:
                    flash('Enter a name.','error')
                    return redirect(url_for('admin.merchandising',kind=kind))
                data={'name':name}
                if kind=='testimonials': data['quote']=request.form.get('quote','').strip()[:2000]
                else: data['slug']=re.sub(r'[^a-z0-9]+','-',(request.form.get('slug') or name).lower()).strip('-')
                if kind=='collections': data['featured']=request.form.get('featured')=='on'
                saved=supa.update(kind, {'id':'eq.'+str(entry_id)},data)
            if _saved(saved, 'Catalogue entry'): _refresh_catalogue()
            return redirect(url_for('admin.merchandising',kind=kind))
        name=request.form.get('name','').strip()[:150]
        if not name: flash('Enter a name.','error')
        else:
            data={'name':name}
            if kind=='testimonials': data['quote']=request.form.get('quote','').strip()[:2000]
            else: data['slug']=re.sub(r'[^a-z0-9]+','-',request.form.get('slug') or name.lower()).strip('-')
            if kind=='collections': data['featured']=request.form.get('featured')=='on'
            saved=supa.insert(kind,data)
            if _saved(saved, 'Catalogue entry'): _refresh_catalogue()
        return redirect(url_for('admin.merchandising',kind=kind))
    entries=supa.select(kind,order='name.asc')
    if kind in ('categories','collections','occasions'):
        entries=models.merchandising_counts(kind, entries=entries)
    return render_template('admin/merchandising.html',kind=kind,title=MERCHANDISING[kind],entries=entries)

@admin_bp.route('/reviews', methods=['GET','POST'])
@admin_only
def reviews():
    if request.method=='POST':
        if _saved(models.update_review(request.form['review_id'],{'visible':request.form.get('visible')=='1'}), "Review"):
            _refresh_catalogue()
        return redirect(url_for('admin.reviews'))
    return render_template('admin/reviews.html',reviews=supa.select('reviews',order='created_at.desc'))


def _catalog_editor_context(pid=None):
    return {'collections':supa.select('collections'),'occasions':supa.select('occasions'),
            'selected_collections':[str(r['collection_id']) for r in supa.select('collection_products',{'product_id':'eq.'+str(pid)})] if pid else [],
            'selected_occasions':[str(r['occasion_id']) for r in supa.select('product_occasions',{'product_id':'eq.'+str(pid)})] if pid else []}


def _save_memberships(pid):
    for kind, table, column in [
        ('collection', 'collection_products', 'collection_id'),
        ('occasion', 'product_occasions', 'occasion_id'),
    ]:
        try:
            ids = {int(key) for key in request.form.getlist(kind + '_ids')}
        except (ValueError, TypeError) as error:
            raise ValueError('Invalid catalogue collection or occasion selection.') from error
        existing = {int(row[column]) for row in supa.select(table, {'product_id': 'eq.' + str(pid)})}
        for old in existing - ids:
            supa.delete(table, {'product_id': 'eq.' + str(pid), column: 'eq.' + str(old)})
        for new in ids - existing:
            if not supa.insert(table, {'product_id': str(pid), column: new}):
                raise ValueError('Failed to link product to ' + kind + '.')
