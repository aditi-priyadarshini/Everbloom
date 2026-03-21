import os
from flask import current_app, render_template_string
from flask_mail import Mail, Message

mail = Mail()

BASE = """<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
body{margin:0;padding:0;background:#FAF6F1;font-family:Georgia,serif}
.wrap{max-width:580px;margin:0 auto}
.hdr{background:#2C1810;padding:24px 32px;text-align:center}
.hdr h1{color:#F0E6D6;margin:0;font-size:24px;letter-spacing:3px;font-weight:300}
.hdr p{color:#C4A882;margin:4px 0 0;font-size:11px;letter-spacing:2px}
.sbar{background:#8B5E3C;padding:14px;text-align:center}
.sbar h2{color:#fff;margin:0;font-size:18px}
.sbar p{color:#F0E6D6;margin:3px 0 0;font-size:11px;letter-spacing:1px;text-transform:uppercase}
.body{padding:24px 32px}
.body p{color:#5C4033;font-size:15px;line-height:1.7}
.box{background:#fff;border:1px solid #E8DDD4;border-radius:8px;padding:16px 20px;margin:16px 0}
.box p{margin:4px 0;font-size:14px;color:#5C4033}
.hl{background:#F0E6D6;border-left:4px solid #8B5E3C;padding:12px 16px;border-radius:0 6px 6px 0;margin:14px 0}
.hl p{margin:0;font-size:14px;color:#5C4033}
.upi{background:#2C1810;color:#F0E6D6;border-radius:8px;padding:16px;text-align:center;margin:14px 0}
.upi .amt{font-size:32px;font-weight:600;color:#C4A882}
.upi .uid{font-size:13px;margin-top:4px;color:#9E8E85}
.cta{text-align:center;margin:24px 0}
.cta a{background:#8B5E3C;color:white;padding:12px 28px;text-decoration:none;border-radius:4px;font-size:13px;letter-spacing:1px;display:inline-block;font-family:sans-serif}
.ftr{background:#2C1810;padding:18px 32px;text-align:center}
.ftr p{color:rgba(196,168,130,0.6);margin:0;font-size:11px}
</style></head><body><div class="wrap">
<div class="hdr"><h1>🌸 EVERBLOOM</h1><p>HANDCRAFTED WITH LOVE</p></div>
<div class="sbar"><p>Order Update</p><h2>{{ status_label }}</h2></div>
<div class="body">{{ body | safe }}</div>
<div class="ftr"><p>© Everbloom. All handcrafted with love.</p></div>
</div></body></html>"""


def _render(status_label, body):
    return render_template_string(BASE, status_label=status_label, body=body)


def _send(to, subject, html):
    try:
        msg = Message(subject=subject, recipients=[to], html=html)
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Email failed to {to}: {e}")
        return False


def send_order_received(order):
    body = f"""
    <p>Dear {order['cust_name']},</p>
    <p>We've received your order! Our team will review it shortly and send you an email with the advance payment details.</p>
    <div class="box">
      <p><strong>Order #{order['id']:04d}</strong></p>
      <p>Total: ₹{float(order['total_amount']):,.0f}</p>
    </div>
    <p>No payment needed yet — we'll email you the advance amount after review.</p>
    <div class="cta"><a href="{current_app.config['SITE_URL']}/orders/{order['id']}/track">View Order →</a></div>"""
    return _send(order['cust_email'],
                 f"Everbloom — Order #{order['id']:04d} Received 📋",
                 _render("Order Received", body))


