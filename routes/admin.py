import re
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from models import (Order, Product, Category, User, Tracking, Notification,
                    STATUS_LABELS, STATUS_ICONS, STATUS_KEYS, ORDER_STATUSES)
from emails import send_advance_request, send_advance_confirmed, send_status_update
import storage

admin_bp = Blueprint("admin", __name__)


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            flash("Admin access required.", "error")
            return redirect(url_for("shop.home"))
        return f(*args, **kwargs)
    return decorated


# ── Dashboard ─────────────────────────────────────────────────
@admin_bp.route("/")
@admin_required
def dashboard():
    stats        = Order.dashboard_stats()
    recent, _    = Order.admin_list(page=1, per_page=10)
    _, total_products = Product.admin_list(page=1, per_page=1)
    total_customers = User.count_customers()
    return render_template("admin/dashboard.html",
                           stats=stats, recent_orders=recent,
                           total_products=total_products,
                           total_customers=total_customers,
                           STATUS_LABELS=STATUS_LABELS, STATUS_ICONS=STATUS_ICONS)


# ── Orders ────────────────────────────────────────────────────
@admin_bp.route("/orders")
@admin_required
def orders():
    status = request.args.get("status", "")
    q      = request.args.get("q", "").strip()
    page   = request.args.get("page", 1, type=int)
    rows, total = Order.admin_list(status=status or None, search=q or None, page=page)
    import math
    total_pages = math.ceil(total / 20) if total else 1
    return render_template("admin/orders.html",
                           orders=rows, total=total, page=page, total_pages=total_pages,
                           status_filter=status, q=q,
                           STATUS_LABELS=STATUS_LABELS, STATUS_ICONS=STATUS_ICONS,
                           ORDER_STATUSES=ORDER_STATUSES)


@admin_bp.route("/orders/<int:order_id>")
@admin_required
def order_detail(order_id):
    order  = Order.get(order_id)
    if not order:
        flash("Order not found.", "error")
        return redirect(url_for("admin.orders"))
    events = Tracking.list(order_id)
    items  = Order.items(order_id)
    return render_template("admin/order_detail.html",
                           order=order, events=events, items=items,
                           STATUS_LABELS=STATUS_LABELS, STATUS_ICONS=STATUS_ICONS,
                           STATUS_KEYS=STATUS_KEYS, ORDER_STATUSES=ORDER_STATUSES)


@admin_bp.route("/orders/<int:order_id>/update", methods=["POST"])
@admin_required
def order_update(order_id):
    order      = Order.get(order_id)
    if not order:
        flash("Order not found.", "error")
        return redirect(url_for("admin.orders"))
    new_status   = request.form.get("status")
    admin_note   = request.form.get("admin_note", "").strip()
    advance_amt  = request.form.get("advance_amount", type=float)

    if new_status not in STATUS_KEYS:
        flash("Invalid status.", "error")
        return redirect(url_for("admin.order_detail", order_id=order_id))

    Order.update_status(order_id, new_status, admin_note or None, advance_amt)
    Tracking.add(order_id, new_status, admin_note or None, current_user.id)
    Notification.add(order["customer_id"], order_id,
                     f"Order Update: {STATUS_LABELS[new_status]}",
                     admin_note or f"Your order status: {STATUS_LABELS[new_status]}")

    # Re-fetch for email (has updated fields now)
    updated = Order.get(order_id)
    try:
        if new_status == "advance_requested":
            send_advance_request(updated)
        elif new_status == "advance_confirmed":
            send_advance_confirmed(updated)
        elif new_status in ("accepted", "material_sourced", "crafting", "quality_check",
                            "packed", "shipped", "delivered", "cancelled"):
            send_status_update(updated, admin_note)
    except Exception as e:
        current_app.logger.error(f"Email failed for order {order_id}: {e}")
        flash(f"Status updated but email failed: {e}", "warning")
        return redirect(url_for("admin.order_detail", order_id=order_id))

    flash(f'Order updated to "{STATUS_LABELS[new_status]}" — email sent!', "success")
    return redirect(url_for("admin.order_detail", order_id=order_id))


