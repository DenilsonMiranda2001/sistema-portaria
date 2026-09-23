/* ControleID shared single-select enhancement. Native select remains the form source of truth. */
(() => {
  const SELECTOR = 'select:not([multiple]):not([size]):not([data-native-select])';
  let sequence = 0;
  const enhanced = new WeakSet();
  const closeAll = (except) => document.querySelectorAll('.pc-select.is-open').forEach(root => {
    if (root !== except) { root.classList.remove('is-open'); root.querySelector('.pc-select-trigger').setAttribute('aria-expanded', 'false'); }
  });
  function enhance(select) {
    if (enhanced.has(select) || select.closest('.pc-select') || select.disabled && !select.options.length) return;
    enhanced.add(select);
    const root = document.createElement('div');
    root.className = 'pc-select';
    const id = 'pc-select-' + (++sequence);
    const trigger = document.createElement('button');
    trigger.type = 'button'; trigger.className = 'pc-select-trigger';
    trigger.setAttribute('aria-haspopup', 'listbox'); trigger.setAttribute('aria-expanded', 'false');
    trigger.setAttribute('aria-controls', id);
    const value = document.createElement('span'); value.className = 'pc-select-value';
    const arrow = document.createElement('span'); arrow.className = 'pc-select-chevron'; arrow.setAttribute('aria-hidden', 'true');
    trigger.append(value, arrow);
    const list = document.createElement('div'); list.id = id; list.className = 'pc-select-list'; list.setAttribute('role', 'listbox'); list.tabIndex = -1;
    const label = select.labels && select.labels[0];
    if (label) {
      if (!label.id) label.id = id + '-label';
      trigger.setAttribute('aria-labelledby', label.id);
    } else if (select.getAttribute('aria-label')) trigger.setAttribute('aria-label', select.getAttribute('aria-label'));
    select.parentNode.insertBefore(root, select); root.append(select, trigger, list);
    select.classList.add('pc-select-native'); select.tabIndex = -1; select.setAttribute('aria-hidden', 'true');
    let active = -1; let query = ''; let queryTimer;
    function options() { return [...select.options].filter(o => !o.hidden && !o.closest('optgroup[disabled]')); }
    function render() {
      const items = options(); list.replaceChildren();
      items.forEach((option, i) => {
        const item = document.createElement('button'); item.type = 'button'; item.className = 'pc-select-option';
        item.id = id + '-option-' + i; item.setAttribute('role', 'option');
        item.setAttribute('aria-selected', String(option.selected)); item.disabled = option.disabled;
        item.textContent = option.textContent.trim();
        if (option.selected) item.classList.add('is-selected');
        if (i === active) item.classList.add('is-active');
        item.addEventListener('click', () => choose(option));
        list.append(item);
      });
      const selected = select.selectedOptions[0];
      value.textContent = selected ? selected.textContent.trim() : (select.dataset.placeholder || 'Selecione');
      root.classList.toggle('is-placeholder', !selected || selected.value === '');
      trigger.disabled = select.disabled;
      active = Math.max(0, items.findIndex(o => o.selected));
    }
    function open() {
      if (select.disabled) return;
      closeAll(root); render(); root.classList.add('is-open');
      trigger.setAttribute('aria-expanded', 'true');
      list.querySelector('.is-selected')?.scrollIntoView({block:'nearest'});
    }
    function close() { root.classList.remove('is-open'); trigger.setAttribute('aria-expanded', 'false'); }
    function choose(option) {
      if (option.disabled) return;
      const changed = select.value !== option.value || select.selectedIndex !== option.index;
      select.selectedIndex = option.index; render(); close(); trigger.focus();
      if (changed) { select.dispatchEvent(new Event('input', {bubbles:true})); select.dispatchEvent(new Event('change', {bubbles:true})); }
    }
    trigger.addEventListener('click', () => root.classList.contains('is-open') ? close() : open());
    trigger.addEventListener('keydown', e => {
      const items = options(); if (!items.length || select.disabled) return;
      if (['ArrowDown','ArrowUp','Home','End'].includes(e.key)) {
        e.preventDefault(); if (!root.classList.contains('is-open')) open();
        const step = e.key === 'ArrowDown' ? 1 : -1;
        let next = e.key === 'Home' ? 0 : e.key === 'End' ? items.length-1 : active;
        for (let n=0; n<items.length; n++) {
          next = e.key === 'Home' || e.key === 'End' ? next : (next + step + items.length) % items.length;
          if (!items[next].disabled) { active=next; break; }
          if (e.key === 'Home' || e.key === 'End') next += e.key === 'Home' ? 1 : -1;
        }
        list.querySelectorAll('.pc-select-option').forEach((item,i) => item.classList.toggle('is-active', i===active));
        list.children[active]?.scrollIntoView({block:'nearest'});
      } else if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault(); if (!root.classList.contains('is-open')) open(); else if (items[active]) choose(items[active]);
      } else if (e.key === 'Escape') { if (root.classList.contains('is-open')) {e.preventDefault();close();} }
      else if (e.key.length===1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
        query += e.key.toLocaleLowerCase('pt-BR'); clearTimeout(queryTimer); queryTimer=setTimeout(()=>query='',650);
        const found=items.findIndex(o=>!o.disabled && o.textContent.trim().toLocaleLowerCase('pt-BR').startsWith(query));
        if (found>=0) {e.preventDefault(); if(!root.classList.contains('is-open'))open(); active=found;list.querySelectorAll('.pc-select-option').forEach((item,i)=>item.classList.toggle('is-active',i===active));list.children[active]?.scrollIntoView({block:'nearest'});}
      }
    });
    select.addEventListener('change', render);
    select.addEventListener('input', render);
    new MutationObserver(render).observe(select,{childList:true,subtree:true,attributes:true,attributeFilter:['disabled','selected','label','hidden']});
    select.form?.addEventListener('reset',()=>setTimeout(render,0));
    render();
  }
  document.addEventListener('click', e => { if (!e.target.closest('.pc-select')) closeAll(); });
  document.addEventListener('focusin', e => { if (!e.target.closest('.pc-select')) closeAll(); });
  const init = (scope=document) => { if(scope.matches?.(SELECTOR)) enhance(scope); scope.querySelectorAll?.(SELECTOR).forEach(enhance); };
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',()=>init()); else init();
  new MutationObserver(records => records.forEach(record => record.addedNodes.forEach(node => {if(node.nodeType===1)init(node);}))).observe(document.documentElement,{childList:true,subtree:true});
})();
