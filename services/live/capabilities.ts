import type {OperationOutput} from './operations';

export const capabilityNames=['research','contact_enrichment','draft_generation','mailbox','crm'] as const;
export type CapabilityPage=OperationOutput<'getCapabilities'>;

/** An incomplete, duplicate or malformed availability response must fail closed. */
export function validCapabilities(data:unknown):data is CapabilityPage {
  if(!data||typeof data!=='object')return false;
  const value=data as Partial<CapabilityPage>;
  return value.total===5&&value.offset===0&&value.limit===5&&Array.isArray(value.items)&&value.items.length===5&&
    value.items.every(item=>item&&typeof item==='object'&&capabilityNames.includes(item.name)&&
      ['unconfigured','blocked','ready','degraded','disabled'].includes(item.status)&&typeof item.checked_at==='string'&&
      Number.isFinite(Date.parse(item.checked_at))&&Array.isArray(item.reason_codes)&&item.reason_codes.every(code=>typeof code==='string')&&typeof item.billable==='boolean')&&
    new Set(value.items.map(item=>item.name)).size===5;
}
