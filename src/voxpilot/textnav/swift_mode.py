"""Swift mode: speak Swift code as you would read it aloud.

Apple guide: "Voice Control writes Swift code. Pronounce the code just as you'd
read it out loud. Voice Control understands Swift syntax and handles formatting
automatically - like where spaces appear, whether expressions correspond to
operators and where medial capitals belong."

Rule based approximation (Apple's exact grammar is not public). Keywords stay
as written, operator words become symbols with Swift spacing, and consecutive
identifier words are joined with medial capitals (camelCase).
"""
from __future__ import annotations

from typing import List

KEYWORDS = {
    "let", "var", "func", "if", "else", "for", "in", "while", "return", "struct", "class", "enum",
    "import", "guard", "switch", "case", "default", "true", "false", "nil", "self", "init", "protocol",
    "extension", "static", "private", "public", "try", "throws", "break", "continue", "where", "as", "is",
    "do", "catch", "defer", "repeat", "override", "final", "async", "await", "some", "any",
}
# word sequence -> (symbol, space_before, space_after)
BINARY = {
    ("equals",): "=", ("is", "equal", "to"): "==", ("double", "equals"): "==", ("equal", "equal"): "==",
    ("not", "equal", "to"): "!=", ("not", "equals"): "!=",
    ("plus",): "+", ("minus",): "-", ("times",): "*", ("divided", "by"): "/", ("modulo",): "%",
    ("less", "than", "or", "equal", "to"): "<=", ("greater", "than", "or", "equal", "to"): ">=",
    ("less", "than"): "<", ("greater", "than"): ">",
    ("and", "and"): "&&", ("logical", "and"): "&&", ("logical", "or"): "||",
    ("arrow",): "->", ("plus", "equals"): "+=", ("minus", "equals"): "-=",
    ("range", "to"): "...", ("half", "open", "range"): "..<",
}
OPEN = {("open", "paren"): "(", ("left", "paren"): "(", ("open", "brace"): "{", ("left", "brace"): "{",
        ("open", "bracket"): "[", ("left", "bracket"): "["}
CLOSE = {("close", "paren"): ")", ("right", "paren"): ")", ("close", "brace"): "}", ("right", "brace"): "}",
         ("close", "bracket"): "]", ("right", "bracket"): "]"}
TIGHT = {("dot",): ".", ("period",): ".", ("comma",): ",", ("colon",): ":", ("semicolon",): ";",
         ("question", "mark"): "?", ("bang",): "!", ("exclamation", "mark"): "!"}
NUMBERS = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
           "seven": "7", "eight": "8", "nine": "9", "ten": "10"}


class SwiftFormatter:
    """Turn a spoken phrase into Swift source text."""

    def format(self, spoken: str) -> str:
        words = spoken.lower().replace(",", " ").split()
        toks: List[tuple] = []  # (kind, text)
        ident: List[str] = []
        i = 0

        def flush() -> None:
            if ident:
                s = ident[0] + "".join(w[:1].upper() + w[1:] for w in ident[1:])
                toks.append(("id", s))
                ident.clear()

        def match(table):
            for n in (5, 4, 3, 2, 1):
                key = tuple(words[i:i + n])
                if len(key) == n and key in table:
                    return key, table[key]
            return None, None

        while i < len(words):
            w = words[i]
            if w == "quote":
                flush()
                j = i + 1
                lit = []
                while j < len(words) and words[j] not in ("quote", "unquote", "end"):
                    lit.append(words[j]); j += 1
                toks.append(("str", '"' + " ".join(lit) + '"'))
                i = j + 1
                continue
            if w == "capital" and i + 1 < len(words):
                ident.append(words[i + 1].capitalize()) if not ident else ident.append(words[i + 1])
                if len(ident) == 1:
                    pass
                i += 2
                continue
            for table, kind in ((BINARY, "bin"), (OPEN, "open"), (CLOSE, "close"), (TIGHT, "tight")):
                key, sym = match(table)
                if key:
                    flush(); toks.append((kind, sym)); i += len(key)
                    break
            else:
                if w in NUMBERS:
                    flush(); toks.append(("num", NUMBERS[w]))
                elif w in KEYWORDS:
                    flush(); toks.append(("kw", w))
                else:
                    ident.append(w)
                i += 1
        flush()
        return self._join(toks)

    @staticmethod
    def _join(toks: List[tuple]) -> str:
        out = ""
        prev = None
        for kind, t in toks:
            if prev is None:
                out += t
            elif kind in ("close", "tight"):
                out += t
            elif prev in ("open",) or (prev == "tight" and out.endswith(".")):
                out += t
            elif kind == "open" and prev in ("id",):
                out += t  # call: foo(
            else:
                out += " " + t
            prev = kind
        return out
