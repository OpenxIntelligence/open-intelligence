// Dependency-free interaction regressions for the synthetic World Model inspector.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const source = fs.readFileSync(path.join(__dirname, "../web/world-model.js"), "utf8");
const wait = () => new Promise((resolve) => setImmediate(resolve));

function fixture() {
  class Element {
    constructor(id = "") {
      this.id = id;
      this.value = "";
      this.open = false;
      this.textContent = "";
      this.children = [];
      this.dataset = {};
      this.listeners = {};
    }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children = [...children]; }
    addEventListener(kind, fn) { (this.listeners[kind] ||= []).push(fn); }
    fire(kind) { for (const fn of this.listeners[kind] || []) fn(); }
    focus() { this.focused = true; }
  }
  const ids = [
    "case-picker", "world-model-detail", "world-model-status",
    "world-model-summary", "world-model-observations",
    "world-model-conflicts", "world-model-history", "event-list",
    "question-text", "question-form",
  ];
  const elements = Object.fromEntries(ids.map((id) => [id, new Element(id)]));
  const requests = [];
  const location = {hash: ""};
  const context = vm.createContext({
    document: {
      getElementById: (id) => elements[id] || null,
      createElement: () => new Element(),
    },
    fetch: (url, opts) => new Promise((resolve) => requests.push({url, opts, resolve})),
    MutationObserver: class { observe() {} },
    queueMicrotask,
    location,
    Error,
  });
  vm.runInContext(source, context, {filename: "world-model.js"});
  return {elements, requests, location};
}
function model(caseId, statement = "Indeterminate") {
  return {
    contract: "oi.synthetic-world-model/1",
    synthetic: true,
    case_id: caseId,
    authority: "source_report_only_unreviewed",
    summary: {current_sources: 1, current_observations: 1,
      unresolved_observations: 1, source_disagreements: 0},
    observations: [{finding_key: "Marker Q", reported_state: "indeterminate",
      source_statement: statement, document_id: "REPORT-1", document_version: 1,
      source_version_id: 7, source_line: 4, event_date: "2026-01-02",
      issued_at: "2026-01-03", received_at: "2026-01-04", source_sha256: "abc123"}],
    conflicts: [], history: [],
    review_needed: {open_question_ids: [2], draft_snapshot_ids: [], stale_snapshot_ids: [5]},
  };
}
async function complete(request, data, ok = true) {
  request.resolve({ok, json: async () => data});
  await wait();
}
test("case A response never reappears after switching to case B", async () => {
  const {elements: e, requests} = fixture();
  e["case-picker"].value = "CASE-A";
  e["world-model-detail"].open = true;
  e["world-model-detail"].fire("toggle");
  assert.equal(requests.length, 1);
  assert.equal(requests[0].opts.cache, "no-store");
  e["case-picker"].value = "CASE-B";
  e["case-picker"].fire("change");
  assert.equal(requests.length, 2);
  assert.equal(e["world-model-observations"].children.length, 0);
  await complete(requests[1], model("CASE-B", "B's unique marker"));
  assert.equal(e["world-model-detail"].dataset.caseId, "CASE-B");
  await complete(requests[0], model("CASE-A", "A's secret marker"));
  const lines = e["world-model-observations"].children.map((x) => x.textContent).join(" ");
  assert.match(lines, /B's unique marker/);
  assert.doesNotMatch(lines, /A's secret marker/);
});
test("source text remains literal and mismatched scope is denied", async () => {
  const {elements: e, requests} = fixture();
  e["case-picker"].value = "CASE-A";
  e["world-model-detail"].open = true;
  e["world-model-detail"].fire("toggle");
  await complete(requests[0], model("CASE-A", "<img src=x onerror=alert(1)>"));
  assert.match(e["world-model-observations"].children[0].textContent,
    /<img src=x onerror=alert\(1\)>/);
  e["world-model-detail"].fire("toggle");
  await complete(requests[1], model("CASE-OTHER"));
  assert.equal(e["world-model-observations"].children.length, 0);
  assert.match(e["world-model-status"].textContent, /contract mismatch/);
  assert.equal(e["world-model-detail"].dataset.caseId, undefined);
});
test("collapsing the inspector invalidates pending patient information", async () => {
  const {elements: e, requests} = fixture();
  e["case-picker"].value = "CASE-A";
  e["world-model-detail"].open = true;
  e["world-model-detail"].fire("toggle");
  e["world-model-detail"].open = false;
  e["world-model-detail"].fire("toggle");
  await complete(requests[0], model("CASE-A", "Must remain hidden"));
  assert.equal(e["world-model-observations"].children.length, 0);
  assert.equal(e["world-model-detail"].dataset.caseId, undefined);
});

test("an exact fictional source prepares a question in the existing form, without saving", async () => {
  const {elements: e, requests, location} = fixture();
  e["case-picker"].value = "CASE-A";
  e["world-model-detail"].open = true;
  e["world-model-detail"].fire("toggle");
  await complete(requests[0], model("CASE-A"));
  const source = e["world-model-observations"].children[0];
  assert.equal(source.children.length, 1);
  source.children[0].fire("click");
  assert.match(e["question-text"].value, /Marker Q/);
  assert.match(e["question-text"].value, /REPORT-1 v1, source line 4/);
  assert.equal(location.hash, "#investigations");
  assert.equal(e["question-text"].focused, true);
  assert.match(e["world-model-status"].textContent, /Review and submit it yourself/);
  assert.equal(requests.length, 1, "handoff must not issue a new write request");
});

test("handoff never overwrites an unfinished question or silently submits it", async () => {
  const {elements: e, requests, location} = fixture();
  e["case-picker"].value = "CASE-A";
  e["world-model-detail"].open = true;
  e["world-model-detail"].fire("toggle");
  await complete(requests[0], model("CASE-A"));
  e["question-text"].value = "Unfinished question in the user's own words";
  e["world-model-observations"].children[0].children[0].fire("click");
  assert.equal(e["question-text"].value, "Unfinished question in the user's own words");
  assert.equal(location.hash, "");
  assert.match(e["world-model-status"].textContent, /unsaved question already exists/);
  assert.equal(requests.length, 1);
});

test("a stale source button cannot prepare a question after changing cases", async () => {
  const {elements: e, requests} = fixture();
  e["case-picker"].value = "CASE-A";
  e["world-model-detail"].open = true;
  e["world-model-detail"].fire("toggle");
  await complete(requests[0], model("CASE-A"));
  const stale = e["world-model-observations"].children[0].children[0];
  e["case-picker"].value = "CASE-B";
  e["case-picker"].fire("change");
  stale.fire("click");
  assert.equal(e["question-text"].value, "");
  await complete(requests[1], model("CASE-B"));
  stale.fire("click");
  assert.equal(e["question-text"].value, "");
  e["world-model-detail"].open = false;
  e["world-model-detail"].fire("toggle");
  assert.equal(e["question-text"].value, "");
});

test("markup-like source values become inert question text, not executable HTML", async () => {
  const {elements: e, requests} = fixture();
  e["case-picker"].value = "CASE-A";
  e["world-model-detail"].open = true;
  e["world-model-detail"].fire("toggle");
  const payload = model("CASE-A", "<img onerror=alert(1)>");
  payload.observations[0].finding_key = "<script>unsafe</script>";
  await complete(requests[0], payload);
  e["world-model-observations"].children[0].children[0].fire("click");
  assert.match(e["question-text"].value, /<script>unsafe<\/script>/);
  assert.equal(e["question-text"].value.length <= 500, true);
  assert.equal(requests.length, 1);
});