def send_advance_request(order):
    upi = current_app.config.get("UPI_ID", "yourname@upi")
    body = f"""
    <p>Dear {order['cust_name']},</p>
    <p>We've reviewed your order and we're excited to craft your piece! 🎨 To confirm your order, please pay the advance amount below via UPI.</p>
    <div class="upi">
      <div style="font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#9E8E85;margin-bottom:4px">Advance Amount</div>
      <div class="amt">₹{float(order['advance_amount']):,.0f}</div>
      <div class="uid">UPI ID: <strong>{upi}</strong></div>
    </div>
    <div class="hl"><p><strong>How to pay:</strong> Open GPay / PhonePe / Paytm → Send Money → Enter UPI ID above → Pay ₹{float(order['advance_amount']):,.0f}</p></div>
    <p>After paying, upload your payment screenshot on the order page.</p>
    <div class="cta"><a href="{current_app.config['SITE_URL']}/orders/{order['id']}/pay-advance">Pay & Upload Screenshot →</a></div>
    <div class="box">
      <p>Order Total: ₹{float(order['total_amount']):,.0f}</p>
      <p>Advance: ₹{float(order['advance_amount']):,.0f} &nbsp;|&nbsp; Balance on delivery: ₹{float(order['total_amount']) - float(order['advance_amount']):,.0f}</p>
    </div>"""
    return _send(order['cust_email'],
                 f"Everbloom — Pay Advance for Order #{order['id']:04d} 💌",
                 _render("Advance Payment Requested", body))


def send_advance_confirmed(order):
    body = f"""
    <p>Dear {order['cust_name']},</p>
    <p>Your advance payment has been confirmed! ✅ Your order is now officially accepted and our artist will begin working on your piece soon.</p>
    <div class="box">
      <p>Advance Paid: ₹{float(order['advance_amount']):,.0f}</p>
      <p>Remaining on delivery: ₹{float(order['total_amount']) - float(order['advance_amount']):,.0f}</p>
    </div>
    <p>You'll receive updates at every step of the crafting process.</p>
    <div class="cta"><a href="{current_app.config['SITE_URL']}/orders/{order['id']}/track">Track Your Order →</a></div>"""
    return _send(order['cust_email'],
                 f"Everbloom — Advance Confirmed! Order #{order['id']:04d} ✅",
                 _render("Advance Confirmed — Crafting Begins!", body))


STATUS_MSGS = {
    "accepted":         ("🎨 Your order has been accepted!", "Our artist has accepted your order and will begin sourcing materials."),
    "material_sourced": ("🪵 Materials sourced for your piece", "Raw materials have been carefully gathered for your unique piece."),
    "crafting":         ("✂️ Your piece is being handcrafted!", "Your piece is now being lovingly handcrafted. This is where the magic happens!"),
    "quality_check":    ("🔍 Quality check underway!", "Your piece has completed crafting and is going through quality inspection."),
    "packed":           ("📦 Packed and ready to ship!", "Your Everbloom piece has been carefully packed and is ready to be dispatched."),
    "shipped":          ("🚚 Your order is on its way!", "Your order has been handed over to our delivery partner. Expect it soon!"),
    "delivered":        ("🌸 Your order has been delivered!", "Your Everbloom piece has arrived! We hope you absolutely love it. 🌸"),
    "cancelled":        ("Your order has been cancelled", "We're sorry, your order has been cancelled. Reply to this email if you have questions."),
}


def send_status_update(order, admin_note=""):
    status = order["status"]
    subject_suffix, body_text = STATUS_MSGS.get(status, (f"Status updated: {status}", f"Your order status is now: {status}"))
    note_html = f'<div class="hl"><p><strong>Note from our team:</strong> {admin_note}</p></div>' if admin_note else ""
    body = f"""
    <p>Dear {order['cust_name']},</p>
    <p>{body_text}</p>
    {note_html}
    <div class="box"><p><strong>Order #{order['id']:04d}</strong> — ₹{float(order['total_amount']):,.0f}</p></div>
    <div class="cta"><a href="{current_app.config['SITE_URL']}/orders/{order['id']}/track">Track Your Order →</a></div>"""
    return _send(order['cust_email'],
                 f"Everbloom — {subject_suffix}",
                 _render(status.replace("_", " ").title(), body))


def send_welcome(user_row):
    body = f"""
    <p>Dear {user_row['full_name']},</p>
    <p>Welcome to Everbloom! 🌸 Your account has been created successfully.</p>
    <p>Start exploring our handcrafted collection and find something beautiful.</p>
    <div class="cta"><a href="{current_app.config['SITE_URL']}/shop">Browse Collection →</a></div>"""
    return _send(user_row['email'], "Welcome to Everbloom 🌸", _render("Welcome!", body))
