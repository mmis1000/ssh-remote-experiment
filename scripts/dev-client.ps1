# Launch the dev VSCodium client with the POC profile. Extra arguments are passed through,
# e.g.  scripts\dev-client.ps1 --remote ssh-remote+nas-poc /root
$root = Split-Path $PSScriptRoot -Parent
& "$root\vscodium\vscode\scripts\code.bat" `
	--user-data-dir "$root\.dev-profile\data" `
	--extensions-dir "$root\.dev-profile\ext" `
	--remote-debugging-port=9333 `
	--log trace `
	@args
