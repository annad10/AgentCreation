"use strict";
const form = document.querySelector("#course-form");
const result = document.querySelector("#result");
const compareButton = form.querySelector('button[type="submit"]');
let pendingUploads = 0;
let comparing = false;
const method = document.querySelector("#comparison-mode");
const consent = document.querySelector("#ai-consent");
const aiStatus = document.querySelector("#ai-status");
method.addEventListener("change", () => {
  const ai = method.value === "ai";
  aiStatus.hidden = !ai;
  document.querySelector("#local-status").hidden = method.value !== "ollama";
  document.querySelector("#ai-consent-group").hidden = !ai;
  consent.disabled = !ai;
  consent.required = ai;
  consent.checked = false;
  result.textContent = "Method changed. Compare again to update the results.";
});
fetch("/config").then(response => {
  if (!response.ok) throw new Error("Configuration unavailable");
  return response.json();
}).then(data => {
  aiStatus.textContent = data.ai_available
    ? "OpenAI key is configured. Access will be checked when you run OpenAI analysis."
    : "To enable OpenAI, add your API key to the project's .env file and restart the server. Local AI works with Ollama and needs no API key.";
}).catch(() => { aiStatus.textContent = "Could not check AI configuration. Make sure the server is running."; });

function showCitation(parent, label, evidence) {
  add(parent, "p", label + (evidence.page ? ` — page ${evidence.page}` : ""));
  add(parent, "blockquote", evidence.quote);
}
function showAI(data) {
  for (const warning of data.warnings) add(result, "p", warning).className = "notice";
  for (const [kind, heading] of [["similarity", "Similarities"], ["difference", "Differences"]]) {
    add(result, "h3", heading);
    const items = data.findings.filter(item => item.kind === kind);
    if (!items.length) add(result, "p", "No supported observations returned in this category.");
    for (const item of items) {
      const section = add(result, "section", "");
      section.className = "evidence";
      add(section, "h4", item.title);
      add(section, "p", item.explanation);
      showCitation(section, "Home-university syllabus", item.home);
      showCitation(section, "Bocconi syllabus", item.bocconi);
    }
  }
  add(result, "h3", "Possible coverage gaps to check");
  add(result, "p", "These are topics whose coverage is unclear in the other supplied syllabus. This does not prove that the course omits them.");
  if (!data.gaps.length) add(result, "p", "No supported gaps returned. This does not establish full coverage.");
  for (const item of data.gaps) {
    const section = add(result, "section", "");
    section.className = "evidence";
    add(section, "h4", item.topic);
    add(section, "p", item.explanation);
    showCitation(section, item.source === "home" ? "Home-university syllabus" : "Bocconi syllabus", item.citation);
  }
  add(result, "p", "Ask your advisor to check academic level, assessment, learning outcomes and credit rules before requesting recognition.");
}
function updateButton() { compareButton.disabled = pendingUploads > 0 || comparing; }
function add(parent, tag, value) {
  const element = document.createElement(tag);
  element.textContent = value;
  parent.appendChild(element);
  return element;
}
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const home = document.querySelector("#syllabus").value;
  const bocconi = document.querySelector("#bocconi-syllabus").value;
  if (!home.trim() || !bocconi.trim()) {
    result.textContent = "Please paste both syllabi first.";
    return;
  }
  if (pendingUploads || comparing) return;
  if (method.value === "ai" && !consent.checked) {
    result.textContent = "Confirm sending both syllabus texts to OpenAI first.";
    return;
  }
  if (method.value === "ollama" && home.length + bocconi.length > 6000) {
    result.textContent = "Local AI accepts at most 6,000 characters across both texts. Keep the relevant content and learning outcomes in the text boxes, then try again. No text was sent or truncated.";
    return;
  }
  comparing = true;
  for (const control of form.querySelectorAll("textarea, input[type=file], select")) control.disabled = true;
  updateButton();
  result.textContent = method.value === "ollama" ? "Comparing with local Qwen… This may take a few minutes." : "Comparing…";
  try {
    const response = await fetch("/match", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({home_syllabus: home, bocconi_syllabus: bocconi, mode: method.value, ai_consent: consent.checked})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === "string"
      ? data.detail : "Check both texts: each must contain 1–30,000 characters.");
    result.replaceChildren();
    add(result, "p", data.message);
    if (data.provider) add(result, "p", data.provider === "ollama" ? "Provider: local Ollama. No text sent to OpenAI." : "Provider: OpenAI.");
    add(result, "p", "Advisor review required. This is not an equivalence approval.");
    add(result, "p", data.limitations).className = "hint";
    if (data.method === "ai") {
      showAI(data);
      return;
    }
    for (const item of data.evidence) {
      const section = add(result, "section", "");
      section.className = "evidence";
      add(section, "h3", item.term);
      add(section, "p", "Home-university syllabus" + (item.home.page ? ` — page ${item.home.page}` : ""));
      add(section, "blockquote", item.home.quote);
      add(section, "p", "Bocconi syllabus" + (item.bocconi.page ? ` — page ${item.bocconi.page}` : ""));
      add(section, "blockquote", item.bocconi.quote);
    }
  } catch (error) {
    result.textContent = error instanceof TypeError
      ? "Cannot reach the server. Make sure it is running, then try again."
      : error.message;
  } finally {
    comparing = false;
    for (const control of form.querySelectorAll("textarea, input[type=file], select")) control.disabled = false;
    updateButton();
  }
});


