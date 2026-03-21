import sys
from flask_mail import Message
from flask import current_app


ORDER_STATUSES_MSGS = {
    "advance_requested": ("Advance Payment Required — Everbloom", "Your advance payment details are ready."),
    "advance_confirmed": ("Your Order is Being Crafted — Everbloom", "We've confirmed your payment and crafting has begun!"),
    "crafting":          ("Crafting in Progress — Everbloom", "Our artisans are working on your piece."),
    "quality_check":     ("Quality Check in Progress — Everbloom", "Your order is undergoing quality inspection."),
    "shipped":           ("Your Order is Shipped — Everbloom", "Your handcrafted piece is on its way!"),
    "delivered":         ("Your Order has been Delivered — Everbloom", "Thank you for shopping with Everbloom!"),
    "cancelled":         ("Your Order has been Cancelled — Everbloom", "Your order has been cancelled."),
}

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


def _send(to, subject, html):
    try:
        from app import mail
        # Check credentials are set before attempting
        username = current_app.config.get("MAIL_USERNAME", "")
        password = current_app.config.get("MAIL_PASSWORD", "")
        if not username or not password:
            print(f"[email SKIP] MAIL_USERNAME or MAIL_PASSWORD not set in env vars", file=sys.stderr)
            return False
        msg = Message(subject, recipients=[to], html=html)
        mail.send(msg)
        print(f"[email OK] sent '{subject}' to {to}", file=sys.stderr)
        return True
    except Exception as e:
        print(f"[email ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        current_app.logger.error(f"Email error: {e}")
        return False


def send_order_placed(user_email, order):
    body = f"""
    <h2 style="color:#5c3d3d;">Order Placed!</h2>
    <p style="color:#3a2a2a;">Hi {order.get('name','there')},<br>
    Your order <strong>#{str(order['id'])[:8].upper()}</strong> has been placed successfully.
    Our team will review it and send you payment details shortly.</p>
    <p style="color:#3a2a2a;"><strong>Total:</strong> &#8377;{order['total']}</p>
    <p style="color:#7a5c5c;font-size:14px;">No payment needed right now.</p>
    """
    return _send(user_email, "Order Placed — Everbloom", BASE.format(body=body))


def send_advance_requested(user_email, order, upi_id, upi_qr_url, site_url):
    pay_link = f"{site_url}/orders/{order['id']}/pay-advance"
    qr_html = f'<img src="{upi_qr_url}" style="width:180px;border-radius:8px;margin:12px 0;display:block;" alt="UPI QR">' if upi_qr_url else ""
    body = f"""
    <h2 style="color:#5c3d3d;">Advance Payment Required</h2>
    <p style="color:#3a2a2a;">Hi {order.get('name','there')},<br>
    Please pay an advance of <strong>&#8377;{order['advance_amount']}</strong> to confirm your order.</p>
    <p style="color:#3a2a2a;"><strong>UPI ID:</strong> {upi_id}</p>
    {qr_html}
    <a href="{pay_link}" style="display:inline-block;margin-top:16px;background:#5c3d3d;color:#fdf6f0;padding:12px 24px;border-radius:4px;text-decoration:none;font-size:14px;">Upload Payment Screenshot</a>
    """
    return _send(user_email, "Advance Payment Required — Everbloom", BASE.format(body=body))


def send_status_update(user_email, order, status, note=None):
    subject, headline = ORDER_STATUSES_MSGS.get(
        status, ("Order Update — Everbloom", "Your order status has been updated."))
    note_html = f"<p style='color:#5c3d3d;font-style:italic;'>{note}</p>" if note else ""
    balance_html = ""
    if status == "delivered":
        balance = float(order.get('total', 0)) - float(order.get('advance_amount') or 0)
        balance_html = f"<p style='color:#3a2a2a;'>Balance due on delivery: <strong>&#8377;{balance:.0f}</strong></p>"
    body = f"""
    <h2 style="color:#5c3d3d;">{headline}</h2>
    <p style="color:#3a2a2a;">Order <strong>#{str(order['id'])[:8].upper()}</strong></p>
    {note_html}
    {balance_html}
    """
    return _send(user_email, subject, BASE.format(body=body))


def send_custom_request_received(user_email, name):
    body = f"""
    <h2 style="color:#5c3d3d;">Custom Order Request Received!</h2>
    <p style="color:#3a2a2a;">Hi {name},<br>
    We've received your custom order request and will get back to you within 2–3 business days.</p>
    """
    return _send(user_email, "Custom Request Received — Everbloom", BASE.format(body=body))


def send_welcome(user_email, name):
    body = f"""
    <h2 style="color:#5c3d3d;">Welcome to Everbloom!</h2>
    <p style="color:#3a2a2a;">Hi {name},<br>
    Your account has been created. Browse our handcrafted collection and find something you'll treasure.</p>
    """
    return _send(user_email, "Welcome to Everbloom", BASE.format(body=body))
