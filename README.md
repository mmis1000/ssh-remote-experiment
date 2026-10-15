# ssh-remote-experiment

Persistent and shared remote terminals for VSCodium over SSH (Open Remote SSH), as a proof of concept.

- A terminal is **window-owned**: it ends a grace period after its window goes away, or **persistent**: it keeps running after every window closes, and the server stays up for it.
- Any window connected to the host can list a remote terminal and attach to it. The terminal is then **shared**: every view shows the same pty, sized to the smallest visible view.

The design is in [PROPOSAL-v2.md](PROPOSAL-v2.md), and the state of the work and how to run it is in [HANDOFF.md](HANDOFF.md).

## Layout

| Path | What |
| --- | --- |
| `patches/vscode/` | The VS Code changes, applied on top of VSCodium's own patches (`git format-patch`). |
| `patches/open-remote-ssh/` | The Open Remote SSH change (`remote.SSH.devServerCommit`). |
| `upstream.env` | The VSCodium tag and Open Remote SSH commit the patches apply to. |
| `.github/workflows/server.yml` | Builds the remote server with the patches and publishes it. |
| `scripts/` | Local setup: prepare VSCodium, run the dev client, build Open Remote SSH, export patches. |
| `poc/` | Test tools: drive the dev windows over CDP, inspect and reset the test host. |

`vscodium/` and `open-remote-ssh/` are local clones and are not tracked. After committing in `vscodium/vscode` (branch `persistent-terminals`) or `open-remote-ssh`, run `bash scripts/export-patches.sh` and commit `patches/`.

## Published server

Each push that changes `patches/vscode/` builds the Linux x64 server and publishes it at

```
https://mmis1000.me/ssh-remote-experiment/reh/<commit>/vscodium-reh-linux-x64.tar.gz
```

`<commit>` is the commit of this repo that built it, and it is also the server's product commit. Builds are listed at <https://mmis1000.me/ssh-remote-experiment/> and in the releases (`reh-<commit>`). The site keeps the latest 5.

To use a build from a VSCodium client with the patched Open Remote SSH:

```jsonc
"remote.SSH.serverDownloadUrlTemplate": "https://mmis1000.me/ssh-remote-experiment/reh/${commit}/vscodium-reh-${os}-${arch}.tar.gz",
// Only for a client run from source, which has no product commit of its own:
"remote.SSH.devServerCommit": "<commit>"
```

The terminal features need the patched client too. For now that means the dev client built from `vscodium/vscode` (see HANDOFF.md).
