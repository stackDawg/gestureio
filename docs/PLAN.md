# gestureio: cross-machine hand gesture control, plan

## Context

You want to control two Windows machines on one desk with hand gestures seen by the
laptop webcam. The goal is a daily-driver tool that stays on all day, not a demo. This
document holds the plan and the design decisions. It was approved on 2026-09-14.
Progress and messages between the two machines are in `docs/SYNC.md`.

## 1. Your answers, turned into decisions

| # | Topic | Decision |
|---|---|---|
| Env | Machines | **PC "Safdar"**: Win 11 Pro 25H2 (26200), Ryzen 5 5600GT, RTX 3050, Ethernet, 1 monitor at 100%, **main machine, on the right**. **Laptop "SafdarL"**: Win 11 Home 24H2 (26100), Ryzen 7 3750H (4C/8T), GTX 1660 Ti Max-Q, 16 GB, Wi-Fi, usually on mains power, 100% scaling, **on the left**, built-in webcam in the lid (you can tilt it). |
| 6 | Network | Private profile, no isolation, the only other device is your phone. The link still gets authentication (see §6), but it's lightweight. |
| 7 | Mouse Without Borders | **Keep it running.** It doesn't conflict. Its injected input also makes "which machine am I using" detection work (see Targeting). |
| 8 | Privilege | The agent runs **non-elevated**. If you gesture at an elevated window, you get a toast saying it can't be touched. |
| 9 | Targeting | **Handedness is the global targeting rule: right hand = PC, left hand = laptop.** It applies to every one-hand gesture. Two-hand gestures target the **active machine**, meaning the one with the most recent keyboard or mouse input (each agent reports `GetLastInputInfo`). If that's unknown, they fall back to the PC. |
| 10 | Feedback location | Gesture overlays render on the **target machine's screen**. The status indicator shows on both. |
| 11 | Cursor | There is no hand-driven cursor. "Window under the cursor" becomes **the foreground window** (config option: `under_mouse`). |
| 12 | Dominant hand | Right. The right hand therefore gets the richest vocabulary. |
| 13 | Apps | WhatsApp is on the PC only. The laptop's slot 2 defaults to opening `https://web.whatsapp.com` in Chrome (config-editable). Discord, Chrome and VS Code are on both machines. |
| 14 | Feature 10 | **Neither lock nor full away mode.** Instead there's a **privacy curtain**: an opaque overlay on both screens while you're away, removed instantly when you come back. It doesn't mute or pause by default (config toggles exist). A "Lock" radial slice (Win+L) is there when you want real security. |
| 15 | Boss key | Two-way. The same gesture restores exactly what it hid. |
| 16 | Media | YouTube in Chrome, driven by media keys through the Windows media session. |
| 17 | Tab handoff | **(a) An unpacked extension.** Both machines use the same signed-in Chrome profile. |
| 18 | File throw | Files up to **15 MB** typical. The hard cap is 50 MB (config). Name clashes get a suffix, like `name (1).ext`. |
| 19 | Flick direction | **Physical: you flick toward the other machine.** The laptop is on the left, so the right hand (PC) flicks **left** to send, and the left hand (laptop) flicks **right** to send. |
| 20 | Camera | Always on is fine. **You make frequent Discord video calls with this camera, so this is a top-3 risk** (see §8). |
| 21–23 | Preview, kill switch, startup | A minimal indicator, with the preview on a hotkey. **Ctrl+Alt+Shift+G** on either keyboard disables everything. Manual start until Phase 4, then autostart. |
| 24–25 | Cut order, time | Not answered. **Assumed cut order: 7 → 8 → 9 → the two-hand parts of 6.** Phases are sized in evenings, not calendar dates. |

## 2. Feasibility verdicts (blunt)

