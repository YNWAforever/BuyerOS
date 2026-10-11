import test from 'node:test';
import assert from 'node:assert/strict';
const load = async () => (await import('../services/live/text-selection-offsets.ts')).selectionToCodePoints;

test('C61T-10 selected Chinese emoji converts UTF-16 to exact code points', async () => {
 const convert=await load(); const text='中😀é文';
 const range=convert(text,1,3);
 assert.deepEqual(range,{start:1,end:2});
 assert.equal(Array.from(text).slice(range.start,range.end).join(''),'😀');
});
test('C61T-10 combining marks and CRLF remain separate unchanged code points', async () => {
 const convert=await load();const text='中😀é文\r\n末';
 assert.deepEqual(convert(text,3,5),{start:2,end:4});
 assert.deepEqual(convert(text,6,8),{start:5,end:7});
 assert.equal(Array.from(text).slice(2,4).join(''),'é');
});
test('C61T-10 half-surrogate selection and caret boundaries are rejected', async () => {
 const convert=await load();
 for(const range of [[0,2],[2,3],[2,2]])assert.throws(()=>convert('中😀文',...range),RangeError);
});
test('C61T-10 keyboard caret and empty text have exact boundaries', async () => {
 const convert=await load();
 assert.deepEqual(convert('中😀文',3,3),{start:2,end:2});
 assert.deepEqual(convert('',0,0),{start:0,end:0});
});
test('C61T-10 invalid offsets fail without clamping or normalizing', async () => {
 const convert=await load();
 for(const range of [[-1,1],[0,5],[3,1],[0.5,1],[NaN,1],[0,Infinity],[false,1]])assert.throws(()=>convert('中😀文',...range),RangeError);
});
test('C61T-10 ZWJ emoji counts code points without changing source bytes', async () => {
 const convert=await load(); const text='甲👩‍💻乙';
 const range=convert(text,1,6);
 assert.deepEqual(range,{start:1,end:4});
 assert.equal(Array.from(text).slice(range.start,range.end).join(''),'👩‍💻');
});
test('C61T-10 malformed lone surrogate source cannot acquire a citation range', async () => {
 const convert=await load();
 for(const text of ['甲\ud800乙','甲\udc00乙'])assert.throws(()=>convert(text,0,1),RangeError);
});

async function movement(){const {moveReadonlySelection}=await import('../services/live/text-selection-offsets.ts');assert.equal(typeof moveReadonlySelection,'function');return moveReadonlySelection;}
test('C61T-10 read-only keyboard caret moves by graphemes and selects exact emoji',async()=>{
 const move=await movement(),text='中😀é文';
 const one=move(text,{start:0,end:0,direction:'none'},'ArrowRight',false);assert.deepEqual(one,{start:1,end:1,direction:'none'});
 const selected=move(text,one,'ArrowRight',true);assert.deepEqual(selected,{start:1,end:3,direction:'forward'});
 assert.deepEqual(move(text,{start:3,end:3,direction:'none'},'ArrowRight',true),{start:3,end:5,direction:'forward'});
 assert.deepEqual(move('甲👩‍💻乙',{start:1,end:1,direction:'none'},'ArrowRight',true),{start:1,end:6,direction:'forward'});
});
test('C61T-10 Shift arrows retain their anchor when shrinking or reversing selection',async()=>{
 const move=await movement(),text='中😀é文';
 assert.deepEqual(move(text,{start:1,end:3,direction:'forward'},'ArrowLeft',true),{start:1,end:1,direction:'none'});
 assert.deepEqual(move(text,{start:1,end:3,direction:'backward'},'ArrowLeft',true),{start:0,end:3,direction:'backward'});
 assert.deepEqual(move(text,{start:1,end:3,direction:'backward'},'ArrowRight',false),{start:3,end:3,direction:'none'});
 assert.deepEqual(move(text,{start:1,end:3,direction:'forward'},'ArrowLeft',false),{start:1,end:1,direction:'none'});
});
test('C61T-10 read-only Home End and limits preserve the exact unchanged text',async()=>{
 const move=await movement(),text='中😀é文';
 assert.deepEqual(move(text,{start:3,end:3,direction:'none'},'Home',false),{start:0,end:0,direction:'none'});
 assert.deepEqual(move(text,{start:3,end:3,direction:'none'},'End',true),{start:3,end:6,direction:'forward'});
 assert.deepEqual(move(text,{start:0,end:0,direction:'none'},'ArrowLeft',true),{start:0,end:0,direction:'none'});
 assert.deepEqual(move('',{start:0,end:0,direction:'none'},'ArrowRight',false),{start:0,end:0,direction:'none'});
});
test('C61T-10 read-only movement rejects malformed or half-surrogate ranges',async()=>{
 const move=await movement();
 for(const range of [{start:2,end:2,direction:'none'},{start:-1,end:1,direction:'none'}])assert.throws(()=>move('中😀文',range,'ArrowRight',true),RangeError);
 assert.throws(()=>move('甲\ud800乙',{start:0,end:0,direction:'none'},'ArrowRight',true),RangeError);
});
