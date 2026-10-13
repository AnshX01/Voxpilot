"""
VoxPilot Number Parser
Owned by: Command-NLU
Parses spoken English numbers 1-999, compound numbers, digit sequences, homophones, and ordinals.
"""

import re
from typing import Optional, List, Tuple

ONES = {
    "zero": 0, "oh": 0, "nil": 0, "nought": 0, "naught": 0,
    "one": 1, "won": 1,
    "two": 2, "to": 2, "too": 2,
    "three": 3, "tree": 3,
    "four": 4, "for": 4, "fore": 4,
    "five": 5,
    "six": 6, "sax": 6, "sex": 6,
    "seven": 7,
    "eight": 8, "ate": 8, "hate": 8,
    "nine": 9, "nein": 9,
}

TEENS = {
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}

TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fourty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}

ORDINALS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
    "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14,
    "fifteenth": 15, "sixteenth": 16, "seventeenth": 17, "eighteenth": 18,
    "nineteenth": 19, "twentieth": 20, "thirtieth": 30,
    "fortieth": 40, "fourtieth": 40, "fiftieth": 50, "sixtieth": 60,
    "seventieth": 70, "eightieth": 80, "ninetieth": 90, "hundredth": 100,
}

ALL_NUMBER_WORDS = (
    set(ONES.keys())
    | set(TEENS.keys())
    | set(TENS.keys())
    | set(ORDINALS.keys())
    | {"hundred", "hundredth"}
)


