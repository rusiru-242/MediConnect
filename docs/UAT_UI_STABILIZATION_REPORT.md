# MediConnect — UAT AI Assistant UI Stabilization Report

For: the project owner, before resuming manual UAT. Branch `fix/uat-ai-assistant-ui-stabilization` (from `fix/comprehensive-system-ai-stabilization` at `7a6c5c5`). Date: 2026-11-25.

## 1. Summary

- **One root cause explains all five blockers (BUG-014, BUG-015, BUG-042, BUG-043, BUG-045).** It was reproduced on the Android emulator the first time the AI Assistant was opened.
- **The first exception** was a layout assertion, not a navigation or lifecycle error:
  `BoxConstraints forces an infinite width` for the emergency banner's **1990** `ElevatedButton` (`ai_care_assistant_screen.dart:1041`).
- **Why:** the app theme (`app_theme.dart`) gives every `ElevatedButton` `minimumSize: Size(double.infinity, 52)`. The banner put that button directly inside a `Row`, and a `Row` gives its children unlimited width. The button asked to be infinitely wide, and layout threw part-way through a frame.
- **Fix:** the button now overrides `minimumSize` with a finite width. The emergency UI was also completed: dedicated 1990 action, confirmation dialog, dialer intent, routine chips hidden, and Sinhala/Tamil strings.
- **Status:** fixed and partly verified on the emulator. **Not every emulator check could be completed** (section 6). Manual retest (UAT **P-17**) is required before UAT continues with P-01f.

## 2. Confirmed root cause and how the five bugs relate

| Step | What happened | Evidence |
|---|---|---|
| 1 | The assistant opens the most recent conversation. If that conversation is an emergency (`isUrgent: true`), the red banner is built. | Backend response captured on port 8001 |
| 2 | The 1990 button inside the banner's `Row` receives `BoxConstraints(w=Infinity, 44<=h<=Infinity)`, and `RenderObject.layout` throws during `PipelineOwner.flushLayout`. | First exception in the debug log (excerpt below) |
| 3 | The rest of that layout pass is abandoned. The banner, the conversation list and the composer are left with render objects that were never laid out. In the screenshot the body is blank and the composer is gone. | 8 cascading `RenderBox was not laid out` errors; `before-fix-assistant-blank.png` |
| 4 | Every later frame, keyboard inset change, rebuild or route removal works on that inconsistent render tree. This produces the assertions seen in UAT: `_owner != null`, `attached`, `!debugNeedsLayout`, `child._parent == this` and `_debugRelayoutBoundaryAlreadyMarkedNeedsLayout`. The display can show stale layers from earlier frames, which appear as a duplicate composer or a missing one. | Matches every assertion and symptom reported in UAT |
| 5 | In debug mode, every failure prints a full error report, and the broken subtree is laid out (and fails) again. The app gets slower the longer it is used. | BUG-045 symptoms |

Mapping:
- **BUG-043** (lifecycle/rendering assertions) is the root cause.
- **BUG-014** (duplicate or missing composer) and **BUG-015** (`_owner != null` on Back) are consequences.
- **BUG-045** (lag): no separate performance defect was found. It is explained by the repeated failures.
- **BUG-042** (emergency UI missing) has two causes:
  - The banner was built but never painted, because its own layout threw.
  - The routine chips stayed visible: the backend keeps `state = COLLECTING_PREFERENCES` during an emergency, and the app showed chips based on `state` alone.
  - The backend contract itself was correct: `isUrgent`, `urgencyReason`, `activeIntent: EMERGENCY_GUIDANCE`, message metadata `type: emergency`, `ambulanceCall: 1990`, `category`.

**Why it recurred immediately and "restart only helped temporarily":** the assistant reopens the latest conversation. Once a chat contained an emergency, every opening rebuilt the crashing banner.

**Why earlier fixes and tests missed it:**
- Every widget test pumped a plain `MaterialApp` without the app theme.
- No fake session was ever urgent. The one test that rendered an urgent session also used no theme, so the button had a finite default size.
- Widget finders count widgets, not stale painted layers, so "exactly one composer" passed even when the screen showed two.

First exception, as captured (debug build, emulator, before the fix):
```
══╡ EXCEPTION CAUGHT BY RENDERING LIBRARY ╞══
The following assertion was thrown during performLayout():
BoxConstraints forces an infinite width.
The offending constraints were: BoxConstraints(w=Infinity, 44.0<=h<=Infinity)
The relevant error-causing widget was: ElevatedButton
  ai_care_assistant_screen.dart:1041:26
#3  RenderObject.layout (rendering/object.dart:2823)
#4  RenderConstrainedBox.performLayout (proxy_box.dart:296)
#7  _RenderInputPadding._computeSize (material/button_style_button.dart:698)
#13 RenderFlex._computeSizes (flex.dart:1237)
#27 _ScaffoldLayout.performLayout (scaffold.dart:1113)
#31 PipelineOwner.flushLayout (object.dart:1174)
```

### Other items investigated (no defect found)

