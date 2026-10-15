# Persistent remote terminals: proposal v2

Status: Draft for the proof of concept
Date: 2026-10-15
Supersedes: [PROPOSAL.md](PROPOSAL.md) (v1). Changes come from [REVIEW.md](REVIEW.md) and the decisions recorded there.
Target: a forked VSCodium (client and REH server) plus a forked Open Remote SSH.
Context: [vscode-remote-release#3096](https://github.com/microsoft/vscode-remote-release/issues/3096). Users want shells, REPLs and builds on a remote host to keep running after they close VS Code, without tmux.

## Goal

A terminal on the remote host can outlive the window that opened it. Any window connected to the same host and account can list every terminal and show it with VS Code's normal terminal UI. Each terminal is either **Persistent** or **Window-owned**, and you can switch between the two at any time without restarting the shell.

## Vocabulary

This proposal does not use "editor", because in VS Code an editor is a file tab.

| Term | Meaning |
| --- | --- |
| **Host scope** | One remote host, one OS account and one server build (commit). Everything below lives inside one host scope. |
| **Terminal** | A shell process and its pty, owned by the server's terminal backend. It has a stable terminal id and does not belong to any window. |
| **Window** | One VSCodium window connected to the host scope. Its **window id** stays the same across Reload Window and reconnects, and is new when the window is opened again later. |
| **View** | One terminal shown in one window's terminal panel. A window **attaches** a view to a terminal and **detaches** it to leave. A terminal can have any number of views from any number of windows. |
| **Lifetime** | Either **Persistent** or **Window-owned**. |
| **Persistent** | The terminal runs until its shell exits or someone closes it. No window going away affects it. |
| **Window-owned** | The terminal has one **owner window**. When the owner window goes away, the terminal ends after the grace period. |
| **Owner window** | The window whose departure ends a window-owned terminal. Ownership only decides lifetime. It gives no extra right to view or type. |
| **Window goes away** | The owner window's connection to the server ends for any reason: closing, quitting, crashing or losing the network. A Reload Window that reconnects with the same window id within the grace period does not count. |
| **Grace period** | The time between the owner window going away and a window-owned terminal ending. It is cancelled when the owner window reconnects, or when any window makes the terminal Persistent or takes ownership. Default: 5 minutes, which is VS Code's existing short reconnection grace time. |
| **Close** | Ends the terminal's shell for everyone, from any view, whatever its lifetime. Every view shows that the terminal ended. |
| **Detach** | Removes one view. The terminal keeps running and its lifetime and owner don't change. |

## Requirements

| ID | Requirement | Observable result |
| --- | --- | --- |
| R1 | Lifetime is switchable. | **Make Persistent** and **Make Window-owned** change only the lifetime. The shell, every view and the input rules stay the same. Make Window-owned sets the window that invoked it as the owner. |
| R2 | Persistent terminals survive. | A Persistent terminal keeps running after every window has gone away, and after the server has no other work, until its shell exits or it is closed. |
| R3 | Window-owned terminals end with their owner. | When the owner window goes away, the terminal ends after the grace period unless something cancels it. Reload Window doesn't end it. |
| R4 | Every terminal is listed. | Any window can list every terminal in the host scope with its name, lifetime, owner window and view count. This includes terminals owned by other windows. |
| R5 | Any listed terminal can be viewed. | Attaching shows the current screen, then live output in order, with no gaps or duplicates. Lifetime and owner don't change. |
| R6 | Close and Detach each mean one thing. | Close always ends the shell for everyone. Detach always removes one view only. |
| R7 | Views share one grid. | The pty and every view use the smallest column count and smallest row count among the views that count toward sizing (see below). |
| R8 | Ordinary terminals are managed from creation. | **New Terminal**, including shell profile selection, creates a terminal that meets R1 to R7 without replacing its shell later. |

## User experience

| Action | Behavior |
| --- | --- |
| New Terminal | Creates a Window-owned terminal owned by the current window. This matches what users expect from VS Code today. |
| Show Remote Terminals | A quick pick that lists every terminal in the host scope (R4). Picking one attaches a view. |
| Make Persistent / Make Window-owned | Actions in the terminal tab's context menu and in the command palette. |
| Close (trash icon) | Ends the shell for everyone. If other views are attached, it first asks for confirmation and says how many. |
| Detach | Uses the existing `workbench.action.terminal.detachSession` command. It leaves the terminal running. |

The tab shows a small marker for Persistent terminals, and the tooltip names the owner window for Window-owned ones.

### Example

1. Window A creates a terminal (Window-owned by A) and starts a long build.
2. Window B opens Show Remote Terminals and attaches to it. The terminal is still owned by A.
3. A's panel is 140 by 40 and B's is 100 by 50, so the pty and both views use 100 by 40.
4. A runs Make Persistent. Both views stay attached and the build continues.
5. A is closed. The terminal keeps running and B keeps viewing it.
6. B detaches. With no views left, the terminal still runs. Tomorrow a new window lists it and attaches.

If A had been closed before step 4, the terminal would end 5 minutes later. During those 5 minutes, B could rescue it with Make Persistent or Make Window-owned.

## Sizing

- Only views in a visible terminal panel with valid, non-zero dimensions count toward the grid. Hidden panels and minimised windows don't count, so one collapsed panel can't shrink everyone's grid.
- When no view counts, the pty keeps its last size.
- Views larger than the grid render the grid at its fixed size and leave the rest of the panel empty. This uses the existing fixed-dimensions path, `ProcessPropertyType.FixedDimensions`.
- Resizes are debounced on the server so full-screen apps don't get a burst of SIGWINCH signals.

## Input

For the POC, every attached view can type, because all of them are the same OS account on the same host. Replies to terminal queries, such as cursor position and device attributes, come only from the **most recently focused view**, so applications don't receive duplicate answers.

## Design

### What exists upstream and is reused

| Need | Existing piece in `microsoft/vscode` |
| --- | --- |
| Restoring the screen when a view attaches | `XtermSerializer` in `src/vs/platform/terminal/node/ptyService.ts` keeps a headless xterm for each pty and produces replay events. |
| Keeping processes across disconnects | `PersistentTerminalProcess`, with `attach()` / `detach()` and the grace timers. |
| Listing and attaching | `listProcesses()`, `attachToProcess()`, and the attach and detach session commands. |
| Fixed grid | `fixedDimensions` and `ProcessPropertyType.FixedDimensions`. |
| Keeping the server alive | `IServerLifetimeService.active()` in `src/vs/server/node/serverLifetimeService.ts`. |

### Changes

**1. Keep the server alive (server).** Open Remote SSH starts the server with `--enable-remote-auto-shutdown`. Today the server exits once no extension host or agent host is active, and the terminal backend doesn't count. Two changes:
- The terminal backend holds `serverLifetimeService.active('PtyHost')` while at least one Persistent terminal exists.
- Persistent terminals are exempt from the 3-hour `reconnectionGraceTime` kill timer.

Auto-shutdown stays enabled for every other case, so an idle server with no Persistent terminals still exits as it does today.

**2. Lifetime and owner per terminal (pty host).** `PersistentTerminalProcess` gains a `lifetime` (`persistent` or `windowOwned`) and an `ownerWindowId`. The fixed `shouldPersist` flag that is set at creation is replaced by these fields. The grace timer starts when the owner window goes away, not when the last view detaches. New IPC calls are `setLifetime(id, lifetime, windowId)` and `onDidChangeLifetime`.

**3. Window id (client).** Each window creates a UUID and keeps it in window-scoped session storage, so it survives Reload Window but not reopening the window. The window sends this id when its terminal connection is set up. The server tracks which window ids are connected, and when a window id's last connection ends, it starts the grace timer for every terminal that window owns.

**4. Many views per terminal (pty host and channel).** Each view attaches with its window id and gets its own replay, then live data. The replay is taken and the subscription is registered under the same queue, so output arrives with no gap and no duplicates. The process tracks its attached views and their sizes, and pushes the common grid back to each view.

**5. List everything (pty host and client).** `listProcesses()` returns every terminal in the host scope, not only orphaned ones. Each entry includes its lifetime, owner window id and view count. Show Remote Terminals is a quick pick that is filled from this list.

**6. Close and Detach (client).** The trash action calls `shutdown` on the terminal (Close) and broadcasts that the terminal ended to every view. Detach reuses the existing `detachFromProcess`.

**7. Distribution (Open Remote SSH fork).** The extension points `serverDownloadUrlTemplate` at the forked REH build and pins the matching client commit. The launch flags stay the same.

## Out of scope for the POC

- Terminals left on an older server after a client update. When the client updates, Open Remote SSH starts a new server for the new commit, and terminals in the old server can't be reached from it. Deferred.
- A pty host that outlives the server process, for example as a detached daemon on a Unix socket. This is the follow-up if terminals need to survive server restarts.
- Host reboot, terminals from other OS accounts, and moving shells that were started outside VS Code.
- Tasks, debug terminals, extension-provided terminals, and Jupyter kernels. #3096 asks for these too, so the POC doesn't close the issue.
- A dedicated tree view for terminals. The quick pick is enough for now.

## Phases

0. **Measure.** On stock VSCodium with Open Remote SSH, start the server without auto-shutdown and with a long `--reconnection-grace-time`. Try detaching in window A, attaching in window B, closing A and reconnecting. Write down which gaps are real.
1. **Lifetime.** Changes 1, 2, 3 and 6. Exit criteria: A Persistent terminal survives every window closing and the server going idle. A Window-owned terminal ends 5 minutes after its owner window closes and survives Reload Window.
2. **Sharing.** Changes 4 and 5, sizing, and the reply authority. Exit criteria: the acceptance scenarios below pass on Linux.
3. **Package.** Change 7. Exit criteria: a fresh install of the fork, connecting to a clean Linux host, passes the scenarios.

The first platform is a Linux remote host. Windows and macOS remotes come after the POC.

## Acceptance scenarios

| Scenario | Expected |
| --- | --- |
| New Terminal from a shell profile | The terminal is Window-owned by the current window, and another window lists it and can attach. |
| Attach while a full-screen app (`htop`, `vim`) is running | The current screen appears, then live output, with no gaps or duplicates. |
| Views at 140 by 40 and 100 by 50 | The pty and both views use 100 by 40. |
| Hide the limiting view's panel | The grid grows to the remaining views' minimum. |
| Make Persistent, then close every window | The shell keeps running and the server stays up. A new window lists it and restores the screen. |
| Close the owner window of a Window-owned terminal | The terminal ends after 5 minutes, and other views see it end. |
| Close the owner window, then Make Persistent from another window within 5 minutes | The terminal survives. |
| Reload Window on the owner window | The terminal survives, and the view comes back attached. |
| Network drop on the owner window, reconnected within 5 minutes | The terminal survives. |
| Close from a non-owner view | The shell ends for everyone, after the confirmation because other views are attached. |
| Detach the last view of a Persistent terminal | The shell keeps running. |
| No Persistent terminals and no windows | The server auto-shuts down as it does today. |
