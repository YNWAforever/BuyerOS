/** Only code-owned locators, never model-provided URLs or source bodies. */
export type CitationRef = {id:string;label:'Approved offer fact'|'Offer document';locator:{surface:'profile'|'document';id:string}};
export type GroundedReply = {status:'needs_review';text:string;citations:CitationRef[];fixture:boolean};
const uuid='[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}';
export function exactFields(value:unknown,keys:readonly string[]):value is Record<string,unknown>{
  if(!value||typeof value!=='object'||Array.isArray(value))return false;
  const proto=Object.getPrototypeOf(value),actual=Reflect.ownKeys(value);
  return (proto===Object.prototype||proto===null)&&actual.length===keys.length&&actual.every(key=>
    typeof key==='string'&&keys.includes(key)&&'value' in Object.getOwnPropertyDescriptor(value,key)!);
}
export function validCitation(value:unknown):value is CitationRef{
  if(!exactFields(value,['id','label','locator'])||typeof value.id!=='string'||
    !exactFields(value.locator,['surface','id'])||typeof value.locator.id!=='string')return false;
  const document=new RegExp(`^document:(${uuid})$`).exec(value.id);
  const fact=new RegExp(`^fact:profile:(${uuid}):${uuid}$`).exec(value.id);
  return document?value.label==='Offer document'&&value.locator.surface==='document'&&value.locator.id===document[1]:
    !!fact&&value.label==='Approved offer fact'&&value.locator.surface==='profile'&&value.locator.id===fact[1];
}
export function validGroundedReply(value:unknown):value is GroundedReply{
  return exactFields(value,['status','text','citations','fixture'])&&value.status==='needs_review'&&typeof value.fixture==='boolean'&&
    typeof value.text==='string'&&!!value.text.trim()&&value.text.length<=4000&&Array.isArray(value.citations)&&
    value.citations.length>=1&&value.citations.length<=20&&value.citations.every(validCitation)&&
    new Set(value.citations.map(row=>row.id)).size===value.citations.length;
}
export function citationPath(ref:CitationRef):string{
  if(!validCitation(ref))throw new Error('Invalid citation');
  return ref.locator.surface==='profile'?`/app/overview?profile=${encodeURIComponent(ref.locator.id)}`:
    `/app/discover/edit?document=${encodeURIComponent(ref.locator.id)}#offer-documents`;
}
