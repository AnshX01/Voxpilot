"""VoxPilot Dictation Text Formatting & Normalization Engine.

Handles:
- Punctuation word conversions (period, comma, question mark, etc.)
- Whitespace and punctuation gluing / trimming
- Sentence, title, and all-caps capitalization states
- Currency, percentage, dates, numbers, URLs, and emails
- NATO phonetic alphabet spelling mode
"""

from __future__ import annotations

import re
from typing import Any, Optional

# NATO Phonetic Alphabet mapping
NATO_PHONETIC = {
    "alpha": "a",
    "bravo": "b",
    "charlie": "c",
    "delta": "d",
    "echo": "e",
    "foxtrot": "f",
    "golf": "g",
    "hotel": "h",
    "india": "i",
    "juliet": "j",
    "kilo": "k",
    "lima": "l",
    "mike": "m",
    "november": "n",
    "oscar": "o",
    "papa": "p",
    "quebec": "q",
    "romeo": "r",
    "sierra": "s",
    "tango": "t",
    "uniform": "u",
    "victor": "v",
    "whiskey": "w",
    "x-ray": "x",
    "xray": "x",
    "yankee": "y",
    "zulu": "z",
    # Digits
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
}

# Spoken punctuation mapping (multi-word phrases first for greedy matching)
PUNCTUATION_PHRASES = [
    # Multi-word phrases
    ("exclamation point", "!"),
    ("exclamation mark", "!"),
    ("question mark", "?"),
    ("full stop", "."),
    ("dot dot dot", "..."),
    ("new line", "\n"),
    ("new paragraph", "\n\n"),
    ("open parenthesis", "("),
    ("close parenthesis", ")"),
    ("left parenthesis", "("),
    ("right parenthesis", ")"),
    ("open paren", "("),
    ("close paren", ")"),
    ("open quotation", '"'),
    ("close quotation", '"'),
    ("open quote", '"'),
    ("close quote", '"'),
    ("end quote", '"'),
    ("single quote", "'"),
    ("open bracket", "["),
    ("close bracket", "]"),
    ("left bracket", "["),
    ("right bracket", "]"),
    ("open brace", "{"),
    ("close brace", "}"),
    ("left brace", "{"),
    ("right brace", "}"),
    ("forward slash", "/"),
    ("at sign", "@"),
    ("at symbol", "@"),
    ("hash tag", "#"),
    ("pound sign", "#"),
    ("number sign", "#"),
    ("dollar sign", "$"),
    ("percent sign", "%"),
    ("plus sign", "+"),
    ("equals sign", "="),
    ("and sign", "&"),
    ("caret sign", "^"),
    ("vertical bar", "|"),
    ("greater than", ">"),
    ("less than", "<"),
    ("tab key", "\t"),
    ("em dash", "—"),
    # Single-word tokens
    ("period", "."),
    ("dot", "."),
    ("comma", ","),
    ("colon", ":"),
    ("semicolon", ";"),
    ("newline", "\n"),
    ("tab", "\t"),
    ("ellipsis", "..."),
    ("hyphen", "-"),
    ("dash", "-"),
    ("slash", "/"),
    ("backslash", "\\"),
    ("asterisk", "*"),
    ("star", "*"),
    ("hashtag", "#"),
    ("hash", "#"),
    ("percent", "%"),
    ("ampersand", "&"),
    ("underscore", "_"),
    ("plus", "+"),
    ("equals", "="),
    ("tilde", "~"),
    ("pipe", "|"),
]

# Cardinal number word values
NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
    "one hundred": 100,
    "hundred": 100,
}

ORDINAL_SUFFIXES = {
    "first": "1",
    "second": "2",
    "third": "3",
    "fourth": "4",
    "fifth": "5",
    "sixth": "6",
    "seventh": "7",
    "eighth": "8",
    "ninth": "9",
    "tenth": "10",
    "eleventh": "11",
    "twelfth": "12",
    "thirteenth": "13",
    "fourteenth": "14",
    "fifteenth": "15",
    "sixteenth": "16",
    "seventeenth": "17",
    "eighteenth": "18",
    "nineteenth": "19",
    "twentieth": "20",
    "twenty-first": "21",
    "twenty first": "21",
    "twenty-second": "22",
    "twenty second": "22",
    "twenty-third": "23",
    "twenty third": "23",
    "twenty-fourth": "24",
    "twenty-fifth": "25",
    "twenty fifth": "25",
    "thirtieth": "30",
    "thirty-first": "31",
    "thirty first": "31",
}

