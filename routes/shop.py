import os
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify, current_app
from flask_login import current_user
from models import Product, Category, Order, OrderItem, TrackingEvent, Notification
from app import db

shop_bp = Blueprint('shop', __name__)


# ── Helpers ───────────────────────────────────────────────────────────────────
def get_cart():
    return session.get('cart', {})

def save_cart(cart):
    session['cart'] = cart
    session.modified = True

def cart_total(cart):
    return sum(item['price'] * item['qty'] for item in cart.values())


# ── Home ──────────────────────────────────────────────────────────────────────
@shop_bp.route('/')
def home():
    categories = Category.query.all()
    featured   = Product.query.filter_by(is_active=True, is_featured=True).limit(4).all()
    new_items  = Product.query.filter_by(is_active=True).order_by(Product.created_at.desc()).limit(4).all()
    return render_template('shop/home.html',
                           categories=categories,
                           featured=featured,
                           new_items=new_items)


# ── Shop listing ──────────────────────────────────────────────────────────────
@shop_bp.route('/shop')
def shop():
    q          = request.args.get('q', '').strip()
    cat_slug   = request.args.get('category', '')
    sort       = request.args.get('sort', 'newest')
    min_price  = request.args.get('min_price', type=float)
    max_price  = request.args.get('max_price', type=float)
    in_stock   = request.args.get('in_stock', type=int, default=0)
    on_sale    = request.args.get('on_sale', type=int, default=0)
    page       = request.args.get('page', 1, type=int)

    query = Product.query.filter_by(is_active=True)

    if q:
        query = query.filter(Product.title.ilike(f'%{q}%') | Product.description.ilike(f'%{q}%'))

    selected_cat = None
    if cat_slug:
        selected_cat = Category.query.filter_by(slug=cat_slug).first()
        if selected_cat:
            query = query.filter_by(category_id=selected_cat.id)

    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)
    if in_stock:
        query = query.filter(Product.stock_qty > 0)
    if on_sale:
        query = query.filter(Product.discount_percent > 0)

    if sort == 'price_asc':
        query = query.order_by(Product.price.asc())
    elif sort == 'price_desc':
        query = query.order_by(Product.price.desc())
    elif sort == 'discount':
        query = query.order_by(Product.discount_percent.desc())
    else:
        query = query.order_by(Product.created_at.desc())

    pagination = query.paginate(page=page, per_page=12, error_out=False)
    categories = Category.query.all()

    return render_template('shop/shop.html',
                           products=pagination.items,
                           pagination=pagination,
                           categories=categories,
                           selected_cat=selected_cat,
                           q=q, sort=sort,
                           min_price=min_price, max_price=max_price,
                           in_stock=in_stock, on_sale=on_sale)


# ── Product detail ────────────────────────────────────────────────────────────
@shop_bp.route('/product/<int:product_id>')
def product(product_id):
    p = Product.query.filter_by(id=product_id, is_active=True).first_or_404()
    related = Product.query.filter(
        Product.category_id == p.category_id,
        Product.id != p.id,
        Product.is_active == True
    ).limit(4).all()
    return render_template('shop/product.html', product=p, related=related)


# ── Cart ──────────────────────────────────────────────────────────────────────
@shop_bp.route('/cart')
def cart():
    cart = get_cart()
    total = cart_total(cart)
    return render_template('shop/cart.html', cart=cart, total=total)


@shop_bp.route('/cart/add', methods=['POST'])
def cart_add():
    product_id = request.form.get('product_id', type=int)
    qty        = request.form.get('qty', 1, type=int)
    p = Product.query.filter_by(id=product_id, is_active=True).first_or_404()

    cart = get_cart()
    key  = str(product_id)

    if key in cart:
        cart[key]['qty'] = min(cart[key]['qty'] + qty, p.stock_qty)
    else:
        cart[key] = {
            'id': p.id, 'title': p.title,
            'price': p.final_price,
            'image': p.first_image or '',
            'stock_qty': p.stock_qty,
            'qty': min(qty, p.stock_qty)
        }
    save_cart(cart)
    flash(f'"{p.title}" added to cart!', 'success')
    return redirect(request.referrer or url_for('shop.cart'))


@shop_bp.route('/cart/update', methods=['POST'])
def cart_update():
    product_id = request.form.get('product_id')
    qty        = request.form.get('qty', type=int)
    cart = get_cart()
    key  = str(product_id)
    if key in cart:
        if qty and qty > 0:
            cart[key]['qty'] = min(qty, cart[key]['stock_qty'])
        else:
            del cart[key]
    save_cart(cart)
    return redirect(url_for('shop.cart'))


