// Shared top bar: brand, page crumb, username and a Home button (top-right).

import { api } from "./api.js";
import { h } from "./dom.js";
import { icon } from "./icons.js";

export async function mountHeader({ crumb = "", showHome = true, showLogout = false } = {}) {
  const container = document.getElementById("app-header");
  let username = "";
  try {
    username = (await api("/api/auth/me")).username;
  } catch {
    return "";
  }

  const actions = h("div", { class: "header-actions" });
  actions.append(
    h(
      "span",
      { class: "user-chip", title: `Signed in as ${username}` },
      h("span", { class: "avatar", text: username.slice(0, 1) }),
      h("span", { class: "name", text: username })
    )
  );
  if (showHome) {
    actions.append(h("a", { class: "btn btn-sm", href: "/home", "aria-label": "Home" }, icon("home"), "Home"));
  }
  if (showLogout) {
    actions.append(
      h(
        "button",
        {
          class: "btn btn-sm btn-ghost",
          type: "button",
          onclick: async () => {
            await api("/api/auth/logout", { method: "POST" }).catch(() => {});
            window.location.href = "/login";
          },
        },
        icon("logout"),
        "Log out"
      )
    );
  }

  container.replaceChildren(
    h(
      "div",
      { class: "brand-wrap", style: { display: "flex", alignItems: "center", gap: "14px", minWidth: "0" } },
      h(
        "a",
        { class: "brand", href: "/home", title: "Multi Agent System Simulator" },
        h("span", { class: "brand-mark" }, icon("network")),
        h("span", { class: "brand-short", text: "MASS" }),
        h("span", { class: "brand-long", text: "Multi Agent System Simulator" })
      ),
      crumb ? h("span", { class: "crumb", text: crumb }) : null
    ),
    actions
  );
  return username;
}
