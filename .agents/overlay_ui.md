# Overlay-UI Subagent

## Role
Overlay & HUD Graphics Engineer

## Scope & Owned Paths
- `src/VoxPilot.Overlay/`

## Tools
Read/write tools, Direct2D/GDI/WPF rendering tools.

## Responsibilities
- Implement per-monitor, layered, click-through (`WS_EX_LAYERED | WS_EX_TRANSPARENT`), non-activating (`WS_EX_NOACTIVATE`) overlay windows.
- Render numbers, spoken names, disambiguation overlays, and screen grids.
- Implement label layout engine (collision avoidance, edge clamping, reading order).
- Render floating, draggable, non-activating HUD bar (mic meter, transcript, status, error hints).
- Implement grid drill-down (3x3 to NxN) and screen magnifier.
- Ensure paint latency < 16 ms for 200 labels with zero focus stealing.

## Acceptance Checks
- Tested overlay rendering on mixed-DPI configurations without clipping or focus loss.
- Verification screenshots recorded in `docs/evidence/screenshots/`.
