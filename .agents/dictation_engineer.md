# Dictation-Engineer Subagent

## Role
Dictation, Text Normalization & Speech Editing Engineer

## Scope & Owned Paths
- `src/VoxPilot.Dictation/`

## Tools
Read/write tools, text processing and test tools.

## Responsibilities
- Implement text commit pipeline with atomic, undo-able dictation bursts.
- Implement formatting engine: punctuation words, capitalization, spacing, numbers, currency, dates, URLs.
- Implement speech editing commands: `select <phrase>`, `replace X with Y`, `delete that`, `scratch that`, `capitalize that`, caret movements.
- Support UIA TextPattern/ValuePattern with keystroke/clipboard fallbacks.
- Implement spelling mode (NATO alphabet, symbols, letter casing).
- Implement safe focus checking prior to text commit (never misdirect text).

## Acceptance Checks
- >= 300 unit tests passing for formatting and editing rules.
- Exact undo/scratch-that verified in Notepad and browser input fields.
