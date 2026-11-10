/** Phase 3 accessibility helpers shared by the conversation studio. */
export type PanelTabName='results'|'sources'|'decisions';

/**
 * APG tabs keyboard model: ArrowLeft/ArrowRight wrap, Home/End jump to the ends.
 * Returns null for keys the tablist does not own, so normal typing/activation is kept.
 */
export function nextTabIndex(key:string,index:number,count:number):number|null{
  if(count<1||index<0||index>=count)return null;
  if(key==='ArrowRight')return (index+1)%count;
  if(key==='ArrowLeft')return (index-1+count)%count;
  if(key==='Home')return 0;
  if(key==='End')return count-1;
  return null;
}
/** Roving tabindex: exactly the selected tab is in the tab sequence. */
export function tabSequenceIndex(active:number,index:number):0|-1{
  return active===index?0:-1;
}
