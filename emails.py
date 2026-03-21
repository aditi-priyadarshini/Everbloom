import os
from flask import current_app, render_template_string
from flask_mail import Message
from app import mail

_BASE = """<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#FDF8F3;font-family:Georgia,serif;color:#3D2B1F}
.wrap{max-width:560px;margin:0 auto;background:#fff}
.hdr{background:#1C0A00;padding:32px;text-align:center}
.hdr-logo{font-size:28px;color:#F5E6D3;letter-spacing:4px;font-weight:400}
.hdr-sub{font-size:10px;color:#B8916A;letter-spacing:3px;text-transform:uppercase;margin-top:6px}
.status-bar{background:#8B4513;padding:18px 32px;text-align:center}
.status-bar h2{color:#fff;font-size:20px;font-weight:400}
.status-bar p{color:rgba(255,255,255,0.7);font-size:11px;letter-spacing:2px;text-transform:uppercase;margin-top:4px}
.body{padding:32px}
.body p{color:#4A3728;font-size:15px;line-height:1.8;margin-bottom:14px}
.info-box{background:#FDF8F3;border:1px solid #E8D5C0;border-radius:6px;padding:18px;margin:18px 0}
.info-box p{margin:5px 0;font-size:14px}
.upi-box{background:#1C0A00;color:#F5E6D3;border-radius:6px;padding:22px;text-align:center;margin:18px 0}
.upi-amount{font-size:36px;color:#D4A96A;margin:8px 0}
.upi-id{font-size:13px;color:#B8916A;margin-top:6px}
.note-box{background:#FFF8F0;border-left:4px solid #8B4513;padding:14px 18px;margin:16px 0;border-radius:0 6px 6px 0}
.note-box p{margin:0;font-size:14px;color:#4A3728}
.cta{text-align:center;margin:24px 0}
.cta a{background:#8B4513;color:#fff;padding:13px 32px;text-decoration:none;border-radius:4px;font-size:13px;letter-spacing:1px;font-family:sans-serif;display:inline-block}
.ftr{background:#1C0A00;padding:20px 32px;text-align:center}
.ftr p{color:rgba(245,230,211,0.4);font-size:11px}
</style></head><body><div class="wrap">
<div class="hdr"><div class="hdr-logo">🌿 EVERBLOOM</div><div class="hdr-sub">Handcrafted with Love</div></div>
<div class="status-bar"><p>Order Update</p><h2>{{ label }}</h2></div>
<div class="body">{{ body|safe }}</div>
<div class="ftr"><p>© Everbloom · Made with love for art lovers</p></div>
</div></body></html>"""


def _render(label, body):
    return render_template_string(_BASE, label=label, body=body)


def _send(to, subject, html):
    try:
        mail.send(Message(subject=subject, recipients=[to], html=html))
    except Exception as e:
        current_app.logger.error(f"Email error → {to}: {e}")


def mail_order_placed(order):
    body = f"""<p>Hi {order['cust_name']},</p>
    <p>We've received your order! Our team will review it and get back to you with the advance payment details within 24 hours.</p>
    <div class="info-box"><p><strong>Order #{order['id']:04d}</strong></p><p>Total: ₹{float(order['total_amount']):,.0f}</p><p>No payment needed yet.</p></div>
    <div class="cta"><a href="{current_app.config['SITE_URL']}/orders/{order['id']}/track">View Order →</a></div>"""
    _send(order['cust_email'], f"Order #{order['id']:04d} Received — Everbloom 📋", _render("Order Received!", body))


