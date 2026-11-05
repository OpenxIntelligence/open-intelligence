# Run the fictional patient workspace

This is the connected React/FastAPI/PostgreSQL application. Use only the supplied independently fictional records. It does not run a model, approve clinical decisions or send records to anyone.

## Start

Use macOS or Linux with Docker Compose v2, Python 3.12+ and Node 22.12+.
The existing container is pinned to Linux amd64; Apple Silicon uses emulation.
Keep ports 8000 and 4173 free. Run these commands from the repository root:

```sh
npm --prefix apps/web ci --omit=optional --ignore-scripts --no-audit --no-fund
npm --prefix apps/web run rights
npm --prefix apps/web run build
python tools/h1_demo.py up --fictional-only
python tools/h1_demo.py credentials
npm --prefix apps/web run preview
```

Open **http://127.0.0.1:4173**. In Overview, paste the synthetic fixture token into the access field and connect. Paste the printed patient ID into the patient field and open it. The launcher creates one patient, one case and one source through the existing APIs; it grants only that patient to this local fixture. The pending assay and evidence example are invented and have no treatment implications.

The first start downloads/builds the pinned backend. Package rights checks must pass; do not install optional packages as a workaround. The two omitted optional packages remain uninspected. The application's distribution license and release-wide rights are still separate decisions.

## Complete one journey

| Step | Action | What should be visible |
|---|---|---|
| Records | Check authorized cases; inspect source versions for `CASE-DEMO`; open the original | The exact fictional report, including the explicitly pending assay and original identity/hash |
| Question | Use the source's question action; enter “What record would resolve the pending assay in this fictional report?”; prepare against the current source, then save | One persistent question anchored to that source version and line; no generated answer |
| Evidence | Refresh question history if needed; choose “Inspect evidence and human comparisons”; select `examples/synthetic/demo-evidence.txt`, confirm it is fictional, and save | An original fictional methods note with its separate permissions and provenance |
| Comparison | Select that evidence; quote `an assay limitation`; choose “Context only” and “Limited”; enter “Fictional methods context only; it cannot resolve the missing assay result.”; save | A human-authored, unreviewed comparison |
| Report | Check “Include this current proposal in a report”; prepare the selected comparison report; choose “Recheck and open report”, then “Recheck permission and download report” | A preserved report with source/evidence references and no clinical approval |
| Follow-up | On the same question, choose “Record follow-up work”; title it “Obtain the fictional final assay report”; enter an owner, a revisit trigger and a reason; record it | A persistent operational task, separate from the report and from unsent drafts |
| Return | Open Overview and inspect the saved-question agenda; use “Inspect records and reports” | The exact question, report and recorded task can be rediscovered through fresh scoped reads |

Overview shows up to three record-preparation prompts for the checked case. Under “Review unresolved source statements”, choose “Inspect source statements” to see the pending assay in Journey. The saved-question agenda links back to the report and follow-up task.

The supplied laboratory file `examples/synthetic/fictional-fhir-r4-lab-bundle.json` can also be deliberately imported in Records for this case. Its patient reference matches the fictional case binding. Original JSON and typed values stay source-reported. Importing does not interpret reference ranges or automatically create questions.
Use the saved-laboratory-question steps below for the subsequent explicit question
workflow; importing a report does not itself create a question.

## Stop, resume and inspect

Stop the frontend with Ctrl+C, then:

```sh
python tools/h1_demo.py stop
```

The database volume and `.local/h1-demo` remain. To resume, run `up --fictional-only`, then `credentials` and `npm --prefix apps/web run preview` again. `up` explicitly renews the local synthetic grant for 12 hours. It reuses the same patient creation request and source; it does not clear the database, overwrite amended originals or recreate missing source history. Keep the state directory with its Docker volume. Do not commit or share the token/state directory.

Saved records, questions, reports and tasks persist. Unsubmitted text stays only in the current browser session and is lost on reload; save deliberately before stopping. Browser reload requires reconnecting the local token and reopening the patient. There is no automatic sign-in, real consent/delegation, recipient authorization or external handoff.

If startup fails, inspect the Docker output and retry the same command/state directory. A missing or malformed state file, changed patient identity or missing original stops setup rather than silently resetting it. The launcher does not offer a destructive reset command.

## Save a question about a laboratory result

In Records, open the source versions for `CASE-DEMO`. Select
[the fictional FHIR bundle](../examples/synthetic/fictional-fhir-r4-lab-bundle.json),
then choose **Preview results without importing**. Check the specimen and the reported
value of `4.20 10*9/L`. The preview sends the original to the case service for a
patient-mapping check. Saving requires a separate confirmation. Confirm the file
and import it as a new report. In Journey, inspect that case and
select `Observation/FICTIONAL-OBS-A`. Write a question, check it against the
report, then explicitly save it. Reopen the saved laboratory questions to see
the original question, report version, file digest and Observation reference.
If the save response is lost, use the offered retry to recover its receipt.

The stored question keeps its original source when a report is amended.
Reopen the history after an amendment to see which questions need reassessment.
Question history requires an active patient/case binding and current source and
question read grants. Text-based investigations use their existing source-line history.

After reopening saved laboratory questions, return to Overview. Laboratory and
text-source counts have separate permission checks. An unchecked laboratory
history remains unavailable instead of showing zero. Use “Reopen laboratory
questions in Journey” to return to the same case and inspect its saved questions.
After a report amendment, reopen the laboratory history to see the preserved
original question counted as needing reassessment. An earlier read is not reused
as a current count.

## Inspect citations for a laboratory question

Reopen saved laboratory questions in Journey and select the question you want
to investigate. Enter a search term for the seeded fictional catalog (for
example, `continuity`). Inspect a result and explicitly attach its citation.
Reopen the citation list to see the exact original Observation and linked
metadata. If the original report has been amended, the list identifies the
earlier question as needing reassessment. Open the result and citation report
to inspect the original measured value or absence reason, specimen, dates and
currently permitted citation metadata together. The catalog supplies independently
authored fictional metadata for this workflow.

## Verification boundary

`apps/web/tools/demo_journey.py` exercises these exact fixtures through a real built browser and a separately owned Docker/PostgreSQL application, then checks repeated setup and persistence after stopping and resuming. It deletes only its own newly created disposable test project. The ordinary launcher never deletes volumes.

The full integration workflow separately exercises wrong-scope and revoked access, text/PDF passages, immutable reports, uncertain saves, images, laboratory sources, keyboard/mobile flows, migration history, and seven backup/recovery stages. Final acceptance belongs to the exact candidate revision and its CI receipts in the PR; this guide alone is not a passing test or a deployment claim.
