# Adversarial Round 1 Attack Report: Phase 2 Core Vertical Slice

**Date**: 2026-10-13  
**Auditor**: Adversary Subagent (`VoxPilot`)  
**Target**: Phase 2 Core Vertical Slice (Audio/FakeMic -> Vosk STT -> Command-NLU -> UIA Provider -> Overlay -> SendInput)  
**Status**: Completed  
**Outcome**: 17 Test Scenarios Executed (9 Passed Robustness Attacks, 8 Actionable Vulnerabilities Discovered & Documented)

---

## Executive Summary

During Phase 2 Vertical Slice qualification, the Adversary conducted an intensive stress and security test against all pipeline stages. The target demonstrated commendable performance and resilience under several high-stress conditions:
- **Audio Capture & STT Resilience**: Feeding zero-byte, odd-byte (1-byte unaligned PCM), random noise (16KB), digital clipping, and 10 seconds of pure silence into `VoskSpeechEngine` caused no segmentation faults, deadlocks, or uncaught exceptions.
- **Rapid Fire Burst Robustness**: Rapid alternations between `show numbers`, `hide numbers`, clicks, and out-of-bounds requests executed cleanly without memory leakage or thread exhaustion.
- **Out-of-Bounds Number Handling**: Requesting element #999 when only ~50 exist cleanly produced typed `CommandStatus.ELEMENT_GONE` (`ERR_ELEMENT_NOT_FOUND`) responses.

However, the attack exposed **8 distinct vulnerabilities** across input injection safety, window lifecycle synchronization, dispatch error handling, contract alignment, speech mode isolation, fuzzy matching, custom command regex security, and overlay caching limits.

---

## Attack Matrix & Results

| Vector ID | Attack Target | Description / Injected Payload | Expected Behavior | Observed Result | Verdict |
|---|---|---|---|---|---|
| **ATK-01** | Rapid Fire Bursts | `["show numbers", "hide numbers", "show numbers", "1", "999", "banana"]` in rapid succession | Smooth state transitions, HUD updates, overlay dismissal | Executed seamlessly, correct final states, 6/6 history tracked | **PASS** |
| **ATK-02** | Rapid Fire Stress | 50 rapid alternating show/hide numbers commands with zero delay | No thread contention, no UI lockup | 50 calls completed in < 4s, clean overlay state | **PASS** |
| **ATK-03** | Out-of-Bounds IDs | Requests for IDs `999`, `1000`, `0`, and `N+10` | Rejection with `ELEMENT_GONE` or `NO_MATCH` | Clean rejection (`ERR_ELEMENT_NOT_FOUND` / `NO_MATCH`), no crash | **PASS** |
| **ATK-04** | Invalid HWND Discovery | HWND `0xDEADBEEF` passed to `discover_elements()` | Graceful return of empty list | Returned `[]` without throwing exceptions | **PASS** |
| **ATK-05** | Dead Window Click Injection | Target window closed after discovery; user speaks `"1"` | Engine detects dead HWND (`IsWindow`) -> `ELEMENT_GONE` | **Blind click injected at stale (cx, cy); returns SUCCESS** | **VULN (BUG-002)** |
| **ATK-06** | Modifier Release on Stop | Sudden `engine.stop()` while modifiers held | Clean release of Shift, Ctrl, Alt, Win | All modifiers released via `release_all_modifiers()` | **PASS** |
| **ATK-07** | Stuck Modifiers on Error | `send_key("INVALID_KEY", modifiers=['ctrl', 'shift'])` | Cleanup modifiers in `finally` block | **Modifiers remain logically held down forever** | **VULN (BUG-001)** |
| **ATK-08** | Corrupted Audio Streams | Empty bytes, odd 1-byte PCM, random noise, square clipping | No crash, recognizer stays healthy | 14 chunks processed without error, metrics tracked | **PASS** |
| **ATK-09** | 10s Digital Silence | 320,000 bytes of `0x00` fed across 10 chunks + flush | No hang, clean silence endpoint | Processed cleanly without hang | **PASS** |
| **ATK-10** | Grammar Dynamic Fuzzing | Emojis (`😀`), control chars (`\x00`), newlines, quotes in grammar | Vosk safely encodes grammar | `set_grammar` and recognition completed normally | **PASS** |
| **ATK-11** | Malformed Intent Basics | Empty name, unknown intent, missing number slot, huge int | Typed `NO_MATCH` or `ELEMENT_GONE` | Handled cleanly by dispatcher | **PASS** |
| **ATK-12** | SCROLL Malformed Slots | `SCROLL` intent with `amount=None` or string `"huge"` | Error result returned | **Unhandled `TypeError` crashes `dispatch_intent`** | **VULN (BUG-003)** |
| **ATK-13** | Empty Query Fuzzy Click | `CLICK_NAME` with `slots={"name": ""}` | Rejection (`ELEMENT_NOT_FOUND`) | **Matches every element (0.85); blind clicks control** | **VULN (BUG-006)** |
| **ATK-14** | Whisper Contract Breach | Feed `AudioChunk` into `WhisperSpeechEngine.process_audio` | Buffer accumulation | **Crashes: `AttributeError: no attribute 'pcm_bytes'`** | **VULN (BUG-004)** |
| **ATK-15** | Sleep Mode Containment | Issue commands after `go to sleep` (`EngineMode.SLEEP`) | Ignore all commands except `WAKE_UP` | **Commands execute freely while engine is asleep** | **VULN (BUG-005)** |
| **ATK-16** | Custom Command ReDoS / Regex | Register pattern `open [file` or `find <text> in <text>` | Sanitized regex or validation error | **`PatternError` bricks parser for all future utterances** | **VULN (BUG-007)** |
| **ATK-17** | Badge Cache Exhaustion | Show numbers for element with ID >= 300 | Badges displayed for all valid IDs (1-999) | **Badges for ID >= 300 are missing from cache and invisible** | **VULN (BUG-009)** |

