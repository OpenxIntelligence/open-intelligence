(() => {
  "use strict";

  const picker = document.querySelector("#case-picker");
  const form = document.querySelector("#case-search-form");
  const input = document.querySelector("#case-search-input");
  const sort = document.querySelector("#case-search-sort");
  const list = document.querySelector("#case-search-list");
  const count = document.querySelector("#case-search-count");
  const eventList = document.querySelector("#event-list");

  if (!picker || !form || !input || !sort || !list || !count) {
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

  function describe(item) {
    const created = item.created_at
      ? "Created " + item.created_at.slice(0, 10)
      : "Created date unavailable";
    const activity = item.last_activity_at
      ? "Last activity " + item.last_activity_at.slice(0, 10)
      : "No recorded activity";
    const counts = item.counts || {};
    return created + " · " + activity +
      " · Current sources: " + (counts.sources ?? 0) +
      " · Open questions: " + (counts.open_questions ?? 0) +
      " · Drafts awaiting review: " + (counts.pending_reviews ?? 0) +
      " · Overdue follow-ups: none tracked";
  }

  function renderList(items, searchTerm, sortValue) {
    // Always clear before rendering so a previous search can never linger.
    list.replaceChildren();
    if (!items.length) {
      if (!searchTerm.trim()) {
        count.textContent = "No fictional cases in this demo.";
        empty(list, "No fictional cases in this demo.");
      } else {
        count.textContent = "No fictional cases match this search.";
        empty(list, "No fictional cases match '" + searchTerm.trim() +
          "'. Try part of a case ID or label.");
      }
      return;
    }
    const sortedBy = sortValue === "recent"
      ? "sorted by most recent activity"
      : "sorted by case ID";
    count.textContent = items.length === 1
      ? "1 fictional case · " + sortedBy + "."
      : items.length + " fictional cases · " + sortedBy + ".";
    for (const item of items) {
      const row = element("div", "question");
      const text = document.createElement("div");
      text.append(element("p", "", (item.label || "") + " · " + (item.case_id || "")));
      text.append(element("span", "pill pill-warn", "FICTIONAL — demo only"));
      if (item.case_id === picker.value) {
        text.append(element("span", "pill", "Currently open"));
      }
      text.append(element("p", "muted", describe(item)));
      const open = element("button", "button secondary minor", "Open this case");
      open.type = "button";
      open.addEventListener("click", () => {
        // Reuse the existing case-switch path so its unfinished-draft
        // guard runs unchanged; never assign the case directly.
        picker.value = item.case_id;
        picker.dispatchEvent(new Event("change"));
        const overview = document.querySelector("#overview");
        if (overview && overview.scrollIntoView) overview.scrollIntoView();
      });
      row.append(text, open);
      list.append(row);
    }
  }

  async function refreshCaseSearch() {
    const sequence = ++requestSequence;
    const searchTerm = input.value;
    const sortValue = sort.value;
    count.textContent = "Loading fictional cases…";
    try {
      const response = await fetch(
        "/api/cases?search=" + encodeURIComponent(searchTerm) +
        "&sort=" + encodeURIComponent(sortValue),
        { cache: "no-store" },
      );
      const payload = await response.json();
      if (sequence !== requestSequence) return;
      if (!response.ok) throw new Error(payload.error || ("HTTP " + response.status));
      if (!Array.isArray(payload)) throw new Error("Case list response was not a list.");
      renderList(payload, searchTerm, sortValue);
    } catch (error) {
      if (sequence !== requestSequence) return;
      list.replaceChildren();
      count.textContent = "Case list unavailable.";
      empty(list, "Case list could not be loaded: " +
        (error instanceof Error ? error.message : "Unknown error"));
    }
  }

  function scheduleRefresh() {
    if (refreshScheduled) return;
    refreshScheduled = true;
    queueMicrotask(() => {
      refreshScheduled = false;
      refreshCaseSearch();
    });
  }

  // The search box and sort control are global list controls, not
  // per-case drafts, so a case switch must not clear them. The list
  // itself is cleared and re-rendered on every response, and stale
  // responses are discarded by sequence above.
  form.addEventListener("submit", (event) => event.preventDefault());
  input.addEventListener("input", scheduleRefresh);
  sort.addEventListener("change", scheduleRefresh);
  picker.addEventListener("change", scheduleRefresh);
  if (eventList) {
    const observer = new MutationObserver(scheduleRefresh);
    observer.observe(eventList, { childList: true });
  }
  scheduleRefresh();
})();
