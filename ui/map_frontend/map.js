export default function ({ data, parentElement, setStateValue }) {
  const root = parentElement.querySelector('.cq-interactive-map');
  const svg = root.querySelector('.cq-map-canvas');
  const world = root.querySelector('.cq-map-world');
  const select = root.querySelector('.cq-map-select');
  const announcement = root.querySelector('.cq-map-announcement');
  const collapseButton = root.querySelector('[data-action="collapse"]');
  const namespace = 'http://www.w3.org/2000/svg';
  const abort = new AbortController();
  const on = (element, event, handler, options = {}) => element.addEventListener(event, handler, { ...options, signal: abort.signal });
  const nodes = data.nodes ?? [];
  const nodeById = new Map(nodes.map(node => [node.id, node]));
  let selectedId = data.view?.selected_id ?? null;
  let collapsed = new Set(data.view?.collapsed ?? []);
  let viewport = data.view?.viewport ? { ...data.view.viewport } : null;
  let visible = [], positions = new Map(), contentHeight = 420;
  let wheelTimer = null, pointer = null, ignoreClick = false;

  function make(tag, attrs = {}, text) {
    const element = document.createElementNS(namespace, tag);
    Object.entries(attrs).forEach(([name, value]) => element.setAttribute(name, String(value)));
    if (text !== undefined) element.textContent = text;
    return element;
  }
  function persist() {
    setStateValue('view', { selected_id: selectedId, viewport, collapsed: [...collapsed] });
  }
  function dimensions() {
    const box = svg.getBoundingClientRect();
    return { width: Math.max(1, box.width), height: Math.max(1, box.height) };
  }
  function initialViewport(fitAll = false) {
    const { width, height } = dimensions();
    const scale = Math.max(0.15, Math.min(1, (width - 20) / 1000, fitAll ? (height - 20) / contentHeight : 1));
    return { x: 10, y: 10, scale };
  }
  function transform() {
    if (!viewport || !Number.isFinite(viewport.scale)) viewport = initialViewport();
    viewport.scale = Math.max(0.15, Math.min(2.8, viewport.scale));
    world.setAttribute('transform', `translate(${viewport.x} ${viewport.y}) scale(${viewport.scale})`);
    root.querySelector('.cq-map-zoom').textContent = `${Math.round(viewport.scale * 100)}%`;
  }
  function zoom(factor, center) {
    const size = dimensions();
    const point = center ?? { x: size.width / 2, y: size.height / 2 };
    const old = viewport.scale;
    const next = Math.max(0.15, Math.min(2.8, old * factor));
    viewport.x = point.x - (point.x - viewport.x) * next / old;
    viewport.y = point.y - (point.y - viewport.y) * next / old;
    viewport.scale = next;
    transform();
  }
  function trackFor(node) { return node?.kind === 'track' ? node : nodeById.get(node?.parent_id); }
  function updateSelection() {
    world.querySelectorAll('.cq-map-node').forEach(element => {
      const active = element.dataset.nodeId === selectedId;
      element.classList.toggle('selected', active);
      element.setAttribute('aria-pressed', String(active));
      element.setAttribute('tabindex', active ? '0' : '-1');
    });
    if (selectedId) select.value = selectedId;
    const track = trackFor(nodeById.get(selectedId));
    collapseButton.disabled = !track;
    collapseButton.textContent = track && collapsed.has(track.id) ? 'Раскрыть ветвь' : 'Свернуть ветвь';
  }
  function focusNode(id) {
    const element = [...world.querySelectorAll('.cq-map-node')].find(item => item.dataset.nodeId === id);
    element?.focus({ preventScroll: true });
    const position = positions.get(id);
    if (position) {
      const { width, height } = dimensions();
      const centerX = viewport.x + (position.x + 140) * viewport.scale;
      const centerY = viewport.y + (position.y + 34) * viewport.scale;
      if (centerX < 30 || centerX > width - 30 || centerY < 30 || centerY > height - 30) {
        viewport.x = width / 2 - (position.x + 140) * viewport.scale;
        viewport.y = height / 2 - (position.y + 34) * viewport.scale;
        transform();
      }
    }
  }
  function choose(id, focus = false) {
    if (!nodeById.has(id)) return;
    selectedId = id;
    updateSelection();
    if (focus) focusNode(id);
    announcement.textContent = `Выбрано: ${nodeById.get(id).label}. Подробности под картой.`;
    persist();
  }
  function toggleBranch() {
    const track = trackFor(nodeById.get(selectedId));
    if (!track) return;
    if (collapsed.has(track.id)) collapsed.delete(track.id);
    else { collapsed.add(track.id); selectedId = track.id; }
    draw();
    persist();
  }
  function shortLines(label) {
    const words = String(label).replace(/\s+/g, ' ').split(' ');
    const lines = [''];
    for (const word of words) {
      const index = lines.length - 1;
      if ((lines[index] + ' ' + word).trim().length <= 30) lines[index] = (lines[index] + ' ' + word).trim();
      else if (lines.length < 2) lines.push(word);
      else { lines[1] = lines[1].slice(0, 27) + '…'; break; }
    }
    return lines.map(line => line.length > 31 ? line.slice(0, 28) + '…' : line);
  }
  function draw() {
    world.replaceChildren();
    select.replaceChildren();
    positions = new Map();
    visible = nodes.filter(node => !node.parent_id || !collapsed.has(node.parent_id));
    const facts = visible.filter(node => node.kind === 'skill' || node.kind === 'certificate');
    facts.forEach((node, index) => positions.set(node.id, { x: 0, y: 45 + index * 82 }));
    let nextY = 45;
    visible.filter(node => node.kind === 'track').forEach(track => {
      const children = visible.filter(node => node.parent_id === track.id);
      const start = nextY;
      children.forEach(node => { positions.set(node.id, { x: 700, y: nextY }); nextY += 82; });
      positions.set(track.id, { x: 350, y: start + Math.max(0, children.length - 1) * 41 });
      nextY = Math.max(nextY, start + 82) + 30;
    });
    contentHeight = Math.max(160, ...[...positions.values()].map(position => position.y + 90));
    [['ПОДТВЕРЖДЁННЫЙ БАГАЖ', 0], ['НАПРАВЛЕНИЯ', 350], ['БУДУЩИЕ ШАГИ · ПРЕДЛОЖЕНИЯ', 700]].forEach(([label, x]) => {
      world.appendChild(make('text', { x, y: 22, class: 'cq-map-column' }, label));
    });
    (data.edges ?? []).forEach(edge => {
      const source = positions.get(edge.source), target = positions.get(edge.target);
      if (!source || !target) return;
      const x1 = source.x + 280, y1 = source.y + 34, x2 = target.x, y2 = target.y + 34;
      world.appendChild(make('path', { class: `cq-map-edge ${edge.kind}`, d: `M${x1} ${y1} C${x1 + 35} ${y1},${x2 - 35} ${y2},${x2} ${y2}` }));
    });
    visible.forEach(node => {
      const position = positions.get(node.id);
      if (!position) return;
      const group = make('g', { class: `cq-map-node ${node.kind}`, transform: `translate(${position.x} ${position.y})`, role: 'button', tabindex: '-1', 'aria-label': `${node.label}. ${node.subtitle}`, 'data-node-id': node.id });
      group.appendChild(make('title', {}, `${node.label} — ${node.subtitle}`));
      group.appendChild(make('rect', { width: 280, height: 68, rx: 10 }));
      shortLines(node.label).forEach((line, index) => group.appendChild(make('text', { x: 12, y: 21 + index * 16, class: 'cq-map-label' }, line)));
      group.appendChild(make('text', { x: 12, y: 55, class: 'cq-map-subtitle' }, node.subtitle));
      if (node.kind === 'track') group.appendChild(make('text', { x: 262, y: 56, class: 'cq-map-collapse-mark' }, collapsed.has(node.id) ? '+' : '−'));
      world.appendChild(group);
      const option = document.createElement('option');
      option.value = node.id;
      option.textContent = `${node.label} · ${node.subtitle}`;
      select.appendChild(option);
    });
    updateSelection();
    transform();
  }
  on(world, 'click', event => {
    if (ignoreClick) { ignoreClick = false; return; }
    const node = event.target.closest('[data-node-id]');
    if (node) choose(node.dataset.nodeId, true);
  });
  on(select, 'change', () => choose(select.value, true));
  on(root.querySelector('.cq-map-toolbar'), 'click', event => {
    const action = event.target.closest('[data-action]')?.dataset.action;
    if (!action) return;
    if (action === 'collapse') { toggleBranch(); return; }
    if (action === 'zoom-in') zoom(1.25);
    if (action === 'zoom-out') zoom(0.8);
    if (action === 'fit' || action === 'reset') { viewport = initialViewport(action === 'fit'); transform(); }
    persist();
  });
  on(svg, 'wheel', event => {
    event.preventDefault();
    const box = svg.getBoundingClientRect();
    zoom(Math.exp(-Math.max(-100, Math.min(100, event.deltaY)) * 0.003), { x: event.clientX - box.left, y: event.clientY - box.top });
    clearTimeout(wheelTimer);
    wheelTimer = setTimeout(persist, 220);
  }, { passive: false });
  on(svg, 'pointerdown', event => {
    if (event.button !== 0) return;
    pointer = { id: event.pointerId, x: event.clientX, y: event.clientY, startX: viewport.x, startY: viewport.y, moved: false };
  });
  on(svg, 'pointermove', event => {
    if (!pointer || pointer.id !== event.pointerId) return;
    const dx = event.clientX - pointer.x, dy = event.clientY - pointer.y;
    if (Math.abs(dx) + Math.abs(dy) > 5) pointer.moved = true;
    if (!pointer.moved) return;
    if (!svg.hasPointerCapture(event.pointerId)) svg.setPointerCapture(event.pointerId);
    viewport.x = pointer.startX + dx;
    viewport.y = pointer.startY + dy;
    svg.classList.add('dragging');
    transform();
  });
  function finishPointer(event) {
    if (!pointer || pointer.id !== event.pointerId) return;
    if (svg.hasPointerCapture(event.pointerId)) svg.releasePointerCapture(event.pointerId);
    svg.classList.remove('dragging');
    ignoreClick = pointer.moved;
    if (pointer.moved) persist();
    pointer = null;
  }
  on(svg, 'pointerup', finishPointer);
  on(svg, 'pointercancel', finishPointer);
  on(svg, 'keydown', event => {
    const nodeElement = event.target.closest('[data-node-id]');
    const currentId = nodeElement?.dataset.nodeId ?? selectedId;
    if (event.key === '+' || event.key === '=') { event.preventDefault(); zoom(1.25); persist(); return; }
    if (event.key === '-') { event.preventDefault(); zoom(0.8); persist(); return; }
    if (event.key === '0') { event.preventDefault(); viewport = initialViewport(true); transform(); persist(); return; }
    if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); if (currentId) choose(currentId, true); return; }
    if (event.key.toLowerCase() === 'c') { event.preventDefault(); toggleBranch(); return; }
    if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const current = positions.get(currentId);
    let target;
    if (event.key === 'Home' || event.key === 'End') target = visible[event.key === 'Home' ? 0 : visible.length - 1];
    else if (current) {
      const horizontal = event.key === 'ArrowLeft' || event.key === 'ArrowRight';
      const positive = event.key === 'ArrowRight' || event.key === 'ArrowDown';
      target = visible.filter(node => {
        const point = positions.get(node.id);
        const difference = horizontal ? point.x - current.x : point.y - current.y;
        return positive ? difference > 0 : difference < 0;
      }).sort((a, b) => {
        const score = node => { const point = positions.get(node.id); return Math.abs(point.x - current.x) * (horizontal ? 1 : 3) + Math.abs(point.y - current.y) * (horizontal ? 3 : 1); };
        return score(a) - score(b);
      })[0];
    }
    if (target) focusNode(target.id);
  });
  draw();
  const observer = new ResizeObserver(() => transform());
  observer.observe(svg);
  return () => { abort.abort(); observer.disconnect(); clearTimeout(wheelTimer); };
}
