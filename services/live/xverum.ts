import {SalesTransport,type SalesSchema as S} from './sales-transport';
import type {LiveClient} from './client';
import type {SessionScope} from './session';
export class XverumClient extends SalesTransport {
  connections(){return this.request<S['ConnectionPage']>('/xverum/connections');}
  stages(task:string){return this.request<S['XverumTaskStages']>(`/xverum/tasks/${task}/stages`);}
  quoteSearch(input:Extract<S['QuoteRequest'],{stage:'search'}>){return this.request<S['XverumQuote']>('/xverum/quotes','POST',input);}
  quoteDetails(input:Extract<S['QuoteRequest'],{stage:'detail'}>){return this.request<S['XverumQuote']>('/xverum/quotes','POST',input);}
  confirm(task:string,quote:S['XverumQuote'],version:number){return this.request<S['StepReceipt']>(`/xverum/tasks/${task}/quotes/${quote.id}/approve`,'POST',{quote_id:quote.id,fingerprint:quote.fingerprint} satisfies S['QuoteApproval'],version);}
  receipt(id:string){return this.request<S['XverumReceipt']>(`/xverum/receipts/${id}`);}
  candidates(id:string){return this.request<S['XverumCandidatesResponse']['data']>(`/xverum/receipts/${id}/candidates`);}
  propose(input:S['EnrichmentCreate']){return this.request<S['EnrichmentProposal']>('/xverum/enrichment-proposals','POST',input);}
  proposal(id:string){return this.request<S['EnrichmentProposal']>(`/xverum/enrichment-proposals/${id}`);}
  apply(input:S['EnrichmentApply']){return this.request<S['NativeRef']>(`/xverum/enrichment-proposals/${input.proposal_id}/apply`,'POST',input,input.buyer_version);}
}
const cache=new WeakMap<SessionScope,XverumClient>();
export function xverumClient(client:LiveClient,session:SessionScope){let api=cache.get(session);if(!api||api.identity!==session.identity()){api=new XverumClient(client,session);cache.set(session,api);}return api;}
