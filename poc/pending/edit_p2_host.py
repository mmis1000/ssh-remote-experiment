import sys
root = sys.argv[1]


def edit(path, pairs):
    p = root + '/' + path
    s = open(p, encoding='utf-8').read()
    for old, new in pairs:
        assert s.count(old) == 1, (path, old[:120])
        s = s.replace(old, new)
    open(p, 'w', encoding='utf-8', newline='').write(s)


# ---- shared types -------------------------------------------------------------------------------
edit('src/vs/platform/terminal/common/terminal.ts', [
    ("""	/** Filled in by the window receiving the info: whether it is the owner. */
	ownedByThisWindow?: boolean;
}""", """	/** Filled in by the window receiving the info: whether it is the owner. */
	ownedByThisWindow?: boolean;
	/** How many windows currently show the terminal. */
	viewCount?: number;
}

/** What one window's view of a terminal reports to the pty host, which sizes the shared grid. */
export interface ITerminalViewState {
	/** The columns and rows the view could show, before the shared grid is applied. */
	cols: number;
	rows: number;
	/** Whether the view is in a visible panel of a visible window. Hidden views don't count. */
	visible: boolean;
	/** Whether the view has focus. The most recently focused view answers terminal queries. */
	focused: boolean;
}"""),
    ("""	attachToProcess(id: number): Promise<void>;
	detachFromProcess(id: number, forcePersist?: boolean): Promise<void>;
	shutdownAll(): Promise<void>;
	/**""", """	attachToProcess(id: number, windowId?: string): Promise<void>;
	detachFromProcess(id: number, forcePersist?: boolean, windowId?: string): Promise<void>;
	shutdownAll(): Promise<void>;
	/** Reports a window's view of a terminal; the pty host sizes the shared grid from these. */
	setViewState?(id: number, windowId: string, state: ITerminalViewState): Promise<void>;
	/**"""),
    ("""	windowHeartbeat?(windowId: string): Promise<void>;""",
     """	windowHeartbeat?(windowId: string, attachedIds?: number[]): Promise<void>;"""),
    ("""	start(id: number): Promise<ITerminalLaunchError | ITerminalLaunchResult | undefined>;
	shutdown(id: number, immediate: boolean): Promise<void>;
	input(id: number, data: string): Promise<void>;""", """	/** Starts or, for a running process, re-attaches; the replay only goes to {@link windowId}. */
	start(id: number, windowId?: string): Promise<ITerminalLaunchError | ITerminalLaunchResult | undefined>;
	shutdown(id: number, immediate: boolean): Promise<void>;
	input(id: number, data: string, windowId?: string): Promise<void>;"""),
    ("""	readonly onProcessReplay: Event<{ id: number; event: IPtyHostProcessReplayEvent }>;
	readonly onProcessOrphanQuestion: Event<{ id: number }>;
	readonly onDidRequestDetach: Event<{ requestId: number; workspaceId: string; instanceId: number }>;
	readonly onDidChangeProperty: Event<{ id: number; property: IProcessProperty }>;
	readonly onProcessExit: Event<{ id: number; event: number | undefined }>;

	createProcess(""", """	/** {@link windowId} is set when the replay is meant for one window only. */
	readonly onProcessReplay: Event<{ id: number; event: IPtyHostProcessReplayEvent; windowId?: string }>;
	readonly onProcessOrphanQuestion: Event<{ id: number }>;
	readonly onDidRequestDetach: Event<{ requestId: number; workspaceId: string; instanceId: number }>;
	readonly onDidChangeProperty: Event<{ id: number; property: IProcessProperty }>;
	readonly onProcessExit: Event<{ id: number; event: number | undefined }>;

	createProcess("""),
    ("""	freePortKillProcess?(port: string): Promise<{ port: string; processId: string }>;""",
     """	freePortKillProcess?(port: string): Promise<{ port: string; processId: string }>;

	/** Reports this window's view of the process so the pty host can size the shared grid. */
	setViewState?(state: ITerminalViewState): void;"""),
])

