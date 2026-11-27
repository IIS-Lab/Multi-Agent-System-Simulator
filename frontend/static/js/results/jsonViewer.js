// Pretty-printed, syntax-highlighted JSON. Shows the complete document.

import { h } from "../core/dom.js";

const TOKEN_RE = /("(?:\\.|[^"\\])*")(\s*:)?|\b(true|false|null)\b|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)|([{}[\],])/g;

export function renderJson(data) {
  const text = JSON.stringify(data, null, 2);
  const pre = h("pre", { class: "json-view", tabindex: "0", "aria-label": "Result JSON" });
  let last = 0;
  for (const match of text.matchAll(TOKEN_RE)) {
    if (match.index > last) pre.append(text.slice(last, match.index));
    const [token, string, colon, literal, number, punct] = match;
    if (string !== undefined) {
      pre.append(h("span", { class: colon ? "k" : "s", text: string }));
      if (colon) pre.append(h("span", { class: "p", text: colon }));
    } else if (literal) pre.append(h("span", { class: "l", text: literal }));
    else if (number) pre.append(h("span", { class: "n", text: number }));
    else if (punct) pre.append(h("span", { class: "p", text: punct }));
    else pre.append(token);
    last = match.index + token.length;
  }
  if (last < text.length) pre.append(text.slice(last));
  return pre;
}
