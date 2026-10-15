# Persistent remote terminal proposal

Status: Draft for implementation planning  
Date: 2026-10-15  
Project: Open Remote SSH and the remote editor terminal backend

Every managed remote terminal is listed and available for viewing from any editor connected to the same remote host and account, including terminals bound to another editor. Viewing is always available within this scope.

A terminal has one of two lifetime settings: **Persistent** or **Close on editor close**. The actions **Make persistent** and **Close on editor close** change only its lifetime. Existing viewers remain connected and input permissions remain unchanged.

Throughout this proposal, **editor** means the whole VS Code window/instance to which the terminal is bound. **Close on editor close** triggers when that instance closes. Closing an individual file/editor tab has no effect on terminal lifetime. Other open VS Code instances remain independent.

Closing a terminal in **Close on editor close** mode immediately ends its process, even while its bound editor remains open. Closing a persistent terminal's view leaves its process running.

Extend the remote server's existing terminal backend and reuse the editor's terminal UI. Ordinary interactive terminals enter this backend when created, so their lifetime can change while their shell and applications keep running.

## Requirements

Requirements describe observable behavior. Implementation choices and proposed defaults are identified separately below.

| ID | Requirement | Observable result |
| --- | --- | --- |
| R1 | Make persistent and Close on editor close control lifetime. | Persistent terminals survive view and editor closure. In Close on editor close mode, explicitly closing the terminal immediately ends its process; closing its designated editor also ends it. Changing lifetime preserves the running process, viewers, and input permissions. |
| R2 | List all managed remote terminals. | Include terminals bound to this editor, terminals bound to other editors, and persistent terminals. Show lifetime and the bound editor where applicable. |
| R3 | Every listed terminal is always viewable within the host/account scope. | Another editor can open a view immediately, regardless of lifetime or editor binding. Existing views remain connected when lifetime or binding changes. |
| R4 | All viewers use a common minimum viewport. | The terminal grid uses the minimum column count and minimum row count across participating views. |
| R5 | Users can force-close a persistent terminal. | Its remote process ends, it leaves the active list, and all viewers receive termination status. |
| R6 | Ordinary remote terminals are managed from creation. | Normal terminal creation, including shell profile selection, produces a listed, viewable terminal whose lifetime can change without replacing its shell. |

Editor binding determines which editor's closure ends a terminal in Close on editor close mode. It has no effect on viewing or input permissions. Sharing toggles and exclusive-view ownership are removed from the design.

The proposed initial scope is ordinary interactive remote shells within one remote host and operating-system account. Coverage of tasks, debugging, and extension-provided terminal implementations remains a separate scope decision.

## User experience

| Action | Behavior |
| --- | --- |
| New Terminal | Create a managed terminal. Proposed default: Close on editor close, bound to the creating editor. |
| Show Remote Terminals | List every managed terminal in scope with its lifetime and bound editor. Optional details include name, working directory, and viewer count. |
| Open Terminal View | Open any listed terminal's current screen and live output. Preserve its lifetime, binding, and input policy. |
| Make persistent | Keep the process running after editor closure. Existing views and input permissions are preserved. |
| Close on editor close | Bind termination to an editor's closure. Proposed default: use the invoking editor. Existing views and input permissions are preserved. |
| Close Terminal | In Close on editor close mode, immediately end the process and notify all viewers. In Persistent mode, close only the invoking view and keep the process running. |
| Terminate Remote Terminal | Force-close a persistent terminal and notify all viewers. |

A command palette picker is sufficient for the first version. A dedicated explorer view is optional.

### Example

1. Editor A opens a terminal with Close on editor close enabled and starts a long-running command.
2. Editor B lists remote terminals and opens A's terminal immediately. It remains bound to A.
3. A offers 140 columns by 40 rows; B offers 100 columns by 50 rows. Both use a 100 by 40 grid.
4. A selects Make persistent. Both views stay connected, the command continues, and input permissions stay the same.
5. A closes. The terminal continues running and B continues viewing it.
6. B selects Close on editor close, binding lifetime to B under the proposed default. Closing B then ends the terminal and any remaining views receive termination status.

