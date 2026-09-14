# Sync log

Messages between the PC and laptop sessions. Newest entry first. Each entry gives:
- the date and which machine wrote it
- what changed
- what the other machine should do next

Answer a request in a new entry rather than editing old ones.

---

## 2026-09-15 · PC → laptop (Phase 0 verdict)

**Phase 0: go.** Here's what the data settled.

- **Recognition.** Counts 1–4, palm, fist and pinch all read correctly in at least
  99% of frames of their recordings. Pinch on/off is clean: 11 taps gave exactly 11
  presses, with no flicker. The `left-count2` redo reads 100% count2 and is now in the
  regression tests.
- **Speed.** With `num_hands=1`: 28.6 fps and 22 ms per frame. Phase 1 will track one
  hand by default. While a hand is visible, it checks for a second hand a few times a
  second, and switches to two-hand tracking when one appears. Without this, a hand
  resting in view would block the other hand from being tracked.
- **GPU.** Not in this MediaPipe build, so CPU only, as planned.
- **Camera.** Keep the Windows "several apps at once" setting **on**.
  - Auto-pause during calls stays the policy, and your microphone check confirms it
    works.
  - Gestures stop during calls, so they never compete with Discord's video for CPU.
    In run A', inference fell to 11 fps while Discord was streaming.
- **Volume dial.** Your turn recording shows the motion is a roughly 90° roll from
  palm-facing to edge-on, with a release between turns. That's the ratchet, as
  designed.
  - The flat knuckle angle flips near edge-on. Phase 2 will measure the 3D roll
    around the wrist-to-middle-knuckle axis instead, which read a clean −85° to −95°
    edge-on.
  - Also for Phase 2: pinch release needs debouncing, because a single-frame spike
    dropped a pinch mid-turn. And the "index not folded" check blocks re-pinching
    while edge-on, so it should only apply when a pinch starts.
- **Flicks: inconclusive.** At about 11 fps, only one up/down pair crossed 0.6
  frame-widths/s at the pinch point, and none of the left/right flicks did. They need
  re-recording at the real frame rate.

**Laptop, please.** None of this blocks Phase 1.
1. Pull. `pytest` should be all green (58 tests).
2. Quit Discord **fully**, from the tray. Then run
   `py -3.12 -m uv run python tools/bench.py --measure 300 --num-hands 1`. Keep your
   hands out of view for about 2.5 minutes, then gesture for about 2.5 minutes. This is
   the baseline with sharing on. I need to know what resolution the camera gives when
   Discord isn't using it, and what idle CPU is: at 1280×720, idle was 6–9%, over the 5%
   budget.
3. Re-record these two, with Discord closed, adding `--num-hands 1` to `record.py`.
   Delete the old versions with `git rm`.
   - **`right-pinch-flick`:** pinch, one quick wrist flick, release. Do left, right, up
     and down, twice each, pausing about 1 s between flicks.
   - **`right-pinch-turn`:** pinch palm-facing, turn to edge-on, release, return. Do
     three turns one way, then three the other way.
4. Push the results with a new entry here.

**PC next:** Phase 1. That's the coordinator, the arbiter, the agent on both machines,
and the finger-count launcher working end to end.

---

## 2026-09-15 · laptop → PC (2)

Answers to both 2026-09-15 requests, in order.

1. **Pulled, pytest green:** 57 passed.
2. **Camera setting:** the built-in camera did have a "let several apps use this
   camera at once" toggle, off by default. Turned it on and repeated runs A and B
   (msmf):
   - **A':** bench first, then Discord. Both showed video, bench kept moving,
     other apps using camera: `discord.exe`.
   - **B':** Discord first, then bench. Same result — both worked, other apps
     using camera: `discord.exe`.

   So the OS-level setting fixes exclusivity entirely; order no longer matters.
   One side effect: the camera negotiated 1280x720 instead of 640x480 once
   sharing was on (still downscaled to `--process-width` before inference).
3. **Throughput runs**, 90 s each:

   | Run | Config | Active cpu median (p95) | Inference fps | Hand model p50 / p95 |
   |---|---|---|---|---|
   | a | num_hands=2, 1 real hand | 16.2% (19.9%) | 17.1 | 51.7 / 75.8 ms |
   | b | **num_hands=1**, 1 real hand | 12.7% (14.8%) | 28.6 | 22.1 / 24.8 ms |
   | c | delegate=gpu | failed to start (see error below) | | |
   | d | num_hands=2, 2 real hands | 16.5% (18.6%) | 19.8 | 47.2 / 53.1 ms |

   Confirms your throughput guess: runs a and d are nearly identical even though
   d has twice the real hands, because `num_hands=2` always pays the
   second-hand-search cost. `num_hands=1` almost doubles fps and halves hand
   model latency.

   Run c error:
   ```
   error: ValidatedGraphConfig Initialization failed.
   ImageCloneCalculator: GPU processing is disabled in build flags
   ```
   GPU delegate isn't available in this MediaPipe build on Windows.
4. **Microphone signal**, plus the auto-pause decision's extra checks:
   - Outside a call (Discord open, not in a call): `mic []`, `cam []`.
   - During a call (video off): `mic [...Discord.exe]`, `cam []`.
   - Within ~5 s of leaving the call: `mic []`, `cam []` again.
   - No other app (browser or otherwise) showed up in `mic` at any point.

   So the mic signal cleanly distinguishes "Discord open" from "Discord in a
   call," and clears quickly after the call ends. Looks solid for the auto-pause
   design.
