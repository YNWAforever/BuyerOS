/**
 * Increment 2.4: the studio's skill library. Commands come from the fetched
 * catalogue (offered ids only), grouped by an authored category map. This module
 * is pure: selection inserts a prompt; sending stays with the composer.
 */
export type CatalogueSkill={id:string;version?:string|number;languages?:ReadonlyArray<string>};
export type SkillCommand={
  id:string;label:string;prompt:string;categoryId:SkillCategoryId;categoryLabel:string;
  available:boolean;reason:string;
};
export type SkillCategoryId='research'|'contacts'|'outreach'|'follow-up'|'proposal'|'analysis'|'documents'|'project';
const CATEGORY_ORDER:readonly SkillCategoryId[]=['research','contacts','outreach','follow-up','proposal','analysis','documents','project'];
const CATEGORY_LABELS:Record<SkillCategoryId,string>={
  research:'Research',contacts:'Contacts',outreach:'Outreach','follow-up':'Follow-up',
  proposal:'Proposal',analysis:'Analysis',documents:'Documents',project:'Project',
};
const CATEGORY_BY_SKILL:Record<string,SkillCategoryId>={
  'sales-prospect':'research','sales-research':'research','sales-quick':'research',
  'sales-qualify':'analysis','sales-contacts':'contacts','sales-outreach':'outreach',
  'sales-followup':'follow-up','sales-prep':'documents','sales-proposal':'proposal',
  'sales-objections':'proposal','sales-icp':'analysis','sales-competitors':'analysis',
  'sales-report':'documents','sales-report-pdf':'documents','first-project':'project',
  'understand-documents':'documents','review-buyers':'analysis',
};
/** Authored EN copy is also the locale key; zh-HK lives in the locale files. */
export const SKILL_AUTHORING:Record<string,{label:string;prompt:string}>={
  'sales-prospect':{label:'Prospect a new market',prompt:'Help me find and qualify suitable buyers for this project.'},
  'sales-research':{label:'Research a market',prompt:'Help me plan research for a market.'},
  'sales-quick':{label:'Quick market check',prompt:'Give me a quick, cited check of this market.'},
  'sales-qualify':{label:'Qualify a buyer',prompt:'Help me qualify whether this buyer fits the project.'},
  'sales-contacts':{label:'Find buying contacts',prompt:'Help me find the right buying contacts and verify their details.'},
  'sales-outreach':{label:'Draft an outreach message',prompt:'Help me prepare an outreach draft for human review.'},
  'sales-followup':{label:'Plan a follow-up',prompt:'Help me prepare a thoughtful follow-up for buyers I reviewed.'},
  'sales-prep':{label:'Prepare a meeting brief',prompt:'Help me prepare a meeting brief for this project.'},
  'sales-proposal':{label:'Shape a proposal',prompt:'Help me shape a proposal from our approved offer.'},
  'sales-objections':{label:'Handle objections',prompt:'Help me prepare responses to likely buyer objections.'},
  'sales-icp':{label:'Refine the ideal buyer profile',prompt:'Help me refine the ideal buyer profile for this project.'},
  'sales-competitors':{label:'Compare competitors',prompt:'Help me compare the competitor set for this project.'},
  'sales-report':{label:'Summarise pipeline progress',prompt:'Help me summarise pipeline progress for this project.'},
  'sales-report-pdf':{label:'Export a report',prompt:'Help me prepare a report export from current results.'},
  'first-project':{label:'Guide my first project',prompt:'Help me set up my first BuyerOS project.'},
  'understand-documents':{label:'Understand my documents',prompt:'Help me understand the documents in this project.'},
  'review-buyers':{label:'Review and shortlist buyers',prompt:'Help me review and shortlist buyers for this project.'},
};
export const SKILL_UNAVAILABLE_REASON='This skill is not available in the current language.';
export const SKILL_MENU_LABEL='Skill commands';
export const SKILL_MENU_EMPTY='No matching skills.';
export const SKILL_MORE_LABEL='More skills';
export const MAX_VISIBLE_SKILLS=8;
function categoryFor(id:string):SkillCategoryId{
  return CATEGORY_BY_SKILL[id]??'project';
}
/**
 * Offered-only catalogue → menu commands. Commands never carry a version/hash:
 * the server pins catalogue versions, the client only sends `skill_id`.
 */
