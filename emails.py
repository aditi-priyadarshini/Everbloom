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
    "order_placed":      ("Order Placed — Everbloom",            "<h2 style='color:#5c3d3d;'>Order Placed!</h2><p style='color:#3a2a2a;'>Hi {{name}},<br>Your order <strong>#{{order_id}}</strong> has been placed. Total: ₹{{total}}</p>"),
    "advance_requested": ("Advance Payment Required — Everbloom", "<h2 style='color:#5c3d3d;'>Advance Payment Required</h2><p style='color:#3a2a2a;'>Hi {{name}},<br>Pay advance of <strong>₹{{advance_amount}}</strong>. UPI ID: {{upi_id}}</p><p><a href='{{pay_link}}' style='background:#5c3d3d;color:#fdf6f0;padding:12px 24px;border-radius:4px;text-decoration:none;'>Upload Screenshot</a></p>"),
    "advance_confirmed": ("Payment Confirmed — Everbloom",        "<h2 style='color:#5c3d3d;'>Payment Confirmed!</h2><p style='color:#3a2a2a;'>Hi {{name}}, crafting has begun on order #{{order_id}}!</p>"),
    "crafting":          ("Crafting in Progress — Everbloom",     "<h2 style='color:#5c3d3d;'>Crafting in Progress</h2><p style='color:#3a2a2a;'>Hi {{name}}, artisans are working on order #{{order_id}}.</p>"),
    "quality_check":     ("Quality Check — Everbloom",            "<h2 style='color:#5c3d3d;'>Quality Check</h2><p style='color:#3a2a2a;'>Hi {{name}}, order #{{order_id}} is being inspected.</p>"),
    "shipped":           ("Your Order is Shipped — Everbloom",    "<h2 style='color:#5c3d3d;'>Shipped!</h2><p style='color:#3a2a2a;'>Hi {{name}}, order #{{order_id}} is on its way!</p>"),
    "delivered":         ("Order Delivered — Everbloom",          "<h2 style='color:#5c3d3d;'>Delivered!</h2><p style='color:#3a2a2a;'>Hi {{name}}, thanks for shopping! Balance due: ₹{{balance}}.</p>"),
    "cancelled":         ("Order Cancelled — Everbloom",          "<h2 style='color:#5c3d3d;'>Order Cancelled</h2><p style='color:#3a2a2a;'>Hi {{name}}, order #{{order_id}} has been cancelled.</p>"),
    "welcome":           ("Welcome to Everbloom!",                "<h2 style='color:#5c3d3d;'>Welcome!</h2><p style='color:#3a2a2a;'>Hi {{name}}, your account is ready. Start shopping!</p>"),
    "custom_request":    ("Custom Request Received — Everbloom",  "<h2 style='color:#5c3d3d;'>Request Received!</h2><p style='color:#3a2a2a;'>Hi {{name}}, we'll review your custom order request in 2–3 days.</p>"),
}


def _get_template(key):
    """Load template from DB, fall back to default."""
    try:
        import models
        t = models.get_email_template(key)
        if t:
            return t["subject"], t["body_html"]
    except Exception:
        pass
    default = DEFAULTS.get(key)
    if default:
        return default
    return "Everbloom Update", "<p>Hi there, you have an update from Everbloom.</p>"


def _render(body_html, variables):
    """Replace {{var}} placeholders with actual values."""
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
        print(f"[email OK] '{subject}' → {to}", file=sys.stderr)
        return True
    except Exception as e:
        print(f"[email ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        current_app.logger.error(f"Email error: {e}")
        return False


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
    # Append QR after body if present
    if qr_html:
        html = html + qr_html
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
