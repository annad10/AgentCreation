"use strict";
const COURSE_LINK_PREFIX = "https://didattica.unibocconi.eu/";

function add(parent, tag, value) {
  const element = document.createElement(tag);
  element.textContent = value;
  parent.appendChild(element);
  return element;
}

// Tabs ---------------------------------------------------------------
const tabs = [...document.querySelectorAll('[role="tab"]')];
function selectTab(tab) {
  for (const other of tabs) {
    const active = other === tab;
    other.setAttribute("aria-selected", active);
    other.tabIndex = active ? 0 : -1;
    document.getElementById(other.getAttribute("aria-controls")).hidden = !active;
  }
}
for (const tab of tabs) {
  tab.addEventListener("click", () => selectTab(tab));
  tab.addEventListener("keydown", event => {
    const step = {ArrowRight: 1, ArrowLeft: -1}[event.key];
    if (!step) return;
    const next = tabs[(tabs.indexOf(tab) + step + tabs.length) % tabs.length];
    selectTab(next);
    next.focus();
  });
}

// OpenAI configuration (one request shared by both tabs) -----------------
const configMessage = fetch("/config").then(response => {
  if (!response.ok) throw new Error("Configuration unavailable");
  return response.json();
}).then(data => data.ai_available
  ? "OpenAI key is configured. Access will be checked when you run OpenAI analysis."
  : "To enable OpenAI, add your API key to the project's .env file and restart the server. Local AI works with Ollama and needs no API key."
).catch(() => "Could not check AI configuration. Make sure the server is running.");

function showCitation(parent, label, evidence) {
  add(parent, "p", label + (evidence.page ? ` — page ${evidence.page}` : "")).className = "source";
  add(parent, "blockquote", evidence.quote);
}

// Behaviour shared by both tabs: method choice, PDF upload, busy state ----------
function setupCommon(panel) {
  const form = panel.querySelector(".panel-form");
  const result = panel.querySelector(".result");
  const submit = form.querySelector(".submit");
  const method = form.querySelector(".mode");
  const consent = form.querySelector(".consent");
  const aiStatus = form.querySelector(".ai-status");
  const state = {pending: 0, busy: false};
  if (aiStatus) configMessage.then(message => { aiStatus.textContent = message; });

  const control = {
    form, result, method, consent, state,
    refresh() { submit.disabled = state.pending > 0 || state.busy; },
    lock(locked) {
      for (const element of form.querySelectorAll("textarea, input, select")) element.disabled = locked;
      if (!locked && consent) consent.disabled = method.value !== "ai";
    },
    text(side) { return form.querySelector(`.doc[data-side="${side}"]`).value; }
  };

  if (method) method.addEventListener("change", () => {
    const ai = method.value === "ai";
    aiStatus.hidden = !ai;
    form.querySelector(".local-status").hidden = method.value !== "ollama";
    form.querySelector(".consent-group").hidden = !ai;
    consent.disabled = !ai;
    consent.checked = false;
    result.textContent = "Method changed. Press the button again to update the results.";
  });

  for (const input of form.querySelectorAll(".pdf-input")) {
    const side = input.dataset.side;
    const status = form.querySelector(`.upload-status[data-side="${side}"]`);
    const textarea = form.querySelector(`.doc[data-side="${side}"]`);
    const preview = form.querySelector(`.preview[data-side="${side}"]`);
    const tables = preview.querySelector(".tables");
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
      state.pending++;
      control.refresh();
      input.disabled = true;
      textarea.readOnly = true;
      preview.hidden = true;
      tables.replaceChildren();
      result.textContent = "PDF changed. Check the extracted text, then press the button again.";
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
        state.pending--;
        control.refresh();
      }
    });
    textarea.addEventListener("input", () => {
      result.textContent = "Text changed. Press the button again to update the results.";
      preview.hidden = true;
      status.textContent = "Text edited manually. The text below will be used.";
    });
  }

  // Sends the request and lets `render` draw the answer.
  control.run = async (url, body, working, render) => {
    state.busy = true;
    control.lock(true);
    control.refresh();
    result.textContent = working;
    try {
      const response = await fetch(url, {
        method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string"
        ? data.detail : "Check your text: each box must contain at least 1 and at most 30,000 characters.");
      result.replaceChildren();
      add(result, "p", data.message);
      if (data.provider) add(result, "p", data.provider === "ollama" ? "Provider: local Ollama. No text sent to OpenAI." : "Provider: OpenAI.");
      add(result, "p", "Advisor review required. This is not an equivalence approval.").className = "notice";
      render(data);
    } catch (error) {
      result.textContent = error instanceof TypeError
        ? "Cannot reach the server. Make sure it is running, then try again."
        : error.message;
    } finally {
      state.busy = false;
      control.lock(false);
      control.refresh();
    }
  };
  return control;
}

