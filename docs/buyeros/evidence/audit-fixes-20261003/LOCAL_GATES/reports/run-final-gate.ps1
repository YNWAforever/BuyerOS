$ErrorActionPreference='Stop'
node --test --test-reporter=spec --test-reporter-destination=stdout --test-reporter=junit --test-reporter-destination=test-results/local-gates/root-node-final.xml 'tests/*.test.mjs' *> test-results/local-gates/root-node-final.log
$testExit=$LASTEXITCODE
Get-Content test-results/local-gates/root-node-final.log -Tail 50
exit $testExit
