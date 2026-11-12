# Increment 3.1 contract — conversation accessibility pass (keyboard, screen reader, 200% zoom, zh-HK)

Status: implementation contract. Frontend + gate only; no backend change.

## Why

Phase 3 asks for a complete zh-HK + keyboard/screen-reader/200% zoom pass and the
conversation gate has no zoom or systematic keyboard/SR coverage today. The studio
already has good basics — transcript `role="log" aria-live="polite"
aria-relevant="additions"`, labelled messages/articles, an `aside` context panel
with a real tablist/tabpanel, labelled icon buttons — but several things are
unproven or wrong at the edges.

## Findings to fix (verify each; fix only real defects)

1. **Duplicate live-region announcements**: the same failure text can render both in
   the inline `role="status"` notice and in the transcript `role="status"` line
   (the gate already hit a strict-mode duplicate for exactly this text). A screen
   reader would announce it twice. Keep one announced source and make the other
   presentation-only (`aria-hidden` or not a live region), without removing visible
   text and without breaking existing assertions.
2. **Tab keyboard pattern**: the context panel tablist has no ArrowLeft/ArrowRight/
   Home/End handling and no roving tabindex. Implement the APG tabs keyboard model
   (arrow wrap, Home/End, focus follows selection, tabpanel `aria-labelledby`) and
   keep mouse behaviour.
3. **Focus management**: opening a discussion (thread list row, deep link, "Discuss
   this company") should move focus somewhere sensible and announce the new
   context; closing/returning should restore focus to the trigger where the
   existing pattern does. Verify the share dialog (native `<dialog>`) has
   `aria-modal` semantics and returns focus to its trigger.
4. **Focus visibility**: every interactive control in the studio (thread rows, menu
   summary/items, composer send/attach/chips, tabs, panel buttons, jump-to-latest,
   retry/cancel/decision buttons) must show a visible `:focus-visible` indicator.
   Fix with an additive CSS rule scoped to the conversation surfaces if missing.
5. **200% zoom**: browser zoom halves the CSS viewport; at 200% of a 1280 px screen
   the studio must reflow with no horizontal scrolling of the page or the
   transcript/composer/panel, keep the composer and its send action reachable, and
   keep the thread list/drawer behaviour. Add the emulation to the gate.
6. **zh-HK completeness**: every visible control label, aria-label, placeholder,
   status and notice used by the studio exists in both catalogues; add a unit scan
   over the studio/panel/transcript/composer/locale keys so a new string cannot
   ship EN-only.

## Gate scenarios (2 new; keep the 27 existing strong)

- **keyboard + screen reader**: tab order from the top reaches the thread list, the
  transcript (log role), the composer and the send action; Enter/Space activate;
  context tabs respond to arrows/Home/End with `aria-selected`/focus moving and the
  panel updating; Escape closes the mobile drawer/menu and returns focus to the
  trigger; the duplicate-notice fix is asserted (exactly one live region announces
  the text); decisions expose accessible names; no keyboard trap.
- **200% zoom**: emulate the 200% CSS viewport, assert `documentElement` has no
  horizontal overflow, the composer + send action are visible and operable, the
  transcript scrolls vertically, the context panel and its close control are
  reachable, and switching to zh-HK keeps the same result with translated labels.
  Also assert no page errors.

## Constraints

- No backend, `.github` (except the core gate constant), dependency or contract
  change; no new UI features beyond the a11y fixes; do not rename existing classes
  or remove existing semantics relied on by the 27 scenarios.
- Keep the DOM stable enough that prior scenarios pass unchanged; report any
  scenario whose strict assertion had to be adjusted and why.
- Report the new core count (179 now) so the Lead bumps the CI gate.
