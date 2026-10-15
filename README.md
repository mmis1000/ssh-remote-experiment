# ssh-remote-experiment

Persistent and shared remote terminals for VSCodium over SSH (Open Remote SSH), as a proof of concept.

- A terminal is **window-owned**: it ends a grace period after its window goes away, or **persistent**: it keeps running after every window closes, and the server stays up for it.
- Any window connected to the host can list a remote terminal and attach to it. The terminal is then **shared**: every view shows the same pty, sized to the smallest visible view.

The design is in [PROPOSAL-v2.md](PROPOSAL-v2.md), and the state of the work and how to run it is in [HANDOFF.md](HANDOFF.md).

## Layout

| Path | What |
| --- | --- |
| `patches/vscode/` | The VS Code changes, applied on top of VSCodium's own patches (`git format-patch`). |
| `patches/open-remote-ssh/` | The Open Remote SSH changes: `remote.SSH.devServerCommit`, and downloading servers from this repo's Pages site by default. |
| `upstream.env` | The VSCodium tag and Open Remote SSH commit the patches apply to. |
| `.github/workflows/` | `server.yml` and `extension.yml` build the server and the extension, and `pages.yml` publishes them. |
| `scripts/` | Local setup: prepare VSCodium, run the dev client, build Open Remote SSH, export patches. |
| `poc/` | Test tools: drive the dev windows over CDP, inspect and reset the test host. |

`vscodium/` and `open-remote-ssh/` are local clones and are not tracked. After committing in `vscodium/vscode` (branch `persistent-terminals`) or `open-remote-ssh`, run `bash scripts/export-patches.sh` and commit `patches/`.

## Published builds

Everything is served from <https://mmis1000.me/ssh-remote-experiment/>:

| Path | What | Built by |
| --- | --- | --- |
| `reh/<commit>/vscodium-reh-linux-x64.tar.gz` | The Linux x64 remote server with `patches/vscode`. `<commit>` is the commit of this repo that built it, and the server's product commit. The latest 5 are kept. | `server.yml`, on changes to `patches/vscode/` |
| `ors/open-remote-ssh.vsix` | Open Remote SSH with `patches/open-remote-ssh`. | `extension.yml`, on changes to `patches/open-remote-ssh/` |
| `builds.json` | `{ latest, builds, extension }` | `pages.yml` |

Both build workflows publish GitHub releases (`reh-<commit>`, `ors-<commit>`). `pages.yml` runs after either of them and rebuilds the whole site from the releases.

The patched extension downloads servers from `reh/${commit}/` by default. When the client has no product commit (a client run from source) and `remote.SSH.devServerCommit` is empty, it uses the latest build from `builds.json`. So the dev client needs no extra settings once the extension is installed.

The server refuses a client whose commit differs from its own, and the terminal features need the patched client too (window ids, view sizes, the commands). For now that client is the dev build from `vscodium/vscode` (see HANDOFF.md). A stock VSCodium client can't use these servers.
