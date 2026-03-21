from flask_mail import Message
from flask import current_app, render_template_string


def _mail():
    from app import mail
    return mail


ORDER_STATUSES_MSGS = {
    "advance_requested": ("Advance Payment Required — Everbloom", "Your advance payment details are ready."),
    "advance_confirmed": ("Your Order is Being Crafted — Everbloom", "We've confirmed your payment and crafting has begun!"),
    "crafting": ("Your Order is Being Crafted — Everbloom", "Our artisans are working on your piece."),
    "quality_check": ("Quality Check in Progress — Everbloom", "Your order is undergoing quality inspection."),
    "shipped": ("Your Order is Shipped — Everbloom", "Your handcrafted piece is on its way!"),
    "delivered": ("Your Order has been Delivered — Everbloom", "Thank you for shopping with Everbloom!"),
    "cancelled": ("Your Order has been Cancelled — Everbloom", "Your order has been cancelled."),
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
    <p style="color:#7a5c5c;font-size:12px;margin:0;">Questions? Reply to this email or WhatsApp us.<br>With love, <strong>Team Everbloom</strong></p>
  </div>
</div>
"""


def _send(to, subject, html):
    try:
        msg = Message(subject, recipients=[to], html=html)
        _mail().send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Email error: {e}")
        return False


def send_order_placed(user_email, order):
    body = f"""
    <h2 style="color:#5c3d3d;">Order Placed!</h2>
    <p style="color:#3a2a2a;">Hi {order.get('name','there')},<br>
    Your order <strong>#{str(order['id'])[:8].upper()}</strong> has been placed successfully.
    Our team will review it and get back to you with payment details.</p>
    <p style="color:#3a2a2a;"><strong>Total:</strong> ₹{order['total']}</p>
    <p style="color:#7a5c5c;font-size:14px;">No payment needed right now — we'll reach out shortly.</p>
    """
    return _send(user_email, "Order Placed — Everbloom", BASE.format(body=body))


def send_advance_requested(user_email, order, upi_id, upi_qr_url, site_url):
    pay_link = f"{site_url}/orders/{order['id']}/pay-advance"
    body = f"""
    <h2 style="color:#5c3d3d;">Advance Payment Required</h2>
    <p style="color:#3a2a2a;">Hi {order.get('name','there')},<br>
    Please pay an advance of <strong>₹{order['advance_amount']}</strong> to confirm your order.</p>
    <p style="color:#3a2a2a;"><strong>UPI ID:</strong> {upi_id}</p>
    {'<img src="'+upi_qr_url+'" style="width:180px;border-radius:8px;" alt="UPI QR">' if upi_qr_url else ''}
    <br><br>
    <a href="{pay_link}" style="background:#5c3d3d;color:#fdf6f0;padding:12px 24px;border-radius:4px;text-decoration:none;font-size:14px;">Upload Payment Screenshot</a>
    """
    return _send(user_email, "Advance Payment Required — Everbloom", BASE.format(body=body))


def send_status_update(user_email, order, status, note=None):
    subject, headline = ORDER_STATUSES_MSGS.get(status, ("Order Update — Everbloom", "Your order status has been updated."))
    extra = f"<p style='color:#5c3d3d;'><em>{note}</em></p>" if note else ""
    body = f"""
    <h2 style="color:#5c3d3d;">{headline}</h2>
    <p style="color:#3a2a2a;">Order <strong>#{str(order['id'])[:8].upper()}</strong></p>
    {extra}
    """
    if status == "delivered":
        body += f"<p style='color:#3a2a2a;'>Balance due: <strong>₹{float(order['total']) - float(order.get('advance_amount') or 0):.2f}</strong> (collect on delivery).</p>"
    return _send(user_email, subject, BASE.format(body=body))


def send_custom_request_received(user_email, name):
    body = f"""
    <h2 style="color:#5c3d3d;">Custom Order Request Received!</h2>
    <p style="color:#3a2a2a;">Hi {name},<br>
    We've received your custom order request. Our artisans will review it and get back to you within 2–3 business days.</p>
    """
    return _send(user_email, "Custom Request Received — Everbloom", BASE.format(body=body))


def send_welcome(user_email, name):
    body = f"""
    <h2 style="color:#5c3d3d;">Welcome to Everbloom!</h2>
    <p style="color:#3a2a2a;">Hi {name},<br>
    Your account has been created. Browse our handcrafted collection and find something you'll treasure.</p>
    """
    return _send(user_email, "Welcome to Everbloom", BASE.format(body=body))
