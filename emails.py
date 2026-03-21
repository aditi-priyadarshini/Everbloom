from flask import current_app, render_template_string
from flask_mail import Message
from app import mail

# ── Email Templates ───────────────────────────────────────────────────────────

BASE_HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body { margin:0; padding:0; background:#FAF6F1; font-family: 'Georgia', serif; }
    .wrap { max-width:580px; margin:0 auto; }
    .header { background:#2C1810; padding:28px 32px; text-align:center; }
    .header h1 { color:#F0E6D6; margin:0; font-size:26px; letter-spacing:3px; font-weight:300; }
    .header p { color:#C4A882; margin:6px 0 0; font-size:11px; letter-spacing:2px; }
    .status-bar { background:#8B5E3C; padding:16px; text-align:center; }
    .status-bar h2 { color:#fff; margin:0; font-size:20px; }
    .status-bar p { color:#F0E6D6; margin:4px 0 0; font-size:12px; letter-spacing:1px; text-transform:uppercase; }
    .body { padding:28px 32px; }
    .body p { color:#5C4033; font-size:15px; line-height:1.7; }
    .info-box { background:#fff; border:1px solid #E8DDD4; border-radius:8px; padding:18px 20px; margin:18px 0; }
    .info-box p { margin:4px 0; font-size:14px; color:#5C4033; }
    .info-box .label { font-size:11px; font-weight:600; letter-spacing:1.5px; text-transform:uppercase; color:#9E8E85; margin-bottom:8px; }
    .highlight { background:#F0E6D6; border-left:4px solid #8B5E3C; padding:14px 16px; border-radius:0 6px 6px 0; margin:16px 0; }
    .highlight p { margin:0; font-size:14px; color:#5C4033; }
    .cta { text-align:center; margin:28px 0; }
    .cta a { background:#8B5E3C; color:white; padding:13px 30px; text-decoration:none; border-radius:4px; font-size:13px; letter-spacing:1px; display:inline-block; font-family:sans-serif; }
    .footer { background:#2C1810; padding:20px 32px; text-align:center; }
    .footer p { color:rgba(196,168,130,0.6); margin:0; font-size:11px; }
    .upi-box { background:#2C1810; color:#F0E6D6; border-radius:8px; padding:18px; text-align:center; margin:16px 0; }
    .upi-box .amount { font-size:32px; font-weight:600; color:#C4A882; }
    .upi-box .upi-id { font-size:14px; margin-top:6px; color:#9E8E85; }
  </style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <h1>🌸 EVERBLOOM</h1>
    <p>HANDCRAFTED WITH LOVE</p>
  </div>
  <div class="status-bar">
    <p>Order Update</p>
    <h2>{{ status_label }}</h2>
  </div>
  <div class="body">
    {{ body_html | safe }}
  </div>
  <div class="footer">
    <p>© Everbloom. All handcrafted with love.</p>
  </div>
</div>
</body>
</html>
"""


def _render(status_label, body_html):
    return render_template_string(BASE_HTML, status_label=status_label, body_html=body_html)


def _send(to_email, subject, html):
    try:
        msg = Message(subject=subject, recipients=[to_email], html=html)
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f'Email send failed to {to_email}: {e}')
        return False


# ── Individual email senders ──────────────────────────────────────────────────

def send_order_received(order):
    """Email 1: Customer places order — admin will review it."""
    body = f"""
    <p>Dear {order.customer.full_name},</p>
    <p>We've received your order! Our team will review it shortly and get back to you soon.</p>
    <div class="info-box">
      <p class="label">Order Details</p>
      <p><strong>Order #{order.id:04d}</strong></p>
      <p>Total: ₹{order.total_amount:,.0f}</p>
      <p>Items: {sum(i.quantity for i in order.items)}</p>
    </div>
    <p>You'll receive another email once we review your order and confirm the advance payment amount.</p>
    <div class="cta"><a href="{current_app.config['SITE_URL']}/orders/{order.id}/track">View Order</a></div>
    """
    return _send(
        order.customer.email,
        f'Everbloom — Order #{order.id:04d} Received 📋',
        _render('Order Received', body)
    )


def send_advance_request(order):
    """Email 2: Admin accepted review — asks customer to pay advance."""
    upi_id = current_app.config.get('UPI_ID', 'yourname@upi')
    site_url = current_app.config['SITE_URL']
    body = f"""
    <p>Dear {order.customer.full_name},</p>
    <p>Great news! We've reviewed your order and we're excited to create your piece. 🎨</p>
    <p>To confirm your order and begin crafting, please pay the <strong>advance amount</strong> below via UPI.</p>
    <div class="upi-box">
      <div style="font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#9E8E85;margin-bottom:6px;">Advance Amount</div>
      <div class="amount">₹{order.advance_amount:,.0f}</div>
      <div class="upi-id">UPI ID: <strong>{upi_id}</strong></div>
    </div>
    <div class="highlight">
      <p><strong>How to pay:</strong> Open GPay / PhonePe / Paytm → Send Money → Enter UPI ID above → Pay ₹{order.advance_amount:,.0f}</p>
    </div>
    <p>After paying, upload your payment screenshot on the order page so we can confirm.</p>
    <div class="cta"><a href="{site_url}/orders/{order.id}/pay-advance">Pay & Upload Screenshot →</a></div>
    <div class="info-box">
      <p class="label">Order Details</p>
      <p><strong>Order #{order.id:04d}</strong> · Total: ₹{order.total_amount:,.0f}</p>
      <p>Advance: ₹{order.advance_amount:,.0f} &nbsp;|&nbsp; Remaining: ₹{float(order.total_amount) - float(order.advance_amount):,.0f} (paid on delivery)</p>
    </div>
    """
    return _send(
        order.customer.email,
        f'Everbloom — Action Required: Pay Advance for Order #{order.id:04d} 💌',
        _render('Advance Payment Requested', body)
    )


def send_advance_confirmed(order):
    """Email 3: Admin confirmed the advance payment."""
    body = f"""
    <p>Dear {order.customer.full_name},</p>
    <p>Your advance payment has been confirmed! ✅ Your order is now officially placed and our artist will begin working on your piece soon.</p>
    <div class="info-box">
      <p class="label">Payment Summary</p>
      <p>Advance Paid: ₹{order.advance_amount:,.0f}</p>
      <p>Remaining (on delivery): ₹{float(order.total_amount) - float(order.advance_amount):,.0f}</p>
    </div>
    <p>You'll receive updates at every step of the crafting process.</p>
    <div class="cta"><a href="{current_app.config['SITE_URL']}/orders/{order.id}/track">Track Your Order →</a></div>
    """
    return _send(
        order.customer.email,
        f'Everbloom — Advance Confirmed! Order #{order.id:04d} ✅',
        _render('Advance Confirmed', body)
    )


STATUS_EMAIL_SUBJECTS = {
    'accepted':          '🎨 Your order has been accepted by our artist!',
    'material_sourced':  '🪵 Raw materials sourced for your piece',
    'crafting':          '✂️ Your piece is being handcrafted!',
    'quality_check':     '🔍 Quality check underway — almost ready!',
    'packed':            '📦 Your order is packed and ready to ship',
    'shipped':           '🚚 Your Everbloom order is on its way!',
    'delivered':         '🌸 Your order has been delivered!',
    'cancelled':         'Your order has been cancelled',
}

STATUS_EMAIL_BODY = {
    'accepted':
        "Great news! Our artist has accepted your order and will begin sourcing materials soon. Get ready for something beautiful! 🎨",
    'material_sourced':
        "Our artist has carefully sourced the raw materials needed for your unique piece. The crafting begins soon!",
    'crafting':
        "Your piece is now being lovingly handcrafted by our artist. This is where the magic happens! ✂️",
    'quality_check':
        "Your piece has completed crafting and is going through our quality inspection. Almost there!",
    'packed':
        "Your Everbloom piece has been carefully packed and is ready to ship. We'll update you once it's dispatched.",
    'shipped':
        "Your order is on its way! It has been handed over to our delivery partner. Expect it soon.",
    'delivered':
        "Your Everbloom piece has been delivered! We hope you absolutely love it. Thank you for being part of the Everbloom family. 🌸",
    'cancelled':
        "We're sorry, your order has been cancelled. If you have any questions please reply to this email.",
}


def send_status_update(order, admin_note=''):
    """Generic status update email for all post-confirmation steps."""
    status = order.status
    subject_suffix = STATUS_EMAIL_SUBJECTS.get(status, f'Order status updated: {order.status_label}')
    body_text = STATUS_EMAIL_BODY.get(status, f'Your order status has been updated to: {order.status_label}')

    note_html = ''
    if admin_note:
        note_html = f'<div class="highlight"><p><strong>Note from our team:</strong> {admin_note}</p></div>'

    body = f"""
    <p>Dear {order.customer.full_name},</p>
    <p>{body_text}</p>
    {note_html}
    <div class="info-box">
      <p class="label">Order #{order.id:04d}</p>
      <p>Total: ₹{order.total_amount:,.0f}</p>
    </div>
    <div class="cta"><a href="{current_app.config['SITE_URL']}/orders/{order.id}/track">Track Your Order →</a></div>
    """
    return _send(
        order.customer.email,
        f'Everbloom — {subject_suffix}',
        _render(order.status_label, body)
    )


def send_welcome(user):
    body = f"""
    <p>Dear {user.full_name},</p>
    <p>Welcome to Everbloom! 🌸 Your account has been created successfully.</p>
    <p>Start exploring our handcrafted collection and find a piece that speaks to you.</p>
    <div class="cta"><a href="{current_app.config['SITE_URL']}/shop">Browse Collection →</a></div>
    """
    return _send(
        user.email,
        'Welcome to Everbloom 🌸',
        _render('Welcome!', body)
    )
