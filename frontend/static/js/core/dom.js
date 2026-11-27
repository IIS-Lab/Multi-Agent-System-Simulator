// Tiny DOM helper: h("div", { class: "x", onclick: fn }, child1, "text", [more]).

export function h(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props || {})) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key === "style" && typeof value === "object") {
      for (const [prop, propValue] of Object.entries(value)) {
        if (prop.startsWith("--")) node.style.setProperty(prop, propValue);
        else node.style[prop] = propValue;
      }
    }
    else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2), value);
    else if (key === "value") node.value = value;
    else if (key in node && typeof value !== "string") node[key] = value;
    else node.setAttribute(key, value === true ? "" : value);
  }
  appendChildren(node, children);
  return node;
}

function appendChildren(node, children) {
  for (const child of children) {
    if (child === null || child === undefined || child === false) continue;
    if (Array.isArray(child)) appendChildren(node, child);
    else node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
}

export function clear(node) {
  node.replaceChildren();
  return node;
}

export function deepCopy(value) {
  return JSON.parse(JSON.stringify(value));
}