class NumberParser:
    """Robust English spoken number parser supporting 1-999, compound numbers, digit sequences, and ordinals."""

    @classmethod
    def _parse_sub_hundred(cls, tokens: List[str]) -> Optional[int]:
        """Parse sub-hundred expressions (0-99) from 1 or 2 word tokens."""
        if not tokens:
            return None

        if len(tokens) == 1:
            t = tokens[0]
            if t.isdigit():
                val = int(t)
                return val if 0 <= val <= 99 else None
            m = re.match(r"^(\d+)(?:st|nd|rd|th)$", t)
            if m:
                val = int(m.group(1))
                return val if 0 <= val <= 99 else None
            if t in ORDINALS and ORDINALS[t] <= 99:
                return ORDINALS[t]
            if t in ONES:
                return ONES[t]
            if t in TEENS:
                return TEENS[t]
            if t in TENS:
                return TENS[t]
            return None

        if len(tokens) == 2:
            t0, t1 = tokens[0], tokens[1]
            if t0 in TENS:
                tens_val = TENS[t0]
                if t1 in ONES:
                    return tens_val + ONES[t1]
                if t1 in ORDINALS and ORDINALS[t1] < 10:
                    return tens_val + ORDINALS[t1]
                if t1.isdigit() and len(t1) == 1:
                    return tens_val + int(t1)
                m = re.match(r"^(\d+)(?:st|nd|rd|th)$", t1)
                if m and len(m.group(1)) == 1:
                    return tens_val + int(m.group(1))
            if (t0.isdigit() and len(t0) == 1 or t0 in ONES) and (
                t1.isdigit() and len(t1) == 1 or t1 in ONES
            ):
                d0 = t0 if t0.isdigit() else str(ONES[t0])
                d1 = t1 if t1.isdigit() else str(ONES[t1])
                try:
                    return int(d0 + d1)
                except ValueError:
                    return None

        return None

    @classmethod
    def parse_number_phrase(cls, phrase: str) -> Optional[int]:
        """Convert a spoken phrase (e.g. 'twenty three', 'two three', '23', 'one hundred twenty') into an integer 0-999."""
        p = phrase.strip().lower()
        if not p:
            return None

        # Direct digit check
        if p.isdigit():
            val = int(p)
            return val if 0 <= val <= 999 else None

        # Check digit ordinal directly (e.g., '1st', '42nd', '999th')
        m_ord = re.match(r"^(\d+)(?:st|nd|rd|th)$", p)
        if m_ord:
            val = int(m_ord.group(1))
            return val if 0 <= val <= 999 else None

        # Replace hyphens with spaces: e.g., 'twenty-five' -> 'twenty five'
        p_clean = p.replace("-", " ")
        tokens = re.findall(r"\b[a-z0-9]+\b", p_clean)
        if not tokens:
            return None

        # Strip optional leading 'number' or 'num'
        if len(tokens) > 1 and tokens[0] in ("number", "num"):
            tokens = tokens[1:]

        # Check single token directly
        if len(tokens) == 1:
            t = tokens[0]
            if t.isdigit():
                val = int(t)
                return val if 0 <= val <= 999 else None
            m = re.match(r"^(\d+)(?:st|nd|rd|th)$", t)
            if m:
                val = int(m.group(1))
                return val if 0 <= val <= 999 else None
            if t in ORDINALS:
                return ORDINALS[t]
            if t in ONES:
                return ONES[t]
            if t in TEENS:
                return TEENS[t]
            if t in TENS:
                return TENS[t]
            if t in ("hundred", "hundredth"):
                return 100
            return None

        # Check if all tokens are individual single digits (e.g., "2 3" -> 23, "1 2 3" -> 123)
        is_all_single_digits = True
        digit_chars = []
        for t in tokens:
            if t.isdigit() and len(t) == 1:
                digit_chars.append(t)
            elif t in ONES:
                digit_chars.append(str(ONES[t]))
            else:
                is_all_single_digits = False
                break

        if is_all_single_digits and len(digit_chars) > 1:
            try:
                seq_val = int("".join(digit_chars))
                if 0 <= seq_val <= 999:
                    return seq_val
            except ValueError:
                pass

        # Filter out filler words: "and", "a", "an"
        filtered_tokens = [t for t in tokens if t not in ("and", "a", "an")]
        if not filtered_tokens:
            return None

        # Check single token after filter (e.g., "a hundred" -> ["hundred"])
        if len(filtered_tokens) == 1:
            t = filtered_tokens[0]
            if t in ORDINALS:
                return ORDINALS[t]
            if t in ONES:
                return ONES[t]
            if t in TEENS:
                return TEENS[t]
            if t in TENS:
                return TENS[t]
            if t in ("hundred", "hundredth"):
                return 100

        # Sub-hundred check on filtered tokens (e.g., "twenty five" -> 25)
        sub_val = cls._parse_sub_hundred(filtered_tokens)
        if sub_val is not None:
            return sub_val

        # Check if "hundred" or "hundredth" is present in compound
        if "hundred" in filtered_tokens or "hundredth" in filtered_tokens:
            h_idx = (
                filtered_tokens.index("hundred")
                if "hundred" in filtered_tokens
                else filtered_tokens.index("hundredth")
            )
            left = filtered_tokens[:h_idx]
            right = filtered_tokens[h_idx + 1 :]

            # Left side (hundreds multiplier: 1-9)
            if not left:
                h_mult = 1
            elif len(left) == 1:
                t_left = left[0]
                if t_left in ONES and 1 <= ONES[t_left] <= 9:
                    h_mult = ONES[t_left]
                elif t_left.isdigit() and 1 <= int(t_left) <= 9:
                    h_mult = int(t_left)
                else:
                    return None
            else:
                return None

            total = h_mult * 100

            # Right side (remainder: 0-99)
            if not right:
                return total if 0 <= total <= 999 else None

            rem = cls._parse_sub_hundred(right)
            if rem is not None and 0 <= rem <= 99:
                val = total + rem
                return val if 0 <= val <= 999 else None
            return None

        # Colloquial three-digit: e.g. "one twenty" -> 120, "one twenty five" -> 125, "two fifty" -> 250, "three fifteen" -> 315
        if len(filtered_tokens) >= 2:
            t0 = filtered_tokens[0]
            h_mult = None
            if t0 in ONES and 1 <= ONES[t0] <= 9:
                h_mult = ONES[t0]
            elif t0.isdigit() and 1 <= int(t0) <= 9:
                h_mult = int(t0)

            if h_mult is not None:
                rem = cls._parse_sub_hundred(filtered_tokens[1:])
                if rem is not None and 10 <= rem <= 99:
                    val = h_mult * 100 + rem
                    return val if 0 <= val <= 999 else None

        return None

    @classmethod
    def number_to_words(cls, n: int) -> str:
        """Convert integer 1-999 into English words (e.g. 12 -> 'twelve', 23 -> 'twenty three')."""
        if n < 0 or n > 999:
            return str(n)
        if n == 0:
            return "zero"

        ones_map = {
            1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
            6: "six", 7: "seven", 8: "eight", 9: "nine",
        }
        teens_map = {
            10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen",
            15: "fifteen", 16: "sixteen", 17: "seventeen", 18: "eighteen", 19: "nineteen",
        }
        tens_map = {
            2: "twenty", 3: "thirty", 4: "forty", 5: "fifty",
            6: "sixty", 7: "seventy", 8: "eighty", 9: "ninety",
        }

        parts = []
        val = n
        if val >= 100:
            h = val // 100
            parts.append(f"{ones_map[h]} hundred")
            val = val % 100

        if val >= 20:
            t = val // 10
            r = val % 10
            if r > 0:
                parts.append(f"{tens_map[t]} {ones_map[r]}")
            else:
                parts.append(tens_map[t])
        elif val >= 10:
            parts.append(teens_map[val])
        elif val > 0:
            parts.append(ones_map[val])

        return " ".join(parts)

    @classmethod
    def extract_numbers(cls, text: str) -> List[Tuple[int, int, int]]:
        """Find all number spans in text: returns list of (value, start_idx, end_idx)."""
        words = text.lower().split()
        results = []
        i = 0
        while i < len(words):
            matched = False
            for span_len in (5, 4, 3, 2, 1):
                if i + span_len <= len(words):
                    candidate = " ".join(words[i : i + span_len])
                    val = cls.parse_number_phrase(candidate)
                    if val is not None:
                        results.append((val, i, i + span_len))
                        i += span_len
                        matched = True
                        break
            if not matched:
                i += 1
        return results
