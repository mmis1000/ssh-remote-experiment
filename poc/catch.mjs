// Pauses on caught exceptions in the window while running a palette command; prints terminal-related stacks.
import { createRequire } from 'node:module';
const require = createRequire('C:/Playground/ssh-persistant/vscodium/vscode/package.json');
const { chromium } = require('playwright-core');
const [, , win, label] = process.argv;
const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
let p; for (const x of b.contexts().flatMap(c => c.pages())) if ((await x.title()).includes(win)) p = x;
const cdp = await p.context().newCDPSession(p);
const out = [];
cdp.on('Debugger.paused', async e => {
	const frames = e.callFrames.slice(0, 12).map(f => `${f.functionName || '<anon>'} ${f.url.replace(/.*\/out\//, '')}:${f.location.lineNumber + 1}`);
	let desc = '';
	try { desc = e.data?.description ?? JSON.stringify(e.data); } catch { }
	if (!/ExplorerItem not found/.test(desc)) out.push(desc.split('\n').slice(0, 6).join('\n') + '\n  ' + frames.join('\n  '));
	cdp.send('Debugger.resume').catch(() => { });
});
await cdp.send('Debugger.enable');
await cdp.send('Debugger.setPauseOnExceptions', { state: 'all' });
await p.bringToFront();
await p.keyboard.press('Escape');
await p.keyboard.press('F1');
await p.waitForTimeout(500);
await p.keyboard.type(label, { delay: 5 });
await p.waitForTimeout(700);
const idx = await p.evaluate(l => [...document.querySelectorAll('.quick-input-widget .monaco-list-row')].findIndex(r => (r.getAttribute('aria-label') || '').startsWith(l + ',')), label);
await p.locator('.quick-input-widget .monaco-list-row').nth(idx).click();
await p.waitForTimeout(5000);
await cdp.send('Debugger.setPauseOnExceptions', { state: 'none' });
await cdp.send('Debugger.disable');
console.log(out.slice(0, 10).join('\n=====\n') || 'no terminal-related exceptions');
process.exit(0);