| # | Feature | Verdict | Why |
|---|---|---|---|
| 1 | Finger-count launcher | **Works, with caveats** | (a) Windows *foreground lock* stops a background process from simply calling `SetForegroundWindow`. The standard fix is a synthetic Alt key tap before focusing, which is well understood. (b) Telling "4 fingers" from "open palm" depends on the thumb state, which is the weakest part of pose classification, so it gets a strict thumb-folded test and a hold time. (c) Discord minimised to the tray has no window, so the fix is to re-run its launcher, which surfaces the running instance. (d) WhatsApp is a Store app, so it launches by AUMID (Store app ID) through `shell:AppsFolder`. |
| 2 | Radial menu | **Works as specified** | A Qt overlay with `WS_EX_NOACTIVATE`/`WS_EX_TRANSPARENT` never steals focus. It **won't appear over exclusive-fullscreen games** (borderless fullscreen, including YouTube fullscreen, is fine). **No second ring**: handedness already picks the machine. A ring would add a second aiming step to every use just to re-select something you already chose by picking a hand. Individual slices can pin a target (`pc`/`laptop`/`both`). |
| 3 | Volume dial | **Needs a redesign (small)** | **The spec's angle source is broken.** While you pinch, thumb-tip and index-tip *touch*, so that vector is near zero length and its angle is noise. Use the **knuckle line instead (index MCP → pinky MCP, landmarks 5→17)**, which is stable during a pinch. Also, the wrist only turns about ±70° comfortably, so the dial **ratchets**: release, re-pinch, turn again, like a real knob. Relative accumulation, wraparound handling and the deadzone stay as you specified. |
| 4 | Instant mute | **Works, with caveat** | The push is detected as fast growth of the bounding box while all 5 fingers are extended. It is a **hard mute on both machines, not a blind toggle.** If both are muted, the push unmutes both. Otherwise it mutes both. Commands are absolute (`set_mute true/false`), so a dropped or repeated message can never invert the state. Unmute: push again, or use the radial slice. |
| 5 | Media swipe | **Works, with caveat** | The collision with flicks is resolved by pinch state: **swipes are open-hand, flicks are pinched**. YouTube responds to next and previous only in playlists and autoplay. On a single video, "previous" restarts it, which is YouTube's behaviour. The target machine follows handedness. |
| 6 | Window management | **Works, with caveat** | Uses `SetWindowPos` into the monitor work area, correcting for invisible borders with `DWMWA_EXTENDED_FRAME_BOUNDS`, plus `ShowWindow` for maximise, restore and minimise. **A non-elevated process cannot move elevated windows (UIPI blocks it).** That case is detected and shown as a toast. Some fixed-size or UWP windows resist resizing. |
| 7 | Screenshot framing | **Works with a redesign** | The concrete approach is a **closed loop with a live preview** (see §4.3). A calibrated "interaction box" in camera space maps proportionally onto the target screen. The rectangle is drawn live on screen, so your eyes correct any mapping error, and it freezes after you hold still. Capturing with the overlay on top is avoided with `WDA_EXCLUDEFROMCAPTURE`. Holding both arms up is **tiring**, but acceptable for a rare action. |
| 8 | Tab handoff | **Works, with caveat** | This uses an unpacked MV3 extension plus a native-messaging host, set up once per machine. Developer mode must stay on. **CDP is ruled out:** since Chrome 136, `--remote-debugging-port` is ignored on the default profile, and you use your signed-in profile. **UI Automation is ruled out as too fragile:** address-bar layouts change between Chrome releases. |
| 9 | File throw | **Works, with caveat** | Reading the selection uses Shell COM (`Shell.Application.Windows()` → `Document.SelectedItems()`). **Windows 11 Explorer tabs share one window handle (HWND)**, so the active tab has to be picked out, with a refuse-if-ambiguous fallback. Files selected on the **desktop are not supported in v1**. |
| 10 | Presence | **Redesigned to your answer** | A privacy curtain, not a lock, and not security. If you sit still but look away, keyboard or mouse input on either machine counts as presence, and absence needs about 90 s of continuous "nothing". Face detection is a separate pipeline at 2 fps. |
| 11 | Boss key | **Works** | Two fists held for 300 ms. It can't half-execute because each agent does the whole bundle in one handler: record the windows, minimise them, record the mute state, mute. It acknowledges the whole bundle, and any failure shows red. Doing it again restores exactly the recorded windows and the previous mute state. |

## 3. Architecture

**Topology: a star with the coordinator as the hub.** Three processes, all Python 3.12:

```
LAPTOP (SafdarL)                                       PC (Safdar)
┌──────────────────────── coordinator ─────────────┐   ┌──────── agent ────────┐
│ T1 capture ─► latest-frame slot (drop stale)     │   │ asyncio WS server     │
│ T2 inference: mirror once → HandLandmarker(VIDEO)│   │ action registry       │
│    every Nth frame → FaceDetector (2 fps)        │   │ Qt UI thread: overlay,│
│    → features → ARBITER → intents                │   │  indicator, toasts,   │
│ T3 asyncio: links to both agents, routing,       │WS │  curtain, radial      │
│    transfers relay, presence, camera guard       │◄─►│ hotkey thread (kill)  │
│ T4 (optional) preview window (hotkey)            │LAN│ nmhost ◄─ Chrome ext  │
└──────────────┬───────────────────────────────────┘   └───────────────────────┘
               │ loopback WS (same protocol)
        ┌──────▼──────── agent (laptop) ─┐
        │ identical agent code           │
        └────────────────────────────────┘
```

- **The same agent code runs on both machines.** The coordinator reaches the laptop's
  agent over loopback with the same protocol. So every action is just "send to agent
  X", and the laptop agent draws the laptop's own overlays. The coordinator has no UI
  except the debug preview.
- **Frame flow:** camera (MSMF, 640×480 at 30 fps, buffer of 1) → capture thread
  overwrites a single slot → the inference thread takes the newest frame →
  **`cv2.flip` exactly once, and nothing downstream ever flips again** → MediaPipe →
  landmark features (smoothed with a One Euro filter) → the arbiter → *intents* such as
  `launch(slot=3, hand=R)` → the router resolves the target → the link thread sends →
  the agent executes and acknowledges → the coordinator tells the target agent to show
  confirmation.
- **The agent resolves context.** The coordinator sends *semantic* intents (for
  example `flick(dir=toward_other)`). The agent knows its own foreground window and
  decides whether that means a file throw, a tab handoff or a window snap. So the
  context check never crosses the network.
