import os
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from functools import wraps
from werkzeug.utils import secure_filename
from models import (Order, OrderItem, Product, Category, User, TrackingEvent,
                    Notification, STATUS_LABELS, STATUS_ICONS, ORDER_STATUSES, STATUS_KEYS)
from app import db
from emails import (send_advance_request, send_advance_confirmed,
                    send_status_update, send_order_received)

admin_bp = Blueprint('admin', __name__)

ALLOWED = {'png', 'jpg', 'jpeg', 'webp', 'gif'}


def allowed_file(f):
    return '.' in f and f.rsplit('.', 1)[1].lower() in ALLOWED


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            flash('Admin access required.', 'error')
            return redirect(url_for('shop.home'))
        return f(*args, **kwargs)
    return decorated


# ── Dashboard ─────────────────────────────────────────────────────────────────
@admin_bp.route('/')
@admin_required
def dashboard():
    total_orders    = Order.query.count()
    pending_review  = Order.query.filter_by(status='draft').count()
    advance_pending = Order.query.filter_by(status='advance_paid').count()
    in_progress     = Order.query.filter(Order.status.in_(
        ['advance_confirmed', 'accepted', 'material_sourced', 'crafting', 'quality_check'])).count()
    shipped         = Order.query.filter_by(status='shipped').count()
    delivered       = Order.query.filter_by(status='delivered').count()
    total_customers = User.query.filter_by(role='customer').count()
    total_products  = Product.query.filter_by(is_active=True).count()

    from sqlalchemy import func
    revenue = db.session.query(func.sum(Order.total_amount))\
                .filter(Order.status.in_(['delivered', 'shipped', 'packed']))\
                .scalar() or 0

    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(10).all()

    return render_template('admin/dashboard.html',
                           total_orders=total_orders,
                           pending_review=pending_review,
                           advance_pending=advance_pending,
                           in_progress=in_progress,
                           shipped=shipped,
                           delivered=delivered,
                           total_customers=total_customers,
                           total_products=total_products,
                           revenue=revenue,
                           recent_orders=recent_orders,
                           STATUS_LABELS=STATUS_LABELS,
                           STATUS_ICONS=STATUS_ICONS)


# ── Orders list ───────────────────────────────────────────────────────────────
@admin_bp.route('/orders')
@admin_required
def orders():
    status_filter = request.args.get('status', '')
    q             = request.args.get('q', '').strip()
    page          = request.args.get('page', 1, type=int)

    query = Order.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    if q:
        query = query.join(User).filter(
            User.full_name.ilike(f'%{q}%') | User.email.ilike(f'%{q}%')
        )

    pagination = query.order_by(Order.created_at.desc()).paginate(page=page, per_page=20, error_out=False)

    return render_template('admin/orders.html',
                           orders=pagination.items,
                           pagination=pagination,
                           status_filter=status_filter,
                           q=q,
                           STATUS_LABELS=STATUS_LABELS,
                           STATUS_ICONS=STATUS_ICONS,
                           ORDER_STATUSES=ORDER_STATUSES)


# ── Order detail / management ─────────────────────────────────────────────────
@admin_bp.route('/orders/<int:order_id>')
@admin_required
def order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    events = order.tracking.order_by(TrackingEvent.created_at.asc()).all()

    return render_template('admin/order_detail.html',
                           order=order,
                           events=events,
                           STATUS_LABELS=STATUS_LABELS,
                           STATUS_ICONS=STATUS_ICONS,
                           ORDER_STATUSES=ORDER_STATUSES,
                           STATUS_KEYS=STATUS_KEYS)


@admin_bp.route('/orders/<int:order_id>/update-status', methods=['POST'])
@admin_required
def order_update_status(order_id):
    order      = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')
    admin_note = request.form.get('admin_note', '').strip()
    advance_amt= request.form.get('advance_amount', type=float)

    if new_status not in STATUS_KEYS:
        flash('Invalid status.', 'error')
        return redirect(url_for('admin.order_detail', order_id=order_id))

    old_status = order.status
    order.status = new_status
    if admin_note:
        order.admin_note = admin_note

    # Set advance amount when requesting advance payment
    if new_status == 'advance_requested' and advance_amt:
        order.advance_amount = advance_amt

    # Set delivered_at
    if new_status == 'delivered':
        from datetime import datetime
        order.delivered_at = datetime.utcnow()

    # Tracking event
    te = TrackingEvent(
        order_id=order.id,
        status=new_status,
        note=admin_note or None,
        created_by=current_user.id
    )
    db.session.add(te)

    # Customer notification
    notif = Notification(
        user_id=order.customer_id,
        order_id=order.id,
        title=f'Order Update: {STATUS_LABELS[new_status]}',
        message=admin_note or f'Your order status has been updated to: {STATUS_LABELS[new_status]}'
    )
    db.session.add(notif)
    db.session.commit()

    # Send the right email
    try:
        if new_status == 'advance_requested':
            send_advance_request(order)
        elif new_status == 'advance_confirmed':
            send_advance_confirmed(order)
        elif new_status in ('accepted', 'material_sourced', 'crafting', 'quality_check',
                            'packed', 'shipped', 'delivered', 'cancelled'):
            send_status_update(order, admin_note)
    except Exception as e:
        current_app.logger.error(f'Email failed for order {order_id}: {e}')
        flash(f'Status updated but email failed: {e}', 'warning')
        return redirect(url_for('admin.order_detail', order_id=order_id))

    flash(f'Order updated to "{STATUS_LABELS[new_status]}" — email sent!', 'success')
    return redirect(url_for('admin.order_detail', order_id=order_id))


