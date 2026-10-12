"""
VoxPilot Command Parser & NLU Implementation
Owned by: Command-NLU
Implements: ICommandParser
"""

import re
from typing import Optional, List, Tuple, Dict, Any
from voxpilot.contracts.dto import Intent, FocusState, LabeledElement
from .number_parser import NumberParser

class CommandParser:
    """Grammar matching, slot extraction, fuzzy name matching, and command catalog."""

    def __init__(self) -> None:
        self.custom_commands: List[Dict[str, Any]] = []
        self._init_builtins()

    def _init_builtins(self) -> None:
        self.builtins: List[Dict[str, Any]] = [
            {"intent": "SHOW_NUMBERS", "patterns": [r"^(?:please\s+)?show\s+numbers(?:\s+everywhere)?$", r"^numbers\s+on$"]},
            {"intent": "HIDE_NUMBERS", "patterns": [r"^(?:please\s+)?(?:hide|remove)\s+(?:the\s+)?numbers$", r"^numbers\s+off$"]},
            {"intent": "SHOW_NAMES", "patterns": [r"^(?:please\s+)?show\s+names$", r"^names\s+on$"]},
            {"intent": "HIDE_NAMES", "patterns": [r"^(?:please\s+)?hide\s+names$", r"^names\s+off$"]},
            {"intent": "SHOW_GRID", "patterns": [r"^(?:show|show me)?\s*(?:the\s+)?(?:screen\s+)?grid$", r"^grid\s+on$"]},
            {"intent": "HIDE_GRID", "patterns": [r"^(?:please\s+)?hide\s+grid$", r"^grid\s+off$", r"^cancel\s+grid$"]},
            {"intent": "SHOW_COMMANDS", "patterns": [r"^show\s+commands$", r"^what\s+can\s+i\s+say$"]},
            {"intent": "WAKE_UP", "patterns": [r"^(?:voxpilot\s+)?wake\s+up(?:\s+voxpilot)?$", r"^start\s+listening$"]},
            {"intent": "GO_TO_SLEEP", "patterns": [r"^(?:put\s+voxpilot\s+to\s+sleep|go\s+to\s+sleep|stop\s+listening|sleep)$"]},
            {"intent": "MUTE", "patterns": [r"^mute(?:\s+microphone)?$"]},
            {"intent": "UNMUTE", "patterns": [r"^unmute(?:\s+microphone)?$"]},
            {"intent": "START_DICTATION", "patterns": [r"^start\s+dictation$", r"^dictate$", r"^dictation\s+mode$"]},
            {"intent": "STOP_DICTATION", "patterns": [r"^stop\s+dictation$", r"^command\s+mode$"]},
            {"intent": "PRESS_ENTER", "patterns": [r"^press\s+enter$", r"^hit\s+enter$", r"^enter$"]},
            {"intent": "PRESS_ESCAPE", "patterns": [r"^press\s+escape$", r"^escape$", r"^cancel$"]},
            {"intent": "PRESS_TAB", "patterns": [r"^press\s+tab$", r"^tab$"]},
            {"intent": "PRESS_BACKSPACE", "patterns": [r"^backspace$", r"^delete\s+character$"]},
            {"intent": "DELETE_LAST_WORD", "patterns": [r"^delete\s+last\s+word$"]},
            {"intent": "COPY", "patterns": [r"^copy(?:\s+that)?$"]},
            {"intent": "CUT", "patterns": [r"^cut(?:\s+that)?$"]},
            {"intent": "PASTE", "patterns": [r"^paste(?:\s+that)?$"]},
            {"intent": "SELECT_ALL", "patterns": [r"^select\s+all$"]},
            {"intent": "UNDO", "patterns": [r"^undo(?:\s+that)?$", r"^scratch\s+that$"]},
            {"intent": "REDO", "patterns": [r"^redo(?:\s+that)?$"]},
            {"intent": "CLOSE_WINDOW", "patterns": [r"^close\s+window$", r"^close\s+app$"]},
            {"intent": "MINIMIZE_WINDOW", "patterns": [r"^minimize\s+window$", r"^minimize$"]},
            {"intent": "MAXIMIZE_WINDOW", "patterns": [r"^maximize\s+window$", r"^maximize$"]},
            {"intent": "RESTORE_WINDOW", "patterns": [r"^restore\s+window$"]},
            {"intent": "SHOW_DESKTOP", "patterns": [r"^show\s+desktop$"]},
            {"intent": "SNAP_WINDOW_LEFT", "patterns": [r"^(?:snap|snap window|snap this)(?:\s+to)?(?:\s+the)?\s+left$"]},
            {"intent": "SNAP_WINDOW_RIGHT", "patterns": [r"^(?:snap|snap window|snap this)(?:\s+to)?(?:\s+the)?\s+right$"]},
            {"intent": "SNAP_WINDOW_UP", "patterns": [r"^(?:snap|snap window|snap this)(?:\s+to)?(?:\s+the)?\s+(?:up|top)$"]},
            {"intent": "SNAP_WINDOW_DOWN", "patterns": [r"^(?:snap|snap window|snap this)(?:\s+to)?(?:\s+the)?\s+(?:down|bottom)$"]},
            {"intent": "SWITCH_APP", "patterns": [r"^(?:switch app|switch window|alt tab)$", r"^switch to next app$"]},
            {"intent": "TASK_VIEW", "patterns": [r"^task view$"]},
            {"intent": "NEXT_DESKTOP", "patterns": [r"^next desktop$"]},
            {"intent": "PREVIOUS_DESKTOP", "patterns": [r"^(?:previous|prior) desktop$"]},
            {"intent": "PAGE_UP", "patterns": [r"^page up$"]},
            {"intent": "PAGE_DOWN", "patterns": [r"^page down$"]},
            {"intent": "UNDO_GRID", "patterns": [r"^(?:zoom out|undo grid|back)$"]},
        ]

    def normalize_number(self, phrase: str) -> Optional[int]:
        return NumberParser.parse_number_phrase(phrase)

    def parse(self, text: str, context: Optional[FocusState] = None) -> Optional[Intent]:
        cleaned = text.strip().lower()
        cleaned = re.sub(r"[.,?!]", "", cleaned)
        # Strip common speech fillers and polite prefixes/suffixes
        cleaned = re.sub(r"^(?:uh+|um+|please|can you|could you|would you)\s+", "", cleaned)
        cleaned = re.sub(r"^(?:hey\s+voxpilot|voxpilot)\s+", "", cleaned)
        cleaned = re.sub(r"\s+(?:please|for me|now)$", "", cleaned)
        cleaned = cleaned.strip()
        if not cleaned:
            return None

        num = self.normalize_number(cleaned)
        if num is not None and 1 <= num <= 999:
            return Intent(
                name="CLICK_NUMBER",
                confidence=0.98,
                slots={"number": num},
                raw_text=text,
            )

        # Check key repeat e.g. "press down 5 times", "press tab 3 times"
        m_repeat = re.match(r"^(?:press|hit)\s+([a-z0-9]+)\s+([a-z0-9]+)\s+times?$", cleaned)
        if m_repeat:
            k_name = m_repeat.group(1).strip()
            c_phrase = m_repeat.group(2).strip()
            count = self.normalize_number(c_phrase) or 1
            return Intent(name="KEY_REPEAT", confidence=0.95, slots={"key": k_name, "count": count}, raw_text=text)

        # Check keyboard chord e.g. "press ctrl shift t", "press alt f4", "press ctrl w"
        m_chord = re.match(r"^(?:press|hit)\s+((?:(?:ctrl|control|shift|alt|win|windows)\s+)+[a-z0-9f]+)$", cleaned)
        if m_chord:
            chord_tokens = m_chord.group(1).split()
            if len(chord_tokens) >= 2:
                return Intent(name="KEY_COMBINATION", confidence=0.95, slots={"keys": chord_tokens}, raw_text=text)

        m_click_num = re.match(r"^(?:please\s+)?(?:click|press|hit)(?:\s+on)?(?:\s+number)?\s+(.+)$", cleaned)
        if m_click_num:
            target_phrase = m_click_num.group(1).strip()
            num = self.normalize_number(target_phrase)
            if num is not None and 1 <= num <= 999:
                return Intent(
                    name="CLICK_NUMBER",
                    confidence=0.99,
                    slots={"number": num},
                    raw_text=text,
                )
            else:
                return Intent(
                    name="CLICK_NAME",
                    confidence=0.90,
                    slots={"name": target_phrase},
                    raw_text=text,
                )

        m_dbl = re.match(r"^(?:please\s+)?double\s+click\s+(.+)$", cleaned)
        if m_dbl:
            target_phrase = m_dbl.group(1).strip()
            num = self.normalize_number(target_phrase)
            if num is not None:
                return Intent(name="DOUBLE_CLICK_NUMBER", confidence=0.99, slots={"number": num}, raw_text=text)
            return Intent(name="DOUBLE_CLICK_NAME", confidence=0.90, slots={"name": target_phrase}, raw_text=text)

        m_right = re.match(r"^(?:please\s+)?right\s+click\s+(.+)$", cleaned)
        if m_right:
            target_phrase = m_right.group(1).strip()
            num = self.normalize_number(target_phrase)
            if num is not None:
                return Intent(name="RIGHT_CLICK_NUMBER", confidence=0.99, slots={"number": num}, raw_text=text)
            return Intent(name="RIGHT_CLICK_NAME", confidence=0.90, slots={"name": target_phrase}, raw_text=text)

        m_scroll = re.match(r"^scroll\s+(up|down|left|right)(?:\s+(.+))?$", cleaned)
        if m_scroll:
            direction = m_scroll.group(1)
            amount_phrase = m_scroll.group(2)
            amount = 120
            if amount_phrase:
                parsed_amt = self.normalize_number(amount_phrase)
                if parsed_amt is not None:
                    amount = parsed_amt * 120
            return Intent(
                name="SCROLL",
                confidence=0.95,
                slots={"direction": direction, "amount": amount},
                raw_text=text,
            )

        # Check grid drill down e.g. "drill down 5", "zoom in 5", "zoom into 5"
        m_drill = re.match(r"^(?:drill down|zoom in|zoom into|drill into|subdivide)\s+(.+)$", cleaned)
        if m_drill:
            target_str = m_drill.group(1).strip()
            num = self.normalize_number(target_str)
            if num is not None and 1 <= num <= 9:
                return Intent(name="DRILL_DOWN_GRID", confidence=0.98, slots={"cell": num}, raw_text=text)

        # Check key repeat e.g. "press down 5 times", "press tab 3 times"
        m_repeat = re.match(r"^(?:press|hit)\s+([a-z0-9]+)\s+([a-z0-9]+)\s+times?$", cleaned)
        if m_repeat:
            k_name = m_repeat.group(1).strip()
            c_phrase = m_repeat.group(2).strip()
            count = self.normalize_number(c_phrase) or 1
            return Intent(name="KEY_REPEAT", confidence=0.95, slots={"key": k_name, "count": count}, raw_text=text)

        # Check keyboard chord e.g. "press ctrl shift t", "press alt f4", "press ctrl w"
        m_chord = re.match(r"^press\s+((?:[a-z0-9]+\s+)+[a-z0-9]+)$", cleaned)
        if m_chord:
            chord_tokens = m_chord.group(1).split()
            if len(chord_tokens) >= 2:
                return Intent(name="KEY_COMBINATION", confidence=0.95, slots={"keys": chord_tokens}, raw_text=text)

        # Check custom registered commands
        for cmd in self.custom_commands:
            compiled = cmd.get("compiled")
            if compiled:
                m = compiled.match(cleaned)
                if m:
                    slots = m.groupdict() if m.groupdict() else {"match": m.group(0)}
                    return Intent(
                        name=f"CUSTOM_{cmd['trigger']}",
                        confidence=0.95,
                        slots=slots,
                        raw_text=text,
                    )

        # Check standard builtin patterns
        for item in self.builtins:
            for pat in item["patterns"]:
                if re.match(pat, cleaned):
                    return Intent(
                        name=item["intent"],
                        confidence=0.95,
                        slots={},
                        raw_text=text,
                    )

        m_open = re.match(r"^(?:open|launch|start)\s+(.+)$", cleaned)
        if m_open:
            app_name = m_open.group(1).strip()
            return Intent(name="OPEN_APP", confidence=0.90, slots={"app": app_name}, raw_text=text)

        return None

    def fuzzy_match_element(
        self, query: str, elements: List[LabeledElement], threshold: float = 0.7
    ) -> List[Tuple[LabeledElement, float]]:
        """Fuzzy score visible element names using token containment and normalized edit distance."""
        q = (query or "").lower().strip()
        if not q:
            # FIX BUG-006: Empty query must never match elements
            return []

        matches = []
        for el in elements:
            name = (el.name or "").lower().strip()
            if not name:
                continue

            # Exact match
            if q == name:
                matches.append((el, 1.0))
                continue

            # Substring match
            if q in name:
                score = 0.85 + (len(q) / len(name)) * 0.1
                matches.append((el, round(score, 3)))
                continue

            # Word token overlap
            q_words = set(q.split())
            name_words = set(name.split())
            if q_words and name_words:
                common = q_words.intersection(name_words)
                if common:
                    score = len(common) / max(len(q_words), len(name_words))
                    if score >= threshold:
                        matches.append((el, round(score, 3)))

        matches.sort(key=lambda x: x[1], reverse=True)
        return matches

    def register_custom_command(
        self, trigger_pattern: str, action_template: str, scope_app: Optional[str] = None
    ) -> None:
        """FIX BUG-007: Safely escape regex literals while preserving typed placeholders."""
        parts = re.split(r"(<text>|<number>)", trigger_pattern)
        regex_parts = []
        text_count = 0
        num_count = 0
        for p in parts:
            if p == "<text>":
                text_count += 1
                name = f"text_{text_count}" if text_count > 1 else "text"
                regex_parts.append(f"(?P<{name}>.+)")
            elif p == "<number>":
                num_count += 1
                name = f"number_{num_count}" if num_count > 1 else "number"
                regex_parts.append(f"(?P<{name}>\\d+)")
            elif p:
                regex_parts.append(re.escape(p))

        regex = "^" + "".join(regex_parts) + "$"
        try:
            compiled = re.compile(regex, re.IGNORECASE)
            self.custom_commands.append({
                "trigger": trigger_pattern,
                "regex": regex,
                "compiled": compiled,
                "action": action_template,
                "scope_app": scope_app,
            })
        except re.error:
            pass

    def get_registered_commands(self) -> List[Dict[str, Any]]:
        cmds = []
        for b in self.builtins:
            cmds.append({"name": b["intent"], "patterns": b["patterns"], "type": "builtin"})
        for c in self.custom_commands:
            cmds.append({"name": c["trigger"], "action": c["action"], "type": "custom"})
        return cmds