- **Adaptive frame rate:** at 8 fps when no hand has been seen for 2 s, and 30 fps once
  a hand appears. Face detection runs at 2 fps regardless.
- **Camera guard:** every 2 s it polls
  `HKCU\...\CapabilityAccessManager\ConsentStore\webcam` for any *other* app with
  `LastUsedTimeStop == 0`. It ignores entries whose app isn't running, because apps
  that crash or update mid-session stay listed forever. If it finds one, it releases
  the camera, turns the indicator amber ("paused: camera in use"), and resumes when
  that app lets go.
  - *Phase 0 finding:* the laptop camera is exclusive. Whichever app opens it first
    keeps it, on both capture backends, and Discord's failed attempt leaves no trace.
    So the guard can't react to Discord *wanting* the camera. How to hand the camera
    over is an open decision, tracked in `docs/SYNC.md`.
- **Handedness correctness.** Frames are mirrored once at capture, before inference.
  *Correction from the 2026-09-14 laptop bench:* MediaPipe's docs say its label
  assumes mirrored input, but on mediapipe 1.0.1 mirrored frames come back labelled
  with the opposite hand. The tracker therefore swaps the label, and a test pins that
  to the verified MediaPipe version. Guards against inversion:
  1. That single flip point.
  2. A first-run check ("raise your RIGHT hand") that records `handedness.invert` in
     config.
  3. A majority vote over 5 frames, plus continuity tracking by wrist position.
  4. Replay tests on recorded left-only and right-only sessions.

## 4. Resolving the pinch collision, and the full vocabulary

### 4.1 Decision: disambiguation by first motion, then foreground context

One **pinch** is the *grab* primitive. It is thumb tip to index tip in the image
plane, over palm length, with hysteresis: on below 0.30, off above 0.45. The index
finger must also not be folded, which is what separates a pinch from a fist. These
values were tuned on the 2026-09-15 laptop recordings. Its meaning comes from **what the
pinched hand does first**, inside a **350 ms disambiguation window**. The first
threshold crossed wins, and that mode stays locked until you release:

| First thing that happens after the pinch | Mode | Threshold (config) |
|---|---|---|
| The knuckle line rotates more than 15° while the wrist moves less than 4% of the box | **Volume dial** | `pinch.rotate_deg` |
| The wrist moves faster than 1.2 box-widths/s and at least 8% of the box | **Flick** (4 directions) | `flick.*` |
| Neither happens within 350 ms (you hold still) | **Radial menu** opens | `pinch.hold_ms` |
| You release before any of the above | Nothing (reserved) | — |

The **flick's meaning comes from the target machine's foreground context**, which that
machine's agent resolves:

| Flick direction | Explorer with a selection | Chrome in the foreground | Anything else |
|---|---|---|---|
| **Toward the other machine** | File throw | Tab handoff | Snap to that half |
| Away from the other machine | Snap to that half | Snap to that half | Snap to that half |
| Up / down | Maximise / restore-or-minimise | same | same |

**Why this and not the alternatives:**
- **Handedness as a modifier:** already used for targeting, so it's not available.
- **A cursor-based context:** needs a hand cursor, which you rejected.
- **Everything through the radial menu:** adds two aiming steps to your most frequent
  actions (volume, snap).
- **What this design gives you:**
  - Each pinch mode is a *different kind of motion*: rotation, fast translation, or
    stillness. Those are easy to tell apart.
  - Context only overloads one direction, and only in two apps.
  - In those two apps, snapping toward the other machine is still reachable with
    Win+Arrow or a radial slice.
  - The radial menu stays the escape valve for everything else.

### 4.2 Unified gesture vocabulary

In the "Needs armed" column, "Yes" means the gesture only works after the engage gate
(G1) has armed the system.

| ID | Gesture | Hands | Pose | Motion | Needs armed | Action | Target |
|---|---|---|---|---|---|---|---|
| G1 | **Engage** | 1 | Open palm (5 fingers extended) | Still for 400 ms | — | Arms the system | — |
| G2 | **Count N** | 1 | 1–4 non-thumb fingers extended, **thumb folded** | Still for 600 ms (≥85% of frames agree) | Yes | Launch or focus app N | Hand's machine |
| G3 | **Pinch-hold** | 1 | Pinch | Still for 350 ms, then aim, then release | Yes | Radial menu, fires on release | Hand's machine (slices may override) |
| G4 | **Pinch-turn** | 1 | Pinch | Rotation first | Yes | Volume dial | Hand's machine |
| G5 | **Pinch-flick** | 1 | Pinch | Fast translation first | Yes | Throw, handoff or snap (§4.1) | Hand's machine is the source |
| G6 | **Swipe** | 1 | Open hand, **not pinched** | Sideways wrist flick | Yes | Previous / next track | Hand's machine |
| G7 | **Push** | 1 | Open palm | Box area ×1.6 within 300 ms | Yes | Mute all / unmute all | Both |
| G8 | **Spread / Close** | 2 | Two open palms | Distance between wrists up or down ≥30% within 400 ms | Yes | Maximise / minimise foreground window | Active machine |
| G9 | **Frame** | 2 | Two "L" shapes (thumb and index out, others curled) | Hold still to lock | Yes | Framed screenshot (§4.3) | Active machine |
| G10 | **Two fists** | 2 | Two fists (0 fingers extended) | Hold 300 ms | **No** (emergency) | Boss key toggle | Both |
| K | **Kill switch** | — | Ctrl+Alt+Shift+G | — | **No** | Disable or re-enable everything | Both |

