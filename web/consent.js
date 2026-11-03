(() => {
  "use strict";

  const picker = document.querySelector("#case-picker");
  const section = document.querySelector("#consent-identity");
  const consentList = document.querySelector("#consent-list");
  const qualifierList = document.querySelector("#qualifier-list");
  const consentForm = document.querySelector("#consent-form");
  const consentScope = document.querySelector("#consent-scope");
  const consentDate = document.querySelector("#consent-date");
  const withdrawForm = document.querySelector("#consent-withdraw-form");
  const withdrawChoice = document.querySelector("#consent-withdraw-choice");
  const withdrawReason = document.querySelector("#consent-withdraw-reason");
  const withdrawDate = document.querySelector("#consent-withdraw-date");
  const qualifierForm = document.querySelector("#qualifier-form");
  const qualifierText = document.querySelector("#qualifier-text");
  const qualifierAnchor = document.querySelector("#qualifier-anchor-choice");
  const qualifierDate = document.querySelector("#qualifier-date");
  const eventList = document.querySelector("#event-list");

  if (!picker || !section || !consentList || !qualifierList || !consentForm ||
      !consentScope || !consentDate || !withdrawForm || !withdrawChoice ||
      !withdrawReason || !withdrawDate || !qualifierForm || !qualifierText ||
      !qualifierAnchor || !qualifierDate) {
    return;
  }

  let requestSequence = 0;
  let refreshScheduled = false;

  function element(tag, className, text) {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (text !== undefined) item.textContent = String(text);
    return item;
  }

  function empty(container, message) {
    container.replaceChildren(element("p", "empty", message));
  }

  function notice(message, isError) {
    const item = document.querySelector("#notice");
    if (!item) return;
    item.textContent = String(message);
    item.className = isError ? "notice error" : "notice";
    item.hidden = false;
  }

  function fictionalPill() {
    return element("span", "pill pill-warn", "FICTIONAL");
  }

  function statusPill(status) {
    return element("span", status === "withdrawn" ? "pill pill-neutral" : "pill", status);
  }

  function renderConsents(consents) {
    const prior = withdrawChoice.value;
    withdrawChoice.replaceChildren();
    if (!consents.length) {
      empty(consentList, "No fictional consents recorded for this case.");
    } else {
      consentList.replaceChildren(...consents.map((item) => {
        const card = element("article", "source-card");
        const top = element("div", "source-top");
        top.append(
          element("strong", "source-title", "Consent #" + item.id),
          fictionalPill(),
          statusPill(item.status),
        );
        card.append(top);
        card.append(element("p", "", item.scope_text));
        card.append(element("p", "snapshot-meta",
          "Date recorded: " + item.date_recorded +
          " · Review: display only, not clinical approval" +
          (item.anchor_label ? " · Linked source: " + item.anchor_label : " · No linked source") +
          " · Recorded " + item.created_at));
        const history = item.versions || [];
        if (!history.length) {
          card.append(element("p", "muted", "No history rows returned."));
        } else {
          card.append(element("p", "snapshot-meta", "Full history, oldest first:"));
          const list = element("ul");
          for (const entry of history) {
            list.append(element("li", "",
              "Version " + entry.version + " · " + entry.status +
              " · date " + entry.date_recorded +
              (entry.reason ? " · reason: " + entry.reason : " · no reason recorded") +
              " · saved " + entry.recorded_at));
          }
          card.append(list);
        }
        return card;
      }));
    }
    const active = consents.filter((item) => item.status === "active");
    if (!active.length) {
      const opt = element("option", "", "No active fictional consent");
      opt.value = "";
      withdrawChoice.append(opt);
    } else {
      for (const item of active) {
        const opt = element("option", "",
          "Consent #" + item.id + " · " + String(item.scope_text).slice(0, 60));
        opt.value = String(item.id);
        withdrawChoice.append(opt);
      }
    }
    if (prior && [...withdrawChoice.options].some((x) => x.value === prior)) {
      withdrawChoice.value = prior;
    } else if (prior) {
      // Do not silently attach a drafted reason to a different consent.
      withdrawChoice.selectedIndex = -1;
      notice("The selected consent is no longer active. Select a current consent explicitly.", true);
    }
  }

  function renderQualifiers(qualifiers) {
    if (!qualifiers.length) {
      empty(qualifierList, "No fictional identity notes for this case. Notes never change existing records.");
      return;
    }
    qualifierList.replaceChildren(...qualifiers.map((item) => {
      const card = element("article", "finding");
      const head = element("div", "finding-head");
      head.append(
        element("strong", "", "Note #" + item.id),
        fictionalPill(),
      );
      card.append(head);
      card.append(element("p", "", item.qualifier_text));
      card.append(element("span", "ref",
        "Linked source: " + item.anchor_label +
        " · Date recorded: " + item.date_recorded +
        " · Review: display only"));
      return card;
    }));
  }

  function renderAnchors(sources) {
    const prior = qualifierAnchor.value;
    qualifierAnchor.replaceChildren();
    const current = (sources || []).filter((s) => s.state === "current");
    const choices = current.length ? current : (sources || []);
    if (!choices.length) {
      const opt = element("option", "", "No source to attach to yet");
      opt.value = "";
      qualifierAnchor.append(opt);
      return;
    }
    for (const source of choices) {
      const opt = element("option", "",
        source.document_id + "@" + source.version + " · #" + source.id);
      opt.value = String(source.id);
      qualifierAnchor.append(opt);
    }
    if (prior && [...qualifierAnchor.options].some((x) => x.value === prior)) {
      qualifierAnchor.value = prior;
    }
  }

  async function fetchJson(path) {
    const response = await fetch(path, {cache: "no-store"});
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || ("HTTP " + response.status));
    return payload;
  }

  async function refreshConsent() {
    const caseId = picker.value;
    if (!caseId) return;
    const sequence = ++requestSequence;
    section.dataset.caseId = caseId;
    empty(consentList, "Loading fictional consents…");
    empty(qualifierList, "Loading fictional identity notes…");
    try {
      const [consentsPayload, qualifiersPayload, statePayload] = await Promise.all([
        fetchJson(`/api/cases/${encodeURIComponent(caseId)}/consents`),
        fetchJson(`/api/cases/${encodeURIComponent(caseId)}/identity-qualifiers`),
        fetchJson(`/api/cases/${encodeURIComponent(caseId)}/state`),
      ]);
      if (sequence !== requestSequence || picker.value !== caseId) return;
      section.dataset.caseId = caseId;
      renderConsents(consentsPayload.consents || []);
      renderQualifiers(qualifiersPayload.identity_qualifiers || []);
      renderAnchors(statePayload.sources || []);
    } catch (error) {
      if (sequence !== requestSequence || picker.value !== caseId) return;
      section.dataset.caseId = caseId;
      empty(consentList, "Fictional consents could not be loaded.");
      empty(qualifierList, error instanceof Error ? error.message : "Unknown error");
      qualifierAnchor.replaceChildren();
    }
  }

  function scheduleRefresh() {
    if (refreshScheduled) return;
    refreshScheduled = true;
    queueMicrotask(() => {
      refreshScheduled = false;
      refreshConsent();
    });
  }

  async function postJson(path, payload) {
    const response = await fetch(path, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || ("HTTP " + response.status));
    return data;
  }

  consentForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const caseId = picker.value;
    if (!caseId) return;
    try {
      const created = await postJson(`/api/cases/${encodeURIComponent(caseId)}/consents`, {
        scope_text: consentScope.value,
        date_recorded: consentDate.value,
      });
      if (picker.value !== caseId) return;
      consentScope.value = "";
      consentDate.value = "";
      notice("Fictional consent #" + created.consent_id + " recorded as active.");
      scheduleRefresh();
    } catch (error) {
      notice(error instanceof Error ? error.message : "Unknown error", true);
    }
  });

  withdrawForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const caseId = picker.value;
    if (!caseId || !withdrawChoice.value) return;
    try {
      const payload = {reason: withdrawReason.value};
      if (withdrawDate.value) payload.date_recorded = withdrawDate.value;
      const outcome = await postJson(
        `/api/cases/${encodeURIComponent(caseId)}/consents/${withdrawChoice.value}/withdraw`,
        payload);
      if (picker.value !== caseId) return;
      withdrawReason.value = "";
      withdrawDate.value = "";
      notice("Fictional consent #" + outcome.consent_id + " withdrawn; history kept (version " + outcome.version + ").");
      scheduleRefresh();
    } catch (error) {
      notice(error instanceof Error ? error.message : "Unknown error", true);
    }
  });

  qualifierForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const caseId = picker.value;
    if (!caseId || !qualifierAnchor.value) return;
    try {
      const created = await postJson(`/api/cases/${encodeURIComponent(caseId)}/identity-qualifiers`, {
        qualifier_text: qualifierText.value,
        anchor_source_version_id: Number(qualifierAnchor.value),
        date_recorded: qualifierDate.value,
      });
      if (picker.value !== caseId) return;
      qualifierText.value = "";
      qualifierDate.value = "";
      notice("Fictional identity note #" + created.qualifier_id + " recorded; no existing record changed.");
      scheduleRefresh();
    } catch (error) {
      notice(error instanceof Error ? error.message : "Unknown error", true);
    }
  });

  picker.addEventListener("change", () => {
    consentList.replaceChildren();
    qualifierList.replaceChildren();
    withdrawChoice.replaceChildren();
    qualifierAnchor.replaceChildren();
    scheduleRefresh();
  });
  if (eventList) {
    const observer = new MutationObserver(scheduleRefresh);
    observer.observe(eventList, {childList: true});
  }
  scheduleRefresh();
})();
