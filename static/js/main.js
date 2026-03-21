// Everbloom — main.js

// ── Mobile nav ────────────────────────────────────────────────
function openMobileNav() {
  document.getElementById('mobile-nav')?.classList.add('open');
  document.getElementById('nav-overlay')?.classList.add('open');
  document.body.style.overflow = 'hidden';
}
function closeMobileNav() {
  document.getElementById('mobile-nav')?.classList.remove('open');
  document.getElementById('nav-overlay')?.classList.remove('open');
  document.body.style.overflow = '';
}

// ── Admin sidebar ─────────────────────────────────────────────
function toggleAdminSidebar() {
  document.querySelector('.admin-sidebar')?.classList.toggle('open');
  document.getElementById('admin-overlay')?.classList.toggle('open');
}

// ── Notification bell ─────────────────────────────────────────
const notifWrap = () => document.getElementById('notif-dd');

function toggleNotif() {
  const dd = notifWrap();
  if (!dd) return;
  const open = dd.classList.toggle('open');
  if (open) loadNotifs();
}

async function loadNotifs() {
  const list = document.getElementById('notif-list');
  if (!list) return;
  try {
    const data = await fetch('/api/notifications').then(r => r.json());
    if (!data.length) {
      list.innerHTML = '<div class="notif-empty">No notifications yet</div>';
      return;
    }
    list.innerHTML = data.map(n => `
      <div class="notif-item ${n.is_read ? '' : 'unread'}" onclick="readNotif(${n.id}, ${n.order_id || 'null'})">
        <div class="notif-item-title">${n.title}</div>
        <div class="notif-item-msg">${n.message}</div>
        <div class="notif-item-time">${n.time}</div>
      </div>`).join('');
  } catch(e) {
    list.innerHTML = '<div class="notif-empty">Could not load notifications</div>';
  }
}

async function readNotif(id, orderId) {
  await fetch(`/api/notifications/read/${id}`, {method:'POST'});
  if (orderId) location.href = `/orders/${orderId}/track`;
  else loadNotifs();
}

async function readAllNotifs() {
  await fetch('/api/notifications/read-all', {method:'POST'});
  document.getElementById('notif-badge').style.display = 'none';
  loadNotifs();
}

async function pollNotifs() {
  const badge = document.getElementById('notif-badge');
  if (!badge) return;
  try {
    const d = await fetch('/api/notifications/count').then(r => r.json());
    const n = d.n || 0;
    badge.textContent = n;
    badge.style.display = n > 0 ? 'flex' : 'none';
  } catch(e) {}
}

// Close notif dropdown on outside click
document.addEventListener('click', e => {
  const wrap = document.getElementById('notif-wrap');
  if (wrap && !wrap.contains(e.target)) notifWrap()?.classList.remove('open');
});

// ── Flash auto-dismiss ────────────────────────────────────────
function initFlash() {
  document.querySelectorAll('.flash').forEach(el => {
    setTimeout(() => {
      el.style.transition = 'opacity .3s';
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 300);
    }, 4000);
  });
}

// ── Image upload preview ──────────────────────────────────────
function initUploadArea() {
  const area  = document.getElementById('upload-area');
  const input = document.getElementById('img-input');
  const grid  = document.getElementById('img-preview-grid');
  if (!area || !input || !grid) return;

  area.addEventListener('click', () => input.click());
  area.addEventListener('dragover', e => { e.preventDefault(); area.classList.add('drag'); });
  area.addEventListener('dragleave', () => area.classList.remove('drag'));
  area.addEventListener('drop', e => {
    e.preventDefault(); area.classList.remove('drag');
    addFiles(e.dataTransfer.files);
  });
  input.addEventListener('change', () => addFiles(input.files));

  function addFiles(files) {
    Array.from(files).forEach((f, i) => {
      if (!f.type.startsWith('image/')) return;
      const url = URL.createObjectURL(f);
      const idx = grid.children.length;
      grid.insertAdjacentHTML('beforeend', `
        <div class="img-thumb" id="thumb-${idx}">
          <img src="${url}">
          ${idx === 0 ? '<span style="position:absolute;bottom:3px;left:3px;background:var(--clay);color:#fff;font-size:9px;padding:1px 5px;border-radius:2px">Main</span>' : ''}
          <button class="img-thumb-rm" onclick="removeThumb(${idx})" type="button">×</button>
        </div>`);
    });
  }
}

function removeThumb(idx) {
  document.getElementById(`thumb-${idx}`)?.remove();
}

// ── Final price calculator (product form) ─────────────────────
function calcFinal() {
  const price = parseFloat(document.getElementById('price-input')?.value) || 0;
  const disc  = parseFloat(document.getElementById('disc-input')?.value) || 0;
  const el    = document.getElementById('final-display');
  if (el) el.textContent = '₹' + (price * (1 - disc/100)).toLocaleString('en-IN', {maximumFractionDigits: 0});
}

// ── Qty controls ──────────────────────────────────────────────
function changeQty(delta) {
  const input = document.getElementById('qty-input');
  if (!input) return;
  const max = parseInt(input.max) || 999;
  input.value = Math.max(1, Math.min(max, parseInt(input.value || 1) + delta));
}

// ── Payment screenshot preview ────────────────────────────────
function previewProof(input) {
  const f = input.files[0];
  if (!f) return;
  const url = URL.createObjectURL(f);
  const el  = document.getElementById('proof-preview');
  if (el) {
    el.innerHTML = `<img src="${url}" style="max-width:100%;max-height:200px;border-radius:var(--r);border:1.5px solid var(--border)">
      <p style="font-size:12px;color:var(--success);margin-top:6px;text-align:center">✓ Screenshot selected</p>`;
  }
  document.getElementById('upload-prompt')?.style && (document.getElementById('upload-prompt').style.display = 'none');
}

// ── Init ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initFlash();
  initUploadArea();
  pollNotifs();
  setInterval(pollNotifs, 30000);
  calcFinal();
});
