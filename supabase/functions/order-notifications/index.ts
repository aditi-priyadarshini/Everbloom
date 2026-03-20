// supabase/functions/order-notifications/index.ts
// Deploy with: supabase functions deploy order-notifications

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const RESEND_API_KEY = Deno.env.get("RESEND_API_KEY")!;
const FROM_EMAIL = "Everbloom <orders@everbloom.store>";

const STATUS_LABELS: Record<string, string> = {
  placed: "Order Placed",
  payment_confirmed: "Payment Confirmed",
  accepted: "Accepted by Artist",
  material_sourced: "Raw Materials Sourced",
  crafting: "Crafting in Progress",
  quality_check: "Quality Check",
  packed: "Packed & Ready",
  shipped: "Shipped",
  delivered: "Delivered 🌸",
  cancelled: "Cancelled",
};

const STATUS_MESSAGES: Record<string, string> = {
  placed: "We've received your order and it's awaiting payment confirmation.",
  payment_confirmed: "Your payment has been confirmed! Your order is now being reviewed by our artist.",
  accepted: "Great news! Our artist has accepted your order and will begin working on it soon.",
  material_sourced: "The raw materials for your piece have been carefully sourced and gathered.",
  crafting: "Your piece is now being lovingly handcrafted by our artist. This is where the magic happens!",
  quality_check: "Your piece has passed crafting and is going through our quality check. Almost there!",
  packed: "Your Everbloom piece has been carefully packed and is ready to be shipped.",
  shipped: "Your order is on its way! It has been handed over to our delivery partner.",
  delivered: "Your Everbloom piece has been delivered! We hope you love it. 🌸",
  cancelled: "Your order has been cancelled. If you have any questions, please contact us.",
};

function getEmailHTML(orderData: any, status: string, note?: string) {
  const statusLabel = STATUS_LABELS[status] || status;
  const statusMessage = STATUS_MESSAGES[status] || "Your order has been updated.";

  const trackingSteps = [
    "placed", "payment_confirmed", "accepted", "material_sourced",
    "crafting", "quality_check", "packed", "shipped", "delivered"
  ];

  const currentIndex = trackingSteps.indexOf(status);

  const stepsHTML = trackingSteps.map((step, i) => {
    const isCompleted = i <= currentIndex;
    const isCurrent = i === currentIndex;
    return `
      <div style="display:flex;align-items:center;margin-bottom:8px;">
        <div style="width:24px;height:24px;border-radius:50%;background:${isCompleted ? '#8B5E3C' : '#E8DDD4'};
          display:flex;align-items:center;justify-content:center;margin-right:12px;flex-shrink:0;">
          ${isCompleted ? '<span style="color:white;font-size:12px;">✓</span>' : ''}
        </div>
        <span style="font-size:14px;color:${isCurrent ? '#8B5E3C' : isCompleted ? '#5C4033' : '#9E8E85'};
          font-weight:${isCurrent ? '600' : '400'};">
          ${STATUS_LABELS[step]}
        </span>
      </div>
    `;
  }).join('');

  return `
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#FAF6F1;font-family:'Georgia',serif;">
  <div style="max-width:600px;margin:0 auto;background:#FAF6F1;">

    <!-- Header -->
    <div style="background:#2C1810;padding:32px;text-align:center;">
      <h1 style="color:#F0E6D6;margin:0;font-size:28px;letter-spacing:3px;font-weight:300;">🌸 EVERBLOOM</h1>
      <p style="color:#C4A882;margin:8px 0 0;font-size:13px;letter-spacing:2px;">HANDCRAFTED WITH LOVE</p>
    </div>

    <!-- Status Badge -->
    <div style="background:#8B5E3C;padding:20px;text-align:center;">
      <p style="color:#F0E6D6;margin:0;font-size:12px;letter-spacing:2px;text-transform:uppercase;">Order Update</p>
      <h2 style="color:#FFFFFF;margin:8px 0 0;font-size:22px;">${statusLabel}</h2>
    </div>

    <!-- Body -->
    <div style="padding:32px;">
      <p style="color:#5C4033;font-size:16px;line-height:1.6;">Dear ${orderData.customer_name},</p>
      <p style="color:#5C4033;font-size:16px;line-height:1.6;">${statusMessage}</p>

      ${note ? `
      <div style="background:#F0E6D6;border-left:4px solid #8B5E3C;padding:16px;margin:20px 0;border-radius:4px;">
        <p style="margin:0;color:#5C4033;font-size:14px;"><strong>Artist Note:</strong> ${note}</p>
      </div>` : ''}

      <!-- Order Info -->
      <div style="background:#FFFFFF;border-radius:8px;padding:20px;margin:24px 0;border:1px solid #E8DDD4;">
        <p style="margin:0 0 8px;color:#9E8E85;font-size:12px;letter-spacing:1px;text-transform:uppercase;">Order Details</p>
        <p style="margin:0;color:#2C1810;font-size:15px;font-weight:600;">Order #${orderData.order_id.substring(0, 8).toUpperCase()}</p>
        <p style="margin:4px 0 0;color:#5C4033;font-size:14px;">Total: ₹${orderData.total_amount}</p>
      </div>

      <!-- Tracking Steps -->
      <div style="background:#FFFFFF;border-radius:8px;padding:20px;margin:24px 0;border:1px solid #E8DDD4;">
        <p style="margin:0 0 16px;color:#9E8E85;font-size:12px;letter-spacing:1px;text-transform:uppercase;">Order Journey</p>
        ${stepsHTML}
      </div>

      <!-- CTA -->
      <div style="text-align:center;margin:32px 0;">
        <a href="${Deno.env.get("SITE_URL")}/track.html?id=${orderData.order_id}"
          style="background:#8B5E3C;color:white;padding:14px 32px;text-decoration:none;
            border-radius:4px;font-size:14px;letter-spacing:1px;display:inline-block;">
          TRACK YOUR ORDER
        </a>
      </div>
    </div>

    <!-- Footer -->
    <div style="background:#2C1810;padding:24px;text-align:center;">
      <p style="color:#C4A882;margin:0;font-size:12px;">© 2024 Everbloom. All handcrafted with love.</p>
      <p style="color:#8B6E5A;margin:8px 0 0;font-size:11px;">You're receiving this because you placed an order with us.</p>
    </div>

  </div>
</body>
</html>`;
}

serve(async (req) => {
  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  try {
    const { order_id, customer_email, customer_name, total_amount, status, note } = await req.json();

    const emailHTML = getEmailHTML(
      { order_id, customer_name, total_amount },
      status,
      note
    );

    const res = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${RESEND_API_KEY}`,
      },
      body: JSON.stringify({
        from: FROM_EMAIL,
        to: [customer_email],
        subject: `Everbloom Order Update: ${STATUS_LABELS[status] || status} — #${order_id.substring(0, 8).toUpperCase()}`,
        html: emailHTML,
      }),
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(JSON.stringify(data));
    }

    return new Response(JSON.stringify({ success: true, data }), {
      headers: { "Content-Type": "application/json" },
    });
  } catch (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
});
