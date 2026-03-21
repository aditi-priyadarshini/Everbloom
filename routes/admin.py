import re, math, time
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from models import Order, Product, Category, User, Tracking, Notification, STATUS_KEYS, STATUS_LABELS, STATUS_ICONS, STATUSES
from emails import mail_advance_request, mail_advance_confirmed, mail_status_update
import storage

bp = Blueprint("admin", __name__)


def admin_only(f):
    @wraps(f)
    @login_required
    def wrap(*a, **kw):
        if not current_user.is_admin:
            flash("Admin access required.", "error")
            return redirect(url_for("shop.home"))
        return f(*a, **kw)
    return wrap


# ── Dashboard ─────────────────────────────────────────────────
@bp.route("/")
@admin_only
def dashboard():
    stats = Order.stats()
    recent, _ = Order.admin_list(page=1, per=8)
    _, total_products = Product.admin_list(per=1)
    _, total_customers = User.all_customers(per=1)
    return render_template("admin/dashboard.html", stats=stats, recent=recent,
                           total_products=total_products, total_customers=total_customers,
                           STATUS_LABELS=STATUS_LABELS, STATUS_ICONS=STATUS_ICONS)


# ── Orders ────────────────────────────────────────────────────
@bp.route("/orders")
@admin_only
def orders():
    status = request.args.get("status", "")
    q      = request.args.get("q", "").strip()
    page   = request.args.get("page", 1, type=int)
    rows, total = Order.admin_list(status=status, q=q, page=page)
    pages = math.ceil(total / 20) if total else 1
    return render_template("admin/orders.html", orders=rows, total=total,
                           page=page, pages=pages, status=status, q=q,
                           STATUS_LABELS=STATUS_LABELS, STATUS_ICONS=STATUS_ICONS, STATUSES=STATUSES)


@bp.route("/orders/<int:oid>")
@admin_only
def order_detail(oid):
    o = Order.get(oid)
    if not o:
        flash("Order not found.", "error")
        return redirect(url_for("admin.orders"))
    events = Tracking.for_order(oid)
    items  = Order.items(oid)
    return render_template("admin/order_detail.html", o=o, events=events, items=items,
                           STATUS_LABELS=STATUS_LABELS, STATUS_ICONS=STATUS_ICONS,
                           STATUS_KEYS=STATUS_KEYS, STATUSES=STATUSES)


@bp.route("/orders/<int:oid>/update", methods=["POST"])
@admin_only
def order_update(oid):
    o          = Order.get(oid)
    new_status = request.form.get("status")
    note       = request.form.get("note", "").strip()
    advance    = request.form.get("advance", type=float)

    if not o or new_status not in STATUS_KEYS:
        flash("Invalid.", "error")
        return redirect(url_for("admin.orders"))

    Order.set_status(oid, new_status, note, advance if new_status == "advance_requested" else None)
    Tracking.add(oid, new_status, note)
    Notification.add(o["customer_id"], oid,
                     f"Update: {STATUS_LABELS[new_status]}",
                     note or f"Your order status: {STATUS_LABELS[new_status]}")

    fresh = Order.get(oid)
    try:
        if new_status == "advance_requested":
            mail_advance_request(fresh)
        elif new_status == "advance_confirmed":
            mail_advance_confirmed(fresh)
        elif new_status in ("crafting","quality_check","shipped","delivered","cancelled"):
            mail_status_update(fresh, note)
    except Exception as e:
        current_app.logger.error(f"Email failed {oid}: {e}")
        flash(f"Status updated but email failed: {e}", "warning")
        return redirect(url_for("admin.order_detail", oid=oid))

    flash(f'Order updated → "{STATUS_LABELS[new_status]}" — email sent!', "success")
    return redirect(url_for("admin.order_detail", oid=oid))


# ── Products ──────────────────────────────────────────────────
@bp.route("/products")
@admin_only
def products():
    q      = request.args.get("q","").strip()
    cat_id = request.args.get("cat", type=int)
    page   = request.args.get("page", 1, type=int)
    rows, total = Product.admin_list(q=q, cat_id=cat_id, page=page)
    pages = math.ceil(total / 20) if total else 1
    cats  = Category.all()
    return render_template("admin/products.html", products=rows, total=total,
                           page=page, pages=pages, cats=cats, q=q, sel_cat=cat_id)


@bp.route("/products/new", methods=["GET","POST"])
@admin_only
def product_new():
    cats = Category.all()
    if request.method == "POST":
        pid = _save(None)
        if pid:
            flash("Product created!", "success")
            return redirect(url_for("admin.products"))
    return render_template("admin/product_form.html", p=None, cats=cats)


@bp.route("/products/<int:pid>/edit", methods=["GET","POST"])
@admin_only
def product_edit(pid):
    p    = Product.get(pid, active_only=False)
    cats = Category.all()
    if not p:
        return redirect(url_for("admin.products"))
    if request.method == "POST":
        if _save(p):
            flash("Product updated!", "success")
            return redirect(url_for("admin.products"))
    return render_template("admin/product_form.html", p=p, cats=cats)


@bp.route("/products/<int:pid>/delete", methods=["POST"])
@admin_only
def product_delete(pid):
    Product.hide(pid)
    flash("Product hidden.", "info")
    return redirect(url_for("admin.products"))


def _save(p):
    title    = request.form.get("title","").strip()
    desc     = request.form.get("description","").strip()
    cat_id   = request.form.get("category_id", type=int)
    price    = request.form.get("price", type=float)
    discount = max(0, min(100, request.form.get("discount_percent", 0, type=int)))
    stock    = max(0, request.form.get("stock_qty", 0, type=int))
    tags     = request.form.get("tags","").strip()
    featured = bool(request.form.get("is_featured"))
    active   = bool(request.form.get("is_active"))

    if not title or not price or not cat_id:
        flash("Title, price and category are required.", "error")
        return None

    # Handle images
    existing = [i for i in request.form.get("existing_images","").split(",") if i.strip()]
    new_urls = []
    pid_for_storage = p["id"] if p else int(time.time())
    for i, f in enumerate(request.files.getlist("images")):
        if f and f.filename:
            url = storage.upload_product_image(f, pid_for_storage, len(existing)+i)
            if url:
                new_urls.append(url)

    images = ",".join(existing + new_urls)
    data   = dict(title=title, description=desc, price=price, discount_percent=discount,
                  images=images, category_id=cat_id, stock_qty=stock,
                  is_featured=featured, is_active=active, tags=tags)
    if p:
        Product.update(p["id"], data)
        return p["id"]
    return Product.create(data)


# ── Customers ─────────────────────────────────────────────────
@bp.route("/customers")
@admin_only
def customers():
    q    = request.args.get("q","").strip()
    page = request.args.get("page", 1, type=int)
    rows, total = User.all_customers(search=q, page=page)
    pages = math.ceil(total/20) if total else 1
    return render_template("admin/customers.html", customers=rows, total=total,
                           page=page, pages=pages, q=q)


# ── Settings ──────────────────────────────────────────────────
@bp.route("/settings", methods=["GET","POST"])
@admin_only
def settings():
    if request.method == "POST":
        f = request.files.get("qr")
        if f and f.filename:
            url = storage.upload_qr(f)
            if url:
                current_app.config["QR_URL"] = url
                flash("QR code updated!", "success")
            else:
                flash("Upload failed — check Supabase Storage config.", "error")
        upi = request.form.get("upi","").strip()
        if upi:
            current_app.config["UPI_ID"] = upi
            flash("UPI ID updated for this session. Set UPI_ID in Vercel env vars to make it permanent.", "info")
        return redirect(url_for("admin.settings"))
    qr_url = current_app.config.get("QR_URL","")
    return render_template("admin/settings.html", qr_url=qr_url, upi=current_app.config.get("UPI_ID",""))
