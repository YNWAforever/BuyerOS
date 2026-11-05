import {readFile, writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import openapiTS, {astToString} from 'openapi-typescript';

const contractUrl = new URL('../docs/buyeros/contracts/sales.openapi.yaml', import.meta.url);
const outputUrl = new URL('../services/generated/sales-api.ts', import.meta.url);
const mode = process.argv[2];
if (!['--check','--write'].includes(mode) || process.argv.length !== 3) {
  console.error('usage: node scripts/generate-sales-api.mjs --write|--check');
  process.exit(2);
}
const header = '/** Generated sales extension; run node scripts/generate-sales-api.mjs --write. */\n\n';
const generated = header + astToString(await openapiTS(contractUrl));
const contract=JSON.parse(await readFile(contractUrl,'utf8'));
function inlineSchema(value,depth=0){
  if(depth>30)throw new Error('Input schema recursion exceeded');
  if(Array.isArray(value))return value.map(v=>inlineSchema(v,depth+1));
  if(value&&typeof value==='object'){
    if(value.$ref)return inlineSchema(contract.components.schemas[value.$ref.split('/').at(-1)],depth+1);
    return Object.fromEntries(Object.entries(value).map(([key,v])=>[key,inlineSchema(v,depth+1)]));
  }return value;
}
const inputSchemas=Object.fromEntries(contract.components.schemas.TaskInput.allOf[0].oneOf.map(branch=>[branch.properties.skill_id.const,inlineSchema(branch.properties.arguments)]));
const inputsUrl=new URL('../services/generated/sales-input-schemas.ts',import.meta.url);
const inputs=header+'export const salesInputSchemas: Record<string, unknown> = '+JSON.stringify(inputSchemas,null,2)+';\n';
if(mode==='--write')await writeFile(inputsUrl,inputs,'utf8');
else if((await readFile(inputsUrl,'utf8').catch(()=>'' )).replaceAll('\r\n','\n')!==inputs){console.error('Sales input schemas are stale');process.exit(1);}
const current = await readFile(outputUrl,'utf8').catch(error => {
  if (error.code === 'ENOENT') return null;
  throw error;
});
const normalize = value => value?.replaceAll('\r\n','\n');
if (mode === '--check') {
  if (normalize(current) !== normalize(generated)) {
    console.error('Sales API types are stale: ' + fileURLToPath(outputUrl));
    process.exit(1);
  }
  console.log('Sales API types match the extension contract');
} else {
  const newline = current?.includes('\r\n') ? '\r\n' : '\n';
  await writeFile(outputUrl, generated.replaceAll('\n',newline),'utf8');
  console.log('Wrote ' + fileURLToPath(outputUrl));
}

