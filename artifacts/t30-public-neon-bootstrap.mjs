import assert from 'node:assert/strict';

/** Inspect only serialized public config; never call an auth endpoint or log its values. */
export function assertPublicNeonBootstrap(body) {
  // Vinext embeds the RSC payload in a JSON string inside an inline script.
  const serialized=body.replaceAll('\\"','"');
  const match=serialized.match(/"publicAuth"\s*:\s*({[^{}]*"config"\s*:\s*{[^{}]*}[^{}]*})/);
  assert.ok(match,'public Neon bootstrap absent');
  let auth;
  try{auth=JSON.parse(match[1]);}catch{assert.fail('public Neon bootstrap malformed');}
  assert.ok(auth.provider==='neon','public Neon provider absent');
  const config=auth.config;
  assert.ok(config&&Object.keys(config).sort().join(',')==='authPath,socialInitOrigin,socialInitPath',
    'public Neon configuration has unexpected fields');
  assert.ok(config.authPath==='/api/auth','same-origin Neon auth path absent');
  let origin;
  try{origin=new URL(config.socialInitOrigin);}catch{assert.fail('public Neon origin malformed');}
  assert.ok(origin.protocol==='https:'&&origin.hostname.endsWith('.neon.tech')&&
    !origin.port&&origin.origin===config.socialInitOrigin,'public Neon origin invalid');
  assert.ok(typeof config.socialInitPath==='string'&&
    /^\/(?:[A-Za-z0-9._~-]+\/)+sign-in\/social\/init$/.test(config.socialInitPath),
    'public Neon social sign-in path invalid');
}
