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
// ── Instagram / Facebook In-App Browser Detection ────────
(function() {
  const ua = navigator.userAgent || '';
  const isIAB = /Instagram|FBAN|FBAV|FB_IAB|FB4A|FBIOS|musical_ly|TikTok|Snapchat|Twitter|LinkedInApp/i.test(ua);

  if (!isIAB) return;

  // Don't show if user already dismissed
  if (sessionStorage.getItem('iab_dismissed')) return;

  const isAndroid = /Android/i.test(ua);
  const isIOS = /iPhone|iPad|iPod/i.test(ua);
  const currentUrl = window.location.href;

  // Build banner
  const banner = document.createElement('div');
  banner.id = 'iab-banner';
  banner.style.cssText = `
    position: fixed; top: 0; left: 0; right: 0; z-index: 99999;
    background: #5c3d3d; color: #fdf6f0;
    padding: 14px 16px; display: flex;
    align-items: center; gap: 12px;
    font-family: 'Jost', sans-serif; font-size: 13px;
    box-shadow: 0 2px 12px rgba(0,0,0,.25);
  `;

  banner.innerHTML = `
    <span style="font-size:1.3rem;flex-shrink:0;">🌸</span>
    <div style="flex:1;line-height:1.5;">
      <strong style="display:block;font-size:14px;margin-bottom:2px;">Open in your browser for full experience</strong>
      <span style="opacity:.8;font-size:12px;">Google sign-in & all features work best in Chrome or Safari.</span>
    </div>
    <div style="display:flex;gap:8px;flex-shrink:0;">
      <button id="iab-open-btn" style="
        background:#e8c4b8; color:#3a2a2a; border:none;
        padding:8px 14px; border-radius:4px; font-size:12px;
        font-weight:500; cursor:pointer; font-family:'Jost',sans-serif;
        white-space:nowrap;
      ">Open in Browser</button>
      <button id="iab-dismiss-btn" style="
        background:none; border:none; color:#e8c4b8;
        font-size:18px; cursor:pointer; padding:4px 6px; line-height:1;
      ">&times;</button>
    </div>
  `;

  document.body.insertBefore(banner, document.body.firstChild);

  // Push page content down
  document.body.style.paddingTop = (parseInt(document.body.style.paddingTop || 0) + 72) + 'px';

  // Dismiss button
  document.getElementById('iab-dismiss-btn').addEventListener('click', function() {
    banner.remove();
    document.body.style.paddingTop = '';
    sessionStorage.setItem('iab_dismissed', '1');
  });

  // Open in browser button
  document.getElementById('iab-open-btn').addEventListener('click', function() {
    if (isAndroid) {
      // Android: intent:// scheme forces Chrome
      const intentUrl = 'intent://' + currentUrl.replace(/^https?:\/\//, '') +
        '#Intent;scheme=https;package=com.android.chrome;end';
      window.location.href = intentUrl;
      // Fallback after 1.5s: show manual instructions
      setTimeout(showInstructions, 1500);
    } else if (isIOS) {
      // iOS: can't force browser, show instructions
      showInstructions();
    } else {
      window.open(currentUrl, '_blank');
    }
  });

  function showInstructions() {
    const isInstagram = /Instagram/i.test(ua);
    const appName = isInstagram ? 'Instagram' : 'this app';
    const instructions = isIOS
      ? `Tap the <strong>···</strong> menu (top right) → <strong>"Open in Safari"</strong> or <strong>"Open in Browser"</strong>`
      : `Tap the <strong>⋮</strong> menu (top right) → <strong>"Open in Chrome"</strong>`;

    banner.innerHTML = `
      <span style="font-size:1.3rem;flex-shrink:0;">📱</span>
      <div style="flex:1;line-height:1.6;font-size:13px;">
        <strong style="display:block;margin-bottom:4px;">To open in your browser:</strong>
        <span style="opacity:.9;">${instructions}</span>
      </div>
      <button id="iab-dismiss-btn2" style="
        background:none; border:none; color:#e8c4b8;
        font-size:18px; cursor:pointer; padding:4px 6px; line-height:1; flex-shrink:0;
      ">&times;</button>
    `;
    document.getElementById('iab-dismiss-btn2').addEventListener('click', function() {
      banner.remove();
      document.body.style.paddingTop = '';
      sessionStorage.setItem('iab_dismissed', '1');
    });
  }
})();

// Mark body so CSS can hide Google button in IAB
(function() {
  const ua = navigator.userAgent || '';
  if (/Instagram|FBAN|FBAV|FB_IAB|FBIOS/i.test(ua)) {
    document.body.classList.add('in-app-browser');
  }
})();