def mail_advance_request(order):
    upi = current_app.config.get("UPI_ID", "yourname@upi")
    body = f"""<p>Hi {order['cust_name']},</p>
    <p>Wonderful news! We've reviewed your order and we'd love to create this piece for you. To confirm your order and begin work, please pay the advance amount below.</p>
    <div class="upi-box">
      <div style="font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#B8916A">Advance Amount Due</div>
      <div class="upi-amount">₹{float(order['advance_amount']):,.0f}</div>
      <div class="upi-id">UPI ID: <strong>{upi}</strong></div>
    </div>
    <div class="note-box"><p><strong>How to pay:</strong> Open any UPI app → Send Money → Enter the UPI ID above → Pay ₹{float(order['advance_amount']):,.0f}</p></div>
    <p>Once you've paid, please upload your payment screenshot on the link below so we can confirm and begin crafting!</p>
    <div class="cta"><a href="{current_app.config['SITE_URL']}/orders/{order['id']}/pay-advance">Upload Payment Screenshot →</a></div>
    <div class="info-box"><p>Order Total: ₹{float(order['total_amount']):,.0f}</p><p>Advance: ₹{float(order['advance_amount']):,.0f} &nbsp;|&nbsp; Remaining on delivery: ₹{float(order['total_amount'])-float(order['advance_amount']):,.0f}</p></div>"""
    _send(order['cust_email'], f"Action Required: Pay Advance for Order #{order['id']:04d} — Everbloom 💌", _render("Advance Payment Requested", body))


def mail_advance_confirmed(order):
    body = f"""<p>Hi {order['cust_name']},</p>
    <p>Your advance payment has been confirmed! Your order is officially placed and our artisan will begin working on your piece very soon. 🎨</p>
    <div class="info-box"><p>Advance paid: ₹{float(order['advance_amount']):,.0f}</p><p>Remaining (on delivery): ₹{float(order['total_amount'])-float(order['advance_amount']):,.0f}</p></div>
    <p>You'll receive email updates at every step of the crafting process.</p>
    <div class="cta"><a href="{current_app.config['SITE_URL']}/orders/{order['id']}/track">Track Your Order →</a></div>"""
    _send(order['cust_email'], f"Advance Confirmed — Crafting Begins! Order #{order['id']:04d} ✅", _render("Advance Confirmed!", body))


_STATUS_COPY = {
    "crafting":      ("Being Crafted 🎨",    "Your piece is now being lovingly handcrafted by our artisan. This is where the magic happens!"),
    "quality_check": ("Quality Check 🔍",     "Your piece has completed crafting and is going through our quality check. Almost there!"),
    "shipped":       ("On Its Way! 🚚",       "Your Everbloom piece is on its way to you. Our delivery partner will have it at your door soon."),
    "delivered":     ("Delivered! 🌸",        "Your Everbloom piece has been delivered! We hope you absolutely love it. Thank you for supporting handcrafted art."),
    "cancelled":     ("Order Cancelled",      "Your order has been cancelled. If you have any questions, please reply to this email."),
}


def mail_status_update(order, note=""):
    status = order["status"]
    label, copy = _STATUS_COPY.get(status, (status.replace("_"," ").title(), f"Your order status has been updated to: {status.replace('_',' ').title()}"))
    note_html = f'<div class="note-box"><p><strong>Note from our team:</strong> {note}</p></div>' if note else ""
    body = f"""<p>Hi {order['cust_name']},</p><p>{copy}</p>{note_html}
    <div class="info-box"><p><strong>Order #{order['id']:04d}</strong> · ₹{float(order['total_amount']):,.0f}</p></div>
    <div class="cta"><a href="{current_app.config['SITE_URL']}/orders/{order['id']}/track">Track Your Order →</a></div>"""
    _send(order['cust_email'], f"Everbloom — {label}", _render(label, body))


def mail_welcome(name, email):
    body = f"""<p>Hi {name},</p>
    <p>Welcome to Everbloom! We're so glad you're here. Explore our collection of handcrafted art pieces — each one made with love by our artisans.</p>
    <div class="cta"><a href="{current_app.config['SITE_URL']}/shop">Browse the Collection →</a></div>"""
    _send(email, "Welcome to Everbloom 🌿", _render("Welcome!", body))
