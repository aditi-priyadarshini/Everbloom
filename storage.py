import os, urllib.request, time

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

PRODUCTS_BUCKET = "product-images"
PAYMENTS_BUCKET = "payment-proofs"
QR_BUCKET       = "qr-codes"


def _upload(bucket, path, data, content_type="image/jpeg"):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{path}"
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": content_type,
                 "apikey": SUPABASE_KEY}
    )
    try:
        with urllib.request.urlopen(req) as r:
            if r.status in (200, 201):
                return f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{path}"
    except Exception as e:
        print(f"Storage error: {e}")
    return None


def upload_product_image(file, product_id, index):
    ext = (file.filename or "jpg").rsplit(".", 1)[-1].lower()
    path = f"{product_id}/{index}_{int(time.time())}.{ext}"
    data = file.read()
    return _upload(PRODUCTS_BUCKET, path, data, f"image/{ext}")


def upload_payment_proof(file, order_id):
    ext = (file.filename or "jpg").rsplit(".", 1)[-1].lower()
    path = f"{order_id}/advance_{int(time.time())}.{ext}"
    data = file.read()
    return _upload(PAYMENTS_BUCKET, path, data, f"image/{ext}")


def upload_qr(file):
    ext = (file.filename or "png").rsplit(".", 1)[-1].lower()
    path = f"upi_qr.{ext}"
    data = file.read()
    return _upload(QR_BUCKET, path, data, f"image/{ext}")
