# VoxPilot Voice Commands Reference Catalog

An exhaustive catalog of all built-in voice commands, variations, arguments, and hotkey mappings in VoxPilot.

---

## 1. System & Engine Control

| Command Intent | Primary Phrases & Synonyms | Action / Description |
|---|---|---|
| `WAKE_UP` | `"wake up"`, `"voxpilot wake up"`, `"wake up voxpilot"`, `"start listening"`, `"hey voxpilot wake up"` | Resumes listening from Sleep mode. Re-enables voice recognition. |
| `GO_TO_SLEEP` | `"go to sleep"`, `"voxpilot go to sleep"`, `"put voxpilot to sleep"`, `"sleep"`, `"stop listening"` | Suspends microphone listening. Hides overlays and HUD. Ignores all commands except `WAKE_UP`. |
| `MUTE` | `"mute"`, `"mute microphone"`, `"mic mute"` | Mutes microphone input. |
| `UNMUTE` | `"unmute"`, `"unmute microphone"` | Unmutes microphone input. |
| `SHOW_COMMANDS` | `"show commands"`, `"what can i say"`, `"help"` | Displays command catalog help overlay or logs available commands. |

---

## 2. Element Numbering & Direct Interaction

| Command Intent | Primary Phrases & Synonyms | Action / Description |
|---|---|---|
| `SHOW_NUMBERS` | `"show numbers"`, `"please show numbers"`, `"numbers on"`, `"show numbers everywhere"` | Discovers all interactive UI controls and displays amber badge numbers. |
| `HIDE_NUMBERS` | `"hide numbers"`, `"numbers off"`, `"hide the numbers"`, `"remove numbers"` | Dismisses all numbered element badges. |
| `SHOW_NAMES` | `"show names"`, `"names on"` | Displays element badges with accessible name text instead of numbers. |
| `HIDE_NAMES` | `"hide names"`, `"names off"` | Dismisses name badges. |
| `CLICK_NUMBER` | `"<number>"`, `"click <number>"`, `"hit <number>"`, `"press <number>"` (e.g. `"12"`, `"click twelve"`, `"click 5"`) | Clicks the center point of the specified element ID immediately without confirmation. |
| `DOUBLE_CLICK_NUMBER` | `"double click <number>"`, `"double click five"` | Performs a fast double-click on the specified element. |
| `RIGHT_CLICK_NUMBER` | `"right click <number>"`, `"right click seven"` | Performs a right-click to open context menus. |
| `CLICK_NAME` | `"click <name>"`, `"click save"`, `"click submit"`, `"click search"` | Clicks the best fuzzy-matched interactive element sharing the spoken name. |
| `SCROLL` | `"scroll down"`, `"scroll up"`, `"scroll down 3"`, `"scroll down a bit"` | Synthesizes mouse wheel scroll events (default 120 units; multiplies by numeric factor if given). |

---

## 3. Recursive Screen Grid Navigation

| Command Intent | Primary Phrases & Synonyms | Action / Description |
|---|---|---|
| `SHOW_GRID` | `"show grid"`, `"grid on"`, `"show me the screen grid"` | Overlays a transparent 3x3 grid dividing the screen into cells 1–9. |
| `HIDE_GRID` | `"hide grid"`, `"grid off"`, `"cancel grid"` | Closes the screen grid overlay without taking action. |
| `DRILL_DOWN_GRID` | `"drill down <cell>"`, `"zoom in <cell>"`, `"zoom into <cell>"` (e.g. `"drill down 5"`, `"zoom into 9"`) | Subdivides the specified cell into a new 3x3 numbered sub-grid. Supports up to 10 recursive levels. |
| `UNDO_GRID` | `"undo grid"`, `"zoom out"`, `"back"` | Steps back up one level in the grid drill-down hierarchy. |
| `CLICK_GRID_CELL` | `"<cell>"`, `"click <cell>"` (e.g. `"5"`, `"click 3"`) | Clicks the center of the specified cell and dismisses the grid. |

---

## 4. Dictation Mode & Text Input

| Command Intent | Primary Phrases & Synonyms | Action / Description |
|---|---|---|
| `START_DICTATION` | `"start dictation"`, `"dictate"`, `"dictation mode"` | Enters continuous dictation mode. Routes all spoken text into focused field. |
| `STOP_DICTATION` | `"stop dictation"`, `"command mode"`, `"exit dictation"` | Exits dictation mode and returns to Command Mode. |

### 4.1 Spoken Punctuation Transformations

| Spoken Phrase | Rendered Symbol |
|---|---|
| `"period"`, `"full stop"` | `.` |
| `"comma"` | `,` |
| `"question mark"` | `?` |
| `"exclamation mark"`, `"exclamation point"` | `!` |
| `"colon"` | `:` |
| `"semicolon"` | `;` |
| `"dash"`, `"hyphen"` | `-` |
| `"quote"`, `"quotation mark"` | `"` |
| `"apostrophe"` | `'` |
| `"slash"` | `/` |
| `"backslash"` | `\` |
| `"at sign"` | `@` |
| `"hash"`, `"pound sign"` | `#` |
| `"dollar sign"`, `"dollar"` | `$` |
| `"percent"`, `"percent sign"` | `%` |
| `"ampersand"` | `&` |
| `"asterisk"`, `"star"` | `*` |
| `"underscore"` | `_` |
| `"new line"`, `"newline"`, `"next line"` | `\n` (Enter) |
| `"new paragraph"` | `\n\n` (Double Enter) |

### 4.2 Entity & Normalization Rules

