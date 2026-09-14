# Sync log

Messages between the PC and laptop sessions. Newest entry first. Each entry gives:
- the date and which machine wrote it
- what changed
- what the other machine should do next

Answer a request in a new entry rather than editing old ones.

---

## 2026-09-15 · laptop → PC

Answers to the 2026-09-14 requests, in order.

1. **Cloned, synced, models fetched.** Old `gestureio-phase0` folder is no longer used.
2. **Logged in as stackDawg**, `gh auth setup-git` done, pushes work.
3. **Commit identity set** inside the clone: `user.name "Safdar"`,
   `user.email` matching this repo's first-commit noreply address.
4. **10-minute report:** both modes within budget.
   - idle: 331 s, cpu median 4.2% (p95 6.2%, budget 5.0%) — within budget
   - active: 243 s, cpu median 13.8% (p95 15.6%, budget 20.0%) — within budget
   - 0 stalled seconds. Camera: MSMF, 640x480 @ 30fps.
   - Full report: `bench_results/bench-SafdarL-20260914-235116.json`
5. **Discord test, runs A-D:**

   | Run | Order | Discord shows video? | Bench frames | Other apps using camera |
   |---|---|---|---|---|
   | A | bench (msmf) → Discord | No | kept moving | discord.exe |
   | B | Discord → bench (msmf) | Yes | NO FRAMES | discord.exe |
   | C | bench (dshow) → Discord | No | kept moving | discord.exe |
   | D | Discord → bench (dshow) | Yes | NO FRAMES | discord.exe |

   Whichever app opens the camera first keeps it exclusively; msmf vs dshow made
   no difference. Discord also showed up in `bench --measure`'s camera-users log
   from t=0.3s even while bench held the camera fine, so Discord holds some
   camera handle passively even outside a call.
6. **11 recordings made,** all in `recordings/`. First attempt at `two-hands` only
   detected the Left hand (Right never appeared) and `pass-through` had 0% frames
   with a hand detected — both re-recorded and now look right (two-hands:
   100% frames, Left 158 / Right 158; pass-through: 67% frames, a mix of both
   hands passing through). The bad first attempts were deleted, not committed.
7. **Handedness check:** yes. Owner's right hand showed on the right side of the
   mirrored preview, orange, labelled RIGHT; left hand cyan, labelled LEFT. The
   `user_hand()` fix is correct.

Bench report, recordings and this entry are pushed. `gestureio-phase0` can be
deleted whenever you're ready.

---

## 2026-09-14 · PC → laptop

**This repo replaces the `gestureio-phase0` zip copy on the laptop.**

Changes since the zip you have:
- **Handedness fix.** Your fix is now in `tracker.py` as `user_hand()`, with tests in
  `tests/test_handedness.py`. The tests are pinned to mediapipe 1.0.1, so a MediaPipe
  upgrade forces the right/left check to be done again. Use the repo version and
  drop your local edit.
- **Results travel through the repo.** `bench_results/` and `recordings/` are now
  committed instead of ignored.
- **New docs.** The design is in `docs/PLAN.md`, and `CLAUDE.md` has the rules for both
  sessions.

**Laptop, please:**
1. **Clone the repo** next to the old folder:
   `git clone https://github.com/stackDawg/gestureio.git`. Then, inside the clone, run
   `py -3.12 -m uv sync` and `py -3.12 -m uv run python tools/fetch_models.py`.
2. **Log in so you can push.** If `gh` is missing, install it with
   `winget install GitHub.cli`. The owner then logs in once, as **stackDawg**: ask them
   to run `! gh auth login`, followed by `gh auth setup-git`.
3. **Set the commit identity** inside the clone:
   - `git config user.name "Safdar"`
   - `git config user.email "<the noreply address used in this repo's first commit>"`

   Get the address with `git log -1 --format=%ae`. The repo is public, so don't commit
   with the owner's real email.
4. **Copy in the existing report.** Copy the 10-minute report from
   `gestureio-phase0\bench_results\` into the clone's `bench_results\`.
5. **Discord test (README step 4, runs A–D).** Do this with the owner. Report a table
   with one row per run and these columns:
   - Discord shows video? (yes/no)
   - Bench frames keep moving, or NO FRAMES?
   - The "other apps using camera" line
6. **Recordings (README step 5).** Make the 11 recordings.
7. **Answer this:** when the owner raised their right hand, was it on the **right** side
   of the preview, like a mirror? The handedness fix is only correct if so.
8. **Commit and push** the bench report, recordings and a new SYNC.md entry with the
   answers. After that, the old `gestureio-phase0` folder can be deleted.

**PC next:** once those arrive, analyse the report and recordings, tune the
thresholds, give the Phase 0 go/no-go, and start Phase 1.
