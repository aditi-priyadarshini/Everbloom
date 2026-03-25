import sys
from flask_mail import Message
from flask import current_app

BASE = """
<div style="font-family:'Georgia',serif;max-width:560px;margin:0 auto;background:#fdf6f0;border:1px solid #e8c4b8;border-radius:8px;overflow:hidden;">
  <div style="background:#5c3d3d;padding:24px 32px;">
    <h1 style="margin:0;color:#f5e6e0;font-size:22px;letter-spacing:0.04em;">Everbloom</h1>
    <p style="margin:4px 0 0;color:#e8c4b8;font-size:12px;letter-spacing:0.1em;">HANDCRAFTED WITH LOVE</p>
  </div>
  <div style="padding:32px;">
    {body}
    <hr style="border:none;border-top:1px solid #e8c4b8;margin:24px 0;">
    <p style="color:#7a5c5c;font-size:12px;margin:0;">Questions? Reply to this email.<br>With love, <strong>Team Everbloom</strong></p>
  </div>
</div>
"""

DEFAULTS = {
    "order_placed":      ("Order Placed — Everbloom", "<h2 style='color:#5c3d3d;'>Order Placed!</h2><p style='color:#3a2a2a;'>Hi {{name}},<br>Your order <strong>#{{order_id}}</strong> has been placed. Total: &#8377;{{total}}</p>"),
    "advance_requested": ("Advance Payment Required — Everbloom", "<h2 style='color:#5c3d3d;'>Advance Payment Required</h2><p style='color:#3a2a2a;'>Hi {{name}},<br>Pay advance of <strong>&#8377;{{advance_amount}}</strong>. UPI ID: {{upi_id}}</p><p><a href='{{pay_link}}' style='background:#5c3d3d;color:#fdf6f0;padding:12px 24px;border-radius:4px;text-decoration:none;display:inline-block;margin-top:12px;'>Upload Screenshot</a></p>"),
    "advance_confirmed": ("Payment Confirmed — Everbloom", "<h2 style='color:#5c3d3d;'>Payment Confirmed!</h2><p style='color:#3a2a2a;'>Hi {{name}}, crafting has begun on order #{{order_id}}!</p>"),
    "crafting":          ("Crafting in Progress — Everbloom", "<h2 style='color:#5c3d3d;'>Crafting in Progress</h2><p style='color:#3a2a2a;'>Hi {{name}}, artisans are working on order #{{order_id}}.</p>"),
    "quality_check":     ("Quality Check — Everbloom", "<h2 style='color:#5c3d3d;'>Quality Check</h2><p style='color:#3a2a2a;'>Hi {{name}}, order #{{order_id}} is being inspected.</p>"),
    "shipped":           ("Your Order is Shipped — Everbloom", "<h2 style='color:#5c3d3d;'>Shipped!</h2><p style='color:#3a2a2a;'>Hi {{name}}, order #{{order_id}} is on its way!</p>"),
    "delivered":         ("Order Delivered — Everbloom", "<h2 style='color:#5c3d3d;'>Delivered!</h2><p style='color:#3a2a2a;'>Hi {{name}}, thanks for shopping! Balance due: &#8377;{{balance}}.</p>"),
    "cancelled":         ("Order Cancelled — Everbloom", "<h2 style='color:#5c3d3d;'>Order Cancelled</h2><p style='color:#3a2a2a;'>Hi {{name}}, order #{{order_id}} has been cancelled.</p>"),
    "welcome":           ("Welcome to Everbloom!", "<h2 style='color:#5c3d3d;'>Welcome!</h2><p style='color:#3a2a2a;'>Hi {{name}}, your account is ready. Start shopping!</p>"),
    "custom_request":    ("Custom Request Received — Everbloom", "<h2 style='color:#5c3d3d;'>Request Received!</h2><p style='color:#3a2a2a;'>Hi {{name}}, we'll review your custom order in 2-3 days.</p>"),
}


def _get_template(key):
    try:
        import models
        t = models.get_email_template(key)
        if t:
            return t["subject"], t["body_html"]
    except Exception:
        pass
    return DEFAULTS.get(key, ("Everbloom Update", "<p>You have an update from Everbloom.</p>"))


def _render(body_html, variables):
    for k, v in variables.items():
        body_html = body_html.replace("{{" + k + "}}", str(v) if v is not None else "")
    return body_html


