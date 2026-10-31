# Synthetic evidence contract — research-only

Status: engineering experiment, not patient/clinical use. Primary implementation: PR #4. No third-party scientific text is included.

## Invariant

An evidence source has an immutable byte-level version, hash, authored source line, receipt date, issued date, and declared rights. A human-authored assessment links a particular source version to a particular case **and** investigation question, with relationship (`supports`, `contradicts`, `context`, `unknown`), applicability (`applicable`, `limited`, `not_applicable`, `unknown`), and a rationale.

Source versions and assessments are not clinical truths or independently validated studies. They are synthetic engineering test objects. Original data is not overwritten on amendment, and the previous assessment remains historical. Adding an amended version or withdrawing the current version marks only dependent snapshots stale and reopens their questions, across every affected synthetic case.

Only the original `OI-SYNTHETIC-EVIDENCE/1` format with `Rights: original-synthetic` is accepted. That field is an unverified declaration: it cannot establish the author's rights to arbitrarily pasted material. Do not paste real studies, patients, restricted text, or copyrighted excerpts. Actual publication ingestion is blocked until separate rights provenance and scientific appraisal are implemented.

## Reviewer checklist

- [ ] Evidence versions are immutable and resolve to exact original bytes and SHA-256.
- [ ] Explicit amendments and withdrawals preserve history and reasons; dependent snapshots are stale.
- [ ] Another case's assessment cannot be reused by a case-specific question.
- [ ] Stale evidence assessments cannot be attached to new drafts.
- [ ] Human-entered `supports` or `applicable` never turns a draft into a clinical conclusion.
- [ ] Real study citations, licenses, abstract/full-text retrieval, and patient-specific applicability are **not** claimed.
- [ ] Browser journey, accessibility, usability, data security, and release-rights review require separate evidence.

## Later production research boundary

A future ingestion service must verify rights for code/data/model/services separately, retain publisher provenance and version, represent permitted use, preserve citations and claim-level text where authorized, detect retractions/corrections, and forbid sending patient identifiers to open public-research tools. It must not infer treatment efficacy from citation metadata.