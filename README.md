# gestureio

Hand gesture control across two Windows machines, driven by the laptop webcam.

**Status: Phase 0 (bench).** This phase answers three questions before anything
else is built:
1. Does hand tracking work well at your desk?
2. Does it fit the CPU budget on the laptop?
3. Can it share the webcam with Discord?

Every command below runs on the **laptop**, from the `gestureio` folder, in PowerShell.

## 1. One-time setup

```powershell
git clone https://github.com/stackDawg/gestureio.git
cd gestureio
py -3.12 --version            # if this fails: winget install Python.Python.3.12
py -3.12 -m pip install --user uv
py -3.12 -m uv sync
py -3.12 -m uv run python tools/fetch_models.py
```

## 2. Look at the preview (about 5 minutes)

```powershell
py -3.12 -m uv run python tools/bench.py
```

If the window shows the wrong camera or a blank picture, try `--camera 1`.
Windows 11 can add a "Windows Virtual Camera Device" (Phone Link) that takes index 0.
Use the same `--camera` value in every command below.

Check these:
- **Raise your right hand.** Its skeleton is **orange**, labelled **RIGHT**, on the
  right side of the window. The window is a mirror.
- **Raise your left hand.** It is **cyan**, labelled **LEFT**.
- **Try each pose.** 1–4 fingers with the thumb tucked should read `count1`…`count4`.
  An open hand reads `palm`, a fist reads `fist`, and thumb-to-index reads `pinch`.
- **Adjust the lid** so that with your elbows on the desk, your hands are fully in
  view.

If the labels are the wrong way round, tell me. Don't work around it with
`--invert-handedness`.

Keys: `q` quit, `h` hide or show the stats, `r` start or stop a recording.

## 3. Measure CPU (10 minutes, laptop plugged in)

```powershell
py -3.12 -m uv run python tools/bench.py --measure 600
```

Keep your hands out of view for the first ~5 minutes, then make gestures for ~5
minutes. The report is saved to `bench_results\`.

## 4. Discord camera test

| Run | Steps |
|---|---|
| A | Start `bench.py`. Then in Discord, open **User Settings → Voice & Video → Test Video**. |
| B | Close both. Start Discord's **Test Video** first, then `bench.py`. |
| C | Repeat A with `bench.py --backend dshow`. |
| D | Repeat B with `bench.py --backend dshow`. |

For each run, note three things:
1. Does Discord show video?
2. Does the bench keep moving, or does it show **NO FRAMES**?
3. What does the stats line "other apps using camera" say?

Also look in **Settings → Bluetooth & devices → Cameras → (your camera)** for an
option that lets several apps use the camera at once.

## 5. Starter recordings (about 5 minutes)

Each one counts down 3 s, then records 10 s. Only landmark positions are saved, no
images.

```powershell
foreach ($l in 'right-palm','right-count1','right-count2','right-count3','right-count4',
               'right-fist','right-pinch','left-palm','left-count2','two-hands','pass-through') {
    py -3.12 -m uv run python tools/record.py $l
}
```

- For each pose, hold it while moving naturally.
- For `right-count4`, keep your thumb tucked.
- For `two-hands`, hold both hands up in any pose.
- For `pass-through`, casually move your hand across the view a few times without
  making any pose.

To check a recording: `py -3.12 -m uv run python tools/replay.py recordings\<file> --text`

## 6. Send the results back

Commit `bench_results\` and `recordings\` and push them. Add a new entry to
`docs/SYNC.md` with the Discord results. `CLAUDE.md` explains how the two machines
stay in sync through this repo.

## Tests

```powershell
py -3.12 -m uv run pytest
```