// Home-university course given as a web link instead of a file ----------------------
function setupLink(c) {
  const form = c.form;
  const fileBox = form.querySelector(".source-file");
  const linkBox = form.querySelector(".source-link");
  const input = form.querySelector("#syllabus-home-link");
  const button = form.querySelector(".read-link");
  const status = form.querySelector(".link-status");
  const textarea = form.querySelector('.doc[data-side="home"]');
  for (const radio of form.querySelectorAll('input[name="syllabus-home-source"]')) {
    radio.addEventListener("change", () => {
      const link = form.querySelector('input[name="syllabus-home-source"]:checked').value === "link";
      linkBox.hidden = !link;
      fileBox.hidden = link;
    });
  }
  input.addEventListener("keydown", event => {
    if (event.key === "Enter") { event.preventDefault(); button.click(); }
  });
  textarea.addEventListener("input", () => { status.textContent = "Text edited manually. The text below will be used."; });
  button.addEventListener("click", async () => {
    const url = input.value.trim();
    if (!url) { status.textContent = "Paste the link to your course or degree page first."; return; }
    if (c.state.pending || c.state.busy) return;
    c.state.pending++;
    c.refresh();
    button.disabled = input.disabled = textarea.readOnly = true;
    c.result.textContent = "Link changed. Check the text read from the page, then compare.";
    status.textContent = "Reading the page…";
    try {
      const response = await fetch("/extract-url", {
        method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({url})});
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Could not read this link. Check that it is a full web address.");
      textarea.value = data.text;
      status.textContent = `${data.title ? "Read “" + data.title + "”" : "Read the page"} (${data.text.length.toLocaleString()} characters). ${data.warnings.join(" ")}`;
    } catch (error) {
      status.textContent = (error instanceof TypeError
        ? "Cannot reach the server. Make sure it is running."
        : error.message) + " Previous text has not been changed.";
    } finally {
      button.disabled = input.disabled = textarea.readOnly = false;
      c.state.pending--;
      c.refresh();
    }
  });
}

// Syllabus tab: home course -> shortlisted Bocconi courses ----------------------------
function renderComparison(parent, data) {
  if (!data) return;
  if (data.method === "ai") {
    for (const warning of data.warnings) add(parent, "p", warning).className = "notice";
    for (const [kind, heading] of [["similarity", "Similarities"], ["difference", "Differences"]]) {
      const items = data.findings.filter(item => item.kind === kind);
      if (!items.length) continue;
      add(parent, "h4", heading);
      for (const item of items) {
        const section = add(parent, "section", "");
        section.className = "evidence";
        add(section, "strong", item.title);
        add(section, "p", item.explanation);
        showCitation(section, "Your course", item.home);
        showCitation(section, "Bocconi course page", item.bocconi);
      }
    }
    if (data.gaps.length) add(parent, "h4", "Possible coverage gaps to check");
    for (const item of data.gaps) {
      const section = add(parent, "section", "");
      section.className = "evidence";
      add(section, "strong", item.topic);
      add(section, "p", item.explanation);
      showCitation(section, item.source === "home" ? "Your course" : "Bocconi course page", item.citation);
    }
    if (!data.findings.length && !data.gaps.length) add(parent, "p", "No supported observations for this course.");
    return;
  }
  if (!data.evidence.length) add(parent, "p", "No shared keywords found in the text of the Bocconi page.");
  for (const item of data.evidence) {
    const section = add(parent, "section", "");
    section.className = "evidence";
    add(section, "strong", item.term);
    showCitation(section, "Your course", item.home);
    showCitation(section, "Bocconi course page", item.bocconi);
  }
}