def _send(to, subject, html):
    try:
        from app import mail
        username = current_app.config.get("MAIL_USERNAME", "")
        password = current_app.config.get("MAIL_PASSWORD", "")
        if not username or not password:
            print("[email SKIP] MAIL_USERNAME or MAIL_PASSWORD not set", file=sys.stderr)
            return False
        msg = Message(subject, recipients=[to], html=html)
        mail.send(msg)
        print(f"[email OK] '{subject}' -> {to}", file=sys.stderr)
        return True
    except Exception as e:
        print(f"[email ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        current_app.logger.error(f"Email error: {e}")
        return False


# ── Transactional ─────────────────────────────────────────

def send_order_placed(user_email, order):
    subject, body = _get_template("order_placed")
    html = _render(body, {
        "name": order.get("name", "there"),
        "order_id": str(order["id"])[:8].upper(),
        "total": f"{float(order.get('total', 0)):.0f}",
    })
    return _send(user_email, subject, BASE.format(body=html))


def send_advance_requested(user_email, order, upi_id, upi_qr_url, site_url):
    subject, body = _get_template("advance_requested")
    pay_link = f"{site_url}/orders/{order['id']}/pay-advance"
    qr_html = f'<img src="{upi_qr_url}" style="width:180px;border-radius:8px;margin:12px 0;display:block;" alt="UPI QR">' if upi_qr_url else ""
    html = _render(body, {
        "name": order.get("name", "there"),
        "order_id": str(order["id"])[:8].upper(),
        "advance_amount": f"{float(order.get('advance_amount', 0)):.0f}",
        "upi_id": upi_id or "",
        "pay_link": pay_link,
        "total": f"{float(order.get('total', 0)):.0f}",
        "shipping_charge": f"{float(order.get('shipping_charge', 0)):.0f}",
    })
    if qr_html:
        html += qr_html
    return _send(user_email, subject, BASE.format(body=html))


def send_status_update(user_email, order, status, note=None):
    subject, body = _get_template(status)
    balance = float(order.get("total", 0)) - float(order.get("advance_amount") or 0)
    html = _render(body, {
        "name": order.get("name", "there"),
        "order_id": str(order["id"])[:8].upper(),
        "balance": f"{balance:.0f}",
        "note": note or "",
    })
    if note:
        html += f"<p style='color:#5c3d3d;font-style:italic;margin-top:1rem;'>{note}</p>"
    return _send(user_email, subject, BASE.format(body=html))


def send_custom_request_received(user_email, name):
    subject, body = _get_template("custom_request")
    html = _render(body, {"name": name})
    return _send(user_email, subject, BASE.format(body=html))


def send_welcome(user_email, name):
    subject, body = _get_template("welcome")
    html = _render(body, {"name": name})
    return _send(user_email, subject, BASE.format(body=html))


# ── Email Verification ────────────────────────────────────

def send_verify_email(user_email, name, verify_url):
    body = f"""
    <h2 style="color:#5c3d3d;">Verify Your Email</h2>
    <p style="color:#3a2a2a;">Hi {name},<br>
    Thanks for signing up! Click the button below to verify your email and activate your Everbloom account.</p>
    <a href="{verify_url}" style="display:inline-block;margin-top:16px;background:#5c3d3d;color:#fdf6f0;padding:14px 28px;border-radius:4px;text-decoration:none;font-size:14px;letter-spacing:0.05em;">Verify My Email</a>
    <p style="color:#7a5c5c;font-size:13px;margin-top:1.5rem;">This link expires in 24 hours.<br>If you didn't sign up for Everbloom, you can safely ignore this email.</p>
    """
    return _send(user_email, "Please verify your email — Everbloom", BASE.format(body=body))


# ── Password Reset ────────────────────────────────────────

def send_password_reset(user_email, name, reset_url):
    body = f"""
    <h2 style="color:#5c3d3d;">Reset Your Password</h2>
    <p style="color:#3a2a2a;">Hi {name},<br>
    We received a request to reset your password. Click below to set a new one.</p>
    <a href="{reset_url}" style="display:inline-block;margin-top:16px;background:#5c3d3d;color:#fdf6f0;padding:14px 28px;border-radius:4px;text-decoration:none;font-size:14px;letter-spacing:0.05em;">Reset My Password</a>
    <p style="color:#7a5c5c;font-size:13px;margin-top:1.5rem;">This link expires in 1 hour.<br>If you didn't request a password reset, ignore this email — your account is safe.</p>
    """
    return _send(user_email, "Reset your password — Everbloom", BASE.format(body=body))


# ── Admin New Order Alert ─────────────────────────────────

def send_admin_new_order(admin_email, order, site_url):
    order_url = f"{site_url}/admin/orders/{order['id']}"
    delivery = "Self Pickup" if order.get("delivery_type") == "pickup" else "Home Delivery"
    preorder = " 🟡 PRE-ORDER" if order.get("is_preorder") else ""
    body = f"""
    <h2 style="color:#5c3d3d;">New Order Received!{preorder}</h2>
    <table style="width:100%;border-collapse:collapse;font-size:.9rem;color:#3a2a2a;">
      <tr><td style="padding:.4rem 0;color:#7a5c5c;">Order ID</td><td><strong>#{str(order['id'])[:8].upper()}</strong></td></tr>
      <tr><td style="padding:.4rem 0;color:#7a5c5c;">Customer</td><td>{order.get('name','—')}</td></tr>
      <tr><td style="padding:.4rem 0;color:#7a5c5c;">Phone</td><td>{order.get('phone','—')}</td></tr>
      <tr><td style="padding:.4rem 0;color:#7a5c5c;">Total</td><td><strong>&#8377;{float(order.get('total',0)):.0f}</strong></td></tr>
      <tr><td style="padding:.4rem 0;color:#7a5c5c;">Delivery</td><td>{delivery}</td></tr>
      <tr><td style="padding:.4rem 0;color:#7a5c5c;">Address</td><td>{order.get('address','—')}</td></tr>
    </table>
    <a href="{order_url}" style="display:inline-block;margin-top:20px;background:#5c3d3d;color:#fdf6f0;padding:12px 24px;border-radius:4px;text-decoration:none;font-size:14px;">View & Manage Order</a>
    """
    return _send(admin_email, f"New Order #{str(order['id'])[:8].upper()} — Everbloom", BASE.format(body=body))


def send_custom_quote(customer_email, name, req, accept_url, decline_url):
    body = f"""
    <h2 style="color:#5c3d3d;">Your Custom Order Quote</h2>
    <p style="color:#3a2a2a;">Hi {name}, we've reviewed your custom order request and have a quote for you!</p>
    <div style="background:#fdf6f0;border:1px solid #e8c4b8;border-radius:6px;padding:1.2rem;margin:1rem 0;">
      <p style="margin:.3rem 0;color:#3a2a2a;"><strong>Quoted Price:</strong> &#8377;{req.get('quoted_price','—')}</p>
      <p style="margin:.3rem 0;color:#3a2a2a;"><strong>Estimated Crafting Time:</strong> {req.get('quoted_days','—')} days</p>
      {f"<p style='margin:.8rem 0 0;color:#5c3d3d;font-style:italic;'>{req.get('quote_message','')}</p>" if req.get('quote_message') else ''}
    </div>
    <p style="color:#3a2a2a;">Please accept or decline below:</p>
    <div style="display:flex;gap:1rem;margin-top:1rem;">
      <a href="{accept_url}" style="background:#5c3d3d;color:#fdf6f0;padding:12px 24px;border-radius:4px;text-decoration:none;font-size:14px;">✓ Accept Quote</a>
      <a href="{decline_url}" style="background:#fff;color:#5c3d3d;padding:12px 24px;border-radius:4px;text-decoration:none;font-size:14px;border:1px solid #e8c4b8;">✗ Decline</a>
    </div>
    <p style="color:#7a5c5c;font-size:12px;margin-top:1rem;">This quote is valid for 7 days.</p>
    """
    return _send(customer_email, "Your Custom Order Quote — Everbloom", BASE.format(body=body))


def send_custom_accepted(customer_email, name, order_id, site_url):
    order_url = f"{site_url}/orders/{order_id}"
    body = f"""
    <h2 style="color:#5c3d3d;">Custom Order Confirmed!</h2>
    <p style="color:#3a2a2a;">Hi {name}, you've accepted the quote and your custom order is now confirmed!</p>
    <p style="color:#3a2a2a;">You'll receive advance payment details shortly. Track your order below.</p>
    <a href="{order_url}" style="display:inline-block;margin-top:16px;background:#5c3d3d;color:#fdf6f0;padding:12px 24px;border-radius:4px;text-decoration:none;font-size:14px;">Track My Order</a>
    """
    return _send(customer_email, "Custom Order Confirmed — Everbloom", BASE.format(body=body))


def send_manual_email(to_email, subject, message, from_name="Everbloom"):
    body = f"""
    <p style="color:#3a2a2a;line-height:1.8;">{message.replace(chr(10), '<br>')}</p>
    """
    return _send(to_email, subject, BASE.format(body=body))
