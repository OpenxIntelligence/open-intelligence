"""Fail-closed evidence validator for technology research, not legal clearance.

Requires exact source commit + root LICENSE blob to make decisions reproducible.
A pass does NOT establish dependency compatibility, clinical suitability, or a
right to commercial release. The validator makes no network requests.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re

HEX40=re.compile(r"[0-9a-f]{40}\Z")
DECISIONS={"RESEARCH","EVALUATE","HOLD","REJECT"}
REQUIRED={"name","repo","commit_sha","license_path","license_blob_sha",
          "root_license","capability","decision","next_gate",
          "commercial_cleared","transitive_dependencies_reviewed",
          "non_code_assets_cleared","clinical_use_validated","review_status",
          "source_url","reviewed_utc"}


def validate(manifest: dict) -> list[str]:
    problems=[]
    if type(manifest) is not dict or manifest.get("schema_version")!="oi-backend-oss-v1":
        return ["Unknown audit schema"]
    records=manifest.get("entries")
    if not isinstance(records,list) or not records:
        return ["Empty or invalid candidate list"]
    names=set()
    for i,row in enumerate(records,1):
        context=f"entry {i}"
        if not isinstance(row,dict):
            problems.append(context+": not an object")
            continue
        missing=REQUIRED-set(row)
        if missing:
            problems.append(context+": missing fields "+",".join(sorted(missing)))
            continue
        if row["repo"] in names:
            problems.append(context+": duplicated repository")
        names.add(row["repo"])
        for field in ("commit_sha","license_blob_sha"):
            if type(row[field]) is not str or not HEX40.fullmatch(row[field]):
                problems.append(context+": invalid "+field)
        if (type(row["repo"]) is not str or
            not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",row["repo"])):
            problems.append(context+": repository format invalid")
        expected=f'https://github.com/{row["repo"]}/blob/{row["commit_sha"]}/{row["license_path"]}'
        if row["source_url"]!=expected:
            problems.append(context+": license link does not match pinned commit/path")
        if row["decision"] not in DECISIONS:
            problems.append(context+": disallowed decision (no implicit adoption)")
        for field in ("commercial_cleared","transitive_dependencies_reviewed",
                      "non_code_assets_cleared","clinical_use_validated"):
            if type(row[field]) is not bool or row[field]:
                problems.append(context+": clearance requires independent reviewed evidence: "+field)
        if row["review_status"]!="research_only":
            problems.append(context+": only research_only receipts permitted")
        if not isinstance(row["next_gate"],str) or not row["next_gate"].strip():
            problems.append(context+": next verification gate missing")
        if not isinstance(row["root_license"],str) or not row["root_license"].strip():
            problems.append(context+": root license observation missing")
    return problems


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--manifest",default=str(
        Path(__file__).resolve().parents[1]/"docs"/"research"/"backend_oss_evidence_2026-11-02.json"))
    args=parser.parse_args()
    problems=validate(json.loads(Path(args.manifest).read_text(encoding="utf-8")))
    if problems:
        for message in problems:
            print("HOLD:",message)
        return 1
    print("PASS: pinned source-license observations complete; NO dependency adoption or legal clearance.")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