@admin_bp.route('/orders/<int:order_id>/view-proof/<proof_type>')
@admin_required
def view_proof(order_id, proof_type):
    from flask import send_from_directory
    order = Order.query.get_or_404(order_id)
    filename = order.advance_proof if proof_type == 'advance' else order.final_proof
    if not filename:
        flash('No proof uploaded.', 'info')
        return redirect(url_for('admin.order_detail', order_id=order_id))
    return send_from_directory(
        os.path.join(current_app.config['UPLOAD_FOLDER'], 'payments'),
        filename
    )


# ── Products ──────────────────────────────────────────────────────────────────
@admin_bp.route('/products')
@admin_required
def products():
    q       = request.args.get('q', '')
    cat_id  = request.args.get('cat', type=int)
    page    = request.args.get('page', 1, type=int)

    query = Product.query
    if q:
        query = query.filter(Product.title.ilike(f'%{q}%'))
    if cat_id:
        query = query.filter_by(category_id=cat_id)

    pagination = query.order_by(Product.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    categories = Category.query.all()

    return render_template('admin/products.html',
                           products=pagination.items,
                           pagination=pagination,
                           categories=categories,
                           q=q, cat_id=cat_id)


@admin_bp.route('/products/new', methods=['GET', 'POST'])
@admin_required
def product_new():
    categories = Category.query.all()

    if request.method == 'POST':
        product = _save_product(None, request)
        if product:
            flash(f'Product "{product.title}" created!', 'success')
            return redirect(url_for('admin.products'))

    return render_template('admin/product_form.html', product=None, categories=categories)


@admin_bp.route('/products/<int:product_id>/edit', methods=['GET', 'POST'])
@admin_required
def product_edit(product_id):
    product    = Product.query.get_or_404(product_id)
    categories = Category.query.all()

    if request.method == 'POST':
        updated = _save_product(product, request)
        if updated:
            flash('Product updated!', 'success')
            return redirect(url_for('admin.products'))

    return render_template('admin/product_form.html', product=product, categories=categories)


@admin_bp.route('/products/<int:product_id>/delete', methods=['POST'])
@admin_required
def product_delete(product_id):
    product = Product.query.get_or_404(product_id)
    product.is_active = False
    db.session.commit()
    flash(f'"{product.title}" hidden from shop.', 'info')
    return redirect(url_for('admin.products'))


def _save_product(product, req):
    title       = req.form.get('title', '').strip()
    description = req.form.get('description', '').strip()
    category_id = req.form.get('category_id', type=int)
    price       = req.form.get('price', type=float)
    discount    = req.form.get('discount_percent', 0, type=int)
    stock       = req.form.get('stock_qty', 0, type=int)
    tags        = req.form.get('tags', '')
    is_featured = bool(req.form.get('is_featured'))
    is_active   = bool(req.form.get('is_active'))

    if not title or not price or not category_id:
        flash('Title, price, and category are required.', 'error')
        return None

    if product is None:
        product = Product()
        db.session.add(product)

    product.title            = title
    product.description      = description
    product.category_id      = category_id
    product.price            = price
    product.discount_percent = max(0, min(100, discount))
    product.stock_qty        = max(0, stock)
    product.tags             = tags
    product.is_featured      = is_featured
    product.is_active        = is_active

    # Slug
    import re
    slug_base = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    slug = slug_base
    counter = 1
    while True:
        existing = Product.query.filter_by(slug=slug).first()
        if not existing or existing.id == product.id:
            break
        slug = f'{slug_base}-{counter}'
        counter += 1
    product.slug = slug

    # Handle image uploads
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'products')
    existing_images = [i for i in (req.form.get('existing_images', '')).split(',') if i.strip()]
    new_images = []

    for file in req.files.getlist('images'):
        if file and file.filename and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = secure_filename(f'p{product.id or "new"}_{len(existing_images)+len(new_images)+1}.{ext}')
            file.save(os.path.join(upload_dir, filename))
            new_images.append(filename)

    product.images = ','.join(existing_images + new_images)
    db.session.commit()
    return product


# ── Customers ─────────────────────────────────────────────────────────────────
@admin_bp.route('/customers')
@admin_required
def customers():
    page  = request.args.get('page', 1, type=int)
    q     = request.args.get('q', '')
    query = User.query.filter_by(role='customer')
    if q:
        query = query.filter(User.full_name.ilike(f'%{q}%') | User.email.ilike(f'%{q}%'))
    pagination = query.order_by(User.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/customers.html', customers=pagination.items,
                           pagination=pagination, q=q)


# ── QR code upload ────────────────────────────────────────────────────────────
@admin_bp.route('/settings', methods=['GET', 'POST'])
@admin_required
def settings():
    qr_exists = os.path.exists(
        os.path.join(current_app.config['UPLOAD_FOLDER'], 'qr', 'upi_qr.png')
    )
    if request.method == 'POST':
        file = request.files.get('qr_code')
        if file and file.filename and allowed_file(file.filename):
            path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'qr', 'upi_qr.png')
            file.save(path)
            flash('QR code updated!', 'success')
        upi_id = request.form.get('upi_id', '').strip()
        if upi_id:
            # Write to .env at runtime (simple approach)
            current_app.config['UPI_ID'] = upi_id
            flash('UPI ID updated for this session. Add UPI_ID to .env for permanent change.', 'info')
        return redirect(url_for('admin.settings'))

    return render_template('admin/settings.html', qr_exists=qr_exists,
                           upi_id=current_app.config.get('UPI_ID', ''))
