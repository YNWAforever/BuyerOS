/** Convert browser UTF-16 offsets without changing the cited source text. */
export function selectionToCodePoints(text: string, startUTF16: number, endUTF16: number): { start: number; end: number } {
  if (typeof text !== 'string' || !Number.isInteger(startUTF16) || !Number.isInteger(endUTF16)
      || startUTF16 < 0 || endUTF16 < startUTF16 || endUTF16 > text.length) {
    throw new RangeError('Selection must be an exact UTF-16 range in the source');
  }
  const boundaries = new Map<number, number>([[0, 0]]);
  let point = 0;
  for (let unit = 0; unit < text.length;) {
    const first = text.charCodeAt(unit);
    if (first >= 0xd800 && first <= 0xdbff) {
      const second = text.charCodeAt(unit + 1);
      if (!(second >= 0xdc00 && second <= 0xdfff)) throw new RangeError('Malformed source surrogate');
      unit += 2;
    } else {
      if (first >= 0xdc00 && first <= 0xdfff) throw new RangeError('Malformed source surrogate');
      unit += 1;
    }
    boundaries.set(unit, ++point);
  }
  const start = boundaries.get(startUTF16), end = boundaries.get(endUTF16);
  if (start === undefined || end === undefined) throw new RangeError('Selection splits a surrogate pair');
  return { start, end };
}

export type ReadonlySelection = {start:number;end:number;direction:'none'|'forward'|'backward'};
/** Some Chromium platforms do not move a read-only textarea caret with arrows.
 * Keep its keyboard selection usable without making the cited text editable.
 * Returned positions are DOM UTF-16 offsets; citation conversion stays separate.
 */
export function moveReadonlySelection(text:string,selection:ReadonlySelection,
  key:'ArrowLeft'|'ArrowRight'|'Home'|'End',extend:boolean):ReadonlySelection {
  selectionToCodePoints(text,selection.start,selection.end);
  if(!['none','forward','backward'].includes(selection.direction))throw new RangeError('Invalid selection direction');
  const anchor=selection.direction==='backward'?selection.end:selection.start;
  const focus=selection.direction==='backward'?selection.start:selection.end;
  const boundaries=[0,...Array.from(new Intl.Segmenter(undefined,{granularity:'grapheme'}).segment(text),part=>part.index+part.segment.length)];
  let next:number;
  if(!extend&&selection.start!==selection.end&&(key==='ArrowLeft'||key==='ArrowRight')){
    next=key==='ArrowLeft'?selection.start:selection.end;
  }else if(key==='Home')next=0;
  else if(key==='End')next=text.length;
  else if(key==='ArrowLeft')next=boundaries.filter(offset=>offset<focus).at(-1)??0;
  else next=boundaries.find(offset=>offset>focus)??text.length;
  if(!extend||next===anchor)return {start:next,end:next,direction:'none'};
  return {start:Math.min(anchor,next),end:Math.max(anchor,next),direction:next<anchor?'backward':'forward'};
}
