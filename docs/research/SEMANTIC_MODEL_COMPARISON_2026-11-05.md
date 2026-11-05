# Open Intelligence — synthetic metadata model comparison

Date: 5 November 2026. Status: research only, synthetic data, draft and unmerged. No clinical approval, production dependency or NVIDIA AI-model execution.

## Engineering decision

Both models were evaluated on the same 72 public, author-labeled fictional questions: 36 expected field lookups and 36 cases requiring abstention. The inference container had only the question-only packet and model weights, with Docker network set to none. Field options were fixed to one abstain label plus the existing 22 allowlisted metadata fields. These forced-choice decisions are actual model logits, not freely generated JSON.

| Result | SmolLM2-135M-Instruct | Qwen2.5-0.5B-Instruct |
| --- | ---: | ---: |
| Correct field lookups (36 reference positives) | 0 | 1 |
| Wrong positive field mappings | 0 | 1 |
| Abstentions on positive lookups | 36 | 34 |
| Correct abstentions (36 reference negatives) | 36 | 34 |
| False mappings on unsafe cases | 0 | 2 |
| False specimen/case-join mappings | 0 | 0 |
| Invalid response format | 0 | 0 |
| Real model forward passes | 72 | 72 |
| Aggregate local compute time | 67,486 ms | 176,707 ms |

SmolLM2 selected abstain for every question, so it provided no measured lookup utility. Before this continuation the scorer's experimental stop flags detected only wrong/unsafe/invalid results and did not flag zero recall. A new zero_correct_field_lookups stop reason now rejects this degenerate all-abstain behavior; this is an engineering sanity gate, not an accepted clinical safety or accuracy threshold.

Qwen selected a field four times: one correct, one wrong on expected lookup B-203, and two false mappings on unsafe reference cases B-252 and B-260. Its conservative research stop correctly triggered unsafe_field_mapping and incorrect_positive_field. Neither model is acceptable for clinical integration.

## Reproducible evidence

- SmolLM2-135M-Instruct, Apache-2.0, immutable source revision 12fd25f77366fa6b3b4b768ec3050bf629380bac. Hosted exact-head [run 42059268955](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/42059268955) passed 112/112 tests on b3dd81e9cf98eea2b92175a13d1c2205e9636871. [Artifact 13431165868](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/42059268955/artifacts/13431165868) ZIP SHA-256 630259d72eab940bbdd748b8b11d48067261a24eff3601b91eb0dd36c5bbc3a2, independently downloaded, hash/integrity checked and parsed.
- [Qwen2.5-0.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct), Apache-2.0, immutable source revision 7ae557604adf67be50417f59c2c2f167def9a775. The hosted job verified the revision and model-card license, downloaded pinned safetensors and hashed the files. [Run 42060360362](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/42060360362) passed 112/112 tests on 95aea36626e09c77bab7161019482bfc2d3fa6bf. [Artifact 13430617407](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/42060360362/artifacts/13430617407) ZIP SHA-256 a2f336c787d4799dba7bcf45688579f92b52658dd5aab417c1f2c4fc64635932, independently downloaded, hash/integrity checked and parsed. The current source contains a scorer gate and report beyond that evaluated head and requires its own exact-head CI.
- Both runs used genuine model forward passes but a fixed 23-token output choice and deterministic first-party formatting. Neither used PHI, a patient database, clinical records, source-value retrieval, joins, SQL generation, or external inference APIs. Hosted API model fee was zero; GitHub Actions CPU cost was not established.
- The reference answers are public and authored by the same research workflow; this is NOT independent adjudication or a blinded generalization study. The logits over 23 restricted tokens are NOT calibrated confidence. Prompt/order effects were not independently measured.

## Next gates and prioritized project work

Stop tuning models on this public benchmark. Any new semantic inference comparison must use independently authored, unseen and adjudicated synthetic cases with patient/case binding, specimen/assay identity, event and issue times, amended report precedence, missing versus negative versus unknown results and consent/authority negatives. Predeclare safety and benefit criteria, then measure reviewer corrections, latency and costs with an isolated and licensed model runtime.

Keep NVIDIA Auto Ontology's catalog interoperability research distinct from NVIDIA AI inference: the catalog was verified on empty synthetic PostgreSQL, but real NVIDIA semantic-model benefit, terms/weights rights, clinical authorization and security were NOT validated. NVIDIA remains Evaluate, not Adopt. The small Qwen and SmolLM reference models are not product dependencies.

Return development priority to the canonical Open Intelligence journey: records from multiple sources into versioned provenance; question, literature/evidence and investigation; reviewable report; amended record follow-up; patient control and human clinical authority. These research results do not grant a new source, model or review owner.