---

## Detailed Vulnerability Analysis

### 1. BUG-001 (Severity S2): Stuck Modifiers on Input Injection Error
- **Location**: `src/voxpilot/input/input_injector.py` (`send_key`)
- **Mechanism**:
  ```python
  def send_key(self, key: str, modifiers: Optional[List[str]] = None) -> None:
      mods = modifiers or []
      for m in mods:
          self.key_down(m)  # Ctrl, Shift pressed down
      time.sleep(0.01)
      self.key_down(key)    # If key is invalid -> raises InputInjectionError!
      time.sleep(0.01)
      self.key_up(key)
      for m in reversed(mods):
          self.key_up(m)    # NEVER REACHED!
  ```
- **Impact**: Any typo, invalid key name, or injection exception leaves physical keyboard modifiers logically stuck down on the host operating system. Clicks turn into Ctrl-clicks, typing turns into shortcut execution.
- **Recommended Remediation**: Wrap `self.key_down(key)` in a `try...finally:` block ensuring `for m in reversed(mods): self.key_up(m)` is always guaranteed to execute.

---

### 2. BUG-002 (Severity S2): Blind Click-Through Injection onto Destroyed Windows
- **Location**: `src/voxpilot/engine.py` (`_handle_click_number`, `_handle_click_name`)
- **Mechanism**:
  When a user commands "show numbers", elements are cached. If the window is subsequently closed or crashes, `_handle_click_number` retrieves the cached element and directly executes:
  ```python
  cx, cy = element.rect.center()
  self.input_injector.click_at(cx, cy, button=button, count=count)
  return CommandResult.success(...)
  ```
  It does NOT check `user32.IsWindow(element.window_handle)`.
- **Impact**: Physical mouse clicks are injected into whatever application or desktop icons are located underneath the destroyed window. Can trigger unintended file deletions, closing arbitrary background apps, or activating sensitive controls.
- **Recommended Remediation**: Validate `user32.IsWindow(element.window_handle)` before clicking. If false, return `CommandResult(status=CommandStatus.ELEMENT_GONE, code="ERR_WINDOW_GONE", message="Target window has closed")`.

---

### 3. BUG-003 (Severity S2): Unhandled TypeErrors in `SCROLL` Dispatch
- **Location**: `src/voxpilot/engine.py` (`dispatch_intent`), `src/voxpilot/input/input_injector.py` (`scroll`)
- **Mechanism**:
  If `intent.slots.get("amount")` is `None` or not an integer (e.g. parsed from malformed NLU or custom command), `input_injector.scroll` executes:
  ```python
  delta = -amount  # TypeError: bad operand type for unary -: 'NoneType'
  inp.u.mi.mouseData = delta & 0xFFFFFFFF  # TypeError: unsupported operand type for &: 'str' and 'int'
  ```
  `VoxPilotEngine.dispatch_intent` has no exception guard.
- **Impact**: Unhandled exception completely crashes the engine dispatcher loop.
- **Recommended Remediation**: Validate and cast `amount = int(intent.slots.get("amount", 120))` with a fallback default in both `engine.py` and `input_injector.py`. Wrap `dispatch_intent` in a top-level error handler returning `CommandResult.error()`.

---

### 4. BUG-004 (Severity S2): Whisper Dictation Engine Contract Breach
- **Location**: `src/voxpilot/speech/whisper_engine.py` (`process_audio`)
- **Mechanism**:
  Line 43 accesses `chunk.pcm_bytes`, but `AudioChunk` DTO defines `data: bytes`:
  ```python
  def process_audio(self, chunk: AudioChunk) -> None:
      if not self._is_running:
          return
      self._buffer.append(chunk.pcm_bytes)  # AttributeError!
  ```