**Why no two entries can be confused.** Every pair differs in at least one *discrete*
feature, either hand count (1 or 2) or pose class (palm, count, pinch, L, fist). Where
two gestures share a pose, they differ in motion class, and the dominant motion must
beat the others by 2:1:

| Pair | Shared | What separates them |
|---|---|---|
| G1 and G7 | Open palm | G1 is still, G7 is movement toward the camera |
| G6 and G7 | Open hand | G6 is sideways movement, G7 is movement toward the camera |
| G3, G4, G5 | Pinch | Stillness vs rotation vs fast translation |
| G5 and G6 | Sideways motion | Pinched vs open |
| G8 and G9 | Two hands | Open palms vs L-shapes |
| G2 "4" and G1 | Four fingers up | Thumb state, plus the hold times differ (a misread palm arms the system instead of launching) |

Residual risk: G2-4 against G1 is the one pair that depends on a single fragile
feature, the thumb. It is flagged in §8 and has its own test fixtures.

### 4.3 Screenshot framing, concretely
1. **One-time calibration** (`tools/calibrate.py`). Put your hands at the corners of a
   comfortable box in front of the laptop. That camera sub-rectangle becomes the
   *interaction box* and is saved to config. It maps proportionally onto the target
   screen.
2. **Framing.** While G9 is held, the target agent draws a live rectangle on screen,
   from the two thumb-index corner points mapped through the box. **Your eyes close the
   loop:** you move your hands until the on-screen rectangle is right, so small mapping
   error doesn't matter.
3. **Lock.** Holding still for 600 ms turns the rectangle green. The capture uses
   `mss`, with the overlay window set to `WDA_EXCLUDEFROMCAPTURE` so it never appears
   in the image.
4. **Send.** Within 2 s, a pinch-flick of either hand toward the other machine sends
   the PNG to that machine's clipboard. Otherwise the image stays on the local
   clipboard and is also saved to `Pictures\gestureio\`.

### 4.4 Ergonomics flags
- **Swipe.** The spec implies an arm sweep. The threshold is instead 12% of the
  interaction box: a wrist flick.
- **Spread / Close.** Shrunk to a 30% change in wrist distance: a small two-hand
  motion, not a full arm spread.
- **Volume dial.** Ratchets instead of forcing a big wrist twist.
- **Framing.** Needs both arms up. That's acceptable only because it's rare. It is
  first on the cut list.
- **Arm height.** Tilt the lid so the interaction box sits just above the keyboard.
  Your elbows can stay on the desk, which avoids tired arms from holding them up.

## 5. The arbiter state machine

One object (`coordinator/arbiter.py`) owns "what are the hands doing". Detectors are
**pure functions of the feature history**. They only *propose* candidates, and the
arbiter decides. There is **one active-gesture slot for the whole system**: while one
hand is in a mode, the other hand is ignored, except for G10 and the kill switch.

```
                 kill hotkey (any state) ─────────► DISABLED ──kill hotkey──► IDLE
   camera guard / "pause" slice ───► CAMERA_PAUSED ──camera free / resume──► IDLE

 IDLE ── G1 engage ──► ARMED ── no hand tracked for 4 s ──► IDLE
   │                     │
   └─ G10 two fists ─────┴──► fire BOSS ─► COOLDOWN(1.5 s) ─► previous state

 ARMED/NEUTRAL, candidates checked in priority order each frame:
   1. two-hand: G10 > G9 FRAME > G8 SPREAD/CLOSE
   2. active one-hand:
      pinch on      ─► PINCH_PENDING(hand)
      count pose    ─► POSE_HOLD(hand, N)
      open lateral  ─► SWIPE
      palm push     ─► PUSH

 PINCH_PENDING ─ rotation first    ─► DIAL   ─ release / lost 300 ms ─► NEUTRAL
               ─ fast translation  ─► FLICK  ─ fire once ─► LATCH ─ release ─► NEUTRAL
               ─ still 350 ms      ─► RADIAL ─ release on slice ─► fire ─► NEUTRAL
                                              ─ release at centre / lost ─► cancel
               ─ release early     ─► NEUTRAL (no-op)
 POSE_HOLD(N)  ─ 600 ms stable     ─► fire ─► POSE_COOLDOWN (until the pose changes, plus 1.5 s)
               ─ pose changes / speed rises ─► NEUTRAL (the progress ring empties)
 SWIPE         ─ fire ─► SWIPE_COOLDOWN (700 ms; the opposite-direction return stroke is suppressed)
 PUSH          ─ fire ─► COOLDOWN (1.5 s)
 FRAME         ─ still 600 ms ─► LOCKED ─► capture ─► AWAIT_SEND (2 s) ─► NEUTRAL
