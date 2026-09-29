import type {Offer} from '@/features/discovery/wizard';
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
    const code = table[part.toLowerCase()]
      ?? (table === MARKETS && /^[a-z]{2}$/i.test(part) ? part.toUpperCase() : undefined)
      ?? (table === LANGUAGES && /^[a-z]{2}(?:-[a-z]{2})?$/i.test(part) ? part.toLowerCase().replace(/-([a-z]{2})$/, (_, region:string)=>`-${region.toUpperCase()}`) : undefined);
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

type RequirementCategory = 'must' | 'nice' | 'exclude';
function requirements(text: string, category: RequirementCategory) {
  return split(text).map((item, index) => ({
    // IDs are stable across same-payload retries and unique within a version.
    id: `e0000000-0000-4000-8000-${{must:'1',nice:'2',exclude:'3'}[category]}${(index + 1).toString(16).padStart(11, '0')}`,
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
    offer_facts: ([
      ['product', offer.product],
      ['value_proposition', offer.value],
    ] as const).map(([field, value], index) => ({
      id: `d0000000-0000-4000-8000-${(index + 1).toString(16).padStart(12, '0')}`,
      field, value: value.trim(), provenance: 'user_entered' as const, approved: false,
    })),
    requirements: requirementsList,
    markets,
    buyer_types: offer.buyerTypes?.length ? offer.buyerTypes : ['Distributor'],
    languages,
    desired_roles: split(offer.roles ?? ''),
  };
}


/** A live project starts blank. Demo fixture values never seed a live form. */
export function emptyLiveOffer(): Offer {
  return {company:'',product:'',value:'',website:'',markets:'',type:'',must:'',nice:'',exclude:'',
    budget:'',contacts:'',target:'',scenario:'',confirmed:false,language:'',buyerTypes:[],advanced:{},roles:''};
}

export function validateLiveOffer(offer: Offer): void {
  if (offer.company.trim().length < 2 || offer.product.trim().length < 2 || offer.value.trim().length < 5)
    throw new ProfileError('Enter company, product and value proposition before saving.');
  if (offer.website.trim()) {
    let url: URL;
    try {url = new URL(offer.website);} catch {throw new ProfileError('Enter a valid website URL.');}
    if (!['http:','https:'].includes(url.protocol)) throw new ProfileError('Enter an HTTP or HTTPS website URL.');
  }
  if (!offer.buyerTypes?.length || !offer.must.trim() || !offer.confirmed)
    throw new ProfileError('Choose a buyer type, enter must-have requirements and confirm them.');
  toProjectCreate(offer);
  toIcpSaveRequest(offer);
}

interface ProfileForOffer {
  offer_facts: {field:string;value:string}[];
  requirements: {category:string;text:string}[];
  buyer_types: string[]; desired_roles?: string[];
}
interface ProjectForOffer {
  name:string; company_name:string; offer:string; website?:string|null;
  markets:string[]; language_preferences:string[];
}
export function offerFromProject(project: ProjectForOffer, icp?: ProfileForOffer | null): Offer {
  const text=project.offer.split('\n');
  const fact=(field:string)=>icp?.offer_facts.find(item=>item.field===field)?.value;
  return {...emptyLiveOffer(),company:project.company_name||project.name,product:fact('product')??text[0]??'',
    value:fact('value_proposition')??text[1]??'',website:project.website??'',
    markets:project.markets.join(', '),language:project.language_preferences.join(', '),
    buyerTypes:icp?.buyer_types??[],roles:icp?.desired_roles?.join(', ')??'',
    must:icp?.requirements.filter(item=>item.category==='must').map(item=>item.text).join('; ')??'',
    nice:icp?.requirements.filter(item=>item.category==='nice').map(item=>item.text).join('; ')??'',
    exclude:icp?.requirements.filter(item=>item.category==='exclude').map(item=>item.text).join('; ')??'',
    confirmed:false};
}
