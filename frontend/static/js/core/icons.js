// Inline SVG icons (stroke style, 24x24 viewBox).

const PATHS = {
  person:
    '<circle cx="12" cy="7.5" r="4"/><path d="M4 21v-1a7 7 0 0 1 7-7h2a7 7 0 0 1 7 7v1"/>',
  robot:
    '<rect x="4" y="8" width="16" height="12" rx="3"/><path d="M12 8V4.5"/><circle cx="12" cy="3.5" r="1"/><circle cx="9" cy="14" r="1.3" fill="currentColor" stroke="none"/><circle cx="15" cy="14" r="1.3" fill="currentColor" stroke="none"/><path d="M2 13v3M22 13v3"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  play: '<path d="M8 5.5v13a1 1 0 0 0 1.5.86l11-6.5a1 1 0 0 0 0-1.72l-11-6.5A1 1 0 0 0 8 5.5Z" fill="currentColor" stroke="none"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" stroke="none"/>',
  home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V20a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1V9.5"/>',
  list: '<path d="M8 6h13M8 12h13M8 18h13"/><circle cx="3.5" cy="6" r="1" fill="currentColor"/><circle cx="3.5" cy="12" r="1" fill="currentColor"/><circle cx="3.5" cy="18" r="1" fill="currentColor"/>',
  close: '<path d="M6 6l12 12M18 6 6 18"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  checkCircle: '<circle cx="12" cy="12" r="9"/><path d="m8 12.5 3 3 5-6"/>',
  alert: '<circle cx="12" cy="12" r="9"/><path d="M12 7.5v5.5"/><circle cx="12" cy="16.5" r="0.6" fill="currentColor"/>',
  stopCircle: '<circle cx="12" cy="12" r="9"/><rect x="9" y="9" width="6" height="6" rx="1" fill="currentColor" stroke="none"/>',
  xCircle: '<circle cx="12" cy="12" r="9"/><path d="m9 9 6 6M15 9l-6 6"/>',
  chevronRight: '<path d="m9 6 6 6-6 6"/>',
  arrowLeft: '<path d="M19 12H5M11 18l-6-6 6-6"/>',
  arrowRight: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  upload: '<path d="M12 20V9M7 13.5l5-5 5 5"/><path d="M4 4h16"/>',
  download: '<path d="M12 4v11M7 10.5l5 5 5-5"/><path d="M4 20h16"/>',
  copy: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 0 1 2-2h8"/>',
  refresh: '<path d="M20 11a8 8 0 0 0-14.6-4.5L4 8"/><path d="M4 4v4h4"/><path d="M4 13a8 8 0 0 0 14.6 4.5L20 16"/><path d="M20 20v-4h-4"/>',
  logout: '<path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3"/><path d="M10 16l-4-4 4-4M6 12h10"/>',
  file: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8Z"/><path d="M14 3v5h5"/><path d="M10 13l-1.5 2 1.5 2M14 13l1.5 2-1.5 2"/>',
  external: '<path d="M14 4h6v6M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  edit: '<path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16Z"/><path d="m13.5 6.5 4 4"/>',
  trash: '<path d="M4 7h16M10 11v6M14 11v6"/><path d="M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12"/><path d="M9 7V4h6v3"/>',
  network:
    '<circle cx="12" cy="5" r="2.2"/><circle cx="5" cy="18" r="2.2"/><circle cx="19" cy="18" r="2.2"/><path d="M10.9 6.9 6.1 16M13.1 6.9l4.8 9.1M7.2 18h9.6"/>',
  minus: '<path d="M5 12h14"/>',
  shuffle: '<path d="M3 7h3.5a5 5 0 0 1 4 2l3 4a5 5 0 0 0 4 2H21"/><path d="M3 17h3.5a5 5 0 0 0 4-2"/><path d="M14.5 9a5 5 0 0 1 3-2H21"/><path d="m18 4 3 3-3 3M18 12l3 3-3 3"/>',
  arrowsRight: '<path d="M4 12h16M14 6l6 6-6 6"/>',
  message: '<path d="M4 5h16v11H9l-5 4Z"/>',
  dice: '<rect x="4" y="4" width="16" height="16" rx="3"/><circle cx="9" cy="9" r="1.2" fill="currentColor" stroke="none"/><circle cx="15" cy="15" r="1.2" fill="currentColor" stroke="none"/><circle cx="15" cy="9" r="1.2" fill="currentColor" stroke="none"/><circle cx="9" cy="15" r="1.2" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1.2" fill="currentColor" stroke="none"/>',
};

export function iconSvg(name) {
  const body = PATHS[name] || "";
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
}

export function icon(name, className = "") {
  const span = document.createElement("span");
  span.className = `icon ${className}`.trim();
  span.innerHTML = iconSvg(name);
  return span;
}
