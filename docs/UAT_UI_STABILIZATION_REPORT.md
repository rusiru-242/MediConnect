# MediConnect — UAT AI Assistant UI Stabilization Report

For: the project owner, before resuming manual UAT. Branch `fix/uat-ai-assistant-ui-stabilization` (from `fix/comprehensive-system-ai-stabilization` at `7a6c5c5`). Date: 2026-11-25.

## 1. Summary

- **Two layout defects caused the UAT blockers. Both were reproduced on the Android emulator and both are fixed.**
  1. **Main root cause (BUG-043):** the emergency banner's **1990** button threw `BoxConstraints forces an infinite width` during layout. The screen was left half laid out, which explains the duplicate or missing composer, the red error screen on Back, the lag, and the missing emergency banner.
  2. **Second cause of a disappearing composer (found during emulator testing):** in landscape with the keyboard open, the fixed-height banners overflowed the screen by 106 px and pushed the composer out of view.
- **Emergency UI completed (BUG-042):**
  - red banner with a dedicated 1990 button
  - a **Call 1990** button under the emergency reply
  - a confirmation dialog, then the phone dialer with 1990 entered (no call is ever placed)
  - routine chips hidden during an emergency
  - English, Sinhala and Tamil text
- **Emulator verification:** the full checklist was run on the emulator, including **20 complete cycles that sent 60 real messages**, with **0 framework exceptions**. Only cancelling an upload mid-flight could not be exercised on the device (section 6).
- **Next:** manual UAT retest **P-17**, then P-01a–e, then **P-01f**.

## 2. Confirmed root causes and how the five bugs relate

### 2.1 Root cause A: infinite-width button (BUG-043)

| Step | What happened | Evidence |
|---|---|---|
| 1 | The assistant reopens the latest conversation. If it is an emergency (`isUrgent: true`), the red banner is built. | Backend response on port 8001 |
| 2 | The app theme (`app_theme.dart`) gives every `ElevatedButton` `minimumSize: Size(double.infinity, 52)`. The banner put its 1990 button directly in a `Row`, which allows unlimited width, so layout received `BoxConstraints(w=Infinity)` and threw in `PipelineOwner.flushLayout`. | First exception in the debug log (below) |
| 3 | The rest of that layout pass was abandoned. The banner, the list and the composer were left with render objects that were never laid out: the body is blank and the composer is gone. | 8 cascading `RenderBox was not laid out` errors; `before-fix-assistant-blank.png` |
| 4 | Later frames, keyboard changes, rebuilds and route removal all worked on that inconsistent render tree. This produced the assertions seen in UAT (`_owner != null`, `attached`, `!debugNeedsLayout`, `child._parent == this`, `_debugRelayoutBoundaryAlreadyMarkedNeedsLayout`), plus stale painted layers that looked like a second composer. | Matches every reported assertion and symptom |
| 5 | In debug mode each failure printed a full report, and the broken subtree was laid out (and failed) again. The app got slower over time. | BUG-045 |

First exception, as captured on the emulator before the fix:
```
══╡ EXCEPTION CAUGHT BY RENDERING LIBRARY ╞══
The following assertion was thrown during performLayout():
BoxConstraints forces an infinite width.
The offending constraints were: BoxConstraints(w=Infinity, 44.0<=h<=Infinity)
The relevant error-causing widget was: ElevatedButton  ai_care_assistant_screen.dart:1041:26
#3  RenderObject.layout (rendering/object.dart:2823)
#4  RenderConstrainedBox.performLayout (proxy_box.dart:296)
#7  _RenderInputPadding._computeSize (material/button_style_button.dart:698)
#13 RenderFlex._computeSizes (flex.dart:1237)
#27 _ScaffoldLayout.performLayout (scaffold.dart:1113)
#31 PipelineOwner.flushLayout (object.dart:1174)
```

### 2.2 Root cause B: composer pushed off-screen in landscape with the keyboard open (BUG-014)

- In landscape with the keyboard open, the body is only about 64 px tall.
- The disclaimer and the emergency banner have fixed heights, and together they overflowed by 106 px (`A RenderFlex overflowed … on the bottom`).
- The composer and the conversation list were pushed out of view (`before-fix-landscape-keyboard-overflow.png`).

### 2.3 How the five bugs relate

