# Frontend contrast measurements

Stylesheet SHA-256: `2f50b7c13589525ec261875a3b35a4b0c8b1c0fe797f202b19d1fe5b501b9d86`.

Calculated from the actual stylesheet; thresholds were compared without rounding. All 25 sampled normal-text pairs exceed 4.5:1. All 9 sampled control/focus/outer-state pairs meet 3:1. These measurements do not establish WCAG 2.2 compliance.

| Pair | Foreground / background | Ratio | Compared threshold | Result |
|---|---|---|---|---|
| Default text / page canvas | `#172e35` / `#f5f6f3` | 13.09:1 | 4.5:1 | Meets |
| Muted text / page canvas | `#52665e` / `#f5f6f3` | 5.66:1 | 4.5:1 | Meets |
| Default text / white surface | `#172e35` / `#ffffff` | 14.20:1 | 4.5:1 | Meets |
| Muted text / white surface | `#52665e` / `#ffffff` | 6.14:1 | 4.5:1 | Meets |
| Primary button text | `#ffffff` / `#174b48` | 9.83:1 | 4.5:1 | Meets |
| Primary button hover text | `#ffffff` / `#20635d` | 6.99:1 | 4.5:1 | Meets |
| Standard button / white | `#174b48` / `#ffffff` | 9.83:1 | 4.5:1 | Meets |
| Standard button hover / soft | `#174b48` / `#edf3ef` | 8.74:1 | 4.5:1 | Meets |
| Rail body text | `#f6faf7` / `#143631` | 12.45:1 | 4.5:1 | Meets |
| Rail navigation text | `#e5efea` / `#143631` | 11.15:1 | 4.5:1 | Meets |
| Rail active navigation text | `#ffffff` / `#31564b` | 8.19:1 | 4.5:1 | Meets |
| Rail navigation hints | `#d1e2d8` / `#143631` | 9.73:1 | 4.5:1 | Meets |
| Rail hints on active navigation | `#d1e2d8` / `#31564b` | 6.08:1 | 4.5:1 | Meets |
| Reading view label | `#d1e4d7` / `#143631` | 9.86:1 | 4.5:1 | Meets |
| Reading view helper text | `#ccded4` / `#143631` | 9.34:1 | 4.5:1 | Meets |
| Reading view select text | `#ffffff` / `#21483f` | 10.18:1 | 4.5:1 | Meets |
| Current / read-only badge text | `#335d45` / `#eff5f0` | 6.80:1 | 4.5:1 | Meets |
| Historical badge text | `#655436` / `#f2efe8` | 6.36:1 | 4.5:1 | Meets |
| Clinical review not established | `#6f5830` / `#ffffff` | 6.74:1 | 4.5:1 | Meets |
| Development label | `#6a552c` / `#f0eadc` | 5.94:1 | 4.5:1 | Meets |
| API ready text | `#28533d` / `#fafbf8` | 8.44:1 | 4.5:1 | Meets |
| API unavailable text | `#79552c` / `#fafbf8` | 6.42:1 | 4.5:1 | Meets |
| Input placeholder | `#5c6d64` / `#ffffff` | 5.49:1 | 4.5:1 | Meets |
| Error status text | `#773b2c` / `#f8ede7` | 7.46:1 | 4.5:1 | Meets |
| Quoted source text | `#172e35` / `#f4f7f3` | 13.15:1 | 4.5:1 | Meets |
| Input border / white | `#7c9185` / `#ffffff` | 3.36:1 | 3.0:1 | Meets |
| Input border / canvas | `#7c9185` / `#f5f6f3` | 3.10:1 | 3.0:1 | Meets |
| Input border / creation panel | `#7c9185` / `#f9faf7` | 3.21:1 | 3.0:1 | Meets |
| Reading view select border / fill | `#769489` / `#21483f` | 3.09:1 | 3.0:1 | Meets |
| Reading view select border / rail | `#769489` / `#143631` | 3.98:1 | 3.0:1 | Meets |
| Focus outline / canvas | `#97621e` / `#f5f6f3` | 4.74:1 | 3.0:1 | Meets |
| Focus outline / white | `#97621e` / `#ffffff` | 5.14:1 | 3.0:1 | Meets |
| Rail focus outline / rail | `#e2c58a` / `#143631` | 7.86:1 | 3.0:1 | Meets |
| Active navigation border / selected fill | `#749586` / `#31564b` | 2.49:1 | Context only | Not classified |
| Active navigation border / outer rail | `#749586` / `#143631` | 3.99:1 | 3.0:1 | Meets |
| Decorative separator / canvas | `#d3ddd6` / `#f5f6f3` | 1.28:1 | Context only | Not classified |

## Interpretation and limits

The active navigation outline measures 2.49:1 against its selected interior fill and 3.99:1 against the adjacent outer rail. The visible outer boundary supplies the stronger contrast. This report flags both values for contextual review rather than declaring the complete selected-state presentation compliant or noncompliant from one pair.

The decorative separator is not the visual boundary used to identify an input. Inputs use the separate darker `--control-line` token, which measures 3.36:1 against white and 3.10:1 against the canvas. Disabled controls have opacity and are outside this static enabled-control measurement.

Text-size and color checks are only one part of accessibility. This review did not run a screen reader, test every focus target or zoom combination, evaluate forced colors, or inspect all possible dynamic states. It does not measure clinical comprehension or real-user task efficiency.

## Final screenshot review

Inspected the eight final images indexed in `../screenshots/README.md`. They show the final passing actual-API browser run, including patient and clinical reading views, persistent patient context during source reading, and narrow-screen handling of unusually long fictional identifiers. No additional serious visual issue was identified from these images.

The 390px source-reading capture now places the source heading and filter below the sticky patient header. The 320px long-source stress capture intentionally shows a scrolled state; part of the long case eyebrow lies above the visible content edge, while the source heading, filter, document identity and persistent patient identity remain visible. It demonstrates wrapping, not the entire source in one viewport. Screenshot evidence does not replace the separate browser focus, reflow, scope and permission checks.

## Primary references

- W3C, [Understanding SC 1.4.3 Contrast (Minimum)](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html): normal text 4.5:1; large text 3:1; specified inactive/decorative exceptions.
- W3C, [Understanding SC 1.4.11 Non-text Contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html): relevant component/state cues 3:1 against adjacent colors. A boundary is not required for every text-labelled control; context matters.
