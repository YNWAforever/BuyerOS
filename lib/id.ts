// Synthetic record IDs only; not authentication tokens.
let sequence=0;
export function uid(){return typeof crypto!=='undefined'&&typeof crypto.randomUUID==='function'?crypto.randomUUID():`demo-${Date.now().toString(36)}-${(++sequence).toString(36)}-${Math.random().toString(36).slice(2,8)}`;}
