import os
from flask import current_app, render_template_string
from flask_mail import Message
from app import mail

_T = """<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>*{margin:0;padding:0;box-sizing:border-box}body{background:#FDF8F3;font-family:Georgia,serif}
.w{max-width:560px;margin:0 auto;background:#fff}
.h{background:#1C0A00;padding:28px 32px;text-align:center}
.h h1{color:#F5E6D3;font-size:24px;letter-spacing:3px;font-weight:400}
.h p{color:#B8916A;font-size:10px;letter-spacing:3px;text-transform:uppercase;margin-top:5px}
.s{background:#8B4513;padding:16px;text-align:center}
.s h2{color:#fff;font-size:19px;font-weight:400}
.b{padding:28px 32px}
.b p{color:#4A3728;font-size:15px;line-height:1.8;margin-bottom:12px}
.box{background:#FDF8F3;border:1px solid #E8D5C0;border-radius:6px;padding:16px 18px;margin:16px 0}
.box p{margin:4px 0;font-size:14px}
.upi{background:#1C0A00;color:#F5E6D3;border-radius:6px;padding:20px;text-align:center;margin:16px 0}
.amt{font-size:36px;color:#D4A96A;margin:6px 0}
.uid{font-size:13px;color:#B8916A;margin-top:5px}
.note{background:#FFF8F0;border-left:4px solid #8B4513;padding:12px 16px;margin:14px 0;border-radius:0 6px 6px 0}
.note p{margin:0;font-size:14px}
.cta{text-align:center;margin:22px 0}
.cta a{background:#8B4513;color:#fff;padding:12px 30px;text-decoration:none;border-radius:4px;font-size:13px;font-family:sans-serif;display:inline-block}
.f{background:#1C0A00;padding:18px;text-align:center}
.f p{color:rgba(245,230,211,.4);font-size:11px}
</style></head><body><div class="w">
<div class="h"><h1>🌿 EVERBLOOM</h1><p>Handcrafted with Love</p></div>
<div class="s"><h2>{{ label }}</h2></div>
<div class="b">{{ body|safe }}</div>
<div class="f"><p>© Everbloom · Made with love for art lovers</p></div>
</div></body></html>"""


def _render(label, body):
    return render_template_string(_T, label=label, body=body)

def _send(to, subject, html):
    try:
        mail.send(Message(subject=subject, recipients=[to], html=html))
    except Exception as e:
        current_app.logger.error(f"Email error: {e}")


def mail_placed(order):
    body = f"""<p>Hi {order['cust_name']},</p>
    <p>We've received your order! Our team will review it and email you the advance payment details within 24 hours. No payment needed yet.</p>
    <div class="box"><p><strong>Order #{order['id']:04d}</strong></p><p>Total: ₹{float(order['total_amount']):,.0f}</p></div>
    <div class="cta"><a href="{current_app.config['SITE_URL']}/orders/{order['id']}/track">View Order →</a></div>"""
    _send(order['cust_email'], f"Order #{order['id']:04d} Received — Everbloom 📋", _render("Order Received!", body))


def mail_advance_request(order):
    upi = current_app.config.get("UPI_ID", "yourname@upi")
    adv = float(order['advance_amount'])
    tot = float(order['total_amount'])
    body = f"""<p>Hi {order['cust_name']},</p>
    <p>Great news — we've reviewed your order and we'd love to create this piece for you! Please pay the advance amount below to confirm your order.</p>
    <div class="upi">
      <div style="font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#B8916A">Advance Amount</div>
      <div class="amt">₹{adv:,.0f}</div>
      <div class="uid">UPI ID: <strong>{upi}</strong></div>
    </div>
    <div class="note"><p>Open GPay / PhonePe / Paytm → Send Money → Enter UPI ID → Pay ₹{adv:,.0f}</p></div>
    <p>After paying, upload your screenshot on the link below.</p>
    <div class="cta"><a href="{current_app.config['SITE_URL']}/orders/{order['id']}/pay-advance">Upload Payment Screenshot →</a></div>
    <div class="box"><p>Total: ₹{tot:,.0f} &nbsp;|&nbsp; Advance: ₹{adv:,.0f} &nbsp;|&nbsp; Balance on delivery: ₹{tot-adv:,.0f}</p></div>"""
    _send(order['cust_email'], f"Pay Advance for Order #{order['id']:04d} — Everbloom 💌", _render("Advance Payment Requested", body))


def mail_advance_confirmed(order):
    adv = float(order['advance_amount'])
    tot = float(order['total_amount'])
    body = f"""<p>Hi {order['cust_name']},</p>
    <p>Your advance payment is confirmed! ✅ Our artisan will begin crafting your piece soon.</p>
    <div class="box"><p>Advance paid: ₹{adv:,.0f}</p><p>Remaining on delivery: ₹{tot-adv:,.0f}</p></div>
    <div class="cta"><a href="{current_app.config['SITE_URL']}/orders/{order['id']}/track">Track Order →</a></div>"""
    _send(order['cust_email'], f"Advance Confirmed — Crafting Begins! ✅", _render("Advance Confirmed!", body))


_COPY = {
    "crafting":      ("Being Crafted 🎨",  "Your piece is now being lovingly handcrafted by our artisan!"),
    "quality_check": ("Quality Check 🔍",  "Your piece has passed crafting and is going through quality inspection."),
    "shipped":       ("On Its Way! 🚚",    "Your Everbloom piece is on its way. Our delivery partner will have it at your door soon."),
    "delivered":     ("Delivered! 🌿",     "Your piece has been delivered! We hope you absolutely love it. Thank you for supporting handcrafted art."),
    "cancelled":     ("Order Cancelled",   "Your order has been cancelled. Reply to this email if you have any questions."),
}


def mail_status(order, note=""):
    status = order["status"]
    label, copy = _COPY.get(status, (status.replace("_"," ").title(), f"Your order status: {status.replace('_',' ').title()}"))
    note_html = f'<div class="note"><p><strong>Note from our team:</strong> {note}</p></div>' if note else ""
    body = f"""<p>Hi {order['cust_name']},</p><p>{copy}</p>{note_html}
    <div class="box"><p>Order #{order['id']:04d} · ₹{float(order['total_amount']):,.0f}</p></div>
    <div class="cta"><a href="{current_app.config['SITE_URL']}/orders/{order['id']}/track">Track Order →</a></div>"""
    _send(order['cust_email'], f"Everbloom — {label}", _render(label, body))


def mail_welcome(name, email):
    body = f"""<p>Hi {name},</p>
    <p>Welcome to Everbloom! 🌿 Explore our collection of handcrafted art pieces — each one made with love.</p>
    <div class="cta"><a href="{current_app.config['SITE_URL']}/shop">Browse Collection →</a></div>"""
    _send(email, "Welcome to Everbloom 🌿", _render("Welcome!", body))