@shop_bp.route('/cart/remove/<int:product_id>', methods=['POST'])
def cart_remove(product_id):
    cart = get_cart()
    cart.pop(str(product_id), None)
    save_cart(cart)
    flash('Item removed from cart.', 'info')
    return redirect(url_for('shop.cart'))


@shop_bp.route('/cart/clear', methods=['POST'])
def cart_clear():
    session.pop('cart', None)
    return redirect(url_for('shop.cart'))


# ── Checkout ──────────────────────────────────────────────────────────────────
@shop_bp.route('/checkout', methods=['GET', 'POST'])
def checkout():
    from flask_login import login_required
    if not current_user.is_authenticated:
        flash('Please log in to checkout.', 'info')
        return redirect(url_for('auth.login', next=url_for('shop.checkout')))

    cart = get_cart()
    if not cart:
        flash('Your cart is empty.', 'info')
        return redirect(url_for('shop.shop'))

    total = cart_total(cart)

    if request.method == 'POST':
        addr_name  = request.form.get('addr_name', '').strip()
        addr_phone = request.form.get('addr_phone', '').strip()
        addr_street= request.form.get('addr_street', '').strip()
        addr_city  = request.form.get('addr_city', '').strip()
        addr_state = request.form.get('addr_state', '').strip()
        addr_pin   = request.form.get('addr_pin', '').strip()
        notes      = request.form.get('notes', '').strip()

        if not all([addr_name, addr_phone, addr_street, addr_city, addr_state, addr_pin]):
            flash('Please fill in all address fields.', 'error')
            return render_template('shop/checkout.html', cart=cart, total=total)

        # Create order
        order = Order(
            customer_id=current_user.id,
            total_amount=total,
            addr_name=addr_name, addr_phone=addr_phone,
            addr_street=addr_street, addr_city=addr_city,
            addr_state=addr_state, addr_pin=addr_pin,
            notes=notes,
            status='draft'
        )
        db.session.add(order)
        db.session.flush()  # get order.id

        # Create items + deduct stock
        for key, item in cart.items():
            p = Product.query.get(item['id'])
            oi = OrderItem(
                order_id=order.id,
                product_id=item['id'],
                quantity=item['qty'],
                unit_price=item['price'],
                title_snap=item['title'],
                image_snap=item['image'],
            )
            db.session.add(oi)
            if p:
                p.stock_qty = max(0, p.stock_qty - item['qty'])

        # First tracking event
        te = TrackingEvent(order_id=order.id, status='draft',
                           note='Order placed. Our team will review it shortly.',
                           created_by=current_user.id)
        db.session.add(te)

        # Notification
        notif = Notification(
            user_id=current_user.id, order_id=order.id,
            title='Order Received 📋',
            message=f'Order #{order.id:04d} placed. We\'ll review and confirm soon.'
        )
        db.session.add(notif)
        db.session.commit()

        # Send email
        from emails import send_order_received
        send_order_received(order)

        # Clear cart
        session.pop('cart', None)

        flash('Order placed! We\'ll review it and be in touch soon. 🌸', 'success')
        return redirect(url_for('orders.track', order_id=order.id))

    # Pre-fill address from profile
    pre = dict(
        addr_name=current_user.full_name,
        addr_phone=current_user.phone or '',
        addr_street='', addr_city='', addr_state='', addr_pin=''
    )
    return render_template('shop/checkout.html', cart=cart, total=total, pre=pre)


# ── Notifications (AJAX) ──────────────────────────────────────────────────────
@shop_bp.route('/notifications')
def notifications():
    from flask_login import current_user
    if not current_user.is_authenticated:
        return jsonify([])
    notifs = Notification.query.filter_by(user_id=current_user.id)\
                .order_by(Notification.created_at.desc()).limit(10).all()
    return jsonify([{
        'id': n.id, 'title': n.title, 'message': n.message,
        'is_read': n.is_read, 'order_id': n.order_id,
        'created_at': n.created_at.strftime('%d %b %Y, %I:%M %p')
    } for n in notifs])


@shop_bp.route('/notifications/read/<int:notif_id>', methods=['POST'])
def notification_read(notif_id):
    from flask_login import current_user
    n = Notification.query.filter_by(id=notif_id, user_id=current_user.id).first()
    if n:
        n.is_read = True
        db.session.commit()
    return jsonify({'ok': True})


@shop_bp.route('/notifications/read-all', methods=['POST'])
def notifications_read_all():
    from flask_login import current_user
    if current_user.is_authenticated:
        Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
        db.session.commit()
    return jsonify({'ok': True})


@shop_bp.route('/notifications/count')
def notification_count():
    from flask_login import current_user
    if not current_user.is_authenticated:
        return jsonify({'count': 0})
    count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({'count': count})
