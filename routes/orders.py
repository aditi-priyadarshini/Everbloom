import os
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import Order, Notification, TrackingEvent, STATUS_KEYS, STATUS_LABELS, STATUS_ICONS, ORDER_STATUSES
from app import db

orders_bp = Blueprint('orders', __name__)

ALLOWED = {'png', 'jpg', 'jpeg', 'webp', 'gif'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED


@orders_bp.route('/')
@login_required
def my_orders():
    orders = Order.query.filter_by(customer_id=current_user.id)\
                  .order_by(Order.created_at.desc()).all()
    return render_template('shop/orders.html', orders=orders,
                           STATUS_LABELS=STATUS_LABELS, STATUS_ICONS=STATUS_ICONS)


@orders_bp.route('/<int:order_id>/track')
@login_required
def track(order_id):
    order = Order.query.filter_by(id=order_id, customer_id=current_user.id).first_or_404()
    events = order.tracking.order_by(TrackingEvent.created_at.asc()).all()
    event_map = {e.status: e for e in events}

    return render_template('shop/track.html',
                           order=order,
                           events=events,
                           event_map=event_map,
                           STATUS_KEYS=STATUS_KEYS,
                           STATUS_LABELS=STATUS_LABELS,
                           STATUS_ICONS=STATUS_ICONS,
                           ORDER_STATUSES=ORDER_STATUSES)


@orders_bp.route('/<int:order_id>/pay-advance', methods=['GET', 'POST'])
@login_required
def pay_advance(order_id):
    order = Order.query.filter_by(id=order_id, customer_id=current_user.id).first_or_404()

    if order.status != 'advance_requested':
        flash('No advance payment is currently required for this order.', 'info')
        return redirect(url_for('orders.track', order_id=order_id))

    if request.method == 'POST':
        file = request.files.get('proof')
        if not file or not file.filename:
            flash('Please upload your payment screenshot.', 'error')
            return render_template('shop/pay_advance.html', order=order)

        if not allowed_file(file.filename):
            flash('Please upload a valid image file (JPG, PNG, etc.)', 'error')
            return render_template('shop/pay_advance.html', order=order)

        filename = secure_filename(f'advance_{order.id}_{file.filename}')
        save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'payments', filename)
        file.save(save_path)

        order.advance_proof = filename
        order.status = 'advance_paid'

        # Tracking event
        te = TrackingEvent(order_id=order.id, status='advance_paid',
                           note='Customer uploaded advance payment screenshot. Awaiting confirmation.',
                           created_by=current_user.id)
        db.session.add(te)

        # Notification for customer
        notif = Notification(
            user_id=current_user.id, order_id=order.id,
            title='Payment Screenshot Uploaded 💳',
            message='Your advance payment screenshot has been submitted. We\'ll confirm shortly.'
        )
        db.session.add(notif)
        db.session.commit()

        flash('Payment screenshot uploaded! We\'ll confirm your payment shortly.', 'success')
        return redirect(url_for('orders.track', order_id=order_id))

    return render_template('shop/pay_advance.html', order=order)