- **BUG-043** is root cause A.
- **BUG-014** (duplicate or missing composer) comes from A, and also from B for the "missing" case.
- **BUG-015** (`_owner != null` on Back) comes from A.
- **BUG-045** (lag) comes from A. No separate performance defect was found.
- **BUG-042** (emergency UI missing) has two causes:
  - A: the banner's own layout threw, so it never painted.
  - The routine chips stayed visible: the backend keeps `state = COLLECTING_PREFERENCES` during an emergency, and the app showed chips based on `state` alone.
  - The backend contract itself was correct: `isUrgent`, `urgencyReason`, `activeIntent: EMERGENCY_GUIDANCE`, message metadata `type: emergency`, `ambulanceCall: 1990`, `category`.

**Why it recurred straight after a restart:** the assistant reopens the latest conversation, so once a chat contained an emergency, every opening rebuilt the crashing banner.

**Why earlier fixes and tests missed it:**
- All widget tests used a plain `MaterialApp` without the app theme, and never an urgent session together with the theme.
- No test used landscape with the keyboard open.
- Widget finders count widgets, not stale painted layers.

### 2.4 Investigated, no defect found

- **Composer construction:** built once (`_buildInputArea`). There are no duplicate branches, overlays or nested `Scaffold`s, and no `GlobalKey`s.
- **Controllers and focus:** controllers are owned and disposed by the screen state; there is no explicit `FocusNode`.
- **Navigation:** route duplication is already guarded by `AssistantNavigation.open`.
- **Async work:**
  - Every async result checks `mounted`; image uploads also check a generation counter.
  - Post-frame scrolls check `_disposed`, `mounted`, `hasClients` and `hasContentDimensions`.
  - The hold timer is cancelled on pop and on dispose.
- **Other full-width buttons** sit in `Column`s or `Wrap`s and pass under the real theme.

No assertion was suppressed and no exception was caught to hide it.

## 3. Files changed