If A closes before step 4, the terminal ends because its lifetime is still bound to A, even while B is viewing it.

Explicitly closing the terminal before step 4 also ends its process immediately and notifies both views. This applies when the close action is invoked from either editor. Merely hiding the terminal panel or losing a connection follows view visibility or disconnection handling.

## Lifetime and viewing behavior

| Event | Result |
| --- | --- |
| Make persistent | Preserve the process beyond editor closure; retain viewers and input permissions. |
| Close on editor close | Set the designated editor binding; retain viewers and input permissions. |
| Another editor opens a view | Restore the current screen and stream live output; keep lifetime and binding unchanged. |
| User closes a terminal in Close on editor close mode | Immediately end its process, remove it from the active list, and notify all viewers. |
| User closes a view in Persistent mode | Remove that viewer and recalculate dimensions; keep the process running. |
| A view loses its connection | Remove that viewer and recalculate dimensions; apply the selected disconnection policy. |
| Bound editor closes in Close on editor close mode | End the process and notify all viewers. |
| An editor closes in Persistent mode | Keep the process alive, including when no viewers remain. |
| Shell exits or user force-closes | Mark the session ended, remove it from the active list, and notify viewers. |

For participating views with valid dimensions:

```text
effective columns = minimum of participating column counts
effective rows    = minimum of participating row counts
```

The minima can come from different viewers. Apply the common grid to the remote PTY and each view; larger panels have unused space. Proposed defaults: retain the last valid size with no viewers and exclude views reporting zero or invalid dimensions.

## Input and remaining policy decisions

Viewing is available to every editor in scope. Input policy is independent and remains to be selected: a single input controller or multiple writers. Neither opening a view nor changing lifetime implicitly changes who can type. The implementation should preserve the selected input policy throughout those operations.

The remaining decisions are:

- Whether new terminals default to Close on editor close and whether selecting that action binds to the invoking editor.
- Input control and its recovery after an editor closes or disconnects.
- How to distinguish intentional editor closure from temporary network loss or a crash. Proposed default: preserve processes during temporary disconnection.
- Whether hidden views with valid dimensions participate in minimum sizing.
- Initial remote platforms, supported editor versions, and coverage beyond ordinary interactive shells.

Persistence covers editor closure and connection loss while the remote session backend remains alive. Host reboot, backend crash recovery, migration of shells created outside this backend, and cross-account or cross-version session sharing are outside the proposed initial scope.

## Proposed implementation

### Existing integration points

