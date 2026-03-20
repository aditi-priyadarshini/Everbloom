// ============================================
// EVERBLOOM — Supabase Client
// Reads config from js/env.js (window.ENV)
// ============================================

const supabase = window.supabase.createClient(
  window.ENV.SUPABASE_URL,
  window.ENV.SUPABASE_ANON_KEY
);

async function getCurrentUser() {
  const { data: { user } } = await supabase.auth.getUser();
  return user;
}

async function getCurrentProfile() {
  const user = await getCurrentUser();
  if (!user) return null;
  const { data } = await supabase.from('profiles').select('*').eq('id', user.id).single();
  return data;
}

async function requireAuth(redirectTo = '/login.html') {
  const user = await getCurrentUser();
  if (!user) { window.location.href = redirectTo; return null; }
  return user;
}

async function requireAdmin() {
  const profile = await getCurrentProfile();
  if (!profile || profile.role !== 'admin') { window.location.href = '/index.html'; return null; }
  return profile;
}

async function signOut() {
  await supabase.auth.signOut();
  window.location.href = '/index.html';
}

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
  setTimeout(() => { toast.style.animation = 'slideIn 0.3s ease reverse'; setTimeout(() => toast.remove(), 300); }, duration);
}

const Cart = {
  get() { return JSON.parse(localStorage.getItem('everbloom_cart') || '[]'); },
  save(items) { localStorage.setItem('everbloom_cart', JSON.stringify(items)); Cart.updateBadge(); },
  add(product, qty = 1) {
    const items = Cart.get();
    const existing = items.find(i => i.id === product.id);
    if (existing) { existing.qty = Math.min(existing.qty + qty, product.stock_qty); }
    else { items.push({ id: product.id, title: product.title, price: product.final_price, image: product.images?.[0] || '', stock_qty: product.stock_qty, qty }); }
    Cart.save(items);
    showToast('Added to cart!', 'success');
  },
  remove(productId) { Cart.save(Cart.get().filter(i => i.id !== productId)); },
  updateQty(productId, qty) {
    const items = Cart.get();
    const item = items.find(i => i.id === productId);
    if (item) { if (qty <= 0) return Cart.remove(productId); item.qty = qty; Cart.save(items); }
  },
  total() { return Cart.get().reduce((sum, i) => sum + (i.price * i.qty), 0); },
  count() { return Cart.get().reduce((sum, i) => sum + i.qty, 0); },
  clear() { localStorage.removeItem('everbloom_cart'); Cart.updateBadge(); },
  updateBadge() {
    const badge = document.querySelector('#cart-badge');
    if (badge) { const c = Cart.count(); badge.textContent = c; badge.style.display = c > 0 ? 'flex' : 'none'; }
  }
};

async function sendOrderEmail(orderId, customerEmail, customerName, totalAmount, status, note = '') {
  try {
    await supabase.functions.invoke('order-notifications', {
      body: { order_id: orderId, customer_email: customerEmail, customer_name: customerName, total_amount: totalAmount, status, note, site_url: window.ENV.SITE_URL }
    });
  } catch(e) { console.warn('Email failed:', e); }
}

function formatPrice(amount) { return `₹${Number(amount).toLocaleString('en-IN', { minimumFractionDigits: 0 })}`; }
function formatDate(d) { return new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }); }
function formatDateTime(d) { return new Date(d).toLocaleString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }); }

function toggleMobileNav() {
  document.getElementById('mobile-nav')?.classList.toggle('open');
  document.getElementById('nav-overlay')?.classList.toggle('open');
}

document.addEventListener('DOMContentLoaded', () => Cart.updateBadge());