```

Rules:
- **Fail closed.** Losing tracking in any mode *cancels* it. Nothing ever commits on
  lost tracking. DIAL simply stops, because volume values already sent were absolute.
- **Global refractory.** After any fire, nothing else can fire for 300 ms.
- **Hand passing through the frame.** Every discrete gesture requires hand speed below
  `still.max_speed` for its entire hold window. A hand crossing the frame never meets
  that.
- **Visible state.** Every state transition emits a UI event, such as a progress ring,
  a radial "charging" ring, or an indicator colour. That gives feedback before
  anything fires.
- **Testability.** The arbiter is deterministic given timestamps and features, so it
  is unit-tested by replaying recorded landmark streams with no camera.

## 6. Protocol

**Transport:** WebSocket over TCP (`websockets`). Messages are JSON text frames, and
file and image payloads are binary frames. The agent listens on `:8765` on the PC and
`127.0.0.1:8765` on the laptop, and the coordinator connects out as the client. The PC
is addressed by hostname `Safdar`, with a fallback IP in config. Recommended: a DHCP
reservation for the PC on your router.

**Envelope** (every message): `{ "v":1, "id":"<uuid>", "type":"...", "ts":<ms>, ... }`

| Type | Direction | Body |
|---|---|---|
| `hello` | A→C | `machine`, `agent_version`, `config_hash`, `nonce` |
| `auth` | C→A | `hmac = HMAC-SHA256(psk, nonce ‖ coord_nonce)`, `coord_nonce` |
| `welcome` | A→C | `hmac` over `coord_nonce` (so both sides prove the key) |
| `ping` / `pong` | both | every 1 s. The link is declared dead after 3 missed pongs |
| `state` | A→C | `muted`, `volume`, `last_input_ms`, `fg_kind` (`chrome`/`explorer`/`other`), `fg_elevated`, `disabled` (sent with each pong) |
| `cmd` | C→A | `action` (a name from the agent's whitelist), `args`, `deadline_ms` |
| `ack` | A→C | `ref`, `ok`, `error?`, `result?` |
| `ui` | C→A | `op: show/update/hide`, `kind` (`radial`, `dial`, `ring`, `frame`, `toast`, `indicator`, `curtain`), `lease_ms`, `data` |
| `event` | A→C | `kill_toggled`, `tab_changed{url,title,tab_id}`, `transfer_offer{...}` |
| `xfer_begin` / binary chunks / `xfer_end` | A→C→A | `xfer_id`, `name`, `size`, `sha256`. Chunks are 256 KB, and the coordinator relays them |
| `xfer_result` | A→C | `ok`, `path` or `error` |

**Behaviour:**
- **Actions are a closed whitelist.** The agent executes `launch(slot)`,
  `set_volume(v)`, `snap(dir)` and so on. **App paths live in the agent's own config
  file. Nothing sent over the wire is ever run as a path or command.** This is the main
  security property, and it matters more than the encryption choice below.
- **Authentication:** a pre-shared key (32 random bytes, generated by the installer)
  with mutual HMAC challenge-response. The agent also only accepts connections from the
  laptop's address range, through a Windows Firewall rule scoped to the Private
  profile. **No TLS.** On a home LAN whose only other device is your phone, the whitelist
  plus the PSK handshake is proportionate. TLS can be added later without changing the
  schema.
- **Reconnect:** exponential backoff from 0.5 s up to 5 s, with jitter.
  - **Commands are never queued.** An intent whose target is offline fails
    immediately. The indicator turns amber with "PC offline" and a toast explains.
    A stale gesture must never fire late.
  - **Actions on the laptop keep working while the PC is offline.**
- **Coordinator disappears mid-gesture:**
  - Every continuous UI element (radial, dial, frame) carries a `lease_ms` of 500 ms,
    renewed at 10 Hz or more. If the lease expires, the agent **hides it without
    firing**.
  - Partial transfers (`*.gestureio-part`) are deleted.
  - The agent keeps running and waits for the coordinator to reconnect.
- **Kill switch:** every agent registers the hotkey with `RegisterHotKey`.
  - Pressing it disables that agent **locally at once**, so it works even with the
    network down.
  - The agent then sends `event kill_toggled`, and the coordinator propagates it to
    everything.
  - Pressing it again re-enables everything.
- **Chrome bridge (on each machine):**
  1. The extension keeps a persistent `chrome.runtime.connectNative` port to `nmhost`,
     a small stdio relay launched by Chrome.
  2. `nmhost` talks to the local agent over localhost, authenticated with the same
     PSK.
  3. The extension *pushes* `tab_changed` on tab activation, update and window focus,
     so the agent always knows the active URL without asking.
  4. A tab handoff runs: source agent → coordinator → target agent opens the URL
     through its own extension (fallback: `chrome.exe <url>`) → acknowledge → **only
     then** does the source close its tab. No acknowledgement means the tab stays and
     a red toast shows.
  5. The extension ID is pinned with a `key` in `manifest.json`, so the native-host
     allow-list stays valid.

## 7. Feedback, engage gate, performance, config

**Indicator (a pill on both screens, top-centre, click-through):**

| Colour | Meaning |
|---|---|
| Grey | No hand seen |
| White outline | Hand seen, not armed |
| **Green** | Armed. Small L/R dots show which hands are tracked |
| Blue | Gesture in progress |
| Amber | Camera paused, or PC offline |
| **Red** | Disabled by the kill switch |

**Per-gesture confirmation** always appears on the target screen within about 150 ms:
- Launcher: a progress ring fills during the hold, then a toast like "Chrome → PC".
- Radial: the wheel highlights the aimed slice live.
- Volume: a numeric readout.
- Screenshot: the live frame rectangle.
- Transfers: a progress toast on *both* screens (sender and receiver), ending with a
  green tick, or a red cross with the reason.

Every failure shows a red toast. Nothing fails silently.

**Performance budget.** These are targets, verified with measurements in Phase 0.

| Metric | Target | Notes |
|---|---|---|
| Hand motion → overlay update (laptop) | ≤ 120 ms | Capture 33–50 ms, inference 20–30 ms, arbiter under 1 ms, paint 16 ms |
| Hand motion → overlay update (PC) | ≤ 150 ms | Adds Wi-Fi at 2–10 ms, with occasional spikes up to about 50 ms |
| Discrete gesture → action | hold time + ≤ 150 ms | The holds are deliberate: 400 ms, 600 ms, 300 ms |
| Laptop CPU, idle watching (8 fps, face at 2 fps) | ≤ 5% of total | Out of 8 threads |
| Laptop CPU, actively gesturing (30 fps) | ≤ 20% of total | About 1.5 threads |
| PC agent CPU | < 1% | Idle except for the Qt paint |

Notes:
- **MediaPipe's Python GPU delegate is not supported on Windows,** so this runs on the
  CPU and the 1660 Ti goes unused. That's fine at these rates.
- Dim light makes the webcam's auto-exposure drop to 15 fps, which doubles the capture
  latency. Where the driver allows, exposure is locked in config.
- Continuous gestures (G3, G4, G9) are the only ones that need the 30 fps rate. All the
  others work at 15 fps.

**Config:** one TOML file, `%APPDATA%\gestureio\gestureio.toml`, with an identical
copy on both machines.
- Each process reads the sections relevant to its own hostname.
- The PSK lives here and never in the repo.
- The agent reports `config_hash` in `hello`, and the coordinator warns if the two
  copies differ.
- The coordinator hot-reloads the `[gestures]` thresholds when the file changes, so
  you can tune without restarting.

Schema sketch:

```toml
[machines.pc]      hostname = "Safdar";  side = "right"; fallback_ip = "192.168.1.x"
[machines.laptop]  hostname = "SafdarL"; side = "left"
[apps.pc]
1 = { name = "Discord",  launch = { exe = "%LOCALAPPDATA%/Discord/Update.exe", args = ["--processStart","Discord.exe"] }, match = "Discord.exe", relaunch_to_show = true }
2 = { name = "WhatsApp", launch = { aumid = "5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App" }, match = "WhatsApp.exe" }
3 = { name = "Chrome",   launch = { exe = "C:/Program Files/Google/Chrome/Application/chrome.exe" }, match = "chrome.exe" }
4 = { name = "VS Code",  launch = { exe = "%LOCALAPPDATA%/Programs/Microsoft VS Code/Code.exe" }, match = "Code.exe" }
[apps.laptop]
2 = { name = "WhatsApp Web", launch = { url = "https://web.whatsapp.com" } }   # others as on the PC
[[radial.slices]]  label = "Play/Pause"; action = "media_play_pause"; target = "hand"
[[radial.slices]]  label = "Lock";       action = "lock_workstation"; target = "hand"
[[radial.slices]]  label = "Pause cam";  action = "camera_pause";     args = { minutes = 60 }
[gestures]  engage_hold_ms = 400; count_hold_ms = 600; pinch_on = 0.25; pinch_off = 0.40
            pinch_hold_ms = 350; dial_deg_per_pct = 3.0; dial_deadzone_deg = 4 ...