| File | Change |
|---|---|
| `mobile/lib/screens/patient/ai_care_assistant_screen.dart` | **Fix A:** the 1990 button gets `minimumSize: Size(72, 40)`.<br>**Fix B:** height-aware body:<br>- below 240 px: conversation and composer only (the composer is limited to 1 line)<br>- otherwise: the header banners get at most 35% of the height and the attachment/progress rows at most 30%, both scrollable<br>- below 420 px: chips hidden; during an emergency the disclaimer gives way to the banner<br>**Emergency UI:** state from `isUrgent` / `EMERGENCY_GUIDANCE`; routine chips hidden; localized banner (en/si/ta), whose language follows the latest emergency reply's script (the backend replies in Sinhala to Romanized Sinhala but keeps `preferences.language = en`); the English-only `urgencyReason` is shown only in the English banner; dedicated **Call 1990** action; confirmation dialog; "dial 1990 manually" message if the dialer fails. |
| `mobile/lib/utils/emergency_dialer.dart` (new) | Opens the dialer through a platform channel. Returns false and never throws if no dialer is available. |
| `mobile/android/app/src/main/kotlin/.../MainActivity.kt` | `mediconnect/emergency_dialer` channel using `Intent.ACTION_DIAL`, which only pre-fills the number. There is no `CALL_PHONE` permission, and only 3–6 digit numbers are accepted. |
| `mobile/android/app/src/main/AndroidManifest.xml` | `<queries>` entry for `ACTION_DIAL` / `tel:` |
| `mobile/test/screens/ai_assistant_ui_stabilization_test.dart` (new) | 14 regression tests (section 4) |
| `mobile/test/screens/ai_care_assistant_screen_test.dart`, `ai_assistant_stabilization_test.dart` | Now use `AppTheme.lightTheme`. Test #8 asserts no exception and the new banner. |
| `docs/…` | Bug tracker, UAT plan (P-17, the owner's P-01 results log), verification matrix addendum, this report, `docs/uat-evidence/2026-11-25/` (10 screenshots) |

No backend code was changed, and emergency detection is unchanged.

## 4. Automated test results (Windows, Flutter 3.47.5)

| Check | Result |
|---|---|
| `flutter analyze` | No issues found |
| `flutter test` (complete suite) | **269 passed**, 0 failed |
| `ai_assistant_ui_stabilization_test.dart` | 14 passed |
| Same tests with fix A reverted | All failed (9 of the original 10 directly; the normal-reply control passes when run alone) |
| Landscape tests run against the screen before fix B | Landscape with keyboard **failed**: `RenderFlex overflowed by 141 pixels` (matches the device) |
| `flutter build apk --debug --dart-define=API_BASE_URL=http://10.0.2.2:8001` | Built |
| GitHub Actions on `6c2be8f` | **Mobile CI: success** ([run 45545156194](https://github.com/rusiru-242/MediConnect/actions/runs/45545156194)). The result for the follow-up commit is recorded in the tracker after push. |
| `test/integration/live_api_test.dart` | **Not run on purpose:** hard-wired to port 8000, the production-like Atlas backend |
| Backend tests | Not needed: no backend code changed |

What the 14 tests cover:
- **Layout:** an emergency chat lays out without an exception; the 1990 button has a finite width; the composer is laid out.
- **Emergency UI:** banner, dedicated action and hidden chips; a normal reply shows no emergency UI.
- **Calling:** Cancel never dials; confirm dials exactly `1990`; a dialer failure shows the manual-dial message.
- **Language:** Sinhala banner for a Sinhala conversation and for a Sinhala reply to a Romanized message.
- **Landscape:** keyboard open and closed — no overflow, composer above the keyboard.
- **Portrait** with keyboard.
- **Keyboard:** 20 open/close cycles.
- **Lifecycle:** 20 cycles of open → emergency → New Chat → History → Back with the keyboard open and a reply pending; a late reply after Back is ignored.
- Composers are counted as widgets and as **attached `RenderEditable` render objects**.

## 5. Emulator verification performed

Environment:
- Android 17 (API 37) emulator.
- `flutter run --debug --dart-define=API_BASE_URL=http://10.0.2.2:8001`.
- UAT backend on 127.0.0.1:8001: `staging`, local MongoDB `mediconnect_uat`, deterministic AI, external image analysis disabled.
- Synthetic `uat.patient1`.
- Composers were counted in the accessibility tree; exceptions were counted in the `flutter run` log.

| Checklist # | Check | Result |
|---|---|---|
| — | **Before fix A:** open the assistant on an emergency chat | Reproduced: 1 layout exception plus 8 cascades; blank body, **no composer** |
| 1, 2 | Open the AI Assistant (after the fix) | One composer, 0 exceptions, every time (more than 45 openings in total) |
| 3 | Keyboard open/close | Layout adapts; one composer (`after-fix-five-messages-one-chat.png`) |
| 4 | **5 messages in one chat** with the send button (food, cardiologist, budget, paracetamol, exercise) | All answered; one composer and 0 exceptions after each |
| 5–9 | **20 automated cycles** (guarded: abort if MediConnect is not in front). Each cycle: open from Home, send an emergency, close the keyboard, New Chat, send a normal message, open/close Chat History, then send and **immediately press Back twice with the keyboard open and the reply in flight** | **20/20 clean:** one composer at all 4 checkpoints, app in front, **0 exceptions, 0 overflow, 0 setState-after-dispose** across the whole run. The backend confirms **all 60 messages arrived and were answered**, including the 20 sent just before Back, and all 20 emergencies were flagged. Cycle times 38.1–39.5 s with no upward trend. |
| 10 | Rotation | Portrait ↔ landscape with the keyboard closed: clean. **With the keyboard open, before fix B: `RenderFlex overflowed by 106 pixels` and the composer pushed off-screen** (`before-fix-landscape-keyboard-overflow.png`). After fix B: composer visible, 0 exceptions (`after-fix-landscape-keyboard-composer.png`); sending from landscape works; the banner returns when the keyboard closes. Emulator rotation settings were restored (auto-rotate on, portrait). |
| 11 | Image selection and cancellation | Picker cancel: clean return. Pick: preview shown. Remove (✕): preview gone. Pick and send: HTTP 200, photo message plus honest "could not be analysed / Not analysed" reply (`after-fix-image-upload-reply.png`). 0 exceptions. **Cancel during upload: not exercisable** (section 6). |
| 12 | Emergency UI, English (P-01a message) | Banner, 1990 button, **Call 1990** action, no chips. 1990 → dialog → **Cancel**: nothing happens. **Open dialer**: system dialer with 1990, `dumpsys telecom` showed 0 calls, Call not pressed. |
| 12 | Emergency UI, **Romanized Sinhala** (P-01b, typed on the device) | Detected; banner, Call 1990, no chips. The banner was first English while the reply was Sinhala → **fixed** (language follows the reply) → Sinhala banner, `1990 අමතන්න` action and Sinhala dialog verified (`after-fix-romanized-sinhala-banner.png`, `after-fix-sinhala-confirmation.png`) |
| 12 | Emergency UI, **Sinhala script** (P-01c) | Message sent through the backend API (adb cannot type Sinhala script), then opened in the app: Sinhala banner, 1990, `1990 අමතන්න`, no chips, 0 exceptions |
| 13 | Normal non-emergency replies | Food, doctor search, medicine and exercise replies render with their cards and no emergency UI |

**Test-process incident:**
- An earlier run of the cycle script continued after the app had gone to the background.
- For about one cycle, its taps and typed test strings ("chest pain severe c1", …) went to the emulator's launcher and Google app. This may have submitted Google searches containing those strings. No personal or UAT data was involved.
- The script now aborts if MediConnect is not in the foreground. That run's results were discarded.

## 6. Not verified on the device

- **Cancel during an image upload:** the local backend with external analysis disabled answers in under 0.4 s, so the Cancel button cannot be tapped in time. It is covered by the widget test `ai_assistant_stabilization_test` "cancel stops waiting and ignores the late result".
- **Typing Sinhala script** on the device; display was verified.
- A **DevTools frame-timing profile** was not captured.
- A **physical phone** was not used; this was the emulator only.

## 7. Performance observations

- **Before fix A:** the failure repeated on every relayout, each time printing a full report and laying out the broken subtree again.
- **After the fixes:** 20 identical cycles took 38.1–39.5 s each with no upward trend, and the whole session logged 0 framework errors. The timing is dominated by fixed script waits, so it is a coarse signal only.
- **Minor, unchanged:** the hold countdown rebuilds the whole screen once a second while a booking hold is active.

## 8. Remaining limitations and related findings

- **BUG-046 (OPEN, not changed here):** the Home **Emergency SOS** shows "Calling National Ambulance Service (1990)…" but never opens the dialer. `EmergencyDialer` can be reused for the fix.
- **For P-01f / BUG-004 (backend):**
  - A follow-up message after a **Sinhala** emergency was escalated correctly (`fromContext: true`) but answered in **English**.
  - `urgencyReason` is English only.
  - `preferences.language` stays `en` for Romanized Sinhala.
- **Tight-height behaviour:** when the body is under 240 px (landscape with the keyboard open), the banners hide until the keyboard closes, so that the composer stays usable.
- **Translations:** the new Sinhala and Tamil strings need native-speaker review (BUG-004).
- **Deferred:** BUG-044 (category-specific guidance).
- **Theme hazard:** the global `minimumSize: Size(double.infinity, …)` in `app_theme.dart` still makes any future `ElevatedButton`/`OutlinedButton` placed directly in a `Row` crash. The test harnesses now use the real theme to catch this.
- **Integration test:** `live_api_test.dart` should be made configurable (port 8001).

## 9. Exact manual retest instructions

1. Start the UAT backend: `powershell -ExecutionPolicy Bypass -File backend/scripts/start_uat_backend.ps1`. Check that `http://127.0.0.1:8001/health` reports `staging`. **Port 8000 is not the UAT backend.**
2. Uninstall the old app.
3. Run `cd mobile`, then one of:
   - Emulator: `flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8001`
   - USB phone: `adb reverse tcp:8001 tcp:8001` and `flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8001`
4. Sign in as `uat.patient1`.
5. Run **P-17** in [MANUAL_UAT_TEST_PLAN.md](MANUAL_UAT_TEST_PLAN.md). Never press Call in the dialer.
6. Re-run **P-01a–e**. The new banner text is "Possible medical emergency" (Sinhala for Sinhala replies).
7. Then run **P-01f**.
8. If anything fails, copy the **first** `EXCEPTION CAUGHT` block from the `flutter run` output.

Earlier P-01 results (P-01a–e PARTIAL PASS, P-01f NOT TESTED) are kept as reported and are not upgraded by this change.
