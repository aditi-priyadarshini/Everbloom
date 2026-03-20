// js/auth.js — Everbloom Authentication

// ============================================
// NAVBAR AUTH STATE
// ============================================
async function initNavAuth() {
  const user = await getCurrentUser();
  const authLinks = document.getElementById('auth-links');
  const userMenu = document.getElementById('user-menu');

  if (!authLinks && !userMenu) return;

  if (user) {
    const profile = await getCurrentProfile();
    if (authLinks) authLinks.style.display = 'none';
    if (userMenu) {
      userMenu.style.display = 'flex';
      const nameEl = userMenu.querySelector('.user-name');
      if (nameEl) nameEl.textContent = profile?.full_name?.split(' ')[0] || 'Account';
      if (profile?.role === 'admin') {
        const adminLink = userMenu.querySelector('.admin-link');
        if (adminLink) adminLink.style.display = 'block';
      }
    }
    // Load notification count
    loadNotifCount(user.id);
  } else {
    if (authLinks) authLinks.style.display = 'flex';
    if (userMenu) userMenu.style.display = 'none';
  }
}

async function loadNotifCount(userId) {
  const badge = document.getElementById('notif-badge');
  if (!badge) return;
  const { count } = await supabase
    .from('notifications')
    .select('*', { count: 'exact', head: true })
    .eq('user_id', userId)
    .eq('is_read', false);
  if (count > 0) {
    badge.textContent = count;
    badge.style.display = 'flex';
  }
}

// ============================================
// NOTIFICATION DROPDOWN
// ============================================
async function loadNotifications() {
  const user = await getCurrentUser();
  if (!user) return;

  const { data } = await supabase
    .from('notifications')
    .select('*')
    .eq('user_id', user.id)
    .order('created_at', { ascending: false })
    .limit(10);

  const list = document.getElementById('notif-list');
  if (!list || !data) return;

  if (data.length === 0) {
    list.innerHTML = `<div style="padding:32px;text-align:center;color:var(--text-muted);font-size:14px;">No notifications yet</div>`;
    return;
  }

  list.innerHTML = data.map(n => `
    <div class="notif-item ${!n.is_read ? 'unread' : ''}" onclick="markRead('${n.id}', '${n.order_id}')">
      <div style="font-size:13px;font-weight:${n.is_read ? '400' : '500'};color:var(--text-primary);margin-bottom:2px;">${n.title}</div>
      <div style="font-size:12px;color:var(--text-muted)">${n.message}</div>
      <div style="font-size:11px;color:var(--text-muted);margin-top:4px;">${formatDateTime(n.created_at)}</div>
    </div>
  `).join('');
}

async function markRead(notifId, orderId) {
  await supabase.from('notifications').update({ is_read: true }).eq('id', notifId);
  if (orderId) window.location.href = `/track.html?id=${orderId}`;
}

async function markAllRead() {
  const user = await getCurrentUser();
  if (!user) return;
  await supabase.from('notifications').update({ is_read: true }).eq('user_id', user.id);
  document.getElementById('notif-badge').style.display = 'none';
  loadNotifications();
}

// Toggle notif dropdown
function toggleNotifDropdown() {
  const dd = document.getElementById('notif-dropdown');
  if (!dd) return;
  dd.classList.toggle('open');
  if (dd.classList.contains('open')) loadNotifications();
}

// Close on outside click
document.addEventListener('click', (e) => {
  const dd = document.getElementById('notif-dropdown');
  const btn = document.getElementById('notif-btn');
  if (dd && !dd.contains(e.target) && !btn?.contains(e.target)) {
    dd.classList.remove('open');
  }
});

document.addEventListener('DOMContentLoaded', initNavAuth);