# ── Products ──────────────────────────────────────────────────
@admin_bp.route("/products")
@admin_required
def products():
    q      = request.args.get("q", "").strip()
    cat_id = request.args.get("cat", type=int)
    page   = request.args.get("page", 1, type=int)
    rows, total = Product.admin_list(search=q or None, category_id=cat_id, page=page)
    import math
    total_pages = math.ceil(total / 20) if total else 1
    categories  = Category.all()
    return render_template("admin/products.html",
                           products=rows, total=total, page=page,
                           total_pages=total_pages, categories=categories,
                           q=q, cat_id=cat_id)


@admin_bp.route("/products/new", methods=["GET", "POST"])
@admin_required
def product_new():
    categories = Category.all()
    if request.method == "POST":
        pid = _save_product(None, request)
        if pid:
            flash("Product created!", "success")
            return redirect(url_for("admin.products"))
    return render_template("admin/product_form.html", product=None, categories=categories)


@admin_bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def product_edit(product_id):
    product    = Product.get(product_id, active_only=False)
    categories = Category.all()
    if request.method == "POST":
        if _save_product(product, request):
            flash("Product updated!", "success")
            return redirect(url_for("admin.products"))
    return render_template("admin/product_form.html", product=product, categories=categories)


@admin_bp.route("/products/<int:product_id>/delete", methods=["POST"])
@admin_required
def product_delete(product_id):
    Product.hide(product_id)
    flash("Product hidden from shop.", "info")
    return redirect(url_for("admin.products"))


def _save_product(product, req):
    title       = req.form.get("title", "").strip()
    description = req.form.get("description", "").strip()
    category_id = req.form.get("category_id", type=int)
    price       = req.form.get("price", type=float)
    discount    = req.form.get("discount_percent", 0, type=int)
    stock       = req.form.get("stock_qty", 0, type=int)
    tags        = req.form.get("tags", "")
    is_featured = bool(req.form.get("is_featured"))
    is_active   = bool(req.form.get("is_active"))

    if not title or not price or not category_id:
        flash("Title, price, and category are required.", "error")
        return None

    # Slug
    slug_base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    import time
    slug = f"{slug_base}-{int(time.time())}"

    # Existing images (URLs)
    existing = [i for i in req.form.get("existing_images", "").split(",") if i.strip()]

    # New image uploads → Supabase Storage
    pid = product["id"] if product else None
    new_urls = []
    files = req.files.getlist("images")
    for i, file in enumerate(files):
        if file and file.filename:
            idx = len(existing) + i
            url = storage.upload_product_image(file, pid or 0, idx)
            if url:
                new_urls.append(url)

    images_csv = ",".join(existing + new_urls)

    data = dict(title=title, slug=slug, description=description,
                category_id=category_id, price=price,
                discount_percent=max(0, min(100, discount)),
                stock_qty=max(0, stock), tags=tags,
                is_featured=is_featured, is_active=is_active, images=images_csv)

    if product:
        Product.update(product["id"], data)
        return product["id"]
    else:
        return Product.create(data)


# ── Customers ─────────────────────────────────────────────────
@admin_bp.route("/customers")
@admin_required
def customers():
    q    = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    rows, total = User.list_customers(search=q or None, page=page)
    import math
    total_pages = math.ceil(total / 20) if total else 1
    return render_template("admin/customers.html",
                           customers=rows, total=total, page=page,
                           total_pages=total_pages, q=q)


# ── Settings ──────────────────────────────────────────────────
@admin_bp.route("/settings", methods=["GET", "POST"])
@admin_required
def settings():
    if request.method == "POST":
        file = request.files.get("qr_code")
        if file and file.filename:
            url = storage.upload_qr_code(file)
            if url:
                current_app.config["QR_CODE_URL"] = url
                flash(f"QR code uploaded!", "success")
            else:
                flash("QR upload failed — check Supabase Storage config.", "error")
        upi = request.form.get("upi_id", "").strip()
        if upi:
            current_app.config["UPI_ID"] = upi
            flash("UPI ID updated for this session. Set UPI_ID in Vercel env vars for permanent change.", "info")
        return redirect(url_for("admin.settings"))

    qr_url = current_app.config.get("QR_CODE_URL") or \
             (storage.get_public_url(storage.QR_BUCKET, "upi_qr.png") if storage.SUPABASE_URL else None)
    return render_template("admin/settings.html",
                           qr_url=qr_url,
                           upi_id=current_app.config.get("UPI_ID", ""))