- **Composer construction:** built exactly once in `_buildInputArea()`. There are no responsive or keyboard-dependent branches and no second `Scaffold` or overlay.
- **Widget identity and controllers:**
  - No `GlobalKey`s on the screen.
  - The `TextEditingController` and `ScrollController` are owned and disposed by the screen state.
  - There is no explicit `FocusNode`.
- **Navigation:** route duplication is already guarded by `AssistantNavigation.open` (kept).
- **Async work:**
  - Every async result checks `mounted`, and image uploads also check a generation counter.
  - Post-frame scrolls check `_disposed`, `mounted`, `hasClients` and `hasContentDimensions`.
  - The hold timer is cancelled on pop and on dispose.
- **Other full-width buttons:** checked under the real theme. They sit in `Column`s or `Wrap`s, which give bounded widths. All 37 assistant tests now run under `AppTheme.lightTheme` and pass, covering doctor cards, slots, booking summary and hold/payment states.

No assertion was suppressed and no exception was caught to hide it.

## 3. Files changed

| File | Change |
|---|---|
| `mobile/lib/screens/patient/ai_care_assistant_screen.dart` | **Root-cause fix:** banner 1990 button gets `minimumSize: Size(72, 40)`. Emergency state comes from the backend contract (`isUrgent` or `EMERGENCY_GUIDANCE`). Routine quick-prompt chips are hidden during an emergency. Localized banner (en/si/ta). A dedicated red **Call 1990** button under the latest emergency reply. A confirmation dialog (Cancel / Open dialer); the dialer fails safely with a "dial 1990 manually" message. |
| `mobile/lib/utils/emergency_dialer.dart` (new) | Opens the dialer through a platform channel. Returns false and never throws if no dialer is available. |
| `mobile/android/app/src/main/kotlin/.../MainActivity.kt` | `mediconnect/emergency_dialer` channel using `Intent.ACTION_DIAL`, which **only pre-fills the number**. The app has no `CALL_PHONE` permission and cannot place a call. Only 3–6 digit numbers are accepted. |
| `mobile/android/app/src/main/AndroidManifest.xml` | `<queries>` entry for `ACTION_DIAL` / `tel:` |
| `mobile/test/screens/ai_assistant_ui_stabilization_test.dart` (new) | 10 regression tests under the real theme and the real emergency contract (section 4) |
| `mobile/test/screens/ai_care_assistant_screen_test.dart`, `ai_assistant_stabilization_test.dart` | Now pump `AppTheme.lightTheme`. Test #8 asserts no exception and the new banner. |
| `docs/MASTER_BUG_TRACKER.md`, `docs/MANUAL_UAT_TEST_PLAN.md`, `docs/AI_AGENT_VERIFICATION_MATRIX.md`, `docs/uat-evidence/2026-11-25/*.png` | Bug entries, P-17 retest procedure, owner's P-01 results log, verification addendum, screenshots |

No backend code was changed, and emergency detection is unchanged.

## 4. Automated test results (2026-11-25, Windows, Flutter 3.47.5)

