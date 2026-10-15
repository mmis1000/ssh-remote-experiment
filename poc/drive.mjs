// Drives the dev VSCodium windows over CDP (scripts/dev-client.ps1 opens port 9333).
// One step per invocation, prints JSON:
//   node poc/drive.mjs windows
//   node poc/drive.mjs cmd   <win> "<command palette label>"
//   node poc/drive.mjs type  <win> "<text>"           (types into the focused element, then Enter)
//   node poc/drive.mjs keys  <win> "<key>" ...         (e.g. Escape, Enter, ArrowDown)
//   node poc/drive.mjs state <win>                     (terminal tabs, visible terminal text, open quick pick)
//   node poc/drive.mjs pick  <win> "<substring>"       (selects the quick pick row containing substring)
//   node poc/drive.mjs shot  <win> <file.png>
//   node poc/drive.mjs dialog <win> "<button label>"   (clicks a button of the open dialog; needs window.dialogStyle custom)
// <win> is a substring of the window title, e.g. poc-a.
import { createRequire } from 'node:module';
const require = createRequire('C:/Playground/ssh-persistant/vscodium/vscode/package.json');
const { chromium } = require('playwright-core');

const [, , action, win, ...rest] = process.argv;
const sleep = ms => new Promise(r => setTimeout(r, ms));

const browser = await chromium.connectOverCDP('http://127.0.0.1:9333');
try {
	const pages = browser.contexts().flatMap(c => c.pages());
	const titled = await Promise.all(pages.map(async p => ({ p, title: await p.title().catch(() => '') })));
	const workbenches = titled.filter(t => t.p.url().includes('workbench'));

	if (action === 'windows') {
		console.log(JSON.stringify(workbenches.map(t => t.title), null, 1));
		process.exit(0);
	}

	const target = workbenches.find(t => t.title.includes(win));
	if (!target) { throw new Error(`no window matching "${win}"; have: ${workbenches.map(t => t.title).join(' | ')}`); }
	const page = target.p;
	await page.bringToFront();

	const state = async () => page.evaluate(() => {
		const text = el => (el?.textContent ?? '').trim();
		const tabs = [...document.querySelectorAll('.terminal-tabs-entry, .single-terminal-tab')].map(e => {
			const icons = [...e.querySelectorAll('[class*="codicon-"]')].flatMap(i => [...i.classList].filter(c => c.startsWith('codicon-') && c !== 'codicon-terminal'));
			return `${(e.getAttribute('aria-label') || text(e)).replace(/\s+/g, ' ').slice(0, 60)} [${[...new Set(icons)].join(' ')}]`;
		});
		const terms = [...document.querySelectorAll('.xterm-rows')].filter(r => r.offsetParent !== null).slice(0, 1).map(rows =>
			[...rows.children].map(r => r.textContent.replace(/\s+$/, '')).filter(Boolean).slice(-15));
		const quick = document.querySelector('.quick-input-widget');
		const quickVisible = quick && quick.style.display !== 'none';
		const picks = quickVisible ? [...quick.querySelectorAll('.monaco-list-row')].map(r => r.getAttribute('aria-label') || text(r)) : [];
		const notifications = [...document.querySelectorAll('.notification-list-item-message')].map(text);
		const dialog = text(document.querySelector('.monaco-dialog-box'));
		return { title: document.title, tabs, terminal: terms[0] ?? null, quickPick: quickVisible ? { title: text(quick.querySelector('.quick-input-title')), picks } : null, notifications, dialog: dialog || null };
	});

	switch (action) {
		case 'cmd': {
			await page.keyboard.press('Escape');
			await page.keyboard.press('F1');
			await page.waitForSelector('.quick-input-widget input', { state: 'visible' });
			await page.keyboard.type(rest[0], { delay: 5 });
			await sleep(600);
			// Pick the row whose label is exactly the command (aria-label is "<label>, <keybinding/group>")
			const idx = await page.evaluate(label => [...document.querySelectorAll('.quick-input-widget .monaco-list-row')]
				.findIndex(r => { const a = r.getAttribute('aria-label') || ''; return a === label || a.startsWith(label + ','); }), rest[0]);
			if (idx < 0) { await page.keyboard.press('Escape'); throw new Error(`command "${rest[0]}" not found in palette`); }
			await page.locator('.quick-input-widget .monaco-list-row').nth(idx).click();
			await sleep(Number(rest[1] ?? 1500));
			break;
		}
		case 'type':
			await page.keyboard.type(rest[0], { delay: 5 });
			await page.keyboard.press('Enter');
			await sleep(1000);
			break;
		case 'keys':
			for (const k of rest) { await page.keyboard.press(k); await sleep(200); }
			await sleep(800);
			break;
		case 'pick': {
			const rows = page.locator('.quick-input-widget .monaco-list-row', { hasText: rest[0] });
			await rows.first().click();
			await sleep(1500);
			break;
		}
		case 'dialog':
			await page.locator('.monaco-dialog-box .monaco-button', { hasText: rest[0] }).first().click();
			await sleep(1000);
			break;
		case 'shot':
			await page.screenshot({ path: rest[0] });
			break;
		case 'state':
			break;
		default:
			throw new Error(`unknown action ${action}`);
	}
	console.log(JSON.stringify(await state(), null, 1));
} finally {
	// Only disconnect; never close the app's browser.
	process.exit(process.exitCode ?? 0);
}
