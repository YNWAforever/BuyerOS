import {test as base, expect} from '@playwright/test';

/** Obtain the Vercel deployment-protection bypass cookie once, into the browser
 * context's shared cookie jar. The raw token is never attached to browser
 * requests (it would otherwise ride cross-origin redirects/assets); only the
 * resulting cookie is sent. With no bypass env this fixture is a no-op. */
const protectionBypass=process.env.BUYEROS_QA_PROTECTION_BYPASS?.trim();
const origin=process.env.BUYEROS_QA_ORIGIN?.trim();

export const test=base.extend({
  context:async({context},run)=>{
    if(protectionBypass&&origin){
      // context.request shares cookies with this browser context; maxRedirects:0
      // keeps the token on the single candidate-origin request.
      await context.request.get(origin,{
        headers:{'x-vercel-protection-bypass':protectionBypass,
          'x-vercel-set-bypass-cookie':'true'},
        maxRedirects:0,
        failOnStatusCode:false,
      });
    }
    await run(context);
  },
});

export {expect};
