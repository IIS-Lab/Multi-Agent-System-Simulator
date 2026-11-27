import { api } from "../core/api.js";
import { h } from "../core/dom.js";
import { icon } from "../core/icons.js";

const errorBox = h("div", { class: "alert alert-danger", role: "alert", hidden: true });
const usernameInput = h("input", { class: "input", id: "username", name: "username", autocomplete: "username", placeholder: "e.g. researcher_01", required: true });
const passwordInput = h("input", { class: "input", id: "password", name: "password", type: "password", autocomplete: "current-password", required: true });
const submitBtn = h("button", { class: "btn btn-dark btn-lg btn-block", type: "submit" }, "Login");

function showError(message) {
  errorBox.replaceChildren(icon("alert"), h("span", { text: message }));
  errorBox.hidden = false;
}

async function onSubmit(event) {
  event.preventDefault();
  errorBox.hidden = true;
  const username = usernameInput.value.trim();
  if (!username) {
    showError("Please enter a username.");
    usernameInput.focus();
    return;
  }
  if (!passwordInput.value) {
    showError("Please enter the password.");
    passwordInput.focus();
    return;
  }
  submitBtn.disabled = true;
  submitBtn.replaceChildren(h("span", { class: "spinner" }), "Signing in…");
  try {
    await api("/api/auth/login", { method: "POST", body: { username, password: passwordInput.value }, redirectOn401: false });
    window.location.href = "/home";
  } catch (error) {
    showError(error.message);
    passwordInput.select();
    submitBtn.disabled = false;
    submitBtn.replaceChildren("Login");
  }
}

document.getElementById("app").append(
  h(
    "div",
    { class: "login-card" },
    h("div", { class: "login-mark" }, icon("network")),
    h("div", { class: "login-eyebrow", text: "MASS" }),
    h("h1", { text: "Multi Agent System Simulator" }),
    h("p", { class: "subtitle", text: "Research prototype. Sign in to configure and run experiments." }),
    h(
      "form",
      { class: "login-form", onsubmit: onSubmit, novalidate: true },
      h("label", { class: "field" }, h("span", { class: "field-label", text: "Username" }), usernameInput),
      h("label", { class: "field" }, h("span", { class: "field-label", text: "Password" }), passwordInput),
      errorBox,
      submitBtn
    ),
    h("p", { class: "login-foot", text: "Your username is recorded in every experiment result you run." })
  )
);
usernameInput.focus();
