import type {components} from '@/services/generated/buyeros-api';
export type GroundingSegment=components['schemas']['GroundingSegment'];
export type SegmentPreparation=Omit<GroundingSegment,'classification'> & {classification:''|GroundingSegment['classification']};
/** Array.from iterates Unicode code points, including emoji; never use JS string.length offsets. */
export function prepareGroundingSegments(subject:string,body:string):SegmentPreparation[]{
 const segments:SegmentPreparation[]=[];
 for(const [field,text] of [['subject',subject],['body',body]] as const){
  const points=Array.from(text);let start=0;
  for(let i=0;i<=points.length;i++)if(i===points.length||points[i]==='\n'){
   const exact=points.slice(start,i).join('');
   if(exact.trim())segments.push({field,start,end:i,exact_text:exact,classification:'',evidence_refs:[],offer_fact_refs:[],reason:''});
   start=i+1;
  }
 }
 return segments;
}
export function splitGroundingSegment(segment:SegmentPreparation,position:number):SegmentPreparation[]{
 const points=Array.from(segment.exact_text);
 if(!Number.isInteger(position)||position<=0||position>=points.length)throw new Error('Invalid code-point split');
 const parts=[{...segment,end:segment.start+position,exact_text:points.slice(0,position).join('')},
  {...segment,start:segment.start+position,exact_text:points.slice(position).join('')}];
 if(parts.some(part=>!part.exact_text.trim()))throw new Error('Each segment needs non-whitespace text');
 return parts.map(part=>({...part,classification:'',reason:'',evidence_refs:[],offer_fact_refs:[]}));
}
