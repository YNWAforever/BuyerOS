$ErrorActionPreference = 'Stop'
# Git Bash prepends GNU tar, which treats a Windows C: archive as a remote host.
# Use the existing Windows tar for the unchanged owned-container source packer.
$env:PATH = "$env:SystemRoot\System32;" + $env:PATH
Write-Output (Get-Command tar.exe).Source
node node_modules/@playwright/test/cli.js test --config playwright.audit-keyboard.config.ts
exit $LASTEXITCODE