| Check | Result |
|---|---|
| `flutter analyze` | No issues found |
| `flutter test` (complete suite) | **265 passed**, 0 failed |
| New `ai_assistant_ui_stabilization_test.dart` | 10 passed |
| Same 10 tests with only the one-line fix reverted | **All 10 failed**. 9 fail directly; the normal-reply control passes when run alone, as expected. |
| `flutter build apk --debug --dart-define=API_BASE_URL=http://10.0.2.2:8001` | Built `build/app/outputs/flutter-apk/app-debug.apk` |
| `test/integration/live_api_test.dart` | **Not run on purpose:** it is hard-wired to `http://127.0.0.1:8000`, the production-like Atlas backend that UAT must not touch |
| Backend tests | Not needed: no backend code changed |
| GitHub Actions on `6c2be8f` | **Mobile CI: success** ([run 45545156194](https://github.com/rusiru-242/MediConnect/actions/runs/45545156194)). It was the only workflow triggered: backend and admin-web CI did not run because their files did not change. |

What the new tests cover:
- **Layout:** an existing emergency conversation lays out without an exception. The 1990 button has a finite width. The composer is laid out after an emergency reply.
- **Emergency UI:** banner, dedicated action and hidden chips. A normal reply shows no emergency UI.
- **Calling:** Cancel never dials, and confirm dials exactly `1990` once. A dialer failure shows the manual-dial message.
- **Language:** Sinhala banner for a Sinhala conversation.
- **Keyboard:** 20 open/close cycles.
- **Lifecycle:** 20 cycles of open → emergency → New Chat → Chat History → Back with the keyboard open and a reply pending. A late reply after Back is ignored.
- The composer is counted both as widgets and as **attached `RenderEditable` render objects**, which catches a "ghost" composer. No composer render object remains after Back.

## 5. Emulator verification actually performed

Environment:
- Emulator `sdk gphone64 x86 64` (Android 17, API 37).
- `flutter run --debug --dart-define=API_BASE_URL=http://10.0.2.2:8001`.
- UAT backend on 127.0.0.1:8001: environment `staging`, local MongoDB `mediconnect_uat`, deterministic AI, external image analysis disabled.
- Signed in as the synthetic `uat.patient1`.

| # | Check | Result |
|---|---|---|
| Before fix | Open AI Assistant (latest chat was an emergency) | **Reproduced:** 1 layout exception plus 8 cascading errors; blank body, **no composer** (`before-fix-assistant-blank.png`) |
| 1, 2 | Open AI Assistant (after fix) | One composer; **0 framework exceptions** |
| 12 | Emergency UI (English cardiac emergency) | Red banner with reason, **1990** button, red **Call 1990** under the reply, no routine chips (`after-fix-emergency-banner.png`) |
| 12 | 1990 → Cancel | Dialog shown (`after-fix-1990-confirmation.png`); Cancel kept the app in front |
| 12 | Call 1990 → Open dialer | System dialer opened with 1990 pre-filled. `dumpsys telecom` showed **0 calls**. Call was not pressed. (`after-fix-dialer-prefilled-no-call.png`) |
| 1, 3, 5, 6, 7, 9 | **15 complete automated cycles** (adb-driven) of: open from Home, keyboard open/close twice, New Chat, Chat History open/close, keyboard open + Back twice | One composer at all 4 checkpoints in every cycle (accessibility tree). **0 framework exceptions** in the debug log. The app stayed in front. 61 keyboard openings logged. |
| — | Cycles 16–20 | **Invalid.** The emulator went `offline` during cycle 16 (the host appears to have slept; one step took about 8 hours). The app log shows no crash or exception before `Lost connection to device`. |
| — | Whole debug session after the fix | 0 `EXCEPTION CAUGHT`, 0 `Another exception`, 0 overflow messages |

**Limitation found in my own test script:** the cycles pressed the Enter key to send. On this multiline composer Enter inserts a new line, and the backend confirms **no cycle message was sent**. The 15 cycles therefore prove stability for opening, the keyboard, New Chat, History and Back. They do **not** prove stability for sending messages.

## 6. Not verified on the emulator (pending)

The emulator stayed `offline` after the host slept. Restarting it was refused by the session's permission policy, so these checks are **pending**:
- Sending messages through the on-device composer (steps 4 and 8: multiple messages, and Back while a response is loading).
- Rotation (step 10).
- Image selection and cancellation (step 11).
- Romanized Sinhala and Sinhala-script emergency banner on the device (step 12).
- Normal non-emergency reply on the device (step 13).
- Cycles 16–20.
- A DevTools frame-timing profile.

All of these are covered by widget tests under the real theme, but not on a device.

## 7. Performance observations

- Before the fix, the failure repeated on every relayout: each failed layout printed a full report with a stack trace and laid out the broken subtree again.
- After the fix, the 15 identical cycles took 31.9–32.8 s each, with no upward trend. That suggests no accumulating slowdown, but the timing is dominated by fixed script sleeps, so it is only a coarse signal.
- No frame-timing or DevTools profile was captured.
- Minor, unchanged: while a booking hold is active, the countdown rebuilds the whole screen once per second.

## 8. Remaining limitations and related findings

- **BUG-046 (new, OPEN, not changed here):** the Home **Emergency SOS** dialog shows "Calling National Ambulance Service (1990)…" but never opens the dialer. That is misleading in an emergency. `EmergencyDialer` can be reused to fix it in a small follow-up.
- **Translations:** the new Sinhala and Tamil emergency strings need native-speaker review (with BUG-004).
- **Deferred:** BUG-044 (category-specific emergency guidance) and BUG-004 (Sinhala quality), as agreed.
- **Theme hazard:** the global `minimumSize: Size(double.infinity, …)` in `app_theme.dart` still makes any future `ElevatedButton`/`OutlinedButton` placed directly in a `Row` crash. Changing the theme would affect full-width buttons across the app, so it was left as is. The test harnesses now use the real theme to catch this.
- **Integration test:** `live_api_test.dart` should be made configurable (port 8001) before it can be used in UAT.

## 9. Exact manual retest instructions

1. Start the UAT backend: `powershell -ExecutionPolicy Bypass -File backend/scripts/start_uat_backend.ps1`.
2. Uninstall the old app from the device.
3. Run `cd mobile` and then one of:
   - Emulator: `flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8001`
   - USB phone: `adb reverse tcp:8001 tcp:8001` and `flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8001`
4. Sign in as `uat.patient1`.
5. Run **P-17** in [MANUAL_UAT_TEST_PLAN.md](MANUAL_UAT_TEST_PLAN.md). Send messages with the **send button**, and never press Call in the dialer.
6. Re-run **P-01a–e**. The new banner text is "Possible medical emergency".
7. Then run **P-01f** (Emergency Conversation Memory).
8. If anything fails, copy the **first** `EXCEPTION CAUGHT` block from the `flutter run` output, not the later "Another exception was thrown" lines.

Earlier P-01 results (P-01a–e PARTIAL PASS, P-01f NOT TESTED) are kept as reported in the UAT plan's execution log and are not upgraded by this change.
