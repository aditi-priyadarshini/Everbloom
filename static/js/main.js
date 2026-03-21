// ============================================================
// EVERBLOOM — Main JS (Flask edition)
// ============================================================

// ── Mobile Nav ───────────────────────────────────────────────
function toggleMobileNav() {
  const nav     = document.getElementById('mobile-nav');
  const overlay = document.getElementById('nav-overlay');
  if (nav)     nav.classList.toggle('open');
  if (overlay) overlay.classList.toggle('open');
  document.body.style.overflow = nav?.classList.contains('open') ? 'hidden' : '';
}

// ── Notification Bell ────────────────────────────────────────
function toggleNotifDropdown() {
  const dd = document.getElementById('notif-dropdown');
  if (!dd) return;
  const isOpen = dd.classList.toggle('open');
  if (isOpen) loadNotifications();
}

async function loadNotifications() {
  const list = document.getElementById('notif-list');
  if (!list) return;

  try {
    const res  = await fetch('/notifications');
    const data = await res.json();

    if (!data.length) {
      list.innerHTML = '<div style="padding:28px;text-align:center;color:var(--text-muted);font-size:14px">No notifications yet</div>';
      return;
    }

    list.innerHTML = data.map(n => `
      <div class="notif-item ${n.is_read ? '' : 'unread'}"
           onclick="markNotifRead(${n.id}, ${n.order_id || 'null'})">
        <div style="font-size:13px;font-weight:${n.is_read ? '400' : '600'};color:var(--text-primary);margin-bottom:2px">${n.title}</div>
        <div style="font-size:12px;color:var(--text-muted);line-height:1.4">${n.message}</div>
        <div style="font-size:11px;color:var(--text-muted);margin-top:4px">${n.created_at}</div>
      </div>
    `).join('');
  } catch (e) {
    list.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-muted);font-size:13px">Could not load notifications</div>';
  }
}

async function markNotifRead(notifId, orderId) {
  await fetch(`/notifications/read/${notifId}`, { method: 'POST' });
  if (orderId) window.location.href = `/orders/${orderId}/track`;
  else loadNotifications();
}

async function markAllRead() {
  await fetch('/notifications/read-all', { method: 'POST' });
  document.getElementById('notif-badge').style.display = 'none';
  loadNotifications();
}

// Poll notification count every 30s
async function pollNotifCount() {
  const badge = document.getElementById('notif-badge');
  if (!badge) return;
  try {
    const res   = await fetch('/notifications/count');
    const data  = await res.json();
    const count = data.count || 0;
    badge.textContent = count;
    badge.style.display = count > 0 ? 'flex' : 'none';
  } catch (e) {}
}

// Close notification dropdown on outside click
document.addEventListener('click', (e) => {
  const dd  = document.getElementById('notif-dropdown');
  const btn = document.getElementById('notif-btn');
  if (dd && !dd.contains(e.target) && btn && !btn.contains(e.target)) {
    dd.classList.remove('open');
  }
});

// ── Auto-dismiss flash messages ──────────────────────────────
function initFlashMessages() {
  document.querySelectorAll('.flash').forEach(flash => {
    setTimeout(() => {
      flash.style.animation = 'slideIn 0.3s ease reverse';
      setTimeout(() => flash.remove(), 300);
    }, 4500);
  });
}

// ── Image upload preview (shared) ───────────────────────────
function previewImages(files, previewGridId = 'preview-grid') {
  const grid = document.getElementById(previewGridId);
  if (!grid) return;
  grid.innerHTML = '';
  Array.from(files).forEach((file, i) => {
    if (!file.type.startsWith('image/')) return;
    const url = URL.createObjectURL(file);
    grid.innerHTML += `
      <div class="img-preview-item">
        <img src="${url}" alt="Preview ${i + 1}">
        ${i === 0 ? '<div style="position:absolute;bottom:4px;left:4px;background:var(--brown-accent);color:white;font-size:9px;padding:2px 6px;border-radius:2px;letter-spacing:1px">MAIN</div>' : ''}
      </div>`;
  });
}

// ── CSRF token helper for fetch() calls ──────────────────────
function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  if (meta) return meta.getAttribute('content');
  // fallback: grab from any hidden csrf input on the page
  const input = document.querySelector('input[name="csrf_token"]');
  return input ? input.value : '';
}

// ── Format price (used in JS calculations) ───────────────────
function formatPrice(amount) {
  return '₹' + Number(amount).toLocaleString('en-IN', { minimumFractionDigits: 0 });
}

// ── On DOM ready ─────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initFlashMessages();
  pollNotifCount();
  setInterval(pollNotifCount, 30000);
});
