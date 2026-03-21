from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager


# ── User / Profile ────────────────────────────────────────────────────────────
class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id          = db.Column(db.Integer, primary_key=True)
    full_name   = db.Column(db.String(120), nullable=False)
    email       = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone       = db.Column(db.String(20))
    address     = db.Column(db.Text)
    password_hash = db.Column(db.String(256), nullable=False)
    role        = db.Column(db.String(20), default='customer')  # 'customer' | 'admin'
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    orders = db.relationship('Order', backref='customer', lazy='dynamic')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == 'admin'

    def __repr__(self):
        return f'<User {self.email}>'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ── Category ──────────────────────────────────────────────────────────────────
class Category(db.Model):
    __tablename__ = 'categories'

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(80), nullable=False)
    slug        = db.Column(db.String(80), unique=True, nullable=False)
    icon        = db.Column(db.String(10), default='🎨')
    description = db.Column(db.Text)

    products = db.relationship('Product', backref='category', lazy='dynamic')

    def __repr__(self):
        return f'<Category {self.name}>'


# ── Product ───────────────────────────────────────────────────────────────────
class Product(db.Model):
    __tablename__ = 'products'

    id               = db.Column(db.Integer, primary_key=True)
    title            = db.Column(db.String(200), nullable=False)
    slug             = db.Column(db.String(200), unique=True)
    description      = db.Column(db.Text)
    price            = db.Column(db.Numeric(10, 2), nullable=False)
    discount_percent = db.Column(db.Integer, default=0)
    images           = db.Column(db.Text, default='')   # comma-separated filenames
    category_id      = db.Column(db.Integer, db.ForeignKey('categories.id'))
    stock_qty        = db.Column(db.Integer, default=0)
    is_featured      = db.Column(db.Boolean, default=False)
    is_active        = db.Column(db.Boolean, default=True)
    tags             = db.Column(db.String(300), default='')
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    order_items = db.relationship('OrderItem', backref='product', lazy='dynamic')

    @property
    def final_price(self):
        return float(self.price) * (1 - self.discount_percent / 100)

    @property
    def image_list(self):
        return [i.strip() for i in self.images.split(',') if i.strip()] if self.images else []

    @property
    def first_image(self):
        imgs = self.image_list
        return imgs[0] if imgs else None

    @property
    def tag_list(self):
        return [t.strip() for t in self.tags.split(',') if t.strip()] if self.tags else []

    def __repr__(self):
        return f'<Product {self.title}>'


# ── Order ─────────────────────────────────────────────────────────────────────
# NEW WORKFLOW:
#   draft → pending_review → advance_requested → advance_paid →
#   advance_confirmed → accepted → material_sourced → crafting →
#   quality_check → packed → shipped → delivered → cancelled

ORDER_STATUSES = [
    ('draft',             'Order Received',        '📋'),
    ('pending_review',    'Pending Admin Review',   '👀'),
    ('advance_requested', 'Advance Payment Requested', '💌'),
    ('advance_paid',      'Advance Paid',           '💳'),
    ('advance_confirmed', 'Advance Confirmed',      '✅'),
    ('accepted',          'Order Accepted',         '🎨'),
    ('material_sourced',  'Raw Material Sourced',   '🪵'),
    ('crafting',          'Crafting in Progress',   '✂️'),
    ('quality_check',     'Quality Check',          '🔍'),
    ('packed',            'Packed & Ready',         '📦'),
    ('shipped',           'Shipped',                '🚚'),
    ('delivered',         'Delivered',              '🌸'),
    ('cancelled',         'Cancelled',              '❌'),
]

STATUS_KEYS   = [s[0] for s in ORDER_STATUSES]
STATUS_LABELS = {s[0]: s[1] for s in ORDER_STATUSES}
STATUS_ICONS  = {s[0]: s[2] for s in ORDER_STATUSES}


class Order(db.Model):
    __tablename__ = 'orders'

    id               = db.Column(db.Integer, primary_key=True)
    customer_id      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    total_amount     = db.Column(db.Numeric(10, 2), nullable=False)
    advance_amount   = db.Column(db.Numeric(10, 2), default=0)   # admin sets this
    advance_proof    = db.Column(db.String(300))                   # filename
    final_proof      = db.Column(db.String(300))                   # filename (full payment)

    # Address snapshot
    addr_name        = db.Column(db.String(120))
    addr_phone       = db.Column(db.String(20))
    addr_street      = db.Column(db.Text)
    addr_city        = db.Column(db.String(80))
    addr_state       = db.Column(db.String(80))
    addr_pin         = db.Column(db.String(10))

    status           = db.Column(db.String(30), default='draft')
    notes            = db.Column(db.Text)          # customer notes
    admin_note       = db.Column(db.Text)          # latest admin note (shown on track page)
    delivered_at     = db.Column(db.DateTime)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    items        = db.relationship('OrderItem', backref='order', lazy='subquery', cascade='all, delete-orphan')
    tracking     = db.relationship('TrackingEvent', backref='order', lazy='dynamic',
                                   cascade='all, delete-orphan', order_by='TrackingEvent.created_at')
    notifications = db.relationship('Notification', backref='order', lazy='dynamic',
                                    cascade='all, delete-orphan')

    @property
    def status_label(self):
        return STATUS_LABELS.get(self.status, self.status)

    @property
    def status_icon(self):
        return STATUS_ICONS.get(self.status, '📋')

    @property
    def status_index(self):
        try:
            return STATUS_KEYS.index(self.status)
        except ValueError:
            return 0

    @property
    def address_dict(self):
        return dict(name=self.addr_name, phone=self.addr_phone, street=self.addr_street,
                    city=self.addr_city, state=self.addr_state, pin=self.addr_pin)

    def __repr__(self):
        return f'<Order #{self.id}>'


class OrderItem(db.Model):
    __tablename__ = 'order_items'

    id          = db.Column(db.Integer, primary_key=True)
    order_id    = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id  = db.Column(db.Integer, db.ForeignKey('products.id'))
    quantity    = db.Column(db.Integer, nullable=False)
    unit_price  = db.Column(db.Numeric(10, 2), nullable=False)
    title_snap  = db.Column(db.String(200))   # snapshot in case product deleted
    image_snap  = db.Column(db.String(300))

    @property
    def subtotal(self):
        return float(self.unit_price) * self.quantity


class TrackingEvent(db.Model):
    __tablename__ = 'tracking_events'

    id         = db.Column(db.Integer, primary_key=True)
    order_id   = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    status     = db.Column(db.String(30), nullable=False)
    note       = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    actor = db.relationship('User', foreign_keys=[created_by])


# ── Notification ──────────────────────────────────────────────────────────────
class Notification(db.Model):
    __tablename__ = 'notifications'

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    order_id   = db.Column(db.Integer, db.ForeignKey('orders.id'))
    title      = db.Column(db.String(200), nullable=False)
    message    = db.Column(db.Text, nullable=False)
    is_read    = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
