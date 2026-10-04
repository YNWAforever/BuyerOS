$ErrorActionPreference='Stop'
$env:PATH="$env:SystemRoot\System32;"+$env:PATH
$env:BUYEROS_AUDIT_UI_RUNTIME='built'
$env:BUYEROS_STRICT_INTEGRATION='1'
$env:PLAYWRIGHT_JSON_OUTPUT_NAME='test-results/u05-ui-final.json'
$env:PLAYWRIGHT_JUNIT_OUTPUT_NAME='test-results/u05-ui-final.xml'
Remove-Item Env:BUYEROS_DATABASE_URL,Env:DATABASE_URL,Env:TEST_DATABASE_URL,Env:BUYEROS_TEST_DATABASE_URL -ErrorAction SilentlyContinue
node node_modules/@playwright/test/cli.js test --config playwright.audit-fixes.config.ts audit-access-revocation.spec.ts audit-auth-entry.spec.ts audit-memberships.spec.ts audit-draft-dirty.spec.ts --reporter=list,json,junit
exit $LASTEXITCODE
