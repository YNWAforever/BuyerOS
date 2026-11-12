# Increment 2.4 review — full skill library in chips and slash menu

Reviewer: `reliability` (independent of the implementation streams)
Date: 2026-11-10 (Asia/Singapore)
Worktree: `C:\Users\laich\Documents\BuyerOS\.worktrees\conv-studio`, branch `feat/conversation-skill-library`, head `adae6d606` (stacked PR #64 on `feat/conversation-attachments`).
Contract: `docs/superpowers/specs/2026-11-10-skill-library.md`.
Scope: catalogue→command mapping, slash-menu selection/keyboard/a11y, bounds/i18n, honesty/security, regression. **No implementation file was modified by this review; the only file written is this document.**

Verification legend:
- **[READ]** verified by reading source at the cited `file:line`.
- **[TEST]** verified by a test/command executed in this sandbox (`node:test`, tsc, eslint — see §6).
- **[BLOCKED]** browser execution is unavailable here (Playwright `spawn EPERM`). CI run 42750508714 is authoritative; no browser result is claimed.
- **[ROUTED]** reported to the Lead.

## 1. Findings summary

| Id | Severity | Finding | Evidence | Status |
| --- | --- | --- | --- | --- |
| MAJOR-1 | Major (IME / a11y) | The menu branch of `onKeyDown` runs before the composition check: while an IME composition is active (zh-HK users typing the slash query), Enter to commit the composition is treated as "select active command" and ArrowUp/Down are consumed for menu navigation, so the composed query can be replaced by an unintended command prompt and IME candidate navigation breaks. The normal send path does check `event.nativeEvent.isComposing`, the menu branch does not. | `features/live/conversation/composer.tsx:68-80` (menu handling before the `isComposing` send check at :81); `skill-library.ts:111-121` | [READ] |
| MAJOR-2 | Major (catalogue parity drift / silent drop) | Commands are derived from the fetched catalogue, but the authored copy is a hardcoded 17-id map and any offered skill without an authored entry is silently filtered out (`filter(...Boolean(authoring[skill.id]))`), so a future server-offered skill becomes unreachable rather than shown/disabled — contrary to "every offered skill is reachable" and the "no hardcoded list" intent. There is no parity test against the real catalogue: the browser scenario reads `catalogue.json` but only asserts the authored-derived counts (8 options + "9 more"), which would still pass if a new catalogue skill were dropped; the unit test builds its input from the authored map. Current catalogue is exactly 17 and all reachable (verified), so this is a drift/robustness finding, not a present-day failure. | `features/live/conversation/skill-library.ts:17-44,57-66`; `tests/core-conversation-skill-library.test.mjs:14,18-35`; browser scenario `tests/conversation-home-responsive.test.mjs` (new slash test) | [READ] |
| MAJOR-3 | Major (latent honesty/authority) | A locale-disabled skill can still be sent via carry-over: `currentSkill` is set at selection time and is not revalidated when the locale or catalogue changes. Select an en-available skill, switch to zh-HK where it is disabled, then press Enter → `submit(text,currentSkill)` sends that `skill_id`; the server does not enforce `skill.languages` (it only checks project language preferences), so nothing rejects it. Not reachable with the current catalogue (all 17 skills list en+zh-HK), but it is the exact "locale-disabled cannot be sent" invariant the contract states. Fix: clear/revalidate `currentSkill` when locale/commands change and validate against the available command set at send time. | `composer.tsx:39-55,61-67` (selection/send); `studio.tsx:302-306` (commands recomputed, currentSkill not cleared); server language gate `services/api/buyeros_api/services/conversation_turns.py:179-186,294,317` (no `skill.languages` check) | [READ] |
| MINOR-1 | Minor (dismissal UX) | The menu closes only on Escape, selection or a text change; it stays open when focus leaves the textarea (Tab to the send/attach controls) and does not close on an outside click. No keyboard trap (Tab works), but a stale open listbox can remain while focus is elsewhere. | `composer.tsx:64-80,113-128` | [READ] |
| MINOR-2 | Minor (no-match Enter) | When the filter matches nothing, Enter is swallowed (`skillMenuKey` returns `none`, then `event.key==='Enter'` is prevented and returns) — no send, no close; the user must Escape or edit. This is safe (no accidental send) but not announced. | `composer.tsx:73-76`; `skill-library.ts:111-121` | [READ] |
| MINOR-3 | Minor (disabled-composer mutation) | Menu options are not gated by `canWrite`/`busy`: if a slash draft text is restored into a disabled composer (e.g. a viewer with a prior draft), the listbox still opens and mouse/keyboard selection mutates the text and `currentSkill` (send is guarded, so nothing leaves the client). | `composer.tsx:61-68,113-124`; `submit` guard `:55-58` | [READ] |
| MINOR-4 | Minor (dead code) | `SKILL_MORE_LABEL` is exported but unused (`skillMoreLabel` hardcodes both locales); `CatalogueSkill.version` is captured into state but unused (no version pinning, which is correct — just dead data). | `skill-library.ts:48,127-129`; `studio.tsx:150,260-263` | [READ] |
| MINOR-5 | Minor (test gaps) | No test covers: IME/composition Enter/Arrow keys (MAJOR-1), blur/outside-click dismissal, the locale-switch carry-over send (MAJOR-3), a catalogue skill without authored copy (MAJOR-2), or an explicit catalogue-parity assertion. The browser scenario does verify the real 17-skill catalogue count indirectly (8 + "9 more") and the zh-HK disabled reason. | `tests/core-conversation-skill-library.test.mjs`; new browser scenario | [READ] |
| MINOR-6 | Minor (render churn) | `commands` depends on the unstable `t` function (workspace-picker recreates `t` each render), so the 17-command array and menu groups are recomputed on every render. No requests and no correctness impact; a memoised `t` or a stable dependency would avoid the churn. | `studio.tsx:302-306`; `composer.tsx` props | [READ] |

**No blocker was found**: selection never sends, no request is issued by open/filter/select, disabled options cannot be inserted, the turn body carries only `skill_id` + text, and the server remains the version-pinning authority.

## 2. Catalogue parity and versioning (focus 1) [READ]

- The studio fetches `GET /sales/skills` once on mount (existing effect, extended to keep the page: `studio.tsx:257-267`) and builds commands with `buildSkillCommands({skills:catalogue,offered:skillIds,locale,translate:t})` (`:302-306`); the registry `offered` gate is the fetched id set, so unoffered skills are absent (not disabled) — `skill-library.ts:57-66`.
- Categories are an authored map (`CATEGORY_BY_SKILL`) ordered by `CATEGORY_ORDER`; grouping/sorting is deterministic and unit-tested (`skill-library.ts:12-24,96-104`; `tests/core-conversation-skill-library.test.mjs:18-35`).
- No client version/hash invention: commands contain no `version`, `commandInsertion` returns `{text, skillId}` only, and `submit` sends `skill_id` + text through the existing turn client (the server pins versions). Unit test asserts `'version' in command === false` (`:26`).
- Guided templates remain the visible quick-action chips (`studio.tsx` `chips` mapping unchanged); the slash menu covers all 17 offered skills including the six template skills (`skill-library.ts:41-43`; browser scenario filters to `sales-objections`, which is not a template).
- MAJOR-2 is the drift risk in the authored-copy map (silent drop of unknown offered ids, no parity test).

## 3. Selection / Enter semantics (focus 2) [READ]

- Selecting inserts only: `choose()` calls `change(insertion.text)` (sets text, clears current skill, writes the draft), then sets the skill id and dismisses the menu, and focuses the textarea (`composer.tsx:61-68`). No `onSend` call, no request; browser scenario asserts zero `/conversation-turns` posts after Enter-select.
- The second Enter takes the normal path and sends exactly one turn with the recorded `skill_id` and prompt text (`composer.tsx:81`; browser asserts one turn with `skill_id='sales-objections'` and the prompt text).
- Escape closes without sending and preserves the typed text (`skillMenuKey` close → `setMenuDismissed(true)`; browser asserts input value `/` and no post).
- Reopening/selection never duplicates a turn: `menuDismissed`/text-change drive open state; the busy/pending guards plus the existing turn idempotency prevent duplicates.
- Send failure keeps the composer consistent: `submit` only clears the draft/text on `onSend===true`; on failure the text and current skill remain and the existing retry path is shown (`composer.tsx:50-60`).
- MAJOR-1 (IME) and MINOR-1/2/3 are the behavioural gaps in this area.

## 4. Keyboard / a11y (focus 3) [READ]

- Listbox pattern: `role="listbox"` with `aria-label={t('Skill commands')}`, `role="group"` per category, `role="option"` per command with `aria-selected` and `aria-disabled`; the textarea keeps its textbox role and focus and carries `aria-haspopup="listbox"`, `aria-expanded`, `aria-controls` and `aria-activedescendant` (`composer.tsx:110-128`).
- Keyboard reducer: ArrowUp/Down wrap, Home/End, Enter selects, Escape closes (`skill-library.ts:105-121`); handler prevents default only for those actions, so Tab is not trapped. Mouse selection uses `onMouseDown` + `preventDefault` (no focus steal) and is equivalent to keyboard (`composer.tsx:119-124`).
- Disabled options are `aria-disabled` with a localized visible reason and cannot be inserted (keyboard `commandInsertion` returns null; mouse checks `available`); the browser scenario asserts the zh-HK reason and that Enter leaves `/pdf` unchanged.
- MAJOR-1 is the missing `isComposing` guard; MINOR-1 is dismissal on focus loss/outside click.

## 5. Bounds / i18n / honesty (focus 4–5) [READ]

- At most `MAX_VISIBLE_SKILLS=8` options with `more = matches.length - items.length` and a truthful localized "N more" line (`skill-library.ts:92-95,127-129`; browser asserts 8 options and "9 more" for the 17-skill catalogue).
- Filtering is case-insensitive on the localized label, localized prompt and skill id (`skill-library.ts:85-91`).
- i18n: all 17 authored labels/prompts, the eight category labels, the unavailable reason, the menu label, the empty label and the more-count text exist in EN and zh-HK; reviewer union scan finds 0 missing (the committed unit test also asserts every authored label/prompt/category/menu string has `liveZh` copy: `tests/core-conversation-skill-library.test.mjs:89-99`). Prompts inserted are the localized copy for the active locale.
- No ids in ordinary text: skill ids appear only in the option `id`/`aria-activedescendant` attributes (not visible copy); the turn body carries `skill_id` + text only.
- Locale-disabled skills cannot be selected or inserted; MAJOR-3 is the carry-over send edge, and MINOR-3 the disabled-composer mutation edge.
- No request on open/filter/select (commands come from the already-fetched page; selection writes the local draft only; browser asserts the request count is unchanged for open and filter).
- 320 px: the composer/menu use `minWidth:0`, `maxWidth:100%`, `boxSizing:border-box`, `overflowWrap:anywhere` and a bounded scroll area (`composer.tsx:110-116`); the browser scenario asserts no horizontal overflow while the menu is open (BLOCKED locally; CI will prove).

## 6. Regression (focus 6) [TEST]

- Browser gate: parent 21 top-level + 2 loop-generated pairs = **25** scenarios; head 22 + 4 = **26** — exactly one new scenario appended, no prior assertion modified, and the six screenshot paths are identical to the parent.
- Core: `node --test --experimental-test-isolation=none tests/core-*.test.mjs tests/audit-research-intent.test.mjs` → **172 tests, 172 pass**; matches the CI core constant 172 (parent 165 + 7 skill-library tests). `tsc --noEmit` → exit 0; targeted eslint → exit 0.
- i18n union scan (liveZh + zh) for all authored labels/prompts/categories/menu strings → 0 missing.
- No backend or dependency change; the `.github` change is only the core constant (165→172).

## 7. Verification executed / BLOCKED

Executed here: core suite 172/172; tsc; targeted eslint; static counts (26 browser scenarios, six screenshots unchanged, i18n union coverage). The browser gate is **BLOCKED** locally (Playwright `spawn EPERM`); no browser result is claimed. No backend tests are needed (UI-only, no backend change).

## 8. CI artifacts that prove acceptance

| Criterion | Proof | Artifact |
| --- | --- | --- |
| Catalogue→command mapping, filtering, 8+truthful count, keyboard reducer, locale availability, selection insertion, i18n coverage | `tests/core-conversation-skill-library.test.mjs` (7 tests) | job `frontend`: `test-results/core-client.xml` (artifact `buyeros-core-client`, count 172) |
| Full offered set in the menu, no send on select, one send on second Enter with `skill_id`, Escape keeps text, zh-HK disabled reason, no request on open/filter, 320 px no overflow | new browser scenario in `tests/conversation-home-responsive.test.mjs` (26 cases) | job `frontend`: `test-results/conversation-studio.xml` + `test-results/conversation-studio/*.png` (artifact `buyeros-conversation-studio`) |
| Regression: prior 25 scenarios untouched, six screenshots unchanged, tsc/lint | same browser + core artifacts; `pnpm lint`/`tsc` steps | job `frontend` |

**Unproven by any artifact**: IME/composition behaviour (MAJOR-1), catalogue-parity drift (MAJOR-2), locale-switch carry-over send (MAJOR-3), blur/outside-click dismissal, and the disabled-composer mutation edge. No artifact covers a future catalogue skill without authored copy.

## 9. Recommendations (owner: conversation-ui)

1. Ignore menu key handling while `event.nativeEvent.isComposing` (Enter and Arrow keys) so IME composition is never interpreted as selection (MAJOR-1); add a composition unit/browser test.
2. Add a catalogue-parity guard: compare the fetched catalogue ids to `SKILL_AUTHORING` (and fail/fallback visibly for unknown ids) and add a test reading `catalogue.json`; do not silently drop offered skills (MAJOR-2).
3. Revalidate `currentSkill` when locale/catalogue changes and at send time against the available command set; optionally have the server enforce `skill.languages` (MAJOR-3).
4. Minors: close on blur/outside click, surface "no matches" Enter behaviour, gate the menu when `canWrite` is false, remove dead `SKILL_MORE_LABEL`/`version` data, and stabilise the `t` dependency.

## 10. Not reviewed / out of scope

- No production deployment/promotion/Vercel changes; no implementation edits (only this document).
- Real provider/paid behaviour, production data and the browser runtime were not exercised here; the CI artifacts above are the substitute.
