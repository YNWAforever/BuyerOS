export type Fit = 'Match'|'Needs review'|'Not a match';
export type Review = 'Awaiting review'|'Accepted'|'Rejected';
export type ContactStatus = 'Not researched'|'Public address / unverified'|'Provider-marked valid'|'Catch-all'|'Unavailable'|'Suppressed';
export interface RecordBase {id:string; projectId:string; workspaceId:string; dataMode:'demo';}
export interface Evidence extends RecordBase {title:string;type:string;excerpt:string;language:string;observedAt:string;requirement:string;kind:'Observation'|'Sample inference';contradicts:boolean;}
export interface Company extends RecordBase {name:string;market:string;type:string;fit:Fit;why:string;review:Review;contact:ContactStatus;policy:'Allowed'|'Unknown';suppressed:boolean;evidence:Evidence[];missing:string;note:string;owner:string;activity:string[];}
export interface Project extends RecordBase {name:string;offer:string;markets:string[];profileVersion:number;}
export interface ICPVersion extends RecordBase {version:number;must:string;nice:string;exclude:string;confirmed:boolean;}
export interface SearchRun extends RecordBase {status:string;stage:number;count:number;rawCount:number;scenario:string;budget:number;startedAt:string;profileVersion:number;target?:number;}
export interface BuyerList extends RecordBase {name:string;members:string[];}
export interface EnrichmentQuote extends RecordBase {companyIds:string[];cost:number;currency:'USD';expiresAt:string;status:'Reserved'|'Confirmed'|'Cancelled';}
export interface OutreachDraft extends RecordBase {buyerId:string;recipient:string;subject:string;body:string;revision:number;status:'Draft'|'In review'|'Approved';approvedRevision?:number;approver?:string;approvedAt?:string;policyReviewed:boolean;sender:string;delivery:'Not connected';followup:string;objective:string;tone:string;language:string;valueProposition:string;}
export interface CostEvent extends RecordBase {category:string;amount:number;currency:'USD';eventId:string;}
export interface OutcomeEvent extends RecordBase {buyerId:string;stage:string;at:string;}
export interface Store {companies:Company[];lists:BuyerList[];drafts:OutreachDraft[];quotes:EnrichmentQuote[];costs:CostEvent[];outcomes:OutcomeEvent[];runs:SearchRun[];budget:number;discoveryBudget:number;contactUnitPrice:number;locale:'en'|'zh-HK';defaultMarkets:string;}
export interface ApiError {code:string;message:string;requestId:string;retryable:boolean;}
export type Workspace={id:string;name:string};
export type LeadAssessment=Pick<Company,'id'|'fit'|'why'|'evidence'>;
export type ContactPoint={id:string;companyId:string;status:ContactStatus;address?:string;dataMode:'demo'};
export type HumanReview={companyId:string;status:Review;reason:string;at:string};
export type ListMembership={listId:string;companyId:string};
export type EnrichmentJob={id:string;quoteId:string;status:string};
export type Approval={draftId:string;revision:number;approver:string;at:string};
export type Suppression={companyId:string;reason:string};

export interface ApiResponse<T>{data:T;requestId:string;dataMode:'demo'|'live'}
export interface Page<T>{items:T[];offset:number;limit:number;total:number;}
export interface RunEvent{eventId:string;runId:string;sequence:number;stage:number;status:string;}
/** Proposed integration boundary, not existing network endpoints. */
export interface BuyerDiscoveryClient {
 createProject(input:Omit<Project,'id'>):Promise<ApiResponse<Project>>;
 updateProject(id:string,input:Partial<Project>):Promise<ApiResponse<Project>>;
 saveICPVersion(input:ICPVersion):Promise<ApiResponse<ICPVersion>>;
 startRun(input:SearchRun):Promise<ApiResponse<SearchRun>>;
 getRun(id:string):Promise<ApiResponse<SearchRun>>;
 cancelRun(id:string):Promise<ApiResponse<SearchRun>>;
 retryRun(id:string):Promise<ApiResponse<SearchRun>>;
 subscribeRunEvents(id:string,listener:(e:RunEvent)=>void):()=>void;
 listBuyers(input:{market?:string;offset:number;limit:number}):Promise<ApiResponse<Page<Company>>>;
 getBuyer(id:string):Promise<ApiResponse<Company>>;
 reviewBuyers(ids:string[],review:Review,reason:string):Promise<ApiResponse<Company[]>>;
 quoteLookup(ids:string[]):Promise<ApiResponse<EnrichmentQuote>>;
 confirmLookup(quoteId:string):Promise<ApiResponse<EnrichmentJob>>;
 saveDraft(draft:OutreachDraft):Promise<ApiResponse<OutreachDraft>>;
 approveDraft(id:string,expectedRevision:number):Promise<ApiResponse<Approval>>;
 getUsage():Promise<ApiResponse<{spent:number;reserved:number;remaining:number}>>;
 recordOutcome(event:OutcomeEvent):Promise<ApiResponse<OutcomeEvent>>;
}
