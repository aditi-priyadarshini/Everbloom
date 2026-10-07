'use strict';
// Native dialogs provide focus containment, Escape and inert backgrounds.
let dialogTrigger;
function openDialog(dialog, trigger) {
  if (!dialog || dialog.open) return;
  dialogTrigger = trigger || document.activeElement;
  dialog.showModal(); document.body.classList.add('body-locked');
  dialog.querySelector('[type=search]')?.focus();
  trigger?.setAttribute('aria-expanded','true');
}
document.querySelectorAll('dialog').forEach(dialog => {
  dialog.addEventListener('close', () => {
    document.body.classList.remove('body-locked');
    dialogTrigger?.setAttribute('aria-expanded','false'); dialogTrigger?.focus();
  });
  dialog.addEventListener('click', event => {
    const rect=dialog.getBoundingClientRect();
    if(event.target===dialog && (event.clientX<rect.left || event.clientX>rect.right || event.clientY<rect.top || event.clientY>rect.bottom)) dialog.close();
  });
});
document.querySelectorAll('[data-dialog-open]').forEach(button=>button.addEventListener('click',()=>openDialog(document.getElementById(button.dataset.dialogOpen),button)));
document.getElementById('hamburger')?.addEventListener('click',event=>openDialog(document.getElementById('mobileNav'),event.currentTarget));
document.querySelectorAll('[data-dialog-close]').forEach(button=>button.addEventListener('click',()=>button.closest('dialog').close()));
const filterDialog=document.getElementById('filterDialog');
const filters=document.getElementById('shopFilters');
const filterParent=filters?.parentElement;
document.querySelectorAll('[data-filter-open]').forEach(button=>button.addEventListener('click',()=>{
  document.getElementById('filterSlot').append(filters); openDialog(filterDialog,button);
  if(button.hasAttribute('data-filter-sort')) filters.querySelector('[name=sort]').focus();
}));
filterDialog?.addEventListener('close',()=>filterParent.prepend(filters));
const sidebar=document.getElementById('adminSidebar');
const adminToggle=document.querySelector('[data-admin-open]');
const adminBackdrop=document.querySelector('.admin-backdrop');
let adminPrevious;
function closeAdmin(){
  sidebar?.classList.remove('open');adminBackdrop?.classList.remove('open');
  sidebar?.removeAttribute('role');sidebar?.removeAttribute('aria-modal');
  document.body.classList.remove('body-locked');adminToggle?.setAttribute('aria-expanded','false');
  document.querySelector('.admin-main')?.removeAttribute('inert');adminPrevious?.focus();
}
adminToggle?.addEventListener('click',()=>{
  adminPrevious=document.activeElement;sidebar.classList.add('open');adminBackdrop.classList.add('open');
  sidebar.setAttribute('role','dialog');sidebar.setAttribute('aria-modal','true');
  document.body.classList.add('body-locked');adminToggle.setAttribute('aria-expanded','true');
  document.querySelector('.admin-main').setAttribute('inert','');sidebar.querySelector('[data-admin-close]').focus();
});
document.querySelectorAll('[data-admin-close]').forEach(button=>button.addEventListener('click',closeAdmin));
document.addEventListener('keydown',event=>{
  if(!sidebar?.classList.contains('open')) return;
  if(event.key==='Escape') closeAdmin();
  if(event.key==='Tab'){
    const items=Array.from(sidebar.querySelectorAll('a,button')).filter(el=>el.getClientRects().length);
    const first=items[0],last=items[items.length-1];
    if(event.shiftKey && document.activeElement===first){event.preventDefault();last.focus();}
    else if(!event.shiftKey && document.activeElement===last){event.preventDefault();first.focus();}
  }
});
window.matchMedia('(min-width:769px)').addEventListener('change',event=>{if(event.matches && sidebar?.classList.contains('open'))closeAdmin();});
document.querySelectorAll('.nav-dropdown').forEach(details=>{
  details.addEventListener('keydown',event=>{if(event.key==='Escape'){details.open=false;details.querySelector('summary').focus();}});
  document.addEventListener('click',event=>{if(!details.contains(event.target))details.open=false;});
});
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
 event.preventDefault();main.src=link.dataset.gallerySrc;main.alt=link.dataset.galleryAlt||main.alt;
 document.querySelectorAll('.thumb').forEach(image=>image.classList.remove('active'));
 link.querySelector('img').classList.add('active');
}));

document.querySelectorAll('[data-copy]').forEach(button=>button.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(button.dataset.copy);button.textContent='Copied';}catch{button.textContent='Select the phone number to copy';}}));