for (const [key, textId] of [["home", "syllabus"], ["bocconi", "bocconi-syllabus"]]) {
  const input = document.querySelector(`#${key}-pdf`);
  const status = document.querySelector(`#${key}-upload-status`);
  const textarea = document.getElementById(textId);
  const preview = document.querySelector(`#${key}-preview`);
  const tables = document.querySelector(`#${key}-tables`);
  input.addEventListener("change", async () => {
    const file = input.files[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      status.textContent = "Choose a PDF file. Previous text has not been changed.";
      input.value = "";
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      status.textContent = "PDF must be 10 MB or smaller. Previous text has not been changed.";
      input.value = "";
      return;
    }
    pendingUploads++;
    updateButton();
    input.disabled = true;
    textarea.readOnly = true;
    preview.hidden = true;
    tables.replaceChildren();
    result.textContent = "PDF changed. Review the extracted text, then compare again.";
    status.textContent = "Reading PDF and extracting tables…";
    try {
      const response = await fetch("/extract-pdf", {
        method: "POST", headers: {"Content-Type": "application/pdf"}, body: file
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Could not extract this PDF.");
      textarea.value = data.text;
      status.replaceChildren();
      add(status, "span", `${file.name}: ${data.page_count} page(s) loaded. `);
      add(status, "span", data.warnings.join(" "));
      for (const page of data.pages) {
        page.tables.forEach((rows, index) => {
          const table = add(tables, "table", "");
          add(table, "caption", `Page ${page.number}, table ${index + 1}`);
          const body = add(table, "tbody", "");
          for (const row of rows) {
            const tr = add(body, "tr", "");
            for (const cell of row) add(tr, "td", cell);
          }
        });
      }
      preview.hidden = !tables.childElementCount;
    } catch (error) {
      status.textContent = (error instanceof TypeError
        ? "Cannot reach the server. Make sure it is running."
        : error.message) + " Previous text has not been changed.";
    } finally {
      input.value = "";
      input.disabled = false;
      textarea.readOnly = false;
      pendingUploads--;
      updateButton();
    }
  });
  textarea.addEventListener("input", () => {
    result.textContent = "Text changed. Compare again to update the results.";
    preview.hidden = true;
    status.textContent = "Text edited manually. Compare using the text below.";
  });
}
