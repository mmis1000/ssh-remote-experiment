# Review of PROPOSAL.md (persistent remote terminals)

Reviewed 2026-10-15 against `microsoft/vscode` main at `83caa64d` and `jeanp413/open-remote-ssh` main.
The specific issue comment (#3096, comment 6170328148) could not be loaded from this session, so the
context below comes from the issue thread as a whole: users want long-running work (REPLs, builds,
notebooks) to survive closing the client, without tmux.

## Verdict

The direction is right: extend the server's existing pty host and keep the native terminal UI.
But the proposal spends most of its length restating UI semantics and skips the one thing that
decides whether the POC works at all: **the pty host dies with the server, and the server is told to
die.** A large part of the rest already exists upstream and the plan should start from it instead of
treating it as new work.

## 1. The blocker the proposal leaves as "an implementation choice"

- Open Remote SSH launches the server with `--enable-remote-auto-shutdown`
  (`src/scripts/server-setup.sh:250`, `server-setup.ps1:204`).
- The server's `ServerLifetimeService` (`src/vs/server/node/serverLifetimeService.ts`) shuts the
  server down once no consumer is active. Extension hosts and the agent host register as consumers
  (`remoteExtensionHostAgentServer.ts:494`, `serverAgentHostManager.ts:328`); **the pty host does not.**
- Each persistent pty also has its own kill timer: `detach()` schedules a shutdown after
  `reconnectionGraceTime` (default 3h, `ptyService.ts:800-807, 835-842`).

So today a "persistent" terminal lives at most until the server's idle shutdown or the 3h grace,
whichever is first. Every R1/R5 scenario depends on fixing this, so it belongs in phase 1, with a
concrete design. Options, cheapest first:

1. **Server keep-alive while persistent terminals exist.** Have the terminal backend hold
   `serverLifetimeService.active('PtyHost')` while any terminal is marked Persistent, and exempt
   Persistent terminals from the grace timer. Small diff, uses an existing mechanism. Downside: the
   whole server (extension management etc.) stays resident.
2. **Detached pty host daemon.** Spawn the pty host detached, listening on a per-commit Unix socket
   under the server data dir; the server connects to an existing one on start. Survives server
   restarts within one commit. More work, but it is the real answer if you want terminals to outlive
   the server.

I'd do (1) for the POC and note (2) as the follow-up.

**Version upgrades.** The server and its pty host are per commit. When the client updates, Open
Remote SSH installs and starts a new server, and the old persistent terminals sit in the old one,
unreachable. The proposal puts "cross-version sharing" out of scope, but for users this happens with
every monthly update. At minimum the POC should not let the old server get killed, and the list
should say "N terminals running under an older server" rather than silently losing them.

## 2. Much of this already exists; phase 1 should measure it first

| Proposal item | What upstream already has |
| --- | --- |
| "Evaluate `@xterm/headless` for server-side screen state" | Already used: `XtermSerializer` in `ptyService.ts:33, 1032` keeps a headless xterm per pty and produces replay events. |
| Persist terminals across disconnect | `terminal.integrated.enablePersistentSessions`, `PersistentTerminalProcess`, reconnect with replay. |
| List and open terminals from another editor | `listProcesses()` (`ptyService.ts:415`) plus `workbench.action.terminal.attachToSession` / `detachSession`. Today it lists only orphaned persistent terminals, not ones owned by another window. |
| Fixed / non-fitting grid in a larger panel | `fixedDimensions` support (`ProcessPropertyType.FixedDimensions`, "Set Fixed Dimensions"). |
| Lifetime per terminal | `shouldPersist` flag exists per process; it is set at creation only. |

Suggested phase 0, one day, no code: Open Remote SSH plus a stock VSCodium build, server started
without `--enable-remote-auto-shutdown` and with a long `--reconnection-grace-time`. Then try
detach in window A, attach in window B, close A, reconnect. That tells you exactly which gaps are
real (I expect: listing non-orphans, multi-attach, shared sizing, lifetime toggle, keep-alive).

## 3. Design issues in the requirements

- **"Close Terminal" means two different things depending on a mode the user can't see.** In
  Close-on-editor-close mode it kills the process, in Persistent mode it only closes the view. Same
  trash icon, opposite outcomes. Worse, a viewer in editor B can kill A's shell with it. Suggest:
  trash always kills (matches VS Code today), and "Detach" (already a command) is the way to leave a
  view. Then R5 "Terminate Remote Terminal" is no longer a separate action.
- **Editor identity is undefined.** The pty host keys terminals by `workspaceId`, not by window.
  The proposal needs a stable window id that survives "Reload Window" and extension-host restarts,
  otherwise reloading kills every Close-on-editor-close terminal. Two windows on the same folder also
  share a workspaceId.
- **Close vs. disconnect vs. crash is the core of R1, not a "remaining decision".** The server can't
  tell a closed window from a dropped connection. It needs an explicit "window closing" message from
  the client's shutdown path, with disconnect and crash falling back to the grace timer. Without
  this, either laptops sleeping kill terminals or closed windows leak shells.
- **Minimum viewport (R4)** needs client changes: VS Code's terminal fits xterm to its container, so
  forcing a smaller grid on the larger view means using the fixed-dimensions path. Each viewer
  resizing also sends SIGWINCH churn to full-screen apps. Hidden or minimised panels must be excluded
  or one collapsed panel shrinks everyone to a tiny grid; make that the default, not an open question.
- **Multiple writers.** Opening a view currently would also make that view answer terminal queries
  (cursor position, device attributes). The proposal notes this; it needs a concrete rule, e.g. the
  most recently focused view answers.
- **Input policy** being undecided is fine for a POC: same host and account, so "everyone can type"
  is the honest default. Say so and move on.

## 4. Scope and distribution

- **Which client?** Open Remote SSH runs on VSCodium / OSS builds; Microsoft's Remote-SSH and the
  stock VS Code server are closed to this. Any change outside the extension means shipping a forked
  REH server (download URL via `serverDownloadUrlTemplate`) and, if client changes are needed, a
  forked client too. The proposal should state the target client explicitly, and try hard to keep
  phase 1 server-only plus extension commands, because a forked client is a much bigger ask for users.
- **The issue's main use cases are only partly terminals.** People in #3096 ask about Jupyter
  kernels, debug sessions and tasks. The POC covering interactive shells only is fine, but say up
  front that notebooks and debuggers are not addressed, so it isn't sold as closing the issue.
- Remove references a reader can't follow (`thread://...?hostId=local`), and drop the effort section
  until phase 0 has numbers.

## 5. What I'd change in the plan

1. Phase 0: measure existing persistence/attach with auto-shutdown off (above).
2. Phase 1: server keep-alive for Persistent terminals; per-terminal lifetime toggle; list all
   terminals regardless of owner; multi-attach with replay; explicit window-close signal and a
   stable window id.
3. Phase 2: shared minimum grid via fixed dimensions, query-reply authority, UI polish.
4. Later: detached pty host daemon, cross-version handling.

Overall: sound direction, but rewrite it around the lifetime/keep-alive mechanism and a reuse
inventory, and cut the repeated behavior tables to one.

## 6. Decisions (mmis1000, 2026-10-15)

- **Close always kills the shell; Detach leaves a view.** One meaning per button, whatever the lifetime.
- **No explicit "window closing" signal.** Closing a window and losing the connection are treated the
  same: the owned terminal's grace timer starts, and anything that reattaches before it fires rescues it.
- **Client-update / cross-version terminals:** deferred, out of scope for the POC.
- **Target:** a forked VSCodium plus a forked Open Remote SSH. Client-side changes are acceptable.

## 7. Vocabulary

Use these words in the proposal and code; avoid "editor" entirely, because in VS Code it means a file tab.

| Term | Meaning |
| --- | --- |
| **Host scope** | One remote host, one OS account, one server build (commit). Everything below lives inside one host scope. |
| **Terminal** | A shell process and its pty, owned by the server's terminal backend. Has a stable terminal id. Exists independently of any window. |
| **Window** | One VSCodium window connected to the host scope. Identified by a **window id** that stays the same across Reload Window and reconnects, and is new when the window is opened again later. |
| **View** | One terminal shown in one window's terminal panel. A window **attaches** a view to a terminal and **detaches** it to leave. A terminal can have many views from many windows. |
| **Lifetime** | Either **Persistent** or **Window-owned**. |
| **Persistent** | The terminal runs until its shell exits or someone closes it. No window's departure affects it. |
| **Window-owned** | The terminal has one **owner window**. When the owner window goes away, the terminal ends after the grace period. |
| **Owner window** | The window whose departure ends a window-owned terminal. Ownership is only about lifetime; it gives no extra rights to view or type. |
| **Window goes away** | The owner window's connection to the server ends for any reason: closed, app quit, crash, or network loss. Reload Window is not "going away" as long as it reconnects within the grace period with the same window id. |
| **Grace period** | Time between the owner window going away and a window-owned terminal ending. The owner window reconnecting, or any window making the terminal Persistent or taking ownership, cancels it. |
| **Close** | Ends the terminal's shell for everyone, from any view, whatever its lifetime. All views see it ended. |
| **Detach** | Removes one view. The terminal keeps running. A window-owned terminal detached from its owner window stays owned by that window. |
| **Make Persistent / Make Window-owned** | Change lifetime without touching the shell or any views. Make Window-owned sets the invoking window as owner. |

Consequences for the requirements: R5 ("Terminate Remote Terminal") merges into Close, and the
"Close Terminal" row in the UX table no longer depends on lifetime.
