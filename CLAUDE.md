# gestureio: notes for Claude Code sessions

Two Claude Code sessions work on this repo, one on each machine:
- **PC** ("Safdar", on the right, the main machine, no physical camera). Writes most of
  the code.
- **Laptop** ("SafdarL", on the left, has the webcam). Runs everything that needs the
  camera and reports the results.

**The repo is the only channel between the two sessions.** Follow this every time:
1. Before any work: `git pull --rebase`, then read `docs/SYNC.md` from the top.
2. After changing anything:
   1. Run the tests (`py -3.12 -m uv run pytest`).
   2. Add a new entry at the top of `docs/SYNC.md`.
   3. Commit and `git push` in the same push.
3. Never fix something only locally. If the code is wrong, fix it in the repo and say
   so in `docs/SYNC.md`.
4. To ask the other machine for something, write it in a `docs/SYNC.md` entry. Answer
   requests in a new entry; don't edit old ones.

## Rules

- **No Claude attribution.** No `Co-Authored-By` trailer, `Claude-Session` line or
  "Generated with Claude Code" footer on commits or PRs. The owner asked for this.
- **This repo is public.**
  - Never commit secrets. The PSK and machine config live in `%APPDATA%\gestureio\`.
  - Never commit screenshots or camera images.
  - Landmark recordings (`recordings/*.jsonl`) and bench reports
    (`bench_results/*.json`) are fine to commit.
- **Don't open cameras on the PC.** Its only camera device is a Phone Link virtual
  camera, which may switch on the owner's phone camera.
- **The design is `docs/PLAN.md`.** Its decisions are settled. Propose changes in
  `docs/SYNC.md` instead of quietly diverging.
- **Handedness:** mediapipe 1.0.1 labels mirrored frames with the opposite hand, and
  `tracker.user_hand()` corrects it. Never "fix" left/right with `--invert-handedness`.
- **Commands:** use Python 3.12 via `py -3.12 -m uv ...`. Commands are in `README.md`.