Open Remote SSH establishes SSH connectivity and installs and launches the remote editor server. The original discussion inspected extension commit `eb3c8c820da67881fa0acc2e53c6ffe43d58a71a`. Its configuration provides a custom server download URL, binary name, and client/server validation settings. [Open Remote SSH configuration](https://github.com/jeanp413/open-remote-ssh/blob/eb3c8c820da67881fa0acc2e53c6ffe43d58a71a/package.json)

The remote server's terminal channel delegates process creation, attachment, detachment, listing, input, and other operations to the PTY service. Extend this path to track lifetime and viewers independently. [Server services](https://github.com/microsoft/vscode/blob/main/src/vs/server/node/serverServices.ts), [remote terminal channel](https://github.com/microsoft/vscode/blob/main/src/vs/server/node/remoteTerminalChannel.ts)

| Layer | Responsibility |
| --- | --- |
| Open Remote SSH | Install and launch the selected server build; expose terminal commands where extension APIs suffice. |
| Editor terminal UI and client backend | Show the terminal list, render the common grid, open views, and expose lifetime controls. |
| Remote terminal backend | Own processes, track lifetime and editor binding, maintain viewers, apply sizing, and restore screen state. |

Maintain a session registry shared by editor connections within the host/account scope. Each session needs its identity, lifetime mode, bound editor where applicable, active views, and process status. Input-related state depends on the selected policy. Lifetime updates must leave viewer subscriptions and input state intact.

Route an explicit terminal close according to its current lifetime mode: terminate immediately for Close on editor close, or remove only the invoking view for Persistent. Keep explicit close distinguishable from panel hiding and transport disconnection.

Reuse existing PTY and screen replay facilities where possible. If replay cannot reconstruct an already-running terminal application, evaluate `@xterm/headless` for server-side screen state. Its documentation marks the package experimental, so pin and validate the selected version. [Headless terminal documentation](https://github.com/xtermjs/xterm.js/blob/master/headless/README.md)

Coordinate screen restoration with live output to avoid gaps or duplication. Select one authority for terminal-generated replies so multiple views do not send duplicate responses to an application query.

The backend's lifetime must allow persistent shells to survive all editor connections closing. Whether this requires changes inside the PTY host or a separate long-lived process is an implementation choice. Client changes are available where existing APIs cannot express common sizing, replay, or lifetime controls. Pin and test a compatible client/server baseline for distribution.

The preferred direction is to extend the existing server. A separate service with a terminal profile remains a fallback if ordinary creation paths can be covered. The earlier tmux option adds a keyboard interaction layer the user wanted to avoid; the proposed experience uses the editor's existing terminal UI.

## Implementation phases

1. **Validate integration.** Select one platform and client/server baseline. Create a normal terminal in A, list and view it from B while it remains bound to A, change lifetime in both directions, and verify process survival or termination on editor closure. Establish reusable PTY/replay facilities and necessary client changes. End the investigation when these architectural questions are answered.
2. **Implement behavior.** Complete the all-terminal list, always-available viewing, lifetime controls, common sizing, screen restoration, and force-close behavior. Apply the selected input and connection-loss policies.
3. **Validate and package.** Run the acceptance scenarios on supported platforms and editor versions. Verify that reconnecting clients reach the same session registry, then package the required server and client/extension changes.

## Acceptance scenarios

| Scenario | Expected outcome |
| --- | --- |
| Create an ordinary terminal using a shell profile | It appears in the list and another editor can view it immediately. |
| Open a terminal bound to another editor | Current screen and live output are available; lifetime and binding stay unchanged. |
| Open a view while a full-screen application is running | Restore the current screen, then deliver live output in order. |
| View at 140 by 40 and 100 by 50 | Both views and the PTY use 100 by 40. |
| Resize or disconnect the limiting viewer | Recalculate the common grid from remaining participating views. |
| Make persistent with multiple viewers connected | Preserve the process, every view, and input permissions; editor closure leaves the process alive. |
| Select Close on editor close with multiple viewers connected | Preserve every view and input permissions; closure of the designated editor ends the session for everyone. |
| Close a file/editor tab in the bound VS Code instance | Keep the terminal process and its views running. |
| Close the whole bound VS Code instance in Close on editor close mode | End the terminal process and notify viewers in other instances. |
| Explicitly close a terminal in Close on editor close mode while its editor stays open | Immediately end the process and remove it from the active list. |
| Explicitly close that terminal from another editor while multiple viewers are connected | Immediately end the same process and notify every viewer. |
| Close one view of a persistent terminal | Keep the process and other views running. |
| Open another view after either lifetime action | Viewing remains available immediately. |
| Close every view of a persistent terminal and reconnect | The process survives and its current screen is restored. |
| Force-close a persistent terminal | End the process, remove its active list entry, and notify viewers. |

Review findings should identify the requirement or selected policy they affect. Suggested libraries, process boundaries, and protocol mechanisms remain implementation details.

## Effort

The main work is process lifetime, screen restoration for concurrent viewers, sizing, client integration, and compatible builds. Estimate the server-extension approach after the integration prototype establishes what can be reused. Earlier estimates for tmux or a separate custom service apply to those alternatives rather than this simplified design.

## Source discussion

[Assess persistent terminal support](thread://01a13aea-7f23-7741-a659-773fd8907e3f?hostId=local) provides the original investigation and server-extension direction. Subsequent revisions establish independent lifetime controls, a list of all terminals, and viewing that is always available even for terminals bound to other editors. Pin upstream source links to the chosen implementation baseline during integration work.
