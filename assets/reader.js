(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('readzine-data').textContent);
  const $ = id => document.getElementById(id);
  const drawer = $('drawer'), reader = $('reader'), cover = $('cover');
  const wordcard = $('wordcard'), narrow = matchMedia('(max-width: 1149px)');
  let active = null, lastTrigger = null, readerScroll = 0, selectionTimer;
  let wordAnchor = null, wordWasKeyboard = false;
  const own = (obj, key) => Object.hasOwn(obj, key);
  const normalize = word => word.toLowerCase().replaceAll('’', "'");
  const sentenceButtons = [...document.querySelectorAll('[data-sentence]')];
  const analysisButtons = [...document.querySelectorAll('[data-analysis]')];
  const translationCard = $('translation-card');
  const helpDialog = $('help-dialog'), phoneDialog = $('phone-dialog');
  $('help-trigger').addEventListener('click', () => { hideTranslation(); hideWord(); helpDialog.showModal(); });
  $('phone-trigger').addEventListener('click', () => {
    hideTranslation(); hideWord();
    const url = data.mobileUrl;
    const valid = typeof url === 'string' && /^https?:\/\//.test(url);
    $('phone-qr').replaceChildren();
    $('phone-url').hidden = !valid;
    if (valid) {
      const qr = qrcode(0, 'M'); qr.addData(url); qr.make();
      $('phone-qr').innerHTML = qr.createSvgTag({cellSize:5, margin:20, scalable:true});
      $('phone-url').href = url; $('phone-url').textContent = url;
      $('phone-message').textContent = '请将手机和电脑连接到同一个 Wi-Fi，然后用手机相机扫描二维码。';
    } else {
      $('phone-message').textContent = '请先运行 HTML 文件同目录下的“Read on phone.command”，再刷新此页面获取二维码。手机和电脑需连接到同一个 Wi-Fi。';
    }
    phoneDialog.showModal();
  });
  document.querySelectorAll('[data-close]').forEach(button => button.addEventListener('click', () => $(button.dataset.close).close()));
  [helpDialog,phoneDialog].forEach(dialog => dialog.addEventListener('click', e => {
    const r = dialog.getBoundingClientRect();
    if (e.target === dialog && (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom)) dialog.close();
  }));
  let translationPress = null, translationTimer;
  function cancelTranslationPress() {
    clearTimeout(translationTimer);
    if (translationPress?.shown) {
      clearTimeout(selectionTimer);
      window.getSelection()?.removeAllRanges();
    }
    translationPress = null;
    document.body.classList.remove('translation-held');
  }
  function hideTranslation() {
    cancelTranslationPress();
    translationCard.hidden = true;
  }
  $('close-translation').addEventListener('click', hideTranslation);
  function showTranslation(press) {
    if (translationPress !== press || helpDialog.open || phoneDialog.open || (!drawer.hidden && narrow.matches)) return;
    const pid = press.paragraph.dataset.paragraph;
    const uiKey = press.paragraph.dataset.translation;
    const meaning = uiKey ? data.uiTranslations?.[uiKey] : data.translations?.[pid];
    if (!meaning) return;
    press.shown = true;
    clearTimeout(selectionTimer);
    hideWord();
    window.getSelection()?.removeAllRanges();
    document.body.classList.add('translation-held');
    $('translation-title').textContent = uiKey ? '中文译文' : '第 ' + pid.slice(1) + ' 段译文';
    $('translation-text').textContent = meaning;
    translationCard.hidden = false;
    const viewport = window.visualViewport;
    const left = (viewport?.offsetLeft || 0) + 12, top = (viewport?.offsetTop || 0) + 12;
    const right = left + (viewport?.width || innerWidth) - 24;
    const bottom = top + (viewport?.height || innerHeight) - 24;
    const width = translationCard.offsetWidth, height = translationCard.offsetHeight;
    const x = Math.max(left, Math.min(press.x, right - width));
    let y = press.y + 20;
    if (y + height > bottom) y = press.y - height - 20;
    y = Math.max(top, Math.min(y, bottom - height));
    translationCard.style.left = x + 'px';
    translationCard.style.top = y + 'px';
  }
  document.addEventListener('pointerdown', e => {
    if (translationCard.contains(e.target)) return;
    hideTranslation();
    if (e.button !== 0 || !e.isPrimary || e.target.closest('button,a,summary,dialog')) return;
    const paragraph = e.target.closest('.paragraph,[data-translation]');
    if (!paragraph || !(data.translations?.[paragraph.dataset.paragraph] || data.uiTranslations?.[paragraph.dataset.translation])) return;
    const press = {paragraph, x:e.clientX, y:e.clientY, pointerId:e.pointerId, pointerType:e.pointerType, started:performance.now(), shown:false};
    translationPress = press;
    translationTimer = setTimeout(() => showTranslation(press), 550);
  });
  window.addEventListener('pointermove', e => {
    if (translationPress && !translationPress.shown && e.pointerId === translationPress.pointerId &&
        Math.hypot(e.clientX - translationPress.x, e.clientY - translationPress.y) > 8) cancelTranslationPress();
  });
  window.addEventListener('pointerup', e => {
    const press = translationPress;
    const tap = press && press.pointerType === 'touch' && !press.shown && performance.now() - press.started < 500;
    cancelTranslationPress();
    if (tap) tapWord(e.clientX,e.clientY,press.paragraph);
  }, true);
  window.addEventListener('pointercancel', cancelTranslationPress, true);
  window.addEventListener('blur', cancelTranslationPress);
  window.addEventListener('scroll', cancelTranslationPress, {passive:true});
  window.addEventListener('resize', () => {
    cancelTranslationPress();
    if (translationCard.hidden) return;
    translationCard.style.left = Math.max(12,Math.min(parseFloat(translationCard.style.left),innerWidth-translationCard.offsetWidth-12))+'px';
    translationCard.style.top = Math.max(12,Math.min(parseFloat(translationCard.style.top),innerHeight-translationCard.offsetHeight-12))+'px';
  });
  document.addEventListener('contextmenu', e => {
    if (translationPress && e.target.closest('.paragraph,[data-translation]')) e.preventDefault();
    else cancelTranslationPress();
  });
  document.addEventListener('touchstart', e => { if(e.touches.length > 1) cancelTranslationPress(); }, {passive:true});
  document.addEventListener('keydown', e => {
    if (e.code !== 'Space' || e.repeat || !e.target.matches('.paragraph[tabindex],[data-translation]')) return;
    e.preventDefault();
    hideTranslation();
    const rect = e.target.getBoundingClientRect();
    translationPress = {paragraph:e.target, x:rect.left, y:Math.max(12,rect.top), shown:false};
    showTranslation(translationPress);
  });
  window.addEventListener('keyup', e => { if (e.code === 'Space') cancelTranslationPress(); });
  document.addEventListener('focusout', () => { if (translationPress?.pointerId === undefined) cancelTranslationPress(); });

  function tapWord(x,y,scope) {
    const caret = document.caretPositionFromPoint?.(x,y);
    const fallback = !caret && document.caretRangeFromPoint?.(x,y);
    const node = caret?.offsetNode || fallback?.startContainer;
    const offset = caret?.offset ?? fallback?.startOffset;
    if (!node || node.nodeType !== Node.TEXT_NODE || !scope.contains(node)) return;
    const text = node.textContent;
    const expression = /[A-Za-z]+(?:['’\-][A-Za-z]+)*/g;
    for (const match of text.matchAll(expression)) {
      if (offset < match.index || offset > match.index + match[0].length) continue;
      const range = document.createRange(); range.setStart(node,match.index); range.setEnd(node,match.index+match[0].length);
      const rect = range.getBoundingClientRect();
      if (x < rect.left-2 || x > rect.right+2 || y < rect.top-2 || y > rect.bottom+2) return;
      const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range);
      showWord(); return;
    }
  }

  function readingAnchor() {
    const candidates = [...reader.querySelectorAll('.article-heading, .paragraph')];
    const element = candidates.find(el => {const rect=el.getBoundingClientRect(); return rect.bottom > 80 && rect.top < innerHeight;});
    return element ? {element, top:element.getBoundingClientRect().top} : null;
  }
  function keepAnchor(anchor) {
    if (anchor) window.scrollBy({top:anchor.element.getBoundingClientRect().top-anchor.top, behavior:'instant'});
  }

  function hideWord(restoreFocus = false) {
    wordcard.hidden = true;
    if (restoreFocus && wordWasKeyboard && wordAnchor?.isConnected) wordAnchor.focus({preventScroll:true});
  }
  function syncModal() {
    const modal = !drawer.hidden && narrow.matches;
    $('backdrop').hidden = !modal;
    document.body.classList.toggle('modal-open', modal);
    if (modal) drawer.setAttribute('aria-modal', 'true');
    else drawer.removeAttribute('aria-modal');
    for (const el of [reader, $('home'), cover]) el.inert = modal;
  }
  function selectAnalysis(id) {
    active = id;
    document.querySelectorAll('.sentence').forEach(el => el.classList.toggle('selected', el.id === 'sentence-' + id));
    sentenceButtons.forEach(btn => btn.setAttribute('aria-expanded', String(btn.dataset.sentence === id)));
    analysisButtons.forEach(btn => {
      const selected = btn.dataset.analysis === id;
      btn.setAttribute('aria-expanded', String(selected));
      $('detail-' + btn.dataset.analysis).hidden = !selected;
    });
    document.querySelectorAll('.breakdown').forEach(el => { el.open = false; });
  }
  function openDrawer(id, trigger, toggle = false) {
    hideTranslation();
    if (toggle && !drawer.hidden && active === id) { closeDrawer(); return; }
    hideWord();
    if (drawer.hidden) lastTrigger = trigger || $('drawer-trigger');
    else if (trigger && !drawer.contains(trigger)) lastTrigger = trigger;
    const anchor = drawer.hidden && !narrow.matches ? readingAnchor() : null;
    drawer.hidden = false;
    document.body.classList.add('drawer-open');
    keepAnchor(anchor);
    $('drawer-trigger').setAttribute('aria-expanded', 'true');
    selectAnalysis(id);
    syncModal();
    const target = id ? $('analysis-' + id) : null;
    drawer.scrollTop = target ? Math.max(0, target.offsetTop - 122) : 0;
    if (narrow.matches) $('close-drawer').focus({preventScroll:true});
    else if (id) document.querySelector(`[data-analysis="${id}"]`).focus({preventScroll:true});
    else drawer.focus({preventScroll:true});
  }
  function closeDrawer(restore = true) {
    hideWord();
    const anchor = !drawer.hidden && !narrow.matches ? readingAnchor() : null;
    drawer.hidden = true;
    document.body.classList.remove('drawer-open');
    keepAnchor(anchor);
    $('drawer-trigger').setAttribute('aria-expanded', 'false');
    selectAnalysis(null);
    syncModal();
    if (restore && lastTrigger?.isConnected) lastTrigger.focus({preventScroll:true});
  }
  $('start').addEventListener('click', () => {
    cover.hidden = true; reader.hidden = false; $('home').hidden = false;
    window.scrollTo({top:readerScroll, behavior:'instant'});
    $('article-title').focus({preventScroll:true});
  });
  $('home').addEventListener('click', () => {
    closeDrawer(false); readerScroll = window.scrollY;
    reader.hidden = true; cover.hidden = false; $('home').hidden = true;
    window.scrollTo({top:0, behavior:'instant'}); $('start').focus({preventScroll:true});
  });
  sentenceButtons.forEach(btn => btn.addEventListener('click', () => {
    // A drag/selection ending on a number must not open the drawer.
    if (window.getSelection()?.toString().trim()) return;
    openDrawer(btn.dataset.sentence, btn, true);
  }));
  analysisButtons.forEach(btn => btn.addEventListener('click', () => {
    const id = active === btn.dataset.analysis ? null : btn.dataset.analysis;
    selectAnalysis(id);
  }));
  $('drawer-trigger').addEventListener('click', e => openDrawer(null, e.currentTarget));
  $('close-drawer').addEventListener('click', () => closeDrawer());
  $('backdrop').addEventListener('click', () => closeDrawer());
  document.querySelectorAll('[data-return]').forEach(btn => btn.addEventListener('click', () => {
    const id = btn.dataset.return;
    closeDrawer(false);
    const sentence = $('sentence-' + id), button = sentenceButtons.find(b => b.dataset.sentence === id);
    button.focus({preventScroll:true});
    sentence.scrollIntoView({block:'center', behavior:'smooth'});
    sentence.classList.remove('return-flash');
    void sentence.offsetWidth;
    sentence.classList.add('return-flash');
  }));
  narrow.addEventListener('change', () => { syncModal(); if (!drawer.hidden && narrow.matches) $('close-drawer').focus({preventScroll:true}); });

  function selectedWord() {
    const selection = window.getSelection();
    if (!selection || selection.rangeCount !== 1 || selection.isCollapsed || helpDialog.open || phoneDialog.open || (!drawer.hidden && narrow.matches)) return null;
    const range = selection.getRangeAt(0);
    const element = node => node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
    const start = element(range.startContainer), end = element(range.endContainer);
    if (!start || !end) return null;
    const p = start.closest('.paragraph-text,[data-translation]');
    if (!p || !p.contains(end) || start.closest('button') || end.closest('button')) return null;
    const raw = selection.toString().trim();
    // Ignore phrases and partial words. Permit punctuation selected around one word.
    const match = raw.match(/^[\s"“”‘’'([{.,;:!?]*([A-Za-z]+(?:['’\-][A-Za-z]+)*)[\s"“”‘’')\]}.,;:!?]*$/);
    if (!match) return null;
    const before = range.cloneRange(); before.selectNodeContents(p); before.setEnd(range.startContainer,range.startOffset);
    const after = range.cloneRange(); after.selectNodeContents(p); after.setStart(range.endContainer,range.endOffset);
    if (/[A-Za-z]$/.test(before.toString()) && /^[A-Za-z]/.test(raw)) return null;
    if (/^[A-Za-z]/.test(after.toString()) && /[A-Za-z]$/.test(raw)) return null;
    return {word:match[1], rect:range.getBoundingClientRect(), paragraph:p.closest('[data-paragraph]')?.dataset.paragraph || ''};
  }
  function positionCard(rect) {
    const viewport = window.visualViewport;
    const leftEdge = (viewport?.offsetLeft || 0) + 12, topEdge = (viewport?.offsetTop || 0) + 12;
    const rightEdge = leftEdge + (viewport?.width || innerWidth) - 24;
    const bottomEdge = topEdge + (viewport?.height || innerHeight) - 24;
    const width = wordcard.offsetWidth, height = wordcard.offsetHeight;
    const x = Math.max(leftEdge, Math.min(rect.left, rightEdge - width));
    let y = rect.bottom + 10;
    if (y + height > bottomEdge) y = rect.top - height - 10;
    y = Math.max(topEdge, Math.min(y, bottomEdge - height));
    wordcard.style.left = `${x}px`; wordcard.style.top = `${y}px`;
  }
  function showWord() {
    if (!translationCard.hidden) return;
    const selected = selectedWord();
    if (!selected) { hideWord(); return; }
    const key = normalize(selected.word), dict = data.dictionary;
    const lemma = own(dict.lookup, key) ? dict.lookup[key] : null;
    const entry = lemma && own(dict.entries, lemma) ? dict.entries[lemma] : null;
    $('word-title').textContent = selected.word;
    $('word-form').textContent = entry && normalize(entry.word) !== key ? '原形：' + entry.word : '';
    $('word-phonetic').textContent = entry?.phonetic ? '/' + entry.phonetic + '/' : '';
    $('word-pos').textContent = entry?.pos || '';
    const definition = $('word-definition'); definition.replaceChildren();
    const source = document.createElement('p'); source.className = 'dict-source'; source.textContent = entry ? 'ECDICT · 通用释义' : '词典未收录'; definition.append(source);
    if (entry) {
      const meaning = document.createElement('p'); meaning.textContent = entry.translation || entry.definition || '该词条暂无释义'; definition.append(meaning);
    }
    const contexts = own(data.context, selected.paragraph) ? data.context[selected.paragraph] : {};
    const context = own(contexts, key) ? contexts[key] : (lemma && own(contexts, lemma) ? contexts[lemma] : '');
    $('word-context').hidden = !context;
    $('word-context').querySelector('p').textContent = context || '';
    wordAnchor = document.activeElement;
    wordcard.hidden = false; positionCard(selected.rect);
    $('status').textContent = selected.word + '：' + (entry?.translation || entry?.definition || '词典未收录') + (context ? '。本文语境义：' + context : '');
  }
  document.addEventListener('selectionchange', () => {
    if (wordcard.contains(document.activeElement)) return;
    clearTimeout(selectionTimer); selectionTimer = setTimeout(showWord, 140);
  });
  $('close-word').addEventListener('click', () => {
    hideWord(true); window.getSelection()?.removeAllRanges();
  });
  document.addEventListener('pointerdown', e => {
    wordWasKeyboard = false;
    if (!wordcard.contains(e.target)) hideWord();
  });
  document.addEventListener('keydown', e => {
    wordWasKeyboard = true;
    if (e.key === 'Escape') {
      hideTranslation();
      if (!wordcard.hidden) { hideWord(true); window.getSelection()?.removeAllRanges(); }
      else if (!drawer.hidden) closeDrawer();
      return;
    }
    // Keyboard users can move from their selection directly into the definition.
    if (e.key === 'Tab' && !wordcard.hidden && !wordcard.contains(document.activeElement)) {
      e.preventDefault(); $('close-word').focus({preventScroll:true}); return;
    }
    if (e.key === 'Tab' && !drawer.hidden && narrow.matches) {
      const elements = [...drawer.querySelectorAll('button,summary,a[href]')].filter(el => el.getClientRects().length);
      const first = elements[0], last = elements.at(-1);
      if (e.shiftKey && (document.activeElement === first || document.activeElement === drawer)) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  });
  window.addEventListener('resize', () => hideWord());
  window.addEventListener('scroll', () => hideWord(), {passive:true});
  window.visualViewport?.addEventListener('resize', () => hideWord());
})();