# ---- pty host -------------------------------------------------------------------------------------
edit('src/vs/platform/terminal/node/ptyService.ts', [
    ("ITerminalLaunchResult, ITerminalLifetimeInfo, TerminalLifetime } from '../common/terminal.js';",
     "ITerminalLaunchResult, ITerminalLifetimeInfo, ITerminalViewState, TerminalLifetime } from '../common/terminal.js';"),
    # replay event carries the target window
    ("""	private readonly _onProcessReplay = this._register(new Emitter<{ id: number; event: IPtyHostProcessReplayEvent }>());
	readonly onProcessReplay = this._traceEvent('_onProcessReplay', this._onProcessReplay.event);""",
     """	private readonly _onProcessReplay = this._register(new Emitter<{ id: number; event: IPtyHostProcessReplayEvent; windowId?: string }>());
	readonly onProcessReplay = this._traceEvent('_onProcessReplay', this._onProcessReplay.event);"""),
    ("""		persistentProcess.onProcessReplay(event => this._onProcessReplay.fire({ id, event }));""",
     """		persistentProcess.onProcessReplay(({ event, windowId }) => this._onProcessReplay.fire({ id, event, windowId }));"""),
    # heartbeat syncs views
    ("""	@traceRpc
	async windowHeartbeat(windowId: string): Promise<void> {
		this._windowLastSeen.set(windowId, Date.now());
		if (this._goneWindows.delete(windowId)) {
			this._logService.info(`Window ${windowId} is back, cancelling the grace period of the terminals it owns`);
			for (const pty of this._ptys.values()) {
				if (pty.lifetime?.ownerWindowId === windowId) {
					pty.cancelOwnerGrace();
				}
			}
		}
	}""", """	@traceRpc
	async windowHeartbeat(windowId: string, attachedIds?: number[]): Promise<void> {
		this._windowLastSeen.set(windowId, Date.now());
		if (this._goneWindows.delete(windowId)) {
			this._logService.info(`Window ${windowId} is back, cancelling the grace period of the terminals it owns`);
			for (const pty of this._ptys.values()) {
				if (pty.lifetime?.ownerWindowId === windowId) {
					pty.cancelOwnerGrace();
				}
			}
		}
		// The heartbeat lists what the window shows, which repairs views after a reconnect
		if (attachedIds) {
			for (const [id, pty] of this._ptys) {
				if (attachedIds.includes(id)) {
					pty.addView(windowId);
				} else {
					pty.removeView(windowId);
				}
			}
		}
	}

	@traceRpc
	async setViewState(id: number, windowId: string, state: ITerminalViewState): Promise<void> {
		this._ptys.get(id)?.setViewState(windowId, state);
	}"""),
    # window gone removes its views
    ("""			this._logService.info(`Window ${windowId} stopped sending heartbeats, starting the grace period of the terminals it owns`);
			for (const pty of this._ptys.values()) {
				if (pty.lifetime?.ownerWindowId === windowId) {
					pty.startOwnerGrace();
				}
			}""", """			this._logService.info(`Window ${windowId} stopped sending heartbeats, starting the grace period of the terminals it owns`);
			for (const pty of this._ptys.values()) {
				pty.removeView(windowId);
				if (pty.lifetime?.ownerWindowId === windowId) {
					pty.startOwnerGrace();
				}
			}"""),
    # creator is the first view
    ("""		if (shouldPersist && ownerWindowId) {
			await this.windowHeartbeat(ownerWindowId);
			persistentProcess.setLifetime({ lifetime: TerminalLifetime.WindowOwned, ownerWindowId }, this._ownerGraceTime);
		}""", """		if (shouldPersist && ownerWindowId) {
			await this.windowHeartbeat(ownerWindowId);
			persistentProcess.addView(ownerWindowId);
			persistentProcess.setLifetime({ lifetime: TerminalLifetime.WindowOwned, ownerWindowId }, this._ownerGraceTime);
		}"""),
    ("""	async attachToProcess(id: number): Promise<void> {
		try {
			await this._throwIfNoPty(id).attach();""", """	async attachToProcess(id: number, windowId?: string): Promise<void> {
		try {
			const pty = this._throwIfNoPty(id);
			await pty.attach();
			if (windowId) {
				pty.addView(windowId);
			}"""),
    ("""	async detachFromProcess(id: number, forcePersist?: boolean): Promise<void> {
		return this._throwIfNoPty(id).detach(forcePersist);
	}""", """	async detachFromProcess(id: number, forcePersist?: boolean, windowId?: string): Promise<void> {
		const pty = this._throwIfNoPty(id);
		if (windowId) {
			pty.removeView(windowId);
		}
		return pty.detach(forcePersist);
	}"""),
    # list every managed terminal, not only orphans
    ("""		const allTerminals = await Promise.all(promises);
		return allTerminals.filter(entry => entry.isOrphan);""", """		const allTerminals = await Promise.all(promises);
		// Terminals with a lifetime are listed whoever shows them, so any window can attach a view
		return allTerminals.filter(entry => entry.isOrphan || entry.lifetime);"""),
    ("""	async start(id: number): Promise<ITerminalLaunchError | ITerminalLaunchResult | undefined> {
		const pty = this._ptys.get(id);
		return pty ? pty.start() : { message: `Could not find pty with id "${id}"` };""", """	async start(id: number, windowId?: string): Promise<ITerminalLaunchError | ITerminalLaunchResult | undefined> {
		const pty = this._ptys.get(id);
		return pty ? pty.start(windowId) : { message: `Could not find pty with id "${id}"` };"""),
    ("""	async input(id: number, data: string): Promise<void> {
		const pty = this._throwIfNoPty(id);
		if (pty) {
			for (const contrib of this._contributions) {
				contrib.handleProcessInput(id, data);
			}
			pty.input(data);
		}
	}""", """	async input(id: number, data: string, windowId?: string): Promise<void> {
		const pty = this._throwIfNoPty(id);
		if (pty) {
			if (!pty.acceptInputFrom(windowId, data)) {
				return;
			}
			for (const contrib of this._contributions) {
				contrib.handleProcessInput(id, data);
			}
			pty.input(data);
		}
	}"""),
    ("""	async resize(id: number, cols: number, rows: number, pixelWidth?: number, pixelHeight?: number): Promise<void> {
		const pty = this._throwIfNoPty(id);
		if (pty) {""", """	async resize(id: number, cols: number, rows: number, pixelWidth?: number, pixelHeight?: number): Promise<void> {
		const pty = this._throwIfNoPty(id);
		// Views of a terminal with a lifetime size it through setViewState
		if (pty?.sizedByViews) {
			return;
		}
		if (pty) {"""),
    # isOrphan for managed terminals is "no views"
    ("""		const [cwd, isOrphan] = await Promise.all([persistentProcess.getCwd(), wasRevived ? true : persistentProcess.isOrphaned()]);""",
     """		const [cwd, isOrphan] = await Promise.all([persistentProcess.getCwd(), wasRevived ? true : persistentProcess.lifetime ? persistentProcess.viewCount === 0 : persistentProcess.isOrphaned()]);"""),
    ("""			lifetime: persistentProcess.lifetime
		};""", """			lifetime: persistentProcess.lifetime && { ...persistentProcess.lifetime, viewCount: persistentProcess.viewCount }
		};"""),
    # ---- PersistentTerminalProcess
    ("""	private _lifetime: ITerminalLifetimeInfo | undefined;
	private _ownerGraceRunner: ProcessTimeRunOnceScheduler | undefined;
""", """	private _lifetime: ITerminalLifetimeInfo | undefined;
	private _ownerGraceRunner: ProcessTimeRunOnceScheduler | undefined;
	/** Windows showing this terminal, with the size their view could show once reported. */
	private readonly _views = new Map<string, ITerminalViewState | undefined>();
	/** The window whose view answers terminal queries: the most recently focused one. */
	private _replyWindowId: string | undefined;
	private readonly _gridRunner: ProcessTimeRunOnceScheduler;
	private _overrideGrid: { cols: number; rows: number } | undefined;
"""),
    ("""	private readonly _onProcessReplay = this._register(new Emitter<IPtyHostProcessReplayEvent>());
	readonly onProcessReplay = this._onProcessReplay.event;""", """	private readonly _onProcessReplay = this._register(new Emitter<{ event: IPtyHostProcessReplayEvent; windowId?: string }>());
	readonly onProcessReplay = this._onProcessReplay.event;"""),
    ("""	get lifetime(): ITerminalLifetimeInfo | undefined { return this._lifetime; }
""", """	get lifetime(): ITerminalLifetimeInfo | undefined { return this._lifetime; }
	get viewCount(): number { return this._views.size; }
	/** Whether the shared grid of the views sizes the pty, rather than plain resize calls. */
	get sizedByViews(): boolean { return !!this._lifetime && [...this._views.values()].some(v => v !== undefined); }
"""),
    ("""		this._onDidChangeProperty.fire({ type: ProcessPropertyType.Lifetime, value: lifetime });
	}

	startOwnerGrace(): void {""", """		this._fireLifetime();
	}

	addView(windowId: string): void {
		if (!this._views.has(windowId)) {
			this._views.set(windowId, undefined);
			this._replyWindowId ??= windowId;
			this._logService.info(`Persistent process "${this._persistentProcessId}": view added for window ${windowId}, ${this._views.size} view(s)`);
			this._fireLifetime();
		}
	}

	removeView(windowId: string): void {
		if (this._views.delete(windowId)) {
			if (this._replyWindowId === windowId) {
				this._replyWindowId = this._views.keys().next().value;
			}
			this._logService.info(`Persistent process "${this._persistentProcessId}": view removed for window ${windowId}, ${this._views.size} view(s)`);
			this._fireLifetime();
			this._gridRunner.schedule();
		}
	}

	setViewState(windowId: string, state: ITerminalViewState): void {
		this._views.set(windowId, state);
		if (state.focused) {
			this._replyWindowId = windowId;
		}
		// Debounced so a burst of resizes from several views causes one SIGWINCH
		this._gridRunner.schedule();
	}

	/**
	 * Whether input from a window reaches the shell. Every view can type, but replies to terminal
	 * queries only count from one view, otherwise the application gets one answer per view.
	 */
	acceptInputFrom(windowId: string | undefined, data: string): boolean {
		if (!windowId || this._views.size < 2 || !isTerminalReply(data)) {
			if (windowId && this._views.has(windowId) && !isTerminalReply(data)) {
				this._replyWindowId = windowId;
			}
			return true;
		}
		return windowId === this._replyWindowId;
	}

	/** Applies the smallest size among the visible views to the pty and to every view. */
	private _updateGrid(): void {
		const counted = [...this._views.values()].filter((v): v is ITerminalViewState => !!v && v.visible && v.cols > 0 && v.rows > 0);
		if (counted.length === 0) {
			// Nothing visible: keep the last size
			return;
		}
		const cols = Math.min(...counted.map(v => v.cols));
		const rows = Math.min(...counted.map(v => v.rows));
		if (cols !== this._serializerCols || rows !== this._serializerRows) {
			this._logService.info(`Persistent process "${this._persistentProcessId}": grid ${cols}x${rows} from ${counted.length} visible view(s)`);
			this._serializer.handleResize(cols, rows);
			this._serializerCols = cols;
			this._serializerRows = rows;
			this._bufferer.flushBuffer(this._persistentProcessId);
			this._terminalProcess.resize(cols, rows);
		}
		// Only constrain the views when more than one counts, a single view sizes freely
		const override = this._views.size > 1 ? { cols, rows } : undefined;
		if (override?.cols !== this._overrideGrid?.cols || override?.rows !== this._overrideGrid?.rows) {
			this._overrideGrid = override;
			this._onDidChangeProperty.fire({ type: ProcessPropertyType.OverrideDimensions, value: override });
		}
	}

	startOwnerGrace(): void {"""),
    ("""	async start(): Promise<ITerminalLaunchError | ITerminalLaunchResult | undefined> {
		if (!this._isStarted) {""", """	async start(windowId?: string): Promise<ITerminalLaunchError | ITerminalLaunchResult | undefined> {
		if (!this._isStarted) {"""),
    ("""		this._onDidChangeProperty.fire({ type: ProcessPropertyType.ShellType, value: this._terminalProcess.shellType });
		this._fireLifetime();
		this.triggerReplay();
		return undefined;
	}

	private _fireLifetime(): void {
		if (this._lifetime) {
			this._onDidChangeProperty.fire({ type: ProcessPropertyType.Lifetime, value: this._lifetime });
		}
	}""", """		this._onDidChangeProperty.fire({ type: ProcessPropertyType.ShellType, value: this._terminalProcess.shellType });
		this._fireLifetime();
		if (this._overrideGrid) {
			this._onDidChangeProperty.fire({ type: ProcessPropertyType.OverrideDimensions, value: this._overrideGrid });
		}
		this.triggerReplay(windowId);
		return undefined;
	}

	private _fireLifetime(): void {
		if (this._lifetime) {
			this._onDidChangeProperty.fire({ type: ProcessPropertyType.Lifetime, value: { ...this._lifetime, viewCount: this._views.size } });
		}
	}"""),
    ("""	async triggerReplay(): Promise<void> {""", """	async triggerReplay(windowId?: string): Promise<void> {"""),
    ("""		this._onProcessReplay.fire(ev);
		this._terminalProcess.clearUnacknowledgedChars();""", """		this._onProcessReplay.fire({ event: ev, windowId });
		this._terminalProcess.clearUnacknowledgedChars();"""),
    # serializer size tracking + grid runner in ctor
    ("""		this._fixedDimensions = fixedDimensions;
		this._orphanQuestionBarrier = null;""", """		this._fixedDimensions = fixedDimensions;
		this._serializerCols = cols;
		this._serializerRows = rows;
		this._gridRunner = this._register(new ProcessTimeRunOnceScheduler(() => this._updateGrid(), 50));
		this._orphanQuestionBarrier = null;"""),
    ("""	private _inReplay = false;

	private _pid = -1;""", """	private _inReplay = false;
	private _serializerCols: number;
	private _serializerRows: number;

	private _pid = -1;"""),
    ("""		this._serializer.handleResize(cols, rows);

		// Buffered events should flush when a resize occurs""", """		this._serializer.handleResize(cols, rows);
		this._serializerCols = cols;
		this._serializerRows = rows;

		// Buffered events should flush when a resize occurs"""),
    ("""function printTime(ms: number): string {""", """/**
 * Whether data a view sends is only replies to terminal queries (device attributes, cursor
 * position, mode reports, color queries, focus reports), rather than something a user typed.
 */
const terminalReplyRegex = /^(?:\\x1b\\[[?>]?[\\d;]*[cnR]|\\x1b\\[\\??[\\d;]*\\$y|\\x1b\\[[IO]|\\x1b\\]\\d+;[^\\x07\\x1b]*(?:\\x07|\\x1b\\\\)|\\x1bP[^\\x1b]*\\x1b\\\\)+$/;
function isTerminalReply(data: string): boolean {
	return terminalReplyRegex.test(data);
}

function printTime(ms: number): string {"""),
])