[presence]  absent_after_s = 90; return_confirm_ms = 700; pause_media = false; mute = false
[link]      port = 8765; psk = "<generated>"; heartbeat_ms = 1000
[hotkeys]   kill = "ctrl+alt+shift+g"; preview = "ctrl+alt+shift+p"
```

(The AUMID above is illustrative. The installer script reads the real one from
`Get-StartApps`.)

## 8. Dependencies

Python 3.12, with dependencies pinned in `uv.lock`. MediaPipe wheels lag behind new
Python releases, so the Python version stays pinned.

| Package | Where | Why |
|---|---|---|
| `mediapipe` (Tasks API: HandLandmarker, FaceDetector) | Coordinator | The standard for real-time hand landmarks, with a handedness output. **Shaky:** the Python API churns (the legacy `solutions` API is deprecated), so pin the version and use only the Tasks API. |
| `opencv-python` | Coordinator | Camera capture on the MSMF backend, plus the preview window. |
| `numpy` | Coordinator | Feature math. |
| `websockets` | Both | Mature asyncio WebSocket library, with no framework baggage. |
| `PySide6` | Agent | Official Qt bindings. Per-pixel-alpha, frameless, non-activating overlays. Tkinter can't do these cleanly. |
| `pywin32` | Agent | Win32 and COM: windows, Explorer selection, clipboard, `RegisterHotKey`, `SetWindowDisplayAffinity`. Decades-mature. |
| `pycaw` (+ `comtypes`) | Agent | Master volume and mute through `IAudioEndpointVolume`. **Shaky:** effectively one maintainer. The fallback is our own ~60-line `comtypes` wrapper of the same interface. |
| `mss` | Agent | Fast, reliable region screenshots. |
| `Pillow` | Agent | PNG and DIB encoding for the clipboard and saved files. |
| `psutil` | Agent | Finding processes for "focus the existing window". |
| `pytest` | Dev | Tests, including landmark-stream replay tests. |
| `uv` | Dev | Reproducible environments on both machines. |

**Deliberately not used:**
- `keyboard`, `pyautogui`: unmaintained or clumsy. Input injection uses `ctypes`
  `SendInput` instead.
- Any ONNX or CUDA hand-model port: clever, but not boring enough for daily use.
- The Chrome extension is vanilla JavaScript with no build step.

## 9. Risk register (most likely to sink the project first)

| # | Risk | Mitigation / fallback |
|---|---|---|
| 1 | **Real-world recognition quality.** Lighting, the lid-camera angle, hands low in frame. False fires make you turn it off, and misses make it feel broken. | Engage gate; hold times; every threshold in config; each gesture can be switched off individually; record-and-replay harness from Phase 0; the Phase 0 bench measures detection before anything else is built. |
| 2 | **Webcam contention with Discord video calls** (you do these often). | Phase 0 spike tests whether both can share the camera on your hardware. If they can't: (a) the camera guard auto-releases when another app starts the camera; (b) a hotkey and "Pause cam" slice to pause manually; (c) check the Windows 11 multi-app camera setting; (d) hardware fallback: a cheap USB webcam just for gestures. |
| 3 | **Pinch-mode misreads** (dial vs radial vs flick). | Threshold tuning; a "charging" ring visible from the moment you pinch; every mode has a cancel path (release at centre, open hand); actions commit on release, not on entry. |
| 4 | **G2-4 vs open palm (thumb state).** | Strict thumb-folded test with hysteresis; 85% frame agreement; dedicated replay fixtures; fallback: remap slot 4 to a thumb-out pose, or move it to the radial menu. |
| 5 | **CPU, heat and fan noise** from running all day on the 3750H. | Adaptive fps; 640×480 input; face detection at 2 fps; measured in Phase 0 with a go/no-go gate; fallback: 20 fps active, and the laptop's Balanced power plan. |
| 6 | **Silent left/right inversion.** | Single flip point, first-run check, temporal voting, replay tests (§3). |
| 7 | **Windows foreground lock and UIPI** (focusing apps, elevated windows). | Synthetic Alt tap plus `SetForegroundWindow`, then verify that the foreground actually changed and toast if not; detect elevated windows through the process token and toast. |
| 8 | **Wi-Fi drops or jitter** on the laptop. | No command queueing, leases on overlays, offline indicator, laptop actions unaffected; the laptop can also use Ethernet if one is available. |
| 9 | **Explorer tab selection ambiguity** (Windows 11 tabs share an HWND). | Match the active `ShellTabWindowClass` to each shell window's browser HWND; if it's still ambiguous, refuse with a toast. Never guess and send the wrong file. |
| 10 | **Chrome MV3 or unpacked-extension policy changes.** | Persistent native-messaging port (which also keeps the service worker alive); reconnect on `onStartup`; the feature degrades to "copy URL to other machine" using the `tab_changed` cache. |
| 11 | **MediaPipe API or wheel churn.** | Pin the version; wrap the tracker behind a small `Tracker` interface so the model can be swapped. |

## 10. Phased milestones (each ends in something you can run)

**The first feature is the finger-count launcher.** It exercises *every* layer:
- capture, tracking and **handedness routing** (the most bug-prone part, and proven
  directly here);
- hold and debounce, and the engage gate;
- the arbiter, the authenticated link and heartbeat;
- a real agent action, overlay feedback, config and the kill switch.

Its actions are discrete and harmless (opening an app), so errors are cheap while
tuning.

| Phase | Scope | You can run and use… | Size |
|---|---|---|---|
| **0: Bench** | Repo scaffold, `uv` env, `tools/bench.py` (camera → mirror → landmarks → preview showing the handedness label, finger count, pinch distance, FPS and CPU %), `tools/record.py` (landmark JSONL recordings). **Spikes:** does Discord video work while bench holds the camera? Measure CPU. | A live preview that shows the system understands your hands. It ends with a **go/no-go on the CPU numbers and on the camera strategy.** | 1–2 evenings |
| **1: Launcher end to end** | Coordinator skeleton, arbiter (IDLE, ARMED, POSE_HOLD), engage gate, agents on both machines (WebSocket, PSK authentication, heartbeat, reconnect), launch-or-focus action, indicator, progress ring, toasts, kill hotkey, manual camera-pause hotkey, config file, installer script (firewall rule, PSK generation). | Right hand, 3 fingers → Chrome comes to the front on the PC. Left hand → the laptop. | 3–4 evenings |
| **2: Pinch core** | PINCH_PENDING disambiguation, radial overlay with starter slices, volume dial (knuckle-line angle, wraparound, deadzone, ratchet), instant mute and unmute (G7), automatic camera guard. | Daily volume and media control, plus the radial menu. | 3–4 evenings |
| **3: Motion gestures** | Swipe (G6), pinch-flick window snapping (G5, context branch for "anything else" only), spread and close (G8), boss key (G10) with exact restore. | Full window and media control. | 2–3 evenings |
| **4: Daily-driver hardening** | Presence curtain (face at 2 fps + keyboard/mouse input on either machine + hands; 90 s absent → curtain on both; face for 700 ms or any input → removed), autostart through Task Scheduler (at logon, non-elevated, restart on failure), rotating logs, first-run handedness check, `tools/calibrate.py` (interaction box). | **Live with it for a week** and tune thresholds from real use. | 2–3 evenings |
| **5: Transfers** | Shared transfer channel (chunks, SHA-256, `.gestureio-part`, progress and failure toasts). Then the Explorer file throw. Then the Chrome extension and native host tab handoff. | Throw a file or tab to the other machine by flicking toward it. File throw and tab handoff each work on their own. | 4–5 evenings |
| **6: Screenshot framing** | G9 detection, live frame overlay, `WDA_EXCLUDEFROMCAPTURE`, capture, clipboard and send. | Frame a region with your hands and send it across. | 2–3 evenings |

**Cut order if a phase runs long (assumed):**
1. Phase 6 (screenshot framing).
2. The tab-handoff half of Phase 5.
3. The file-throw half of Phase 5.
4. G8 (spread and close).

Phases 0 through 4 on their own give you a complete, usable daily tool.

## 11. Repo layout

```
gestureio/
  pyproject.toml  uv.lock  README.md
  config/gestureio.example.toml
  src/gestureio/
    common/      config.py  protocol.py (envelope, types, validation)  auth.py (PSK HMAC)  log.py
    coordinator/ main.py  capture.py  tracker.py (MediaPipe wrapper)  face.py
                 features.py (finger states, pinch, knuckle angle, box area, One Euro filter)
                 arbiter.py (the state machine)  detectors/ (count, pinch, swipe, push, two_hand, frame, fists)
                 router.py (hand/active-machine → agent)  link.py (client, reconnect)
                 presence.py  camera_guard.py  preview.py
    agent/       main.py  server.py  registry.py (the action whitelist)  hotkey.py
                 actions/ apps.py  audio.py  media.py  windows.py  clipboard.py  screenshot.py
                          files.py  explorer.py  chrome_bridge.py  input_state.py  boss.py
                 ui/ overlay.py (base: non-activating, click-through, capture-excluded)
                     indicator.py  toast.py  ring.py  radial.py  dial.py  frame.py  curtain.py
    nmhost/      host.py (Chrome native-messaging stdio ↔ agent relay)
  chrome_extension/  manifest.json (pinned key)  background.js
  scripts/       install.ps1 (uv sync, PSK, firewall rule, Task Scheduler)  install_nmhost.ps1
  tools/         bench.py  record.py  replay.py  calibrate.py
  tests/         fixtures/*.jsonl (recorded landmark streams)
                 test_arbiter_replay.py  test_features.py  test_angle_wrap.py
                 test_protocol_auth.py  test_config.py  test_handedness.py
```

## 12. Verification

- **Unit tests (`pytest`), run on every phase:**
  - Arbiter replay against recorded fixtures: each gesture fires exactly once; a
    hand-passing-through recording fires nothing; left-only and right-only recordings
    route correctly.
  - Angle wraparound: a synthetic sweep from 170° to −170° gives +20° with no jump.
  - Protocol: handshake with a wrong PSK is rejected; unknown actions are rejected.
  - Config: parses, and hot-reload applies.
- **Phase acceptance checklist (manual, on the real desk):**
  - Right hand, 3 fingers → Chrome on the PC. Left hand → the laptop. Already-running
    apps are focused, not duplicated.
  - 20 casual hand-through-frame passes → zero fires.
  - Unplug the PC's Ethernet → amber indicator within 3 s; the gesture fails with a
    toast; re-plug → it reconnects; nothing fires late.
  - Kill the coordinator during the radial menu → the wheel vanishes within 500 ms and
    nothing fires.
  - Press the kill hotkey on either keyboard → red on both screens; no gestures act.
  - Start a Discord video call → the indicator goes amber and Discord has video; end
    the call → it resumes.
  - Throw a 15 MB file → the SHA-256 matches on arrival; disconnect mid-transfer → red
    toast, no partial file left in Downloads.
- **Performance:** `tools/bench.py --measure` logs frames per second, inference
  milliseconds and process CPU % over 10 minutes, idle and active, to check against the
  §7 budget.
