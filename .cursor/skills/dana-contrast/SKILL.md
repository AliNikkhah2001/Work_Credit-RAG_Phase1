---
name: dana-contrast
description: >-
  Audits and fixes Dana chat text contrast on ICS dark-red motion backgrounds.
  Use when text is hard to read, WCAG contrast fails, glass bubbles wash out,
  or the user asks for shadows, glow, veil, or readability on ics-dark.
---

# Dana contrast — readability on brand backgrounds

## Goal

White/light text on `#8F0046` + watermark must stay readable without killing brand atmosphere.

## Preferred stack (apply in order)

1. **Foreground** — `#fff` on chat body, markdown, suggestions, empty state
2. **Text shadow + glow** — `--dana-text-shadow` + `--dana-text-glow` (see `dana.css` `--dana-readable-shadow`)
3. **Veil** — strengthen `.dana-chat-bg__veil` / `--dana-chat-overlay` before raising glass opacity globally
4. **Glass** — slightly more opaque panels; on `max-width: 640px` use denser `--dana-glass-bg` and lower blur
5. **Widget arcs/pills** — avoid same-hue-on-same-hue (e.g. gauge ring should contrast with BG — prefer white arc + glow)

## Token files

- Runtime CSS vars: `static/dana/themes/ics-dark.json` → `colors`
- DTCG mirror: `static/dana/tokens/dana.tokens.json`
- Diff regressions with frontend-tools `design_token_diff`

## Verify

```bash
# Live page screenshot + axe (via MCP frontend-tools / Playwright)
curl -sI http://127.0.0.1:13000/ | head -5
curl -sI http://127.0.0.1:13000/static/dana/ux-preview.html | head -5
```

Manual: open ics-dark chat, empty state, long Persian reply, gauge widget — all must remain scannable.
