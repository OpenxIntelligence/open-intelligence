# OI-17 — Release rights declaration gate (supplement, proposed)

**Status:** Engineering draft; does not supersede OI-17 or authorize adoption.

OI-17 is authoritative: https://app.notion.com/p/40a3866f77ef815a97d5e016ededf5b9

## What this code checks

The zero-third-party-dependency tool `tools/oss_release_gate.py` reads the *adopted* dependency manifest `docs/OSS_RELEASE_MANIFEST.json`, rejects components without an exact full source commit, Tier-1 SPDX ID, all recorded G1–G10-related rights/security/notices receipts and human authorization evidence, and rejects the founder-excluded Next.js package even though its upstream MIT license is permissive. Receipt files must be nonempty and remain within the repository. Negative tests prove fail-closed behavior on missing receipts, AGPL, revision drift and duplicate records.

**This checks evidence declarations, not truth.** The empty adopted manifest currently passes because this original Python/SQLite synthetic example does not intentionally vendor third-party runtime packages; the gate **does not verify installed dependencies** and cannot certify legal rights. It must be complemented with a generated and reconciled SBOM, source/asset/license inspection, human sign-off and a reproducible build. Candidate evaluations remain in the pre-existing Notion licensing register, not this release manifest.

## Release adoption workflow

1. Select a specific use and exact release plus source SHA. Verify upstream license text at that commit.
2. Resolve the actual production build and all optional/transitive packages; generate SPDX or CycloneDX SBOM with a real tool.
3. Check source modification/distribution/patents/notice, trademarks, data/terminology/model weights, security and maintenance evidence.
4. Store actual review receipts and the SBOM in reviewed repository paths; add the adopted record only after human decision.
5. Run `python3 -m unittest discover -s tests -p test_oss_release_gate.py -v` and `python3 tools/oss_release_gate.py`; confirm the release manifest matches the build.
6. Retain legal/security review authority outside this validator.

This implementation must not be portrayed as 'zero legal risk', broad candidate approval, a complete OSS inventory, or an architectural mandate to select a stack.

Tracking: https://github.com/OpenxIntelligence/open-intelligence/issues/59