// Enhance long operational forms with anchor navigation and a persistent save bar.
document.querySelectorAll('.product-form,#storeSettings .settings-grid').forEach(container=>{
  const sections=container.querySelectorAll('.admin-card');
  const nav=document.createElement('nav');nav.className='editor-section-nav';nav.setAttribute('aria-label','Editor sections');
  sections.forEach((section,index)=>{
    const heading=section.querySelector('h3');if(!heading)return;
    section.id ||= 'editor-section-'+index;
    const link=document.createElement('a');link.href='#'+section.id;link.textContent=heading.textContent;nav.append(link);
  });
  container.before(nav);
});
// Explain browser validation at the field that needs attention.
document.querySelectorAll('input,select,textarea').forEach(field=>{
  field.addEventListener('invalid',()=>{
    field.setAttribute('aria-invalid','true');
    let error=field.parentElement.querySelector('.field-error');
    if(!error){error=document.createElement('p');error.className='field-error';error.id=(field.id||field.name)+'-error';field.after(error);}
    error.textContent=field.validationMessage;field.setAttribute('aria-describedby',error.id);
  });
  field.addEventListener('input',()=>{if(field.validity.valid){field.removeAttribute('aria-invalid');const error=field.parentElement.querySelector('.field-error');if(error){error.remove();field.removeAttribute('aria-describedby');}}});
});
const editorForm=document.querySelector('.product-form');
if(editorForm){let dirty=false;editorForm.addEventListener('change',()=>dirty=true);editorForm.addEventListener('submit',()=>dirty=false);window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});}
// Responsive operational tables retain context without twelve narrow columns.
document.querySelectorAll('.admin-table').forEach(table=>{
  const headings=Array.from(table.querySelectorAll('thead th')).map(th=>th.textContent.trim());
  table.querySelectorAll('tbody tr').forEach(row=>{if(row.children.length!==headings.length)return;Array.from(row.children).forEach((cell,index)=>{cell.dataset.label=headings[index];const value=document.createElement('div');value.className='table-cell-value';while(cell.firstChild)value.append(cell.firstChild);cell.append(value);});});
});
document.querySelector('[data-search-area]')?.addEventListener('change',event=>{document.getElementById('adminSearchForm').action=event.target.value;});
document.querySelectorAll('[data-image-move]').forEach(button=>button.addEventListener('click',()=>{
  const tile=button.closest('.existing-img-wrap');const direction=Number(button.dataset.imageMove);
  const sibling=direction<0?tile.previousElementSibling:tile.nextElementSibling;
  if(sibling){if(direction<0)sibling.before(tile);else sibling.after(tile);}
  tile.parentElement.querySelectorAll('.media-position').forEach((label,index)=>label.textContent=index===0?'Cover image':'Image '+(index+1));
  tile.dispatchEvent(new Event('change',{bubbles:true}));
}));
// A structured editor progressively enhances the existing JSON storage contract.
const personalisationSource=document.querySelector('[data-personalisation-editor]');
if(personalisationSource){
  try {
    const fields=JSON.parse(personalisationSource.value);
    if(!Array.isArray(fields))throw new Error('Expected fields');
    const panel=document.createElement('div');panel.className='personalisation-editor';
    const list=document.createElement('div');panel.append(list);
    function sync(){personalisationSource.value=JSON.stringify(fields);personalisationSource.dispatchEvent(new Event('change',{bubbles:true}));}
    function render(){list.replaceChildren();fields.forEach((field,index)=>{
      const row=document.createElement('div');row.className='personalisation-field-row';
      [['Label','label'],['Field key','name']].forEach(([title,key])=>{
        const label=document.createElement('label');label.textContent=title;
        const input=document.createElement('input');input.value=field[key]||'';input.maxLength=key==='name'?40:100;input.required=true;
        if(key==='name') input.pattern='[a-z][a-z0-9_]{0,39}';
        input.addEventListener('input',()=>{field[key]=input.value;sync();});label.append(input);row.append(label);
      });
      const remove=document.createElement('button');remove.type='button';remove.className='btn-outline-sm';remove.textContent='Remove';remove.addEventListener('click',()=>{fields.splice(index,1);sync();render();});row.append(remove);
      const requiredLabel=document.createElement('label');requiredLabel.className='field-required';
      const required=document.createElement('input');required.type='checkbox';required.checked=Boolean(field.required);required.addEventListener('change',()=>{field.required=required.checked;sync();});requiredLabel.append(required,document.createTextNode('Customer must complete this field'));row.append(requiredLabel);list.append(row);
    });}
    const add=document.createElement('button');add.type='button';add.className='btn-outline-sm';add.textContent='Add a personalisation field';add.addEventListener('click',()=>{fields.push({name:'',label:'',required:false});sync();render();list.lastElementChild.querySelector('input').focus();});panel.append(add);
    personalisationSource.hidden=true;personalisationSource.parentElement.querySelector('.form-hint')?.remove();personalisationSource.after(panel);render();
  }catch{/* Preserve the original editable field for unsupported legacy content. */}
}
const materialSearch=document.querySelector('[data-material-search]');
const materialLow=document.querySelector('[data-material-low]');
function filterMaterials(){
 const query=(materialSearch?.value||'').trim().toLowerCase();let visible=0;
 document.querySelectorAll('[data-material-row]').forEach(row=>{row.hidden=!(row.dataset.search.toLowerCase().includes(query)&&(!materialLow.checked||row.dataset.low==='true'));if(!row.hidden)visible++;});
 const empty=document.querySelector('[data-material-empty]');if(empty)empty.hidden=visible>0;
}
materialSearch?.addEventListener('input',filterMaterials);materialLow?.addEventListener('change',filterMaterials);
document.querySelector('[data-error-summary]')?.focus();
