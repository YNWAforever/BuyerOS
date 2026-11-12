# Increment 2.4 contract — full skill/template library in chips and slash menu

Status: implementation contract. UI-only; the catalogue endpoint already exists.

## What exists (verified)

- `GET /v1/workspaces/{ws}/projects/{pj}/sales/skills` returns `SkillPage` with the
  full catalogue: 17 `SkillDefinition`s (`id`, `version`, `output_kind`,
  `allowed_actions`, `languages`, `budget_class`, `upstream_hash`), from
  `services/api/buyeros_api/sales/catalogue.json` (`template_skills` maps the seven
  templates to skills).
- The studio already fetches that page but keeps only the id set
  (`studio.tsx` `skillIds`). Chips are six hardcoded `guidedTemplates`; the slash
  menu filters only those six and has no keyboard navigation.
- `TurnRequest` carries `skill_id` and `template_id`; the server pins the skill
  version.

## Contract

- **Catalogue parity**: the UI derives commands from the fetched catalogue, not a
  hardcoded list. A skill appears only when the workspace registry actually offers
  it (existing `skillIds` gate). Every offered skill is reachable from the slash
  menu; the guided templates remain the visible quick-action chips.
- **Slash menu**: typing `/` at the start of an empty or slash-prefixed composer
  opens a labelled listbox of the offered skills, grouped by an authored category
  map (research / contacts / outreach / follow-up / proposal / analysis /
  documents / project). It filters on label, prompt and skill id; shows at most
  eight options with a truthful "N more" count; closes on Escape.
- **Keyboard**: ArrowUp/ArrowDown (wrap), Home/End, Enter selects, Escape closes,
  all with `aria-activedescendant` and an `aria-selected` option; the textarea keeps
  focus. Mouse selection is equivalent.
- **Selection is not sending**: choosing a command inserts its localized starter
  prompt into the composer and records the skill id; a second Enter sends, so a
  slash-menu choice can be edited and never spends or executes by accident.
- **Availability honesty**: a skill whose `languages` do not include the current
  locale is disabled in the menu with a localized reason; skills not offered by the
  registry are absent (not disabled). No request is issued by opening, filtering or
  selecting.
- **Version pinning**: send `skill_id` exactly as catalogued; do not invent versions
  or hashes. The server pins the version.
- EN + zh-HK for every new string: 17 skill labels, their starter prompts, the
  category names, the unavailable reason, the "more" count and the menu aria label.
- No new dependency, no backend change, no part-type change.

## Tests

- Unit: catalogue → command mapping (offered only, categories, version untouched),
  filter (label/prompt/id), bounded eight + truthful count, keyboard reducer
  (up/down wrap, home/end, enter/escape), locale-language availability, prompt
  insertion without sending.
- Browser gate: type `/` → listbox opens with the full offered set; filter to a skill
  that is NOT one of the six templates (e.g. an objections/proposal skill) → Enter
  selects and inserts its prompt without any request; second Enter sends exactly one
  turn whose body carries that `skill_id` and the prompt text; Escape closes without
  a request; a locale-disabled skill is disabled and shows its reason; zh-HK labels;
  no horizontal overflow at 320 px while the menu is open. Keep the existing 25
  scenarios strong; report the new core count (165).
