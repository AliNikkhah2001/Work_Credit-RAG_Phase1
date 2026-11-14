# Dana UI / UX agent tooling

Installed for professional Persian RTL frontend work on Work_RAG-WebUI.

## Skills

| Skill | Path | Use |
|---|---|---|
| `dana-ui` | `.cursor/skills/dana-ui/` | Themes, magic widgets, empty state, ICS prompts |
| `dana-contrast` | `.cursor/skills/dana-contrast/` | Shadows/glow/veil readability on ics-dark |

## Rules

| Rule | Globs |
|---|---|
| `dana-frontend.mdc` | `components/webui/**`, `**/static/dana/**` |

## MCP (`.cursor/mcp.json`)

| Server | Role | Status |
|---|---|---|
| `vibefarsi` | Remote Persian design rules + registry | Remote often times out; use local fallback |
| `vibefarsi-local` | Offline MCP from `dev/vibefarsiui/mcp` | **Verified** (`npm run smoke`) |
| `playwright` | Browser MCP (`npx @playwright/mcp`) | **Verified** CLI boots |
| `figma` | `https://mcp.figma.com/mcp` + Cursor Figma plugin | Plugin installed — **Connect** once in Settings → MCP |
| `frontend-tools` | axe / screenshots / token diff | **Verified** (uses system Chrome via `PLAYWRIGHT_CHANNEL=chrome`) |

## Tokens

`components/webui/static/dana/tokens/dana.tokens.json` — DTCG mirror for `design_token_diff`.

Served at: `http://127.0.0.1:13000/static/dana/tokens/dana.tokens.json`

## Component gallery (Storybook substitute)

Full Storybook on the OWUI fork is deferred. Use:

`http://127.0.0.1:13000/static/dana/ux-preview.html`

## Smoke results (2026-11-11)

| Check | Result |
|---|---|
| WebUI `:13000` | HTTP 200, title `دانا` |
| VibeFarsi local smoke | design rules + registry search OK |
| VibeFarsi remote | timed out (fallback configured) |
| frontend-tools `page_screenshot` | PNG written (`ux-preview`) |
| frontend-tools `design_token_diff` | detects primary color change |
| frontend-tools `axe_audit` (URL) | 0 violations; color-contrast incomplete notes |
| Playwright MCP CLI | boots (`--help`) |
| Cursor IDE browser | opens دانا auth/home |
| Figma plugin | installed; OAuth connect required in UI |

## Enable in Cursor

1. **Settings → Tools & MCP** — enable each server (green dot).
2. **Figma** — click Connect → Allow access.
3. Reload window if a new MCP does not appear.

## Rebuild note

Live container may lag git `main` until WebUI image is rebuilt. Tooling works against whatever is on `:13000` + static files (tokens were docker-cp’d for smoke).
