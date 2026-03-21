import os
import psycopg2
import psycopg2.extras
from contextlib import contextmanager

DATABASE_URL = os.environ.get("DATABASE_URL", "")


def get_conn():
    return psycopg2.connect(
        DATABASE_URL,
        cursor_factory=psycopg2.extras.RealDictCursor,
        connect_timeout=10
    )


@contextmanager
def db():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def run(sql, params=None, one=False, many=False):
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            if one:
                return cur.fetchone()
            if many:
                return cur.fetchall() or []
            return cur.rowcount


def init_db():
    sql = """
    CREATE TABLE IF NOT EXISTS users (
        id            SERIAL PRIMARY KEY,
        full_name     TEXT NOT NULL,
        email         TEXT UNIQUE NOT NULL,
        phone         TEXT DEFAULT '',
        address       TEXT DEFAULT '',
        password_hash TEXT NOT NULL,
        role          TEXT NOT NULL DEFAULT 'customer',
        created_at    TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS categories (
        id          SERIAL PRIMARY KEY,
        name        TEXT NOT NULL,
        slug        TEXT UNIQUE NOT NULL,
        icon        TEXT DEFAULT '🎨',
        description TEXT DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS products (
        id               SERIAL PRIMARY KEY,
        title            TEXT NOT NULL,
        description      TEXT DEFAULT '',
        price            NUMERIC(10,2) NOT NULL,
        discount_percent INTEGER DEFAULT 0 CHECK (discount_percent >= 0 AND discount_percent <= 100),
        images           TEXT DEFAULT '',
        category_id      INTEGER REFERENCES categories(id),
        stock_qty        INTEGER DEFAULT 0,
        is_featured      BOOLEAN DEFAULT FALSE,
        is_active        BOOLEAN DEFAULT TRUE,
        tags             TEXT DEFAULT '',
        created_at       TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS orders (
        id             SERIAL PRIMARY KEY,
        customer_id    INTEGER REFERENCES users(id) NOT NULL,
        total_amount   NUMERIC(10,2) NOT NULL,
        advance_amount NUMERIC(10,2) DEFAULT 0,
        advance_proof  TEXT DEFAULT '',
        addr_name      TEXT DEFAULT '',
        addr_phone     TEXT DEFAULT '',
        addr_street    TEXT DEFAULT '',
        addr_city      TEXT DEFAULT '',
        addr_state     TEXT DEFAULT '',
        addr_pin       TEXT DEFAULT '',
        notes          TEXT DEFAULT '',
        admin_note     TEXT DEFAULT '',
        status         TEXT DEFAULT 'placed',
        delivered_at   TIMESTAMPTZ,
        created_at     TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS order_items (
        id         SERIAL PRIMARY KEY,
        order_id   INTEGER REFERENCES orders(id) ON DELETE CASCADE,
        product_id INTEGER REFERENCES products(id),
        quantity   INTEGER NOT NULL,
        unit_price NUMERIC(10,2) NOT NULL,
        title_snap TEXT DEFAULT '',
        image_snap TEXT DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS tracking (
        id         SERIAL PRIMARY KEY,
        order_id   INTEGER REFERENCES orders(id) ON DELETE CASCADE,
        status     TEXT NOT NULL,
        note       TEXT DEFAULT '',
        created_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS notifications (
        id         SERIAL PRIMARY KEY,
        user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
        order_id   INTEGER REFERENCES orders(id) ON DELETE SET NULL,
        title      TEXT NOT NULL,
        message    TEXT NOT NULL,
        is_read    BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );

    INSERT INTO categories (name, slug, icon, description) VALUES
        ('Paintings',  'paintings',  '🎨', 'Original hand-painted artworks'),
        ('Pottery',    'pottery',    '🏺', 'Handcrafted clay and ceramic pieces'),
        ('Jewellery',  'jewellery',  '💍', 'Artisan-made jewellery and accessories'),
        ('DIY Kits',   'diy-kits',   '🧰', 'Complete craft kits for home creation'),
        ('Textiles',   'textiles',   '🧵', 'Handwoven and embroidered fabrics'),
        ('Sculptures', 'sculptures', '🗿', 'Three-dimensional art pieces')
    ON CONFLICT (slug) DO NOTHING;
    """
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
    print("DB ready")
