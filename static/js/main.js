// Everbloom main.js

// ── Mobile nav ──────────────────────────────────────────
const hamburger = document.getElementById('hamburger');
const mobileNav = document.getElementById('mobileNav');
if (hamburger && mobileNav) {
  hamburger.addEventListener('click', () => mobileNav.classList.toggle('open'));
  document.addEventListener('click', e => {
    if (!hamburger.contains(e.target) && !mobileNav.contains(e.target)) {
      mobileNav.classList.remove('open');
    }
  });
}

// ── Notifications ────────────────────────────────────────
const notifBtn      = document.getElementById('notifBtn');
const notifDropdown = document.getElementById('notifDropdown');
const notifBadge    = document.getElementById('notifBadge');
const notifList     = document.getElementById('notifList');

if (notifBtn) {
  notifBtn.addEventListener('click', async e => {
    e.stopPropagation();
    notifDropdown.classList.toggle('open');
    if (notifDropdown.classList.contains('open')) {
      await loadNotifications();
      await markRead();
    }
  });
  document.addEventListener('click', e => {
    if (!notifBtn.contains(e.target) && !notifDropdown.contains(e.target)) {
      notifDropdown.classList.remove('open');
    }
  });

  async function loadNotifications() {
    try {
      const res = await fetch('/api/notifications');
      const data = await res.json();
      if (data.unread > 0) {
        notifBadge.textContent = data.unread;
        notifBadge.style.display = 'flex';
      } else {
        notifBadge.style.display = 'none';
      }
      if (data.notifications && data.notifications.length > 0) {
        notifList.innerHTML = data.notifications.map(n => `
          <a href="${n.link || '#'}" class="notif-item">
            <div style="font-size:.84rem;color:var(--text);">${n.message}</div>
            <div style="font-size:.72rem;color:var(--text-soft);margin-top:.2rem;">${n.created_at ? n.created_at.slice(0,16).replace('T',' ') : ''}</div>
          </a>
        `).join('');
      } else {
        notifList.innerHTML = '<p class="notif-empty">All caught up!</p>';
      }
    } catch (e) {}
  }

  async function markRead() {
    try {
      await fetch('/api/notifications/read', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRF() }
      });
      notifBadge.style.display = 'none';
    } catch (e) {}
  }

  // Poll for new notifications every 30s
  setInterval(async () => {
    try {
      const res = await fetch('/api/notifications');
      const data = await res.json();
      if (data.unread > 0) {
        notifBadge.textContent = data.unread;
        notifBadge.style.display = 'flex';
      }
    } catch (e) {}
  }, 30000);
}

// ── CSRF helper ──────────────────────────────────────────
function getCSRF() {
  const el = document.querySelector('input[name="csrf_token"]');
  return el ? el.value : '';
}

// ── Add to cart feedback ─────────────────────────────────
document.querySelectorAll('.btn-add-cart:not(.disabled)').forEach(btn => {
  btn.addEventListener('click', () => {
    const orig = btn.textContent;
    btn.textContent = '✓ Added';
    btn.style.background = '#5c3d3d';
    btn.style.color = '#fdf6f0';
    setTimeout(() => {
      btn.textContent = orig;
      btn.style.background = '';
      btn.style.color = '';
    }, 1600);
  });
});

// ── Auto-dismiss flash messages ──────────────────────────
document.querySelectorAll('.flash').forEach(el => {
  setTimeout(() => {
    el.style.opacity = '0';
    el.style.transition = 'opacity .4s';
    setTimeout(() => el.remove(), 400);
  }, 4000);
});

// ── Scroll-triggered fade-up animations ─────────────────
const fadeEls = document.querySelectorAll('.fade-up');
if (fadeEls.length) {
  const observer = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (e.isIntersecting) e.target.classList.add('visible');
    });
  }, { threshold: 0.1 });
  fadeEls.forEach(el => observer.observe(el));
}

// ── Image preview before upload ──────────────────────────
document.querySelectorAll('input[type="file"][accept*="image"]').forEach(input => {
  input.addEventListener('change', () => {
    const prev = input.parentElement.querySelector('.img-preview-row');
    if (prev) prev.remove();
    if (!input.files.length) return;
    const row = document.createElement('div');
    row.className = 'img-preview-row';
    row.style.cssText = 'display:flex;gap:.5rem;flex-wrap:wrap;margin-top:.6rem;';
    Array.from(input.files).forEach(file => {
      if (!file.type.startsWith('image/')) return;
      const reader = new FileReader();
      reader.onload = e => {
        const img = document.createElement('img');
        img.src = e.target.result;
        img.style.cssText = 'width:64px;height:64px;object-fit:cover;border-radius:4px;border:1px solid #e8c4b8;';
        row.appendChild(img);
      };
      reader.readAsDataURL(file);
    });
    input.parentElement.appendChild(row);
  });
});
