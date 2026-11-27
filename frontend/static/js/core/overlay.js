// Modal dialog, side drawer and toast notifications.

import { h } from "./dom.js";
import { icon } from "./icons.js";

/**
 * Open a modal (or drawer). Returns { close, body, footer, root }.
 * options: { title, body, footer, size: "sm" | "md", variant: "modal" | "drawer", dismissible, onClose }
 */
export function openOverlay({ title, body, footer, size = "md", variant = "modal", dismissible = true, onClose } = {}) {
  const previousFocus = document.activeElement;
  const bodyEl = h("div", { class: "modal-body" }, body);
  const footerEl = footer ? h("div", { class: "modal-foot" }, footer) : null;
  const closeBtn = dismissible
    ? h("button", { class: "icon-btn", type: "button", "aria-label": "Close", onclick: () => close() }, icon("close"))
    : null;

  const panel = h(
    "div",
    {
      class: variant === "drawer" ? "drawer" : `modal ${size === "sm" ? "modal-sm" : ""}`,
      role: "dialog",
      "aria-modal": "true",
      "aria-label": title || "Dialog",
    },
    title ? h("div", { class: "modal-head" }, h("h2", { text: title }), closeBtn) : null,
    bodyEl,
    footerEl
  );
  const overlay = h("div", { class: `overlay ${variant === "drawer" ? "drawer-overlay" : ""}` }, panel);

  let closed = false;
  function close(reason = "dismiss") {
    if (closed) return;
    closed = true;
    overlay.remove();
    document.removeEventListener("keydown", onKey);
    if (previousFocus && previousFocus.focus) previousFocus.focus();
    if (onClose) onClose(reason);
  }

  function onKey(event) {
    if (event.key === "Escape" && dismissible) close();
  }

  overlay.addEventListener("mousedown", (event) => {
    if (event.target === overlay && dismissible) close();
  });
  document.addEventListener("keydown", onKey);
  document.body.append(overlay);

  const focusTarget = panel.querySelector("input, textarea, select") || panel.querySelector(".modal-foot .btn-primary") || panel;
  requestAnimationFrame(() => focusTarget.focus && focusTarget.focus());

  return {
    close,
    root: overlay,
    body: bodyEl,
    footer: footerEl,
    setFooter(...nodes) {
      footerEl.replaceChildren(...nodes.filter(Boolean));
    },
    setBody(...nodes) {
      bodyEl.replaceChildren(...nodes.filter(Boolean));
    },
  };
}

let toastStack = null;

export function toast(message, { kind = "danger", timeout = 6000 } = {}) {
  if (!toastStack) {
    toastStack = h("div", { class: "toast-stack", role: "status", "aria-live": "polite" });
    document.body.append(toastStack);
  }
  const node = h(
    "div",
    { class: `toast toast-${kind}` },
    icon(kind === "danger" ? "alert" : "checkCircle"),
    h("div", { text: message })
  );
  toastStack.append(node);
  setTimeout(() => node.remove(), timeout);
}
