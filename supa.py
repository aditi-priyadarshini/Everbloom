"""
supa.py — Supabase REST API client.
All database calls go through here. No SQL, no drivers, just HTTP.
"""
import os, requests

URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
KEY = os.environ.get("SUPABASE_KEY", "")

# Use service role key for writes that bypass RLS (optional, falls back to anon)
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", KEY)


def _headers(use_service=False):
    k = SERVICE_KEY if use_service else KEY
    return {
        "apikey": k,
        "Authorization": f"Bearer {k}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _url(table):
    return f"{URL}/rest/v1/{table}"


# ── Core operations ───────────────────────────────────────────

def select(table, filters="", order="", limit=None, single=False):
    """GET rows from a table."""
    params = {"select": "*"}
    if filters:
        # filters is a dict like {"column": "eq.value"}
        params.update(filters)
    if order:
        params["order"] = order
    if limit:
        params["limit"] = limit
    headers = _headers()
    if single:
        headers["Accept"] = "application/vnd.pgrst.object+json"
    r = requests.get(_url(table), headers=headers, params=params)
    if r.status_code in (200, 206):
        return r.json()
    if r.status_code == 406 and single:
        return None
    return [] if not single else None


def select_one(table, filters):
    result = select(table, filters=filters, single=True)
    return result


def insert(table, data, service=True):
    """Insert a row and return it."""
    r = requests.post(_url(table), headers=_headers(service), json=data)
    if r.status_code in (200, 201):
        rows = r.json()
        return rows[0] if isinstance(rows, list) and rows else rows
    raise Exception(f"Insert failed {r.status_code}: {r.text}")


def update(table, filters, data, service=True):
    """Update rows matching filters."""
    r = requests.patch(_url(table), headers=_headers(service), json=data, params=filters)
    if r.status_code in (200, 204):
        return True
    raise Exception(f"Update failed {r.status_code}: {r.text}")


def delete(table, filters, service=True):
    """Delete rows matching filters."""
    r = requests.delete(_url(table), headers=_headers(service), params=filters)
    return r.status_code in (200, 204)


def rpc(fn_name, params=None, service=True):
    """Call a Supabase RPC / Edge Function."""
    r = requests.post(
        f"{URL}/rest/v1/rpc/{fn_name}",
        headers=_headers(service),
        json=params or {}
    )
    if r.status_code == 200:
        return r.json()
    raise Exception(f"RPC {fn_name} failed: {r.text}")


# ── Storage ───────────────────────────────────────────────────

def upload_file(bucket, path, file_bytes, content_type="image/jpeg"):
    """Upload a file to Supabase Storage and return its public URL."""
    r = requests.post(
        f"{URL}/storage/v1/object/{bucket}/{path}",
        headers={
            "apikey": SERVICE_KEY,
            "Authorization": f"Bearer {SERVICE_KEY}",
            "Content-Type": content_type,
        },
        data=file_bytes,
    )
    if r.status_code in (200, 201):
        return f"{URL}/storage/v1/object/public/{bucket}/{path}"
    return None


def upload_image(file_storage, bucket, path):
    """Upload a Flask FileStorage object."""
    import time
    ext = (file_storage.filename or "jpg").rsplit(".", 1)[-1].lower()
    full_path = f"{path}.{ext}"
    data = file_storage.read()
    ct = f"image/{ext}".replace("image/jpg", "image/jpeg")
    return upload_file(bucket, full_path, data, ct)


# ── Convenience query builders ────────────────────────────────

def eq(col, val):
    """Build an equality filter param."""
    return {col: f"eq.{val}"}


def get_by_id(table, id):
    return select_one(table, eq("id", id))


def count(table, filters=None):
    params = {"select": "id"}
    if filters:
        params.update(filters)
    headers = {**_headers(), "Prefer": "count=exact", "Range-Unit": "items", "Range": "0-0"}
    r = requests.get(_url(table), headers=headers, params=params)
    cr = r.headers.get("Content-Range", "0/0")
    try:
        return int(cr.split("/")[1])
    except Exception:
        return 0
