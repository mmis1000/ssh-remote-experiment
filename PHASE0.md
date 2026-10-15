# Phase 0: what stock 1.140.0 already does

Date: 2026-10-15. Goes with [PROPOSAL-v2.md](PROPOSAL-v2.md) (phase 0) and [DEV-ENV.md](DEV-ENV.md).
Build: VSCodium 1.140.06880 patches on VS Code `07f806f9`, run from source on both sides. No terminal code changed.

## Setup

| Piece | Where |
| --- | --- |
| Client | `vscodium/vscode` on the Windows PC, started with `scripts/dev-client.ps1` (own profile in `.dev-profile/`, debug port 9333). |
| Server | `/root/src/vscode` on `nas`, same commit, Node 24.21.0. Open Remote SSH starts it through `~/.vscodium-server/bin/<placeholder>/bin/codium-server`. |
| Server flags | `~/.vscodium-server/poc-flags.env` on nas: `POC_STRIP_AUTO_SHUTDOWN=1` drops `--enable-remote-auto-shutdown`; `POC_EXTRA_ARGS` adds flags such as `--reconnection-grace-time`. |
| Open Remote SSH | Our fork in `open-remote-ssh/`, one change: `remote.SSH.devServerCommit`, used when the client's product.json has no commit. |
| Test tools | `poc/drive.mjs` drives the windows over CDP; `poc/nas-state.sh` shows the server, pty host and shells on nas; `poc/nas-reset.sh` stops them. |

Each test shell starts a marker process (`exec -a poc-A1 sleep …`) so nas can confirm it is still alive.

## Results

Unless noted, the server ran without auto-shutdown and with `--reconnection-grace-time=86400`.

| # | Step | Result |
| --- | --- | --- |
| 1 | Window A creates terminal A1. Window B opens on the same host and runs **Attach to Session**. | "There are no unattached terminals to attach to". `listProcesses()` returns only orphaned terminals, so a live terminal in another window is invisible. **Gap R4.** |
| 2 | A runs **Detach Session** on A1, then B attaches. | Works. B gets the replayed screen, then live output with no visible gap (ticks continuous). |
| 3 | While B holds A1, A runs Attach to Session. | Nothing to attach: same orphan-only listing. |
| 4 | B closes its window while attached to A1 (no detach). A lists again, also after 20 s more. | A1 is still running on nas but **never listed**. The pty host asks "is anyone attached?" and window A answers yes: a window keeps a pty in `RemoteTerminalBackend._ptys` after detaching (entries are only removed when the process exits), so it keeps replying to `onProcessOrphanQuestion` for terminals it no longer shows. **Bug; affects R4/R5.** |
| 5 | Close every window. | Server, pty host and both shells keep running (auto-shutdown off). |
| 6 | Open a new window B on `/root/poc-b`. | B **reattaches A1 by itself**, because B's saved terminal layout from step 2 still names it. A's other shell is listed as attachable. Restore follows "the last workspace that showed it", not ownership. |
| 7 | Open window A on `/root/poc-a` again. | A does not reattach its old shell; it **starts a new shell** and shows "History restored". The old shell keeps running unattached. The attach list shows 3 entries, one with pid `-1`. |
| 8 | A attaches A1 while B is showing it. | Allowed, because the list in step 7 offered it. **Both windows then show A1 live at once.** The pty host can already feed two views; only listing and sizing are missing. Each view resizes the pty to its own size, last write wins. **Gap R7.** |
| 9 | Stock Open Remote SSH flags (auto-shutdown on, default 3 h grace). Create a terminal, close the window, watch nas for 13 minutes. | Server, pty host, extension host and shell all still alive after 13 min. The extension host stays for its 3 h reconnection grace and counts as an active consumer, so the server's 5 min idle shutdown never starts. |
| 10 | Auto-shutdown on, `--reconnection-grace-time=120`. Same as 9. | Extension host exits at about 2 min (its grace). The shell is still alive then. The server shuts down about 5 min later (gone at 7 min 9 s) and **takes the pty host and the shell with it.** So with stock flags a terminal lives at most grace time + 5 min after its last window goes, whatever its persistence setting. |

Cosmetic: the attach list shows the remote cwd as `\root\poc-a` (Windows path separators on a Linux path).

## Which gaps are real

| Proposal item | Status after phase 0 |
| --- | --- |
| Change 1, keep the server alive | Real (steps 9 and 10). Today a terminal survives only as long as the extension host's reconnection grace (3 h) plus the 5 min idle shutdown. The pty host does not hold the server alive. |
| Change 2, lifetime per terminal | Real. Persistence today is a side effect of the reconnection grace and of which workspace layout last held the terminal. |
| Change 3, window id | Real. Restore is keyed by workspace layout, not window, and reopening the same folder can start a new shell instead of reattaching (step 7). |
| Change 4, many views | Mostly exists in the pty host (step 8). Needed: sizing (R7) and query-reply authority. |
| Change 5, list everything | Real (steps 1 and 3), plus the stale orphan-reply bug (step 4). |
| Change 6, Close and Detach | Not tested yet. |

## Not done yet

- Reload Window and a network drop on the owner window.
- Full-screen apps (`htop`, `vim`) during attach, and checking for duplicates in the replay seam with a byte-exact comparison.
