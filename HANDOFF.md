# Handoff: persistent remote terminals POC

Date: 2026-10-15. Read with [PROPOSAL-v2.md](PROPOSAL-v2.md), [DEV-ENV.md](DEV-ENV.md) and [PHASE0.md](PHASE0.md).
Everything is local to this PC and the `nas` host. Nothing is pushed to GitHub, and no forks were created.

## Where things are

| Path | What |
| --- | --- |
| `vscodium/` | VSCodium at tag `1.140.06880`. `dev/build.env` was written by `scripts/prepare-vscodium.sh`. |
| `vscodium/vscode/` | VS Code `07f806f9` (1.140.0) with VSCodium patches applied. Work branch `persistent-terminals`. |
| `open-remote-ssh/` | jeanp413/open-remote-ssh. Branch `persistent-terminals`, commit `14ae32f` adds `remote.SSH.devServerCommit`. |
| `scripts/prepare-vscodium.sh` | Applies the VSCodium patches and runs `npm ci` (already done, don't rerun on top of the work). |
| `scripts/dev-client.ps1` | Starts the dev client with its own profile (`.dev-profile/`), `--log trace` and CDP on port 9333. Extra args pass through, e.g. `--remote ssh-remote+nas-poc /root/poc-a`. |
| `scripts/build-ors.ps1` | Builds Open Remote SSH into a VSIX and installs it into the dev profile. |
| `poc/ssh_config` | Host `nas-poc` (nas:2222, root). Used through `remote.SSH.configFile` in the dev profile settings. |
| `poc/drive.mjs` | Drives the dev windows over CDP: `windows`, `cmd <win> "<palette label>"`, `type`, `keys`, `pick`, `state`, `shot`. |
| `poc/nas-state.sh`, `poc/nas-reset.sh` | Run with `ssh -p 2222 root@nas bash -s < poc/<file>`: show / stop the dev server, pty host and `poc-*` marker processes. |
| `poc/pending/edit_p2_host.py` | Unapplied Phase 2 edits (see below). |

### vscode commits on `persistent-terminals`

1. `54daeca5` VSCodium 1.140.06880 baseline.
2. `01dc37a9` Fix VSCodium's policy-watcher test typings (otherwise `npm run compile` fails with 7 errors).
3. `9ae78b43` Phase 1: terminal lifetime (see below).
4. `d022e593` Detach lifetime-managed terminals when a window closes instead of killing them. **Not yet pushed to nas** (client-only, the server doesn't need it).
5. `c63c53b7` Phase 2: shared terminal views (see below).
6. `79f08fc8` Terminal shutdown: send SIGHUP again after 1 s and SIGKILL after 5 s if the shell is still alive (see "Shell leak" below).

Both are pushed to nas and compiled on both sides (gulp, 0 errors).

## Repo and CI

The root folder is the repo `git@github.com:mmis1000/ssh-remote-experiment.git` (public, branch `main`, `core.sshCommand` set to Windows OpenSSH). `vscodium/` and `open-remote-ssh/` are ignored local clones. Their changes are tracked as `patches/` (re-export with `bash scripts/export-patches.sh` after committing in either clone), pinned to the versions in `upstream.env`.

Workflows (see README.md for the published layout):
- `server.yml` runs on changes to `patches/vscode/`, `upstream.env` or itself. It clones VSCodium at the tag, copies the patches into `vscodium/patches/user/` (VSCodium applies those last), and runs VSCodium's `build.sh` and `build/linux/package_reh.sh` (the same two jobs as its publish-stable-linux workflow). The server's product commit is the repo commit, and the release is `reh-<commit>`. Linux x64 only; add rows to the `reh` matrix for more architectures. The first run hit a transient GitHub API 403 while downloading built-in extensions, and a re-run passed. If it recurs, use a PAT secret as `GITHUB_TOKEN` for that step.
- `extension.yml` runs on changes to `patches/open-remote-ssh/`. It applies the patches to Open Remote SSH at `OPEN_REMOTE_SSH_COMMIT`, builds the VSIX, and creates release `ors-<commit>`.
- `pages.yml` runs after either one succeeds and rebuilds the whole Pages site from the releases (Pages source: GitHub Actions; the `github-pages` environment allows `main`).

The patched extension (`de5d599` locally, `patches/open-remote-ssh/0002`) downloads from Pages by default. A client without a product commit and without `devServerCommit` uses `builds.json`'s latest. Verified 2026-10-15: with `devServerCommit` removed, the dev client installed the published server `2844181` on nas and connected. Terminals, views and Make Persistent (with keep-alive) all worked there. The dev profile keeps `devServerCommit = deadc0de…`, so it uses the from-source server on nas; remove that setting to use the published builds instead. The published server logs to `~/.local/state/VSCodium/<date>/` on the host, not `~/.vscodium-server/data/logs`.

## Build and run

- Node: fnm with 24.18.0 as default; the PowerShell profile loads fnm. Run builds from a real terminal: Claude's sandboxed shell doesn't see fnm's junctions.
- Client: in `vscodium/vscode`, `npm run compile` (about 1 min, check `compile-src ... with 0 errors`), then `scripts\dev-client.ps1 --remote ssh-remote+nas-poc /root/poc-a`. A second window: add `--new-window` and another folder (`/root/poc-b`).
- Server on nas: source at `/root/src/vscode`, synced through the bare repo `/root/src/vscode.git` (git remote `nas` in `vscodium/vscode`; push with `GIT_LFS_SKIP_PUSH=1 git push nas persistent-terminals`). Then on nas: `cd /root/src/vscode && git pull && . ~/.nvm/nvm.sh && nvm use 24.18.0 && npm run compile`.
- Open Remote SSH runs the launcher `~/.vscodium-server/bin/deadc0de…/bin/codium-server` (placeholder commit, set by `remote.SSH.devServerCommit`). It runs the server from source with Node 24.21.0 and must not `exec` (Open Remote SSH detects a running server by the script path in `ps`).
- Launcher knobs: `~/.vscodium-server/poc-flags.env`. Currently set for Phase 1 tests:
  ```
  POC_STRIP_AUTO_SHUTDOWN=0          # 1 drops --enable-remote-auto-shutdown
  POC_EXTRA_ARGS="--reconnection-grace-time=120"
  export VSCODE_TERMINAL_OWNER_GRACE_TIME=60000   # owner grace override (default 5 min)
  ```
- Don't put a `commit` into `product.json`: the dev workbench then loads xterm from `node_modules.asar` and every New Terminal fails.

## Phase 1 (done, mostly verified)

Design as implemented:
- Pty host (`src/vs/platform/terminal/node/ptyService.ts`): each persistent-session terminal created by a window gets `lifetime` (`persistent` / `windowOwned`) and `ownerWindowId`. Windows send `windowHeartbeat` every 10 s; a window silent for 30 s is "gone" and its window-owned terminals start the owner grace (`shortGraceTime`, 5 min, or `VSCODE_TERMINAL_OWNER_GRACE_TIME`). A heartbeat, Make Persistent or Make Window-owned cancels it. Detach and disconnects no longer schedule kills for these terminals.
- Lifetime reaches the windows as a new process property (`ProcessPropertyType.Lifetime`). Tab marker: pin for persistent, window icon for "owned by another window".
- Server: `src/vs/server/node/ptyHostKeepAlive.ts` holds `serverLifetimeService.active('PtyHost')` while any terminal is Persistent.
- Client: window id in `sessionStorage` (survives Reload Window, new when reopened), commands `Terminal: Make Persistent` / `Make Window-owned` (palette and tab context menu), remote buffer revive disabled (it spawned duplicate shells), a window forgets a pty when it detaches (fixes the stale orphan-reply bug from Phase 0), and closing a window detaches managed terminals.

Verified on nas:
- Make Persistent sets the lifetime; the server logs "PtyHostKeepAlive: 1 persistent terminal(s)"; the tab shows the pin.
- Reload Window: both terminals reattach with their markers.
- Close the only window, auto-shutdown on, 120 s grace: the window was detected gone after about 30 s, the window-owned shells were shut down 60 s later, the persistent shell and the server were still up more than 10 minutes later (without the keep-alive the server exits at about 7 min).
- Caveat in the test, not the code: the `poc-W1` marker survived because a background job outlives its shell. Check the shell pid instead, or start the marker without `&`.

Not yet tested: Make Window-owned from a second window and closing it. (Reopening a window and attaching a persistent terminal, and rescuing from another window within the grace period, now pass; see Phase 2.)

## Phase 2 (committed, compiled, mostly verified on nas)

`poc/pending/edit_p2_host.py` has been applied on top of `d022e593`, and the rest has been written by hand. All of it is in commit `c63c53b7`.
- Pty host: views per terminal (`addView` / `removeView`). The heartbeat carries the window's attached ids. A window that is gone loses its views. `viewCount` is in the lifetime info, and `listProcesses()` lists every terminal that has a lifetime.
- Shared grid: `setViewState(cols, rows, visible, focused)`. The pty host debounces it (50 ms), sizes the pty to the minimum over visible views, and sends `OverrideDimensions` when more than one view exists. Plain `resize` is ignored once views report.
- Replays go only to the window that is attaching (`start(id, windowId)`; `RemoteTerminalBackend` drops replays meant for another window). Replays keep exact dimensions: each replay event forces the size the buffer was recorded at. When the replay ends, `BasePty` switches straight to `_getOverrideAfterReplay()` (in `RemotePty` that is the shared grid, otherwise none), so nothing resizes in between. Grid changes that arrive during a replay are only stored. The server sends the grid before the replay so a new view knows it.
- Reply authority: data that is only terminal replies is accepted only from the view that was focused or typed most recently.
- Channels: `$setViewState` is new, and `windowId` is passed to attach, detach, start and input. The heartbeat sends `attachedIds`, except while a create or attach is in flight; then it sends no list, so the new view isn't dropped.
- Client: `RemotePty.setViewState` is debounced 50 ms and ANDs in `document.visibilityState`. `TerminalInstance._reportViewState()` runs on resize, visibility, focus and the first lifetime info, using `_cols/_rows`.
- `safeDisposeTerminal`: when `viewCount > 1`, it asks "Remove From This Window" (detach) or "Close Everywhere".
- New command `Terminal: Show Remote Terminals` lists every pty-host terminal with its lifetime, window count and "shown here". Picking one focuses it or attaches it. `Attach to Session` shares the same code.

Type-check is clean (`node node_modules/typescript/lib/tsc.js -p src/tsconfig.json --noEmit --skipLibCheck` with fnm's Node on PATH). The 2 errors in `agentFinderRestProvider.test.ts` were there before.

Acceptance results on nas (2026-10-15):

| Scenario | Result |
| --- | --- |
| New Terminal; another window lists it and attaches | Pass. Window-owned, view count 1 → 2, B replays the screen, input from either view is echoed once in both. |
| Attach while `top` runs | Pass. Screen is clean and live in the second window. |
| Different view sizes | Pass. B split to 58 columns: the pty is `12 58` (`stty size`), and A wraps output at 58. |
| Hide the limiting view's panel | Pass. The grid went back to 120×12, and A reflowed. |
| Make Persistent, close every window | Pass. The shell and `top` kept running and the server stayed up (keep-alive logged). A new window listed it and restored the screen. |
| Close the owner window | Pass. The other view saw the terminal end after the grace period (60 s override). |
| Make Persistent from another window within the grace period | Mechanism passes (grace cancelled, the terminal survived). In the run, though, the *other* terminal got made persistent: picking T1 in Show Remote Terminals didn't activate it. That couldn't be reproduced afterwards (picking switches correctly). Possibly the driver chose a row before the pick loaded. Watch for it. |
| Reload Window on the owner | Pass. Views are removed and re-added under the same window id, and the terminal works. |
| Close from a non-owner view | Pass. The confirmation shows. "Remove From This Window" detaches (view count 2 → 1, shell keeps running). "Close Everywhere" ends the shell, and the owner window's tab goes away too. |
| Network drop on the owner window | Pass. Window A's sshd session and the sshd listener on nas were frozen with SIGSTOP for 50 s. A was declared gone after 27 s and the grace period started. When A came back it was cancelled, the heartbeat re-added A's view, and the shell kept working. Killing A's sshd session (a real reconnect on a new connection, back within 5 s) also passed. |
| No persistent terminals and no windows | Pass. After Make Window-owned (keep-alive released) and closing both windows, the window-owned shells ended at the end of the grace period. The server logged "all consumers inactive, shutting down" and exited about 7 min after the windows closed. |

Shell leak (fixed in `79f08fc8`): bash ignores the first SIGHUP while readline waits for the rest of an escape sequence (lone ESC or `ESC [`) and exits on the second. Every kill path (closing a terminal, end of the owner grace period) sends only one SIGHUP, so a shell where the user had just pressed Escape stayed alive with no pty-host process attached. This was reproduced in isolation with node-pty inside the pty host. Stock VS Code has the same kill path. `TerminalProcess._ensureExit` now follows up. Verified: "Process N is still running after SIGHUP, sending it again", then the shell is gone.

Testing notes:
- `poc/drive.mjs cmd` presses Escape first. When the terminal has focus that reaches the shell (two in a row trigger bash completion), and the first character typed right after a palette command is often lost. Also, after Reload Window the terminal has no focus, so `type` goes to the editor.
- `window.dialogStyle` is now `custom` in the dev profile, so dialogs are in the DOM, and `node poc/drive.mjs dialog <win> "<button>"` clicks them. Native Windows dialogs can't be seen or clicked over CDP.
- Launch dev windows from Git Bash with `MSYS_NO_PATHCONV=1`, otherwise `/root/poc-a` becomes `C:/Program Files/Git/root/poc-a`.
- SSH from the shell tool: use `C:/Windows/System32/OpenSSH/ssh.exe` (it has your key via the agent; Git Bash's ssh doesn't). It also has to run outside the sandbox.
- The pty host listens for the inspector on 5877 on nas. `node /tmp/inspect-eval.mjs 5877 @file.js` (source: `poc/inspect-eval.mjs`) evaluates code in it (used to hook `process.kill`).
- Network drop without touching Windows networking: Open Remote SSH uses `ssh2` inside the extension host (there's no `ssh.exe` per window), so freeze the window's `sshd: root@notty` session and the sshd listener (pid 25) on nas with `kill -STOP`. Schedule the `kill -CONT` first with `setsid nohup sh -c "sleep 50; kill -CONT ..." &`, because your own SSH can't get in while the listener is stopped.
- Cosmetic: Show Remote Terminals shows remote cwds with backslashes (`URI.file` on a Windows client, same as the old Attach to Session).

## Why this session kept prompting

Commands typed into the Terminal panel (`run_in_terminal`) always ask for approval when the work was started or steered over Remote Control, whatever the permission mode. Most prompts came from that (builds, the dev client, winget, the Visual Studio installer UAC). Running builds through the normal shell tool avoids it, except that the sandboxed shell can't see fnm's Node, so either point it at `%APPDATA%\fnm\node-versions\v24.18.0\installation` directly or allow that shell to run outside the sandbox.