- **Impact**: Dictation mode cannot ingest audio chunks; raises unhandled `AttributeError` upon first audio packet.
- **Recommended Remediation**: Change `chunk.pcm_bytes` to `chunk.data`.

---

### 5. BUG-005 (Severity S2): Command Bypass in Engine SLEEP Mode
- **Location**: `src/voxpilot/engine.py` (`process_text_command`, `dispatch_intent`)
- **Mechanism**:
  When "go to sleep" is executed, `self.mode` is set to `EngineMode.SLEEP`. However, `process_text_command` performs no check on `self.mode`:
  ```python
  def process_text_command(self, phrase: str) -> CommandResult:
      intent = self.command_parser.parse(phrase)
      # No mode check!
      res = self.dispatch_intent(intent)
  ```
- **Impact**: While the user believes VoxPilot is asleep, any spoken commands or accidental utterances continue executing mouse clicks and displaying overlays.
- **Recommended Remediation**: In `process_text_command` / `dispatch_intent`, if `self.mode == EngineMode.SLEEP` and `intent.name != "WAKE_UP"`, ignore the command or return `CommandResult(status=CommandStatus.BLOCKED, message="Engine is asleep")`.

---

### 6. BUG-006 (Severity S3): Empty Query False-Positive in `fuzzy_match_element`
- **Location**: `src/voxpilot/commands/command_parser.py` (`fuzzy_match_element`)
- **Mechanism**:
  Line 179 performs:
  ```python
  if q in name:
      score = 0.85 + (len(q) / len(name)) * 0.1
      matches.append((el, round(score, 3)))
  ```
  When `query` is empty string (`""`), `"" in name` evaluates to `True` for every string! All elements score 0.85 (> threshold 0.70). The first element is returned as the "best match".
- **Impact**: If a user utters an incomplete phrase ("click ") or an empty name is dispatched, VoxPilot immediately clicks whatever element happens to be first in the cache.
- **Recommended Remediation**: Guard with `if not q: return []` at the entry of `fuzzy_match_element`.

---

### 7. BUG-007 (Severity S3): Regex Injection in Custom Command Registration
- **Location**: `src/voxpilot/commands/command_parser.py` (`register_custom_command`)
- **Mechanism**:
  Patterns are constructed by unescaped string substitution:
  ```python
  regex = "^" + trigger_pattern.replace("<text>", r"(?P<text>.+)").replace("<number>", r"(?P<number>\d+)") + "$"
  ```
  If `trigger_pattern` contains brackets `[` or multiple identical placeholders (e.g. `find <text> in <text>`), compiling or matching raises `PatternError: redefinition of group name` or `unterminated character set`.
- **Impact**: Every subsequent call to `command_parser.parse()` crashes, bricking voice control for all commands.
- **Recommended Remediation**: Validate regex syntax and uniquely index group names (e.g. `text_1`, `text_2`), or escape regex metacharacters in literal segments before injecting capture groups.

---

### 8. BUG-008 (Severity S3): Overlay Canvas Badges Invisible for Element IDs >= 300
- **Location**: `src/voxpilot/overlay/overlay_service.py` (`OverlayCanvas`)
- **Mechanism**:
  `_pre_render_badges` only caches badges for IDs 1 through 299:
  ```python
  for i in range(1, 300):
      ...
  ```
  In `paintEvent`:
  ```python
  pix = self.badge_cache.get(key)
  if pix:
      painter.drawPixmap(...)
  ```
  For element ID >= 300, `pix` is `None` and no badge is drawn.
- **Impact**: In applications with > 300 controls, elements numbered 300-999 receive no visible badge on screen, making them impossible for the user to target by voice.
- **Recommended Remediation**: Expand pre-rendered cache up to 999 or add on-demand rendering fallback when `pix is None`.

---

## Test Suite Execution Evidence

All adversarial attack vectors were formalized into `tests/test_adversarial_slice.py`.

```
============================= test session starts =============================
platform win32 -- Python 3.14.2, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\anshw\Documents\Voxpilot
configfile: pytest.ini
testpaths: tests
collected 45 items

tests\test_adversarial_slice.py ....x..x...xxxxxx                        [ 37%]
tests\test_commands.py ............                                      [ 64%]
tests\test_contracts.py ...........                                      [ 88%]
tests\test_targets_e2e.py ...                                            [ 95%]
tests\test_vertical_slice_e2e.py ..                                      [100%]

======================= 37 passed, 8 xfailed in 26.71s ========================
```

The test suite achieves **100% clean test execution (0 regressions)** with the 8 vulnerabilities formally documented as tracked `xfailed` regression tests that will automatically transition to `XPASS` upon resolution.
