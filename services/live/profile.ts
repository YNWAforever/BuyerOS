// services/live/profile.ts
/** Turn the wizard's free-text Offer into contract payloads, or refuse. */

export class ProfileError extends Error {}

const MARKETS: Record<string, string> = {
  germany: 'DE', deutschland: 'DE', de: 'DE',
  netherlands: 'NL', holland: 'NL', nl: 'NL',
  belgium: 'BE', belgie: 'BE', belgi: 'BE', be: 'BE',
};
const LANGUAGES: Record<string, string> = {
  english: 'en', en: 'en',
  german: 'de', deutsch: 'de', de: 'de',
  dutch: 'nl', nederlands: 'nl', nl: 'nl',
  french: 'fr', francais: 'fr', fr: 'fr',
};

function split(text: string): string[] {
  return String(text || '').split(/[,;/]/).map((part) => part.trim()).filter(Boolean);
}

function resolve(text: string, table: Record<string, string>): {codes: string[]; unknown: string[]} {
  const codes: string[] = [];
  const unknown: string[] = [];
  for (const part of split(text)) {
    const code = table[part.toLowerCase()];
    if (code) { if (!codes.includes(code)) codes.push(code); }
    else unknown.push(part);
  }
  return {codes, unknown};
}

export function resolveMarkets(text: string) { return resolve(text, MARKETS); }
export function resolveLanguages(text: string) { return resolve(text, LANGUAGES); }

export interface Offerish {
  company: string; product: string; value: string; website?: string; markets: string;
  language: string; must?: string; nice?: string; exclude?: string;
  buyerTypes?: string[]; roles?: string; advanced?: Record<string, string>;
}

function requireKnown(label: string, text: string, table: Record<string, string>): string[] {
  const {codes, unknown} = resolve(text, table);
  if (unknown.length) throw new ProfileError(`${label} not recognised: ${unknown.join(', ')}`);
  if (!codes.length) throw new ProfileError(`${label} is required`);
  return codes;
}

export function toProjectCreate(offer: Offerish) {
  const markets = requireKnown('market', offer.markets, MARKETS);
  const languages = requireKnown('language', offer.language, LANGUAGES);
  const advanced = Object.entries(offer.advanced ?? {}).filter(([, v]) => v)
    .map(([k, v]) => `${k}: ${v}`).join('\n');
  return {
    name: offer.company,
    company_name: offer.company,
    offer: [offer.product, offer.value, advanced].filter(Boolean).join('\n'),
    website: offer.website ? offer.website : undefined,
    markets,
    language_preferences: languages,
  };
}

function requirements(text: string, category: string) {
  return split(text).map((item, index) => ({
    id: `${category}-${index + 1}`,
    text: item,
    category,
    hard_exclusion: category === 'exclude',
  }));
}

export function toIcpSaveRequest(offer: Offerish) {
  const markets = requireKnown('market', offer.markets, MARKETS);
  const languages = requireKnown('language', offer.language, LANGUAGES);
  const requirementsList = [
    ...requirements(offer.must ?? '', 'must'),
    ...requirements(offer.nice ?? '', 'nice'),
    ...requirements(offer.exclude ?? '', 'exclude'),
  ];
  if (!requirementsList.length) throw new ProfileError('at least one buyer requirement is required');
  return {
    offer_facts: [],
    requirements: requirementsList,
    markets,
    buyer_types: offer.buyerTypes?.length ? offer.buyerTypes : ['Distributor'],
    languages,
    desired_roles: split(offer.roles ?? ''),
  };
}
