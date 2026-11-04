# Actual-platform hackathon recording

This isolated production branch records the existing React/FastAPI/PostgreSQL synthetic browser acceptance journey from application baseline `02f920c40959d26937df0f737e17e5392d041d26`. It does not change application source, bypass patient grants, introduce model execution, or merge/deploy anything.

Backlog mapping: OI-006 source evidence and the existing H1 acceptance/demo work. Acceptance: the inherited browser journey completes, an MP4 contains actual rendered browser frames, no credential entry is recorded, and capture metadata links frames and screenshot checkpoints to the exact revision.

Capture uses the repository's existing standard-library CDP client, Python standard library, Chrome already installed on the GitHub runner, and the runner's Ubuntu `ffmpeg` package solely as a production utility. The workflow records the installed FFmpeg version/configuration; its upstream license and linked-library scope are reported by that binary. No FFmpeg binary is vendored or distributed, and no new application runtime dependency is introduced.

Outputs: raw 1920×1080 H.264 MP4 at 8 sampled frames per second, screenshot-checkpoint timeline/hashes, and inherited browser evidence. Capture sampling and pauses are editorial; footage does not establish response-time performance. Model execution and bioinformatics analysis are not claimed. Only independently authored fictional data is used.

The final edited video can combine these actual clips with explicitly labeled research-roadmap cards and an openly synthetic voice. This branch is for capture/reproduction, not a production or clinical release.

The capture now wraps the existing persistent demo, after running the inherited full browser acceptance unchanged. It retains the candidate's `prepare_dependencies.py` step and exact derived-wheel hash gate. No dependency hashes were changed. The first capture attempt used the older download-only setup and failed before app startup; that attempt produced no footage.
