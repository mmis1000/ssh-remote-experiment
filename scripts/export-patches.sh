#!/usr/bin/env bash
# Exports the local work branches as patch files into patches/, which is what the repo tracks and
# what CI applies. Run after committing in vscodium/vscode or open-remote-ssh:
#   bash scripts/export-patches.sh
set -e
root="$(cd "$(dirname "$0")/.." && pwd)"
. "$root/upstream.env"

# vscodium/vscode: everything on top of the commit that holds the tree prepare_vscode.sh produced
base=$(git -C "$root/vscodium/vscode" log --format=%H --grep='^VSCodium .* baseline' -1 persistent-terminals)
rm -rf "$root/patches/vscode"
git -C "$root/vscodium/vscode" format-patch -q --no-signature --zero-commit -o "$root/patches/vscode" "$base..persistent-terminals"

rm -rf "$root/patches/open-remote-ssh"
git -C "$root/open-remote-ssh" format-patch -q --no-signature --zero-commit -o "$root/patches/open-remote-ssh" "$OPEN_REMOTE_SSH_COMMIT..persistent-terminals"

ls "$root/patches/vscode" "$root/patches/open-remote-ssh"
