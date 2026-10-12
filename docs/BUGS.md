# Bug Tracker & Adversarial Findings

| Bug ID | Severity (S1-S4) | Description | Repro Steps | Owner | Status | Regression Test |
|---|---|---|---|---|---|---|
| BUG-001 | S2 | `send_key()` exception left modifiers (Shift/Ctrl/Alt) logically held down | Call `send_key` with modifiers and invalid key | Input-Engineer | **FIXED & VERIFIED** | `tests/test_adversarial_slice.py::test_adversarial_stuck_modifiers_on_send_key_failure` |
| BUG-002 | S2 | Blind click injection onto closed/dead HWND instead of returning `ELEMENT_GONE` | Cache element, close HWND, speak number | Orchestrator | **FIXED & VERIFIED** | `tests/test_adversarial_slice.py::test_adversarial_click_on_destroyed_window` |
| BUG-003 | S2 | `SCROLL` command crashed on non-int amount with unhandled `TypeError` | Dispatch `SCROLL` with `amount="huge"` | Orchestrator | **FIXED & VERIFIED** | `tests/test_adversarial_slice.py::test_adversarial_scroll_malformed_slots` |
| BUG-004 | S2 | `WhisperSpeechEngine.process_audio` raised `AttributeError: no attribute 'pcm_bytes'` | Ingest `AudioChunk` into Whisper engine | Speech-Engine | **FIXED & VERIFIED** | `tests/test_adversarial_slice.py::test_adversarial_whisper_engine_contract` |
| BUG-005 | S2 | Engine executed commands while in `EngineMode.SLEEP` | Say "go to sleep", then speak active command | Orchestrator | **FIXED & VERIFIED** | `tests/test_adversarial_slice.py::test_adversarial_sleep_mode_isolation` |
| BUG-006 | S3 | Empty query in `fuzzy_match_element` matched all elements with 0.85 confidence | Dispatch `CLICK_NAME` with `name=""` | Command-NLU | **FIXED & VERIFIED** | `tests/test_adversarial_slice.py::test_adversarial_click_name_empty_string` |
| BUG-007 | S3 | `register_custom_command` crashed on regex metacharacters or multiple placeholders | Register `open [file` or `find <text> in <text>` | Command-NLU | **FIXED & VERIFIED** | `tests/test_adversarial_slice.py::test_adversarial_custom_command_regex_injection` |
| BUG-008 | S3 | Number badges for element IDs >= 300 were missing from cache | Render overlay with element ID >= 300 | Overlay-UI | **FIXED & VERIFIED** | `tests/test_adversarial_slice.py::test_adversarial_overlay_badge_cache_limit` |
| BUG-009 | S3 | Screen grid sub-cell width/height collapsed to 0 after deep recursive drill-down | Drill down grid 10 levels deep | Overlay-UI | **FIXED & VERIFIED** | `tests/test_adversarial_round2.py::test_adversarial_grid_extreme_drill_down` |
| BUG-010 | S3 | `CustomCommandLoader.load_from_dict` crashed on `commands: None` or non-dict items | Pass `{"commands": None}` or non-dict items | Command-NLU | **FIXED & VERIFIED** | `tests/test_adversarial_round2.py::test_adversarial_custom_commands_malformed_structures` |
