// js/supabase.js — Everbloom Supabase Client

// ============================================
// CONFIG — Replace with your Supabase project values
// ============================================
const SUPABASE_URL = 'YOUR_SUPABASE_URL';
const SUPABASE_ANON_KEY = 'YOUR_SUPABASE_ANON_KEY';

// Initialize Supabase client (loaded via CDN in HTML)
const supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

// ============================================
// AUTH HELPERS
// ============================================
async function getCurrentUser() {
  const { data: { user } } = await supabase.auth.getUser();
  return user;
}

async function getCurrentProfile() {
  const user = await getCurrentUser();
  if (!user) return null;
  const { data } = await supabase
    .from('profiles')
    .select('*')
    .eq('id', user.id)
    .single();
  return data;
}

async function requireAuth(redirectTo = '/login.html') {
  const user = await getCurrentUser();
  if (!user) {
    window.location.href = redirectTo;
    return null;
  }
  return user;
}

async function requireAdmin() {
  const profile = await getCurrentProfile();
  if (!profile || profile.role !== 'admin') {
    window.location.href = '/index.html';
    return null;
  }
  return profile;
}

async function signOut() {
  await supabase.auth.signOut();
  window.location.href = '/index.html';
}

// ============================================
// TOAST NOTIFICATIONS
// ============================================
function showToast(message, type = 'default', duration = 3500) {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  const icons = { success: '✓', error: '✕', warning: '⚠', default: '🌸' };
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${icons[type] || icons.default}</span><span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.animation = 'slideIn 0.3s ease reverse';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// ============================================
// CART (localStorage)
// ============================================
const Cart = {
  get() {
    return JSON.parse(localStorage.getItem('everbloom_cart') || '[]');
  },
  save(items) {
    localStorage.setItem('everbloom_cart', JSON.stringify(items));
    Cart.updateBadge();
  },
  add(product, qty = 1) {
    const items = Cart.get();
    const existing = items.find(i => i.id === product.id);
    if (existing) {
      existing.qty = Math.min(existing.qty + qty, product.stock_qty);
    } else {
      items.push({
        id: product.id,
        title: product.title,
        price: product.final_price,
        image: product.images?.[0] || '',
        stock_qty: product.stock_qty,
        qty
      });
    }
    Cart.save(items);
    showToast('Added to cart!', 'success');
  },
  remove(productId) {
    Cart.save(Cart.get().filter(i => i.id !== productId));
  },
  updateQty(productId, qty) {
    const items = Cart.get();
    const item = items.find(i => i.id === productId);
    if (item) {
      if (qty <= 0) return Cart.remove(productId);
      item.qty = qty;
      Cart.save(items);
    }
  },
  total() {
    return Cart.get().reduce((sum, i) => sum + (i.price * i.qty), 0);
  },
  count() {
    return Cart.get().reduce((sum, i) => sum + i.qty, 0);
  },
  clear() {
    localStorage.removeItem('everbloom_cart');
    Cart.updateBadge();
  },
  updateBadge() {
    const badge = document.querySelector('#cart-badge');
    if (badge) {
      const count = Cart.count();
      badge.textContent = count;
      badge.style.display = count > 0 ? 'flex' : 'none';
    }
  }
};

// ============================================
// TRIGGER EMAIL NOTIFICATION
// ============================================
async function sendOrderEmail(orderId, customerEmail, customerName, totalAmount, status, note = '') {
  try {
    await supabase.functions.invoke('order-notifications', {
      body: { order_id: orderId, customer_email: customerEmail, customer_name: customerName, total_amount: totalAmount, status, note }
    });
  } catch (e) {
    console.warn('Email notification failed:', e);
  }
}

// ============================================
// FORMAT HELPERS
// ============================================
function formatPrice(amount) {
  return `₹${Number(amount).toLocaleString('en-IN', { minimumFractionDigits: 0 })}`;
}

function formatDate(dateStr) {
  return new Date(dateStr).toLocaleDateString('en-IN', {
    day: 'numeric', month: 'short', year: 'numeric'
  });
}

function formatDateTime(dateStr) {
  return new Date(dateStr).toLocaleString('en-IN', {
    day: 'numeric', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  });
}

// ============================================
// STATUS CONFIG
// ============================================
const ORDER_STATUSES = [
  { key: 'placed', label: 'Order Placed', icon: '🛒', color: '#8B6E3C' },
  { key: 'payment_confirmed', label: 'Payment Confirmed', icon: '✅', color: '#4A7A4D' },
  { key: 'accepted', label: 'Accepted by Artist', icon: '🎨', color: '#3B6DB8' },
  { key: 'material_sourced', label: 'Raw Material Sourced', icon: '🪵', color: '#5A7A53' },
  { key: 'crafting', label: 'Crafting in Progress', icon: '✂️', color: '#8B6A20' },
  { key: 'quality_check', label: 'Quality Check', icon: '🔍', color: '#8B5E3C' },
  { key: 'packed', label: 'Packed & Ready', icon: '📦', color: '#6A4A8A' },
  { key: 'shipped', label: 'Shipped', icon: '🚚', color: '#2A7A9A' },
  { key: 'delivered', label: 'Delivered', icon: '🌸', color: '#388E3C' },
];

// Update nav active states & cart badge on load
document.addEventListener('DOMContentLoaded', () => {
  Cart.updateBadge();

  // Highlight active nav link
  const links = document.querySelectorAll('.nav-links a');
  links.forEach(link => {
    if (link.href === window.location.href) link.classList.add('active');
  });
});
