"""
storage.py — Supabase Storage client for image uploads.
Vercel has no writable filesystem, so all images go to Supabase Storage.
"""
import os
import io
import urllib.request
import urllib.parse
import json

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

PRODUCT_BUCKET  = "product-images"
PAYMENT_BUCKET  = "payment-proofs"
QR_BUCKET       = "qr-codes"


def _auth_headers(content_type="application/octet-stream"):
    return {
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": content_type,
        "apikey": SUPABASE_SERVICE_KEY,
    }


def upload_file(bucket: str, path: str, file_bytes: bytes, content_type: str = "image/jpeg") -> str | None:
    """
    Upload file_bytes to Supabase Storage bucket at path.
    Returns the public URL or None on failure.
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return None

    url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{path}"
    headers = _auth_headers(content_type)

    try:
        req = urllib.request.Request(url, data=file_bytes, headers=headers, method="POST")
        with urllib.request.urlopen(req) as resp:
            if resp.status in (200, 201):
                return get_public_url(bucket, path)
    except Exception as e:
        print(f"Storage upload error: {e}")
    return None


def get_public_url(bucket: str, path: str) -> str:
    """Return the public URL for an object in a public bucket."""
    return f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{path}"


def delete_file(bucket: str, path: str) -> bool:
    """Delete a file from Supabase Storage."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return False
    url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{path}"
    headers = _auth_headers("application/json")
    try:
        req = urllib.request.Request(url, headers=headers, method="DELETE")
        with urllib.request.urlopen(req) as resp:
            return resp.status in (200, 204)
    except Exception:
        return False


def upload_product_image(file_storage, product_id: int, index: int) -> str | None:
    """Upload a Flask FileStorage object as a product image."""
    ext = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else "jpg"
    path = f"{product_id}/{index}.{ext}"
    file_bytes = file_storage.read()
    ct = f"image/{ext}" if ext != "jpg" else "image/jpeg"
    return upload_file(PRODUCT_BUCKET, path, file_bytes, ct)


def upload_payment_proof(file_storage, order_id: int, proof_type: str = "advance") -> str | None:
    """Upload a payment screenshot."""
    ext = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else "jpg"
    path = f"{order_id}/{proof_type}.{ext}"
    file_bytes = file_storage.read()
    ct = f"image/{ext}" if ext != "jpg" else "image/jpeg"
    return upload_file(PAYMENT_BUCKET, path, file_bytes, ct)


def upload_qr_code(file_storage) -> str | None:
    """Upload UPI QR code image."""
    ext = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else "png"
    file_bytes = file_storage.read()
    ct = f"image/{ext}"
    return upload_file(QR_BUCKET, f"upi_qr.{ext}", file_bytes, ct)