export function buildSkillCommands(input:{
  skills:ReadonlyArray<CatalogueSkill>;offered:ReadonlySet<string>;locale:'en'|'zh-HK';
  translate:(value:string)=>string;
}):SkillCommand[]{
  const authoring=SKILL_AUTHORING;
  return input.skills
    .filter(skill=>skill&&typeof skill.id==='string'&&input.offered.has(skill.id))
    .map((skill,index)=>({skill,index}))
    .filter(({skill})=>Boolean(authoring[skill.id]))
    .sort((left,right)=>{
      const order=CATEGORY_ORDER.indexOf(categoryFor(left.skill.id))-CATEGORY_ORDER.indexOf(categoryFor(right.skill.id));
      return order||left.index-right.index;
    })
    .map(({skill})=>{
      const authored=authoring[skill.id];
      const categoryId=categoryFor(skill.id);
      const available=Array.isArray(skill.languages)?skill.languages.includes(input.locale):false;
      return {
        id:skill.id,
        label:input.translate(authored.label),
        prompt:input.translate(authored.prompt),
        categoryId,
        categoryLabel:input.translate(CATEGORY_LABELS[categoryId]),
        available,
        reason:available?'':input.translate(SKILL_UNAVAILABLE_REASON),
      };
    });
}
export function filterSkillCommands(commands:ReadonlyArray<SkillCommand>,query:string):SkillCommand[]{
  const needle=query.trim().toLowerCase();
  if(!needle)return [...commands];
  return commands.filter(command=>
    command.label.toLowerCase().includes(needle)||command.prompt.toLowerCase().includes(needle)||
    command.id.toLowerCase().includes(needle));
}
export function visibleSkillCommands(commandList:ReadonlyArray<SkillCommand>,limit=MAX_VISIBLE_SKILLS){
  const items=commandList.slice(0,limit);
  return {items,more:Math.max(0,commandList.length-items.length)};
}
export function groupSkillCommands(commandList:ReadonlyArray<SkillCommand>):{categoryId:SkillCategoryId;label:string;items:SkillCommand[]}[]{
  const groups:{categoryId:SkillCategoryId;label:string;items:SkillCommand[]}[]=[];
  for(const command of commandList){
    const last=groups.at(-1);
    if(last&&last.categoryId===command.categoryId)last.items.push(command);
    else groups.push({categoryId:command.categoryId,label:command.categoryLabel,items:[command]});
  }
  return groups;
}
export type SkillMenuAction={type:'move';index:number}|{type:'select';index:number}|{type:'close'}|{type:'none'};
function wrap(index:number,count:number):number{
  if(count<=0)return -1;
  return ((index%count)+count)%count;
}
/** Pure keyboard reducer for the slash-menu listbox. */
export function skillMenuKey(key:string,activeIndex:number,count:number):SkillMenuAction{
  if(count<=0)return key==='Escape'?{type:'close'}:{type:'none'};
  const active=activeIndex>=0&&activeIndex<count?activeIndex:0;
  if(key==='ArrowDown')return {type:'move',index:wrap(active+1,count)};
  if(key==='ArrowUp')return {type:'move',index:wrap(active-1,count)};
  if(key==='Home')return {type:'move',index:0};
  if(key==='End')return {type:'move',index:count-1};
  if(key==='Enter')return {type:'select',index:active};
  if(key==='Escape')return {type:'close'};
  return {type:'none'};
}
/** A chosen command only stages text + skill id; sending is a separate action. */
export function commandInsertion(command:SkillCommand):{text:string;skillId:string}|null{
  if(!command||!command.available)return null;
  return {text:command.prompt,skillId:command.id};
}
export function skillMoreLabel(more:number,locale:'en'|'zh-HK'):string{
  return locale==='zh-HK'?`還有 ${more} 項`:`${more} more`;
}
