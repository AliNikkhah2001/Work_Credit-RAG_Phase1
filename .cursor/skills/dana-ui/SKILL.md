---
name: dana-ui
description: >-
  Designs and implements دانا (ICS) WebUI: Persian RTL, ics-dark/ics-maroon
  themes, glass chat, magic widgets, empty-state hierarchy, and contrast over
  motion backgrounds. Use when editing components/webui, static/dana, Svelte
  chat UI, themes, prompts, gauges/timelines, or Dana UX polish.
---

# Dana UI — ICS / دانا frontend skill

## Own the right tree

Edit only in `components/webui` (Work_RAG-WebUI). Commit there → PR → develop → main → advance parent gitlink.

## Brand tokens (source of truth)

| Token | Value | Notes |
|---|---|---|
| Primary (ics-dark) | `#8F0046` | Exact ICS logo red |
| Primary (ics-maroon) | `#BA0C54` | Light theme |
| FG on dark | `#ffffff` | Always pair with text-shadow/glow |
| Font | Vazirmatn | `letter-spacing: 0`, body line-height ~1.75–1.8 |
| Digits | Persian | Use `$lib/dana/fa.ts` on widgets |

Theme packs: `static/dana/themes/ics-dark.json`, `ics-maroon.json`  
CSS: `static/dana/dana.css` (sync to `backend/open_webui/static/dana/`)  
Tokens JSON (DTCG): `static/dana/tokens/dana.tokens.json`

## Non-negotiables

1. **RTL first** — `dir=rtl`, logical CSS (`inset-inline-start`, `text-start`), no LTR English chrome defaults.
2. **No stock OWUI prompts** — use theme `prompt_suggestions` (credit/ICS intents only).
3. **Empty state** — brand-first: large `دانا`, short subtitle; do not let model name dominate.
4. **One magic widget per assistant reply** — `parseMagicSegments` priority: gauge > timeline > bands > banner > birthday.
5. **Readable on motion BG** — white text + `--dana-text-shadow` / `--dana-text-glow`; denser glass on mobile.
6. **Max two product themes** in UI lists: `ics-dark` (default), `ics-maroon` (+ `vanilla` escape). Alias `ics-gauge` → `ics-dark`.
7. **No left/right chrome** under `html.dana-theme` (sidebars hidden).
8. **Allowlisted magic only** — `static/dana/magic-tokens.json`; never execute model JS.

## Tooling to call

1. Read this skill, then `.cursor/rules/dana-frontend.mdc`
2. VibeFarsi MCP: `get_design_rules` → `search_registry` / `get_component` for Persian patterns (adapt to Svelte; do not paste React/shadcn wholesale)
3. Playwright MCP or `cursor-ide-browser` for live QA on `http://127.0.0.1:13000`
4. `frontend-tools` MCP: `axe_audit`, `page_screenshot`, `design_token_diff` against Dana tokens
5. Figma MCP when a frame/file URL is provided

## QA checklist

- [ ] New chat shows ICS suggestions only
- [ ] Empty title is large `دانا`
- [ ] Chat text readable over watermark (desktop + ≤640px)
- [ ] Multi-magic reply renders a single widget
- [ ] Favicon/login mark is ICS, not Open WebUI
- [ ] Streaming TTFT still on (`stream` default true)

## Preview

- Widgets: `http://127.0.0.1:13000/static/dana/ux-preview.html`
- App: `http://127.0.0.1:13000`