MONTHS = [
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
]


class FormattingEngine:
    """Production text formatting engine for speech dictation."""

    def __init__(self) -> None:
        self.all_caps_active: bool = False
        self.sentence_start: bool = True

    def reset_state(self) -> None:
        """Reset ongoing sentence and casing state."""
        self.all_caps_active = False
        self.sentence_start = True

    def format_text(
        self,
        raw_text: str,
        spelling_mode: bool = False,
        rules: Optional[dict[str, Any]] = None,
    ) -> str:
        """Transform raw speech transcript into formatted, punctuated text."""
        if not raw_text or not raw_text.strip():
            return ""

        text = raw_text.strip()

        # 1. Spelling mode check (NATO phonetics or explicit 'spell ...' command)
        if spelling_mode or text.lower().startswith("spell "):
            return self._format_spelling(text)

        # 2. Spoken number phrases before special terms ("fifty percent" -> "50 percent", "dollar one hundred" -> "dollar 100")
        text = self._convert_spoken_quantities(text)

        # 3. Handle spoken formatting keywords and state commands
        text = self._apply_spoken_modifiers(text)

        # 4. Spoken punctuation expansion
        text = self._expand_punctuation(text)

        # 5. Spacing and attachment fixes (before special entities)
        text = self._fix_punctuation_spacing(text)

        # 6. Currency, percentage, URLs, emails, dates (after punctuation spacing so domain dots are not spaced)
        text = self._format_special_entities(text)

        # 7. Sentence and paragraph capitalization
        text = self._apply_sentence_casing(text)

        # 8. Clean up internal sentinels
        text = text.replace("\x01", "")

        return text

    def _convert_spoken_quantities(self, text: str) -> str:
        """Convert spoken word numbers preceding currency or percent into digits."""
        # e.g. "one hundred" -> "100", "fifty" -> "50"
        for word, val in sorted(NUMBER_WORDS.items(), key=lambda x: -len(x[0])):
            text = re.sub(
                rf"\b(?:dollar|dollars|dollar sign|\$)\s+{re.escape(word)}\b",
                rf"${val}",
                text,
                flags=re.IGNORECASE,
            )
            text = re.sub(
                rf"\b{re.escape(word)}\s+(percent|percent sign|dollars?)\b",
                rf"{val} \1",
                text,
                flags=re.IGNORECASE,
            )
        return text

    def _format_spelling(self, text: str) -> str:
        """Convert NATO phonetic words into concatenated letters."""
        tokens = text.lower().split()
        if tokens and tokens[0] == "spell":
            tokens = tokens[1:]

        result_chars: list[str] = []
        caps_next = False
        all_caps = self.all_caps_active
        i = 0

        while i < len(tokens):
            two_words = f"{tokens[i]} {tokens[i+1]}" if i + 1 < len(tokens) else ""
            if two_words == "all caps" or tokens[i] == "uppercase":
                all_caps = True
                i += 2 if two_words == "all caps" else 1
                continue
            if two_words in ("caps off", "no caps") or tokens[i] == "lowercase":
                all_caps = False
                i += 2 if two_words in ("caps off", "no caps") else 1
                continue
            if two_words in ("cap next", "capitalize next") or tokens[i] in ("cap", "capital", "capitalize"):
                caps_next = True
                i += 2 if two_words in ("cap next", "capitalize next") else 1
                continue

            token = tokens[i]
            char = NATO_PHONETIC.get(token, token)
            if len(char) == 1:
                if all_caps or caps_next:
                    char = char.upper()
                    caps_next = False
                result_chars.append(char)
            else:
                result_chars.append(char)
            i += 1

        return "".join(result_chars)

    def _apply_spoken_modifiers(self, text: str) -> str:
        """Process inline formatting directives like 'capitalize next', 'all caps'."""
        tokens = text.split()
        out_tokens: list[str] = []
        i = 0
        n = len(tokens)

        cap_next = False
        all_caps_next = False
        lower_next = False
        no_space_next = False

        while i < n:
            word = tokens[i].lower()
            two_words = f"{word} {tokens[i+1].lower()}" if i + 1 < n else ""
            three_words = (
                f"{word} {tokens[i+1].lower()} {tokens[i+2].lower()}"
                if i + 2 < n
                else ""
            )

            # Check multi-word modifier phrases
            if three_words == "all caps next":
                all_caps_next = True
                i += 3
                continue
            if two_words == "all caps":
                self.all_caps_active = True
                i += 2
                continue
            if two_words in ("caps off", "no caps", "lowercase mode"):
                self.all_caps_active = False
                i += 2
                continue
            if two_words in ("capitalize next", "cap next"):
                cap_next = True
                i += 2
                continue
            if two_words in ("lowercase next", "lower next", "no cap next"):
                lower_next = True
                i += 2
                continue
            if three_words == "no space next":
                no_space_next = True
                i += 3
                continue
            if two_words == "no space":
                no_space_next = True
                i += 2
                continue

            # Process word with active modifiers
            curr_word = tokens[i]
            if all_caps_next or self.all_caps_active:
                curr_word = curr_word.upper()
                all_caps_next = False
            elif cap_next:
                curr_word = curr_word.capitalize()
                cap_next = False
            elif lower_next:
                # Mark with sentinel \x01 so sentence casing does not capitalize it
                curr_word = "\x01" + curr_word.lower()
                lower_next = False

            if no_space_next and out_tokens:
                out_tokens[-1] = out_tokens[-1] + curr_word
                no_space_next = False
            else:
                out_tokens.append(curr_word)

            i += 1

        return " ".join(out_tokens)

    def _expand_punctuation(self, text: str) -> str:
        """Replace spoken punctuation phrases with punctuation characters."""
        for phrase, symbol in PUNCTUATION_PHRASES:
            pattern = re.compile(rf"\b{re.escape(phrase)}\b", re.IGNORECASE)
            text = pattern.sub(lambda _, s=symbol: s, text)

        return text

    def _fix_punctuation_spacing(self, text: str) -> str:
        """Attach trailing punctuation to preceding words, and fix bracket spaces."""
        # Attach trailing punctuation (. , ? ! : ; % ) ] } —) to preceding word
        text = re.sub(r"\s+([.,?!:;%)\]}—])", r"\1", text)

        # Attach trailing punctuation (. , ? ! : ; % ) ] } — * _ ~) to preceding word
        text = re.sub(r"\s+([.,?!:;%)\]}—*_~])", r"\1", text)

        # Attach leading symbols to following word: ( [ { $ # @ ~ * \ / |
        text = re.sub(r"([(\[{])\s+", r"\1", text)
        text = re.sub(r"([$#@~*\\/|])\s+(\w+)", r"\1\2", text)

        # Attach hyphens, em dashes, and underscores without spaces if connecting words
        text = re.sub(r"\s*-\s*", "-", text)
        text = re.sub(r"\s*—\s*", "—", text)
        text = re.sub(r"\s*_\s*", "_", text)

        # Clean spaces around tabs
        text = re.sub(r"[ ]*\t[ ]*", "\t", text)

        # Fix quotes: " word " -> "word"
        text = re.sub(r'"\s+([^"]*?)\s+"', r'"\1"', text)

        # Ensure single space after punctuation if followed by word (except inside numbers/URLs)
        text = re.sub(r"([,?!;])([a-zA-Z])", r"\1 \2", text)
        text = re.sub(r"([.:])([a-zA-Z])", r"\1 \2", text)

        # Fix newlines: remove spaces before/after newline
        text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)

        # Collapse redundant double spaces
        text = re.sub(r"[ ]{2,}", " ", text)

        return text

    def _format_special_entities(self, text: str) -> str:
        """Format emails, URLs, currency, percentages, dates, and number phrases."""
        # 1. Emails: e.g. "john at example. com" -> "john@example.com"
        text = re.sub(
            r"\b([a-zA-Z0-9._%+-]+)\s*(?:at|@)\s*([a-zA-Z0-9.-]+)\s*(?:dot|\.)\s*(com|org|net|edu|gov|io|ai|co|in)\b",
            r"\1@\2.\3",
            text,
            flags=re.IGNORECASE,
        )

        # 2. URLs: e.g. "www dot google dot com" -> "www.google.com"
        text = re.sub(
            r"\b(www)\s*(?:dot|\.)\s*([a-zA-Z0-9.-]+)\s*(?:dot|\.)\s*(com|org|net|edu|gov|io|ai|co|in)\b",
            r"\1.\2.\3",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"\b(https?):\s*//\s*",
            r"\1://",
            text,
            flags=re.IGNORECASE,
        )

        # 2b. Filename extensions: e.g. "archive dot zip" -> "archive.zip"
        text = re.sub(
            r"\b([a-zA-Z0-9_-]+)\s*(?:dot|\.)\s*(zip|tar|gz|json|yaml|yml|py|exe|dll|txt|md|csv|pdf|html|css|js|ts)\b",
            r"\1.\2",
            text,
            flags=re.IGNORECASE,
        )

        # 3. Currency: e.g. "$ 120" -> "$120", "dollar 120" -> "$120", "50 dollars" -> "$50"
        text = re.sub(
            r"\b(?:dollar|dollars)\s+(\d+(?:\.\d+)?)\b",
            r"$\1",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"\b(\d+(?:\.\d+)?)\s+(?:dollar|dollars)\b",
            r"$\1",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"\$\s+(\d+(?:\.\d+)?)\b",
            r"$\1",
            text,
        )
        text = re.sub(
            r"\b(\d+(?:\.\d+)?)\s+\$",
            r"$\1",
            text,
        )

        # 4. Percentages: e.g. "25 %" -> "25%"
        text = re.sub(
            r"\b(\d+(?:\.\d+)?)\s*%",
            r"\1%",
            text,
        )
        text = re.sub(
            r"\b(\d+(?:\.\d+)?)\s+percent\b",
            r"\1%",
            text,
            flags=re.IGNORECASE,
        )

        # 5. Dates: e.g. "October twelfth 2026" -> "October 12, 2026"
        for month in MONTHS:
            pattern = re.compile(
                rf"\b({month})\s+([a-zA-Z0-9-]+)\s+(\d{{4}})\b", re.IGNORECASE
            )
            match = pattern.search(text)
            if match:
                m_name = match.group(1).capitalize()
                day_raw = match.group(2).lower()
                year = match.group(3)
                day_val = ORDINAL_SUFFIXES.get(day_raw, day_raw)
                day_num = re.sub(r"\D", "", day_val) or day_val
                text = pattern.sub(f"{m_name} {day_num}, {year}", text, count=1)

        # 6. Spoken compound numbers into digits if prefixed with "number ..."
        text = re.sub(
            r"\bnumber\s+(\d+)\b",
            r"\1",
            text,
            flags=re.IGNORECASE,
        )

        return text

    def _apply_sentence_casing(self, text: str) -> str:
        """Ensure the first word of each sentence or paragraph is capitalized."""
        if not text:
            return ""

        # First character of overall string if sentence_start
        if self.sentence_start and len(text) > 0:
            # If starts with @, #, or marked with \x01, preserve lowercase
            if not text.startswith(("@", "#", "\x01")):
                for idx, c in enumerate(text):
                    if c.isalpha():
                        text = text[:idx] + c.upper() + text[idx + 1 :]
                        break

        # Capitalize after sentence boundaries (. ? ! or \n or \t)
        def _cap_match(m: re.Match) -> str:
            prefix = m.group(1)
            char = m.group(2)
            # If marked with \x01, preserve lowercase
            return prefix + char.upper()

        text = re.sub(r"([.?!]\s+|\n+[ \t]*|\t+[ \t]*)([a-z])", _cap_match, text)

        # Update sentence_start state for next burst
        stripped = text.strip()
        if stripped and stripped[-1] in (".", "?", "!", "\n"):
            self.sentence_start = True
        else:
            self.sentence_start = False

        return text
