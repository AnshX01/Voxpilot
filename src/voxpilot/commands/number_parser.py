"""
VoxPilot Number Parser
Owned by: Command-NLU
Parses spoken English numbers 1-999, digit sequences, homophones, and ordinals.
"""

import re
from typing import Optional, List, Tuple

ONES = {
    "zero": 0, "oh": 0, "one": 1, "won": 1, "two": 2, "to": 2, "too": 2,
    "three": 3, "four": 4, "for": 4, "fore": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "ate": 8, "nine": 9
}

TEENS = {
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19
}

TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fourty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90
}

ORDINALS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
    "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14,
    "fifteenth": 15, "sixteenth": 16, "seventeenth": 17, "eighteenth": 18,
    "nineteenth": 19, "twentieth": 20, "thirtieth": 30
}

ALL_NUMBER_WORDS = set(ONES.keys()) | set(TEENS.keys()) | set(TENS.keys()) | set(ORDINALS.keys()) | {"hundred"}

class NumberParser:
    """Robust English spoken number parser supporting 1-999, digit sequences, and ordinals."""

    @classmethod
    def parse_number_phrase(cls, phrase: str) -> Optional[int]:
        """Convert a spoken phrase (e.g. 'twenty three', 'two three', '23') into an integer."""
        p = phrase.strip().lower()
        if not p:
            return None

        # Direct digit check
        if p.isdigit():
            val = int(p)
            return val if 0 <= val <= 999 else None

        # Clean punctuation and normalize
        tokens = re.findall(r"\b[a-z0-9]+\b", p)
        if not tokens:
            return None

        # Check if single token is ordinal
        if len(tokens) == 1 and tokens[0] in ORDINALS:
            return ORDINALS[tokens[0]]

        # Check if single token is a digit
        if len(tokens) == 1 and tokens[0].isdigit():
            val = int(tokens[0])
            return val if 0 <= val <= 999 else None

        # Check if all tokens are individual digits / single ones (e.g., "2 3" or "one two three")
        is_all_digits = True
        digit_chars = []
        for t in tokens:
            if t.isdigit() and len(t) == 1:
                digit_chars.append(t)
            elif t in ONES and ONES[t] < 10:
                digit_chars.append(str(ONES[t]))
            else:
                is_all_digits = False
                break

        if is_all_digits and len(digit_chars) > 1:
            try:
                seq_val = int("".join(digit_chars))
                if 0 <= seq_val <= 999:
                    return seq_val
            except ValueError:
                pass

        # Try standard composite number parsing (e.g., "one hundred twenty five")
        total = 0
        current = 0
        is_composite = True

        for t in tokens:
            if t.isdigit():
                current += int(t)
            elif t in ONES:
                current += ONES[t]
            elif t in TEENS:
                current += TEENS[t]
            elif t in TENS:
                current += TENS[t]
            elif t == "hundred":
                if current == 0:
                    current = 1
                current *= 100
                total += current
                current = 0
            elif t in ORDINALS:
                current += ORDINALS[t]
            elif t == "and":
                continue
            else:
                is_composite = False
                break

        if is_composite:
            res = total + current
            if 0 <= res <= 999:
                return res

        return None

    @classmethod
    def number_to_words(cls, n: int) -> str:
        """Convert integer 1-999 into English words (e.g. 12 -> 'twelve', 23 -> 'twenty three')."""
        if n < 0 or n > 999:
            return str(n)
        if n == 0:
            return "zero"

        ones_map = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine"}
        teens_map = {10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen", 15: "fifteen", 16: "sixteen", 17: "seventeen", 18: "eighteen", 19: "nineteen"}
        tens_map = {2: "twenty", 3: "thirty", 4: "forty", 5: "fifty", 6: "sixty", 7: "seventy", 8: "eighty", 9: "ninety"}

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
            for span_len in (4, 3, 2, 1):
                if i + span_len <= len(words):
                    candidate = " ".join(words[i:i+span_len])
                    val = cls.parse_number_phrase(candidate)
                    if val is not None:
                        results.append((val, i, i + span_len))
                        i += span_len
                        matched = True
                        break
            if not matched:
                i += 1
        return results
