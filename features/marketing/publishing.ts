import defaults from '@/config/marketing.public.json';

export interface PublisherInput {
  siteUrl?: string | null; legalEntity?: string | null; contactEmail?: string | null;
  leadRetentionDays?: number | null; privacyApproved?: boolean; termsApproved?: boolean;
}
export interface Publisher {
  origin: string | null; legalEntity: string | null; contactEmail: string | null;
  leadRetentionDays: number | null; legalApproved: boolean; indexable: boolean;
}

export function publishing(input: PublisherInput = {...defaults, siteUrl: process.env.MARKETING_SITE_URL || defaults.siteUrl}): Publisher {
  let origin: string | null = null;
  try {
    const url = new URL(input.siteUrl ?? '');
    const loopback = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
    if ((url.protocol === 'https:' || (loopback && url.protocol === 'http:')) && !url.username && !url.password &&
      url.pathname === '/' && !url.search && !url.hash) origin = url.origin;
  } catch { /* No made-up canonical origin in a preview. */ }
  const legalEntity = input.legalEntity?.trim() || null;
  const contactEmail = input.contactEmail && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(input.contactEmail) ? input.contactEmail : null;
  const leadRetentionDays = Number.isInteger(input.leadRetentionDays) && input.leadRetentionDays! > 0 ? input.leadRetentionDays! : null;
  const legalApproved = Boolean(input.privacyApproved && input.termsApproved && legalEntity && contactEmail && leadRetentionDays);
  return {origin, legalEntity, contactEmail, leadRetentionDays, legalApproved, indexable: Boolean(origin && legalApproved)};
}
