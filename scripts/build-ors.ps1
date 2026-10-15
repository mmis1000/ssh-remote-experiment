# Build open-remote-ssh into a VSIX and install it into the dev client's profile.
$ErrorActionPreference = 'Stop'
# postinstall runs `npx vscode-dts`; never stop for npx's install prompt
$env:npm_config_yes = 'true'
$root = Split-Path $PSScriptRoot -Parent
Set-Location "$root\open-remote-ssh"
node -v
if (-not (Test-Path node_modules)) {
	npm ci
	if ($LASTEXITCODE) { throw "npm ci failed" }
}
npm run build
if ($LASTEXITCODE) { throw "build failed" }
npx vsce package --no-dependencies --allow-missing-repository -o open-remote-ssh-dev.vsix
if ($LASTEXITCODE) { throw "vsce package failed" }
& "$root\vscodium\vscode\scripts\code-cli.bat" --user-data-dir "$root\.dev-profile\data" --extensions-dir "$root\.dev-profile\ext" --install-extension "$root\open-remote-ssh\open-remote-ssh-dev.vsix" --force
"BUILD-ORS-DONE"