5. **Recordings:**
   - `left-count2` re-recorded (old one `git rm`'d). First attempt at the redo
     also came out wrong — it read mostly as **Right** (112 frames) with only
     48 as Left, meaning the other hand ended up in frame too. Redone a second
     time with only the left hand in view: 100% frames, all Left.
   - `right-pinch-taps`, `right-pinch-turn`, `right-pinch-flick` recorded:
     89%, 75%, and 100% frames with a hand respectively, all Right. The lower
     rate on `-turn` is likely motion blur/self-occlusion while rotating.

All 5 new bench reports, the corrected recordings, and this entry are pushed.

---

## 2026-09-15 · PC → laptop (decision)

**The owner chose auto-pause during calls.** While another app has the microphone
open, gestureio releases the camera so Discord video can take it. It takes the camera
back when the call ends.

That makes **item 4 below (microphone signal) the one this design depends on**.
Please extend it:
- **Outside a call:** with Discord open but not in a call, `mic` must **not** list
  Discord. Check this with your usual voice setting (voice activity or push-to-talk).
- **In a call:** during a Discord voice call, `mic` **must** list Discord.
- **After the call:** run the command again within about 5 s of leaving the call.
  Discord should be gone from the list.
- **Other apps:** note anything else that shows up in `mic`, such as a browser tab.

---

## 2026-09-15 · PC → laptop

Thanks, everything arrived. Here's what the data shows.

**Fine:**
- **CPU** is within budget: idle 4.2%, active 13.8%.
- **The camera** delivers a steady 30 fps.
- **Counts 1–4, palm and fist** read correctly in 99–100% of frames, with wide
  margins.
- **Handedness** is confirmed.

**Found and fixed (in this push):**
- **Pinch was broken.** The held-pinch recording read as pinch in only 17% of frames,
  because world-landmark depth is too noisy: a steady pinch measured anywhere from
  0.21 to 0.72. Pinch now uses the image-plane distance, which holds at 0.17–0.24.
  Because a fist also brings the thumb and index tips together, a pinch additionally
  needs the index finger not folded (fist 0.46–0.50, pinch 0.73–0.84). The recording
  now reads 100% pinch.
- **Thumb threshold.** The folded-thumb threshold (`thumb_in`) moved from 0.60 to 0.65,
  sitting between real counts (≤ 0.57) and palms (≥ 0.75).
- **The "passive Discord handle" is a stale registry entry,** left by the *old* Discord
  version folder `app-1.0.9255`. The version in use, `app-1.0.9257`, appeared and
  disappeared correctly during your runs. The camera guard now ignores entries whose
  app isn't running.
- **Stillness gate.** Simulating the engage and launcher holds on your recordings:
  without a stillness gate, `pass-through` would have armed the system twice. With the
  hand-speed limit at 0.25 frame-widths per second: zero false fires, and every static
  pose still fires once. Phase 1 will use that value.
- **Regression tests.** `tests/test_recordings.py` now runs the real recordings on every
  test run.

**Still open:**
- **Throughput.** Active inference ran at 19.5 fps, not 30. The hand model takes 49.5 ms
  per frame with a hand in view and 25.7 ms on empty frames. My guess: with
  `num_hands=2`, MediaPipe keeps searching for a second hand on every frame. See
  test 3.
- **Camera sharing.** It's exclusive, so gestures and Discord video can't share the
  camera. How to hand it over is a decision for the owner, which I'm asking them
  about directly.
- **`left-count2`** reads as **count1** in 100% of frames: the middle finger is folded
  throughout. Either the pose was one finger, or MediaPipe misreads it.

**Laptop, please:**
1. **Pull**, then run `py -3.12 -m uv run pytest`. It should be all green.
2. **Windows camera setting.** Open **Settings → Bluetooth & devices → Cameras →** the
   built-in camera. Is there an option to let several apps use the camera at once? If
   there is, turn it on and repeat Discord runs A and B (msmf). Report what you saw.
3. **Throughput runs**, 90 s each. For runs a–c keep **one** hand in view the whole
   time. For run d keep **both** hands in view.
   - a. `py -3.12 -m uv run python tools/bench.py --measure 90`
   - b. `... --measure 90 --num-hands 1`
   - c. `... --measure 90 --delegate gpu`. It may fail on Windows; if so, report the
     error text.
   - d. `... --measure 90` (both hands)
4. **Microphone signal.** With Discord open but **not** in a call, run:
   `py -3.12 -m uv run python -c "from gestureio.coordinator.camera_guard import microphone_users, webcam_users; print('mic', microphone_users()); print('cam', webcam_users())"`
   Then run it again **during** a Discord voice call with video off. Report both
   outputs.
5. **Recordings:**
   - `left-count2`, with index and middle up and the thumb tucked. Also `git rm` the
     old `left-count2` recording.
   - `right-pinch-taps`: pinch and release about once a second.
   - `right-pinch-turn`: hold a pinch and turn the hand like a volume knob, both ways,
     several times.
   - `right-pinch-flick`: pinch, flick the wrist left, right, up or down, then release.
     Repeat.
6. **Push** the reports, recordings and a new entry here with answers to 2–4.

**PC next:** the Phase 0 verdict, then Phase 1 (the launcher, end to end).

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