# ---- server proxy ----------------------------------------------------------------------------
edit('src/vs/platform/terminal/node/ptyHostService.ts', [
    ("ITerminalsLayoutInfo, ProcessPropertyType, TerminalIcon, TerminalIpcChannels, TerminalLifetime, TerminalSettingId, TitleEventSource } from '../common/terminal.js';",
     "ITerminalsLayoutInfo, ITerminalViewState, ProcessPropertyType, TerminalIcon, TerminalIpcChannels, TerminalLifetime, TerminalSettingId, TitleEventSource } from '../common/terminal.js';"),
    ("""	private readonly _onProcessReplay = this._register(new Emitter<{ id: number; event: IPtyHostProcessReplayEvent }>());""",
     """	private readonly _onProcessReplay = this._register(new Emitter<{ id: number; event: IPtyHostProcessReplayEvent; windowId?: string }>());"""),
    ("""	attachToProcess(id: number): Promise<void> {
		return this._proxy.attachToProcess(id);
	}
	detachFromProcess(id: number, forcePersist?: boolean): Promise<void> {
		return this._proxy.detachFromProcess(id, forcePersist);
	}""", """	attachToProcess(id: number, windowId?: string): Promise<void> {
		return this._proxy.attachToProcess(id, windowId);
	}
	detachFromProcess(id: number, forcePersist?: boolean, windowId?: string): Promise<void> {
		return this._proxy.detachFromProcess(id, forcePersist, windowId);
	}
	async setViewState(id: number, windowId: string, state: ITerminalViewState): Promise<void> {
		return this._proxy.setViewState?.(id, windowId, state);
	}"""),
    ("""	async windowHeartbeat(windowId: string): Promise<void> {
		return this._proxy.windowHeartbeat?.(windowId);
	}""", """	async windowHeartbeat(windowId: string, attachedIds?: number[]): Promise<void> {
		return this._proxy.windowHeartbeat?.(windowId, attachedIds);
	}"""),
])
print('ok')
