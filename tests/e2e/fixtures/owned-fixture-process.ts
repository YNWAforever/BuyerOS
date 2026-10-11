import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
const execute=promisify(execFile);
type Options={cwd:string;timeout:number;maxBuffer?:number};
type Failure={code?:string|number;signal?:string|null;killed?:boolean;stdout?:string;stderr?:string;message?:string;stack?:string;cmd?:string};
const redact=(value:string)=>value.replace(/postgres(?:ql)?(?:\+\w+)?:\/\/[^\s]+/g,'[REDACTED_FIXTURE_DSN]');

/** Native owned-fixture subprocess only. Preserve failure identity; never retry. */
export async function runOwnedFixtureProcess(executable:string,args:string[],options:Options){
  try{return await execute(executable,args,{...options,encoding:'utf8'});}
  catch(error){
    const failure=error as Failure;
    // Node includes stderr and command text in Error.message/stack, so console
    // redaction alone cannot protect the eventual JUnit or thrown exception.
    for(const key of ['message','stack','stdout','stderr','cmd'] as const){
      const value=failure[key];if(typeof value==='string')failure[key]=redact(value);
    }
    console.error('C61_FIXTURE_PROCESS_FAILURE',JSON.stringify({code:failure.code,signal:failure.signal,
      killed:failure.killed,stdout:failure.stdout??'',stderr:failure.stderr??''}));
    throw error;
  }
}
