import { h } from "../core/dom.js";
import { mountHeader } from "../core/header.js";
import { icon } from "../core/icons.js";

const username = await mountHeader({ showHome: false, showLogout: true });

function tile({ href, iconName, title, description, secondary = false }) {
  return h(
    "a",
    { class: `home-tile ${secondary ? "secondary" : ""}`, href },
    h("span", { class: "tile-icon" }, icon(iconName)),
    icon("arrowRight", "tile-arrow"),
    h("h2", { text: title }),
    h("p", { text: description })
  );
}

document.getElementById("app").append(
  h(
    "div",
    { class: "home-inner" },
    h("div", { class: "home-eyebrow", text: "Research workspace" }),
    h("h1", { class: "home-title", text: username ? `Welcome, ${username}.` : "Welcome." }),
    h("p", { class: "home-sub", text: "Configure a simulated human and AI agents, run the conversation, and review saved results." }),
    h(
      "div",
      { class: "home-actions" },
      tile({
        href: "/run",
        iconName: "play",
        title: "Run Experiment",
        description: "Configure personas, rounds and ordering, then run a multi-agent simulation.",
      }),
      tile({
        href: "/results",
        iconName: "list",
        title: "Check Result",
        description: "Browse experiment results saved to GitHub and inspect the full JSON.",
        secondary: true,
      })
    )
  )
);