function showMatch(parent, match) {
  const card = add(parent, "article", "");
  card.className = "course";
  add(card, "span", "Possible match from the course title").className = "tag";
  add(card, "h3", match.title);
  add(card, "p", `Course ${match.code} · ${match.level} · ${match.department}`).className = "meta";
  const offers = add(card, "ul", "");
  offers.className = "offers";
  for (const offer of match.offerings) add(offers, "li", `${offer.term} — ${offer.credits} credits`);
  if (match.profile_year) add(card, "p", `Bocconi's page says its content refers to the ${match.profile_year} academic year, so the 2026–27 course may differ.`).className = "notice";
  if (match.note) add(card, "p", match.note).className = "notice";
  renderComparison(card, match.comparison);
  if (match.url.startsWith(COURSE_LINK_PREFIX)) {
    const link = add(card, "a", "View course description on the Bocconi website");
    link.href = match.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.className = "course-link";
  }
}

function setupSyllabus(panel) {
  const c = setupCommon(panel);
  const result = c.result;
  setupLink(c);
  c.form.addEventListener("submit", event => {
    event.preventDefault();
    const home = c.text("home");
    const terms = [...c.form.querySelectorAll(".term:checked")].map(box => box.value);
    const level = c.form.querySelector('input[name="syl-level"]:checked').value;
    if (!home.trim()) { result.textContent = "Step 1: upload your course as a PDF or paste a link to it."; return; }
    if (!terms.length) { result.textContent = "Step 2: choose Fall 2026, Spring 2027 or both."; return; }
    if (c.state.pending || c.state.busy) return;
    c.run("/match-offer", {home_syllabus: home, terms, level, mode: "keyword", ai_consent: false},
      "Finding courses and reading their Bocconi pages…",
      data => {
        add(result, "p", `Searched ${data.candidate_count} courses in the Fall 2026 and Spring 2027 offer.`).className = "hint";
        const list = add(result, "div", "");
        list.className = "course-list";
        for (const match of data.matches) showMatch(list, match);
        add(result, "p", data.limitations).className = "hint";
      });
  });
}

// Course recommendation tab -------------------------------------------------
const CATEGORY = {
  background: "Based on your background",
  interest: "Based on your interests or job goal",
  gap: "Possible skill gap to check"
};
const SOURCE = {cv: "Your CV", job: "Your job of interest", interests: "Your interests"};

function showCourse(parent, rec) {
  const card = add(parent, "article", "");
  card.className = "course";
  add(card, "span", CATEGORY[rec.category] || "Suggestion").className = "tag tag-" + rec.category;
  add(card, "h3", rec.title);
  add(card, "p", `Course ${rec.code} · ${rec.level} · ${rec.department}`).className = "meta";
  const offers = add(card, "ul", "");
  offers.className = "offers";
  for (const offer of rec.offerings) add(offers, "li", `${offer.term} — ${offer.credits} credits`);
  add(card, "p", rec.reason);
  showCitation(card, SOURCE[rec.evidence.source] || "Your text", rec.evidence);
  if (rec.url.startsWith(COURSE_LINK_PREFIX)) {
    const link = add(card, "a", "View course description on the Bocconi website");
    link.href = rec.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.className = "course-link";
  }
}

function setupRecommend(panel) {
  const c = setupCommon(panel);
  const result = c.result;
  const job = panel.querySelector("#rec-job");
  const interests = panel.querySelector("#rec-interests");
  c.form.addEventListener("submit", event => {
    event.preventDefault();
    const cv = c.text("home");
    const terms = [...c.form.querySelectorAll(".term:checked")].map(box => box.value);
    const level = c.form.querySelector('input[name="level"]:checked').value;
    if (!cv.trim()) { result.textContent = "Step 1: upload your CV as a PDF."; return; }
    if (!job.value.trim()) { result.textContent = "Step 2: enter the job or career you are interested in."; return; }
    if (!terms.length) { result.textContent = "Step 3: choose Fall 2026, Spring 2027 or both."; return; }
    if (c.state.pending || c.state.busy) return;
    c.run("/recommend", {cv_text: cv, job: job.value, interests: interests.value, terms, level,
        mode: "keyword", ai_consent: false},
      "Finding courses…",
      data => {
        add(result, "p", `Searched ${data.candidate_count} courses in the Fall 2026 and Spring 2027 offer.`).className = "hint";
        for (const warning of data.warnings) add(result, "p", warning).className = "notice";
        const list = add(result, "div", "");
        list.className = "course-list";
        for (const rec of data.recommendations) showCourse(list, rec);
        add(result, "p", data.limitations).className = "hint";
      });
  });
}

for (const panel of document.querySelectorAll("[data-kind]")) {
  (panel.dataset.kind === "recommend" ? setupRecommend : setupSyllabus)(panel);
}