| Spoken Dictation Phrase | Automatically Formatted Text |
|---|---|
| `"send dollar 150 to account"` | `Send $150 to account` |
| `"increased by 25 percent"` | `Increased by 25%` |
| `"release date is january 15 2026"` | `Release date is January 15, 2026` |
| `"alex at voxpilot dot com"` | `alex@voxpilot.com` |
| `"https colon slash slash github dot com"` | `https://github.com` |
| `"config dot json"` | `config.json` |
| `"capitalize voxpilot"` | `Voxpilot` |
| `"all caps emergency"` | `EMERGENCY` |
| `"lowercase text"` | `lowercase text` |

---

## 5. Spoken Text Editing & Navigation

| Command Intent | Spoken Phrases | Action / Shortcut Synthesized |
|---|---|---|
| `SCRATCH_THAT` | `"scratch that"`, `"delete that"`, `"undo that"` | Reverses and deletes the entire preceding spoken text burst. |
| `DELETE_LAST_WORD` | `"delete last word"` | Deletes preceding word (Ctrl + Backspace). |
| `DELETE_LINE` | `"delete line"` | Clears current line (Home, Shift + End, Delete). |
| `SELECT_ALL` | `"select all"` | Selects all text (Ctrl + A). |
| `COPY` | `"copy"`, `"copy that"` | Copies selected text (Ctrl + C). |
| `PASTE` | `"paste"`, `"paste that"` | Pastes clipboard content (Ctrl + V). |
| `CUT` | `"cut"`, `"cut that"` | Cuts selected text (Ctrl + X). |
| `GO_TO_START` | `"go to start of line"`, `"line start"` | Moves cursor to start of current line (Home). |
| `GO_TO_END` | `"go to end of line"`, `"line end"` | Moves cursor to end of current line (End). |
| `SELECT_PHRASE` | `"select <phrase>"` | Searches and selects target text. |
| `REPLACE_PHRASE` | `"replace <old> with <new>"` | Replaces target phrase with new phrase. |

---

## 6. NATO Phonetic Alphabet (Spelling Mode)

Prefix your phrase with `"spell ..."` to type individual letters or acronyms:

| NATO Word | Letter Typed | NATO Word | Letter Typed |
|---|---|---|---|
| `alpha` | `A` | `november` | `N` |
| `bravo` | `B` | `oscar` | `O` |
| `charlie` | `C` | `papa` | `P` |
| `delta` | `D` | `quebec` | `Q` |
| `echo` | `E` | `romeo` | `R` |
| `foxtrot` / `fox` | `F` | `sierra` | `S` |
| `golf` | `G` | `tango` | `T` |
| `hotel` | `H` | `uniform` | `U` |
| `india` | `I` | `victor` | `V` |
| `juliet` | `J` | `whiskey` | `W` |
| `kilo` | `K` | `xray` | `X` |
| `lima` | `L` | `yankee` | `Y` |
| `mike` | `M` | `zulu` | `Z` |

*Example:* `"spell alpha bravo charlie"` -> Types `ABC`.

---

## 7. Windows Desktop & App Management

| Command Intent | Spoken Phrases | Windows Shortcut |
|---|---|---|
| `SNAP_WINDOW_LEFT` | `"snap left"`, `"snap window left"`, `"snap this left"` | Win + Left Arrow |
| `SNAP_WINDOW_RIGHT` | `"snap right"`, `"snap window right"`, `"snap this right"` | Win + Right Arrow |
| `SNAP_WINDOW_UP` | `"snap up"`, `"snap window top"` | Win + Up Arrow |
| `SNAP_WINDOW_DOWN` | `"snap down"`, `"snap window bottom"` | Win + Down Arrow |
| `MAXIMIZE_WINDOW` | `"maximize window"`, `"maximize"` | Win + Up Arrow |
| `MINIMIZE_WINDOW` | `"minimize window"`, `"minimize"` | Win + Down Arrow |
| `RESTORE_WINDOW` | `"restore window"` | Win + Down Arrow |
| `CLOSE_WINDOW` | `"close window"`, `"close app"` | Alt + F4 |
| `SWITCH_APP` | `"switch app"`, `"switch window"`, `"alt tab"` | Alt + Tab |
| `TASK_VIEW` | `"task view"` | Win + Tab |
| `SHOW_DESKTOP` | `"show desktop"` | Win + D |
| `NEXT_DESKTOP` | `"next desktop"` | Win + Ctrl + Right Arrow |
| `PREVIOUS_DESKTOP` | `"previous desktop"`, `"prior desktop"` | Win + Ctrl + Left Arrow |
| `PAGE_UP` | `"page up"` | Page Up |
| `PAGE_DOWN` | `"page down"` | Page Down |

---

## 8. Keyboard Chords & Key Repeats

### 8.1 Key Chords
Speak `"press <chord>"` with two or more keys:
- `"press ctrl shift t"` -> Reopen closed tab
- `"press alt f4"` -> Close window
- `"press ctrl w"` -> Close tab
- `"press win r"` -> Run dialog
- `"press ctrl alt delete"` -> Windows security screen

### 8.2 Key Repeats
Speak `"press <key> <n> times"`:
- `"press down 5 times"` -> Injects Down Arrow 5 times
- `"press backspace 3 times"` -> Injects Backspace 3 times
- `"press tab 4 times"` -> Injects Tab 4 times
- `"press enter 2 times"` -> Injects Enter 2 times

---

## 9. Custom Command Configuration Schema

User commands are defined in `%LOCALAPPDATA%\VoxPilot\custom_commands.yaml`:

```yaml
commands:
  # Hotkey action
  - phrase: "reopen tab"
    action: "hotkey"
    keys: ["ctrl", "shift", "t"]

  # Text boilerplate injection
  - phrase: "insert address"
    action: "text"
    text: "123 Innovation Way, Suite 400"

  # Executable invocation
  - phrase: "launch calculator"
    action: "command"
    command: "calc.exe"
```
