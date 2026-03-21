"""
db.py — PostgreSQL connection via psycopg2 (Supabase-hosted Postgres)
Uses a simple connection-per-request pattern safe for Vercel serverless.
"""
import os
import psycopg2
import psycopg2.extras
from contextlib import contextmanager

DATABASE_URL = os.environ.get("DATABASE_URL", "")


def get_conn():
    """Open a new connection. Caller is responsible for closing."""
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn


@contextmanager
def get_db():
    """Context manager — auto-commits and closes."""
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def query(sql, params=None, fetchone=False, fetchall=False):
    """Run a query and optionally fetch results."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            if fetchone:
                return cur.fetchone()
            if fetchall:
                return cur.fetchall()
            return cur.rowcount


def init_db():
    """Create all tables if they don't exist. Run once on deploy."""
    sql = """
    CREATE EXTENSION IF NOT EXISTS pgcrypto;

    CREATE TABLE IF NOT EXISTS users (
        id          SERIAL PRIMARY KEY,
        full_name   TEXT NOT NULL,
        email       TEXT UNIQUE NOT NULL,
        phone       TEXT,
        address     TEXT,
        password_hash TEXT NOT NULL,
        role        TEXT NOT NULL DEFAULT 'customer',
        created_at  TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS categories (
        id          SERIAL PRIMARY KEY,
        name        TEXT NOT NULL,
        slug        TEXT UNIQUE NOT NULL,
        icon        TEXT DEFAULT '🎨',
        description TEXT
    );

    CREATE TABLE IF NOT EXISTS products (
        id               SERIAL PRIMARY KEY,
        title            TEXT NOT NULL,
        slug             TEXT UNIQUE,
        description      TEXT,
        price            NUMERIC(10,2) NOT NULL,
        discount_percent INTEGER DEFAULT 0,
        images           TEXT DEFAULT '',
        category_id      INTEGER REFERENCES categories(id),
        stock_qty        INTEGER DEFAULT 0,
        is_featured      BOOLEAN DEFAULT FALSE,
        is_active        BOOLEAN DEFAULT TRUE,
        tags             TEXT DEFAULT '',
        created_at       TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS orders (
        id               SERIAL PRIMARY KEY,
        customer_id      INTEGER REFERENCES users(id) NOT NULL,
        total_amount     NUMERIC(10,2) NOT NULL,
        advance_amount   NUMERIC(10,2) DEFAULT 0,
        advance_proof    TEXT,
        final_proof      TEXT,
        addr_name        TEXT,
        addr_phone       TEXT,
        addr_street      TEXT,
        addr_city        TEXT,
        addr_state       TEXT,
        addr_pin         TEXT,
        status           TEXT DEFAULT 'draft',
        notes            TEXT,
        admin_note       TEXT,
        delivered_at     TIMESTAMPTZ,
        created_at       TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS order_items (
        id          SERIAL PRIMARY KEY,
        order_id    INTEGER REFERENCES orders(id) ON DELETE CASCADE,
        product_id  INTEGER REFERENCES products(id),
        quantity    INTEGER NOT NULL,
        unit_price  NUMERIC(10,2) NOT NULL,
        title_snap  TEXT,
        image_snap  TEXT
    );

    CREATE TABLE IF NOT EXISTS tracking_events (
        id          SERIAL PRIMARY KEY,
        order_id    INTEGER REFERENCES orders(id) ON DELETE CASCADE,
        status      TEXT NOT NULL,
        note        TEXT,
        created_by  INTEGER REFERENCES users(id),
        created_at  TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS notifications (
        id          SERIAL PRIMARY KEY,
        user_id     INTEGER REFERENCES users(id) ON DELETE CASCADE,
        order_id    INTEGER REFERENCES orders(id) ON DELETE CASCADE,
        title       TEXT NOT NULL,
        message     TEXT NOT NULL,
        is_read     BOOLEAN DEFAULT FALSE,
        created_at  TIMESTAMPTZ DEFAULT NOW()
    );

    -- Seed categories if empty
    INSERT INTO categories (name, slug, icon, description) VALUES
        ('Paintings',  'paintings',  '🎨', 'Original hand-painted artworks'),
        ('Pottery',    'pottery',    '🏺', 'Handcrafted clay and ceramic pieces'),
        ('Jewelry',    'jewelry',    '💍', 'Artisan-made jewelry and accessories'),
        ('DIY Kits',   'diy-kits',   '🧰', 'Complete craft kits for home creation'),
        ('Textiles',   'textiles',   '🧵', 'Handwoven and embroidered fabrics'),
        ('Sculptures', 'sculptures', '🗿', 'Three-dimensional art pieces')
    ON CONFLICT (slug) DO NOTHING;
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
    print("✓ Database initialised")
