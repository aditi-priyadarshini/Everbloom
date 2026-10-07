'use strict';
const menu = document.getElementById('hamburger');
const navigation = document.getElementById('mobileNav');
function closeMenu() { if (navigation && menu) { navigation.classList.remove('open'); menu.setAttribute('aria-expanded','false'); } }
menu?.addEventListener('click', () => { const opened=navigation.classList.toggle('open'); menu.setAttribute('aria-expanded',String(opened)); });
document.addEventListener('keydown', e => { if (e.key==='Escape') { closeMenu(); menu?.focus(); } });
document.addEventListener('click', e => { if (menu && navigation && !menu.contains(e.target) && !navigation.contains(e.target)) closeMenu(); });
document.querySelectorAll('form').forEach(form => {
  form.addEventListener('submit', e => {
    if (!form.checkValidity()) return;
    if (form.dataset.submitting) { e.preventDefault(); return; }
    form.dataset.submitting='true';
    const button=e.submitter;
    if (button) { button.setAttribute('aria-busy','true'); setTimeout(()=>{button.disabled=true;},0); }
  });
});
window.addEventListener('pageshow',()=>{document.querySelectorAll('form').forEach(f=>delete f.dataset.submitting);document.querySelectorAll('[aria-busy=true]').forEach(b=>{b.disabled=false;b.removeAttribute('aria-busy');});});
document.querySelectorAll('input[type=file][accept*=image]').forEach(input=>input.addEventListener('change',()=>{
  const prior=input.parentElement.querySelector('.image-preview'); prior?.remove();
  const preview=document.createElement('div'); preview.className='image-preview';
  Array.from(input.files).slice(0,12).forEach(file=>{if(!file.type.startsWith('image/'))return; const img=document.createElement('img'); const url=URL.createObjectURL(file);img.src=url;img.alt='Selected image preview';img.width=80;img.height=100;img.style.objectFit='cover';img.onload=()=>URL.revokeObjectURL(url);preview.append(img);});input.after(preview);
}));
// Bind labels even on legacy forms; do not rely on placeholder text.
document.querySelectorAll('label').forEach((label,index)=>{if(label.htmlFor||label.querySelector('input,select,textarea'))return;const field=label.parentElement.querySelector('input:not([type=hidden]),select,textarea');if(field){field.id ||= 'field-'+index;label.htmlFor=field.id;}});

// Gallery anchors remain usable without JavaScript.
document.querySelectorAll('[data-gallery-src]').forEach(link=>link.addEventListener('click',event=>{
 const main=document.getElementById('mainImg'); if(!main)return;
 event.preventDefault();main.src=link.dataset.gallerySrc;
 document.querySelectorAll('.thumb').forEach(image=>image.classList.remove('active'));
 link.querySelector('img').classList.add('active');
}));

document.querySelectorAll('[data-copy]').forEach(button=>button.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(button.dataset.copy);button.textContent='Copied';}catch{button.textContent='Select the phone number to copy';}}));
