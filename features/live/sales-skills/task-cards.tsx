import type { SalesSchema as S } from "@/services/live/sales-transport";
export const skillTitles: Record<string, string> = {
  "sales-prospect": "Plan prospecting",
  "sales-research": "Research a buyer",
  "sales-quick": "Quick research",
  "sales-qualify": "Assess buyer fit",
  "sales-contacts": "Enrich buyer profile",
  "sales-outreach": "Prepare outreach",
  "sales-followup": "Prepare a follow-up",
  "sales-prep": "Prepare a meeting",
  "sales-proposal": "Prepare a proposal",
  "sales-objections": "Handle objections",
  "sales-icp": "Define ideal buyers",
  "sales-competitors": "Compare competitors",
  "sales-report": "Report progress",
  "sales-report-pdf": "Export a report",
  "first-project": "Guide my first project",
  "understand-documents": "Understand my documents",
  "review-buyers": "Review buyers",
};
export function suggestSkill(
  text: string,
  skills: S["SkillDefinition"][],
  translate: (value: string) => string = (value) => value,
) {
  const value = text.trim().normalize("NFKC").toLowerCase();
  return (
    skills.find((skill) =>
      [
        skill.id,
        skillTitles[skill.id],
        translate(skillTitles[skill.id] ?? skill.id),
      ]
        .filter(Boolean)
        .some((alias) => value.includes(alias.normalize("NFKC").toLowerCase())),
    )?.id ?? ""
  );
}
export function TaskCards({
  skills,
  t,
  onSelect,
}: {
  skills: S["SkillDefinition"][];
  t: (s: string) => string;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="sales-cards">
      {skills.map((s) => (
        <button
          type="button"
          data-skill={s.id}
          key={s.id}
          onClick={() => onSelect(s.id)}
        >
          {t(skillTitles[s.id] ?? s.id)}
        </button>
      ))}
    </div>
  );
}
