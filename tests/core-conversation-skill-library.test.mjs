import test from 'node:test';
import assert from 'node:assert/strict';
import {registerHooks} from 'node:module';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
registerHooks({resolve(s,c,next){try{return next(s,c);}catch(e){if(s.startsWith('.'))for(const ext of ['.ts','.tsx'])try{return next(s+ext,c);}catch{}throw e;}},load(u,c,next){if(/\.tsx?$/.test(u))return {format:'module',shortCircuit:true,source:ts.transpileModule(readFileSync(new URL(u),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText};return next(u,c);}});

const {SKILL_AUTHORING,SKILL_MENU_EMPTY,SKILL_MENU_LABEL,SKILL_UNAVAILABLE_REASON,MAX_VISIBLE_SKILLS,
  buildSkillCommands,filterSkillCommands,visibleSkillCommands,groupSkillCommands,skillMenuKey,commandInsertion,
  skillMoreLabel}=await import('../features/live/conversation/skill-library.ts');
const {liveZh}=await import('../features/live/locale.ts');

const identity=value=>value;
const skills=Object.keys(SKILL_AUTHORING).map(id=>({id,version:'1',languages:['en','zh-HK']}));
const offered=new Set(skills.map(skill=>skill.id));
const commands=buildSkillCommands({skills,offered,locale:'en',translate:identity});

test('commands derive from the offered catalogue only, preserving authored categories',()=>{
  assert.equal(commands.length,Object.keys(SKILL_AUTHORING).length);
  const unoffered=buildSkillCommands({skills:[...skills,{id:'future-skill',languages:['en']}],offered,locale:'en',translate:identity});
  assert.equal(unoffered.some(command=>command.id==='future-skill'),false,'unoffered skills are absent');
  const empty=buildSkillCommands({skills,offered:new Set(),locale:'en',translate:identity});
  assert.deepEqual(empty,[],'no offered ids means no commands');
  for(const command of commands){
    assert.equal(command.available,true);
    assert.equal('version' in command,false,'the client never carries catalogue versions');
    assert.equal(command.label,SKILL_AUTHORING[command.id].label);
    assert.equal(command.prompt,SKILL_AUTHORING[command.id].prompt);
  }
  const categories=commands.map(command=>command.categoryId);
  const firstCategories=[...new Set(categories)];
  assert.deepEqual(firstCategories,['research','contacts','outreach','follow-up','proposal','analysis','documents','project'],
    'commands are grouped in the authored category order');
  assert.deepEqual(groupSkillCommands(commands).map(group=>group.categoryId),firstCategories);
});

test('filter matches label, starter prompt or skill id case-insensitively',()=>{
  assert.deepEqual(filterSkillCommands(commands,'objections').map(command=>command.id),['sales-objections']);
  assert.deepEqual(filterSkillCommands(commands,'buyer').map(command=>command.id).includes('review-buyers'),true,'prompt/label text matches');
  assert.deepEqual(filterSkillCommands(commands,'SALES-PROPOSAL').map(command=>command.id),['sales-proposal']);
  assert.equal(filterSkillCommands(commands,'   ').length,commands.length,'blank query keeps all');
  assert.deepEqual(filterSkillCommands(commands,'nothing-matches-this'),[]);
});

test('the menu shows at most eight options with a truthful more count',()=>{
  const all=visibleSkillCommands(commands);
  assert.equal(all.items.length,MAX_VISIBLE_SKILLS);
  assert.equal(all.more,commands.length-MAX_VISIBLE_SKILLS);
  assert.ok(all.more>0);
  const small=visibleSkillCommands(commands.slice(0,3));
  assert.equal(small.items.length,3);
  assert.equal(small.more,0);
  assert.equal(skillMoreLabel(all.more,'en'),`${all.more} more`);
  assert.equal(skillMoreLabel(all.more,'zh-HK'),`還有 ${all.more} 項`);
});

test('keyboard reducer wraps, jumps and selects without ever sending',()=>{
  assert.deepEqual(skillMenuKey('ArrowDown',0,3),{type:'move',index:1});
  assert.deepEqual(skillMenuKey('ArrowDown',2,3),{type:'move',index:0},'down wraps');
  assert.deepEqual(skillMenuKey('ArrowUp',0,3),{type:'move',index:2},'up wraps');
  assert.deepEqual(skillMenuKey('Home',2,3),{type:'move',index:0});
  assert.deepEqual(skillMenuKey('End',0,3),{type:'move',index:2});
  assert.deepEqual(skillMenuKey('Enter',1,3),{type:'select',index:1});
  assert.deepEqual(skillMenuKey('Escape',1,3),{type:'close'});
  assert.deepEqual(skillMenuKey('Tab',1,3),{type:'none'});
  assert.deepEqual(skillMenuKey('Enter',0,0),{type:'none'},'no options means no accidental selection');
});

test('locale-incompatible skills are disabled with a localized reason',()=>{
  const localised=buildSkillCommands({skills:[
    {id:'sales-objections',languages:['en']},
    {id:'sales-proposal',languages:['en','zh-HK']},
  ],offered:new Set(['sales-objections','sales-proposal']),locale:'zh-HK',translate:key=>liveZh[key]??key});
  const disabled=localised.find(command=>command.id==='sales-objections');
  assert.equal(disabled.available,false);
  assert.equal(disabled.reason,liveZh[SKILL_UNAVAILABLE_REASON]);
  assert.equal(disabled.label,liveZh[SKILL_AUTHORING['sales-objections'].label]);
  assert.equal(commandInsertion(disabled),null,'a disabled command cannot be inserted');
  assert.equal(localised.find(command=>command.id==='sales-proposal').available,true);
});

test('selection inserts the localized prompt and records only the skill id',()=>{
  const command=commands.find(item=>item.id==='sales-objections');
  assert.deepEqual(commandInsertion(command),{text:SKILL_AUTHORING['sales-objections'].prompt,skillId:'sales-objections'});
  assert.equal('version' in commandInsertion(command),false);
  assert.equal(commandInsertion(undefined),null);
});

test('every authored skill/category/menu string has EN and zh-HK copy',()=>{
  for(const authored of Object.values(SKILL_AUTHORING)){
    assert.equal(typeof liveZh[authored.label],'string',authored.label);
    assert.equal(typeof liveZh[authored.prompt],'string',authored.prompt);
  }
  for(const category of ['Research','Contacts','Outreach','Follow-up','Proposal','Analysis','Documents','Project'])
    assert.equal(typeof liveZh[category],'string',category);
  assert.equal(typeof liveZh[SKILL_UNAVAILABLE_REASON],'string');
  assert.equal(typeof liveZh[SKILL_MENU_LABEL],'string');
  assert.equal(typeof liveZh[SKILL_MENU_EMPTY],'string');
});
