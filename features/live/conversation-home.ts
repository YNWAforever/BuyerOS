/** Public build-time switch. Unset or any value other than `true` keeps the #35 shell. */
export function conversationHomeEnabled(value: string | undefined): boolean {
  return value === 'true';
}

/** Keep an explicit source profile when the ON shell adds the current scope. */
export function applyConversationNavigationScope(target:URL,params:URLSearchParams,enabled:boolean):void {
  for(const [key,value] of params){
    if(enabled&&key==='profile'&&target.searchParams.has('profile'))continue;
    target.searchParams.set(key,value);
  }
}

export const guidedTemplates = [
  {id:'first-project',title:'Guide my first project',prompt:'Help me set up my first BuyerOS project.',question:'What do you already know about your offer?',choices:['I have an offer to describe','I have documents to review'],destination:'Offer',path:'/app/discover/edit'},
  {id:'understand-documents',title:'Understand my documents',prompt:'Help me understand the documents in this project.',question:'Which document would you like to review in Offer?',choices:['Review extraction status','Review candidate facts'],destination:'Offer',path:'/app/discover/edit'},
  {id:'research-market',title:'Research a market',prompt:'Help me plan research for a market.',question:'What would you like to check before research?',choices:['Review existing runs','Review the buyer profile and budget'],destination:'Research runs',path:'/app/runs'},
  {id:'review-buyers',title:'Review & shortlist buyers',prompt:'Help me review and shortlist buyers for this project.',question:'Which part of buyer review needs your attention?',choices:['Review company fit','Review source evidence'],destination:'Buyers',path:'/app/discover'},
  {id:'check-company',title:'Check a company',prompt:'Help me check a company against this project.',question:'What would you like to check in Buyers?',choices:['Find an existing company','Review its evidence and contact context'],destination:'Buyers',path:'/app/discover'},
  {id:'prepare-follow-up',title:'Prepare a follow-up',prompt:'Help me prepare a thoughtful follow-up for buyers I have reviewed.',question:'What would you like to prepare in Drafts?',choices:['Review an existing draft','Prepare a follow-up for human review'],destination:'Drafts',path:'/app/outreach'},
] as const;
export type GuidedTemplate = typeof guidedTemplates[number];
export const customGuidance = {id:'custom',title:'Discussion',prompt:'',question:'Choose the project surface for your next step.',choices:['Review my offer','Review existing results'],destination:'Offer',path:'/app/discover/edit'} as const;
export function templateForId(id:string) {return guidedTemplates.find(item=>item.id===id)??customGuidance;}
// Existing Stage 0 bookmarks remain template entries; they never manufacture a saved thread.
export const illustrativeDiscussions = [
  {id:'prepare-follow-up',title:'Prepare follow-up'},
  {id:'review-buyers',title:'Review buyers'},
] as const;

export type DiscussionRoute = {id:string;title:string};

export function discussionForPath(pathname: string, enabled: boolean): DiscussionRoute | undefined {
  if (!enabled) return undefined;
  if (pathname === '/app') return {id:'home',title:'Discussions'};
  if (pathname === '/app/discussions/new') return {id:'new',title:'New discussion'};
  const legacy=illustrativeDiscussions.find(item => pathname === `/app/discussions/${item.id}`);
  if(legacy)return legacy;
  if(/^\/app\/discussions\/local-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(pathname))return {id:pathname.split('/')[3],title:'Discussion'};
  return undefined;
}

export function isLiveOverviewRoute(pathname: string, enabled: boolean): boolean {
  return pathname === (enabled ? '/app/overview' : '/app');
}
