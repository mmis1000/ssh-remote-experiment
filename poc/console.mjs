// Collects renderer console messages from the window matching argv[2] for argv[3] ms after reload-free attach.
import { createRequire } from 'node:module';
const require = createRequire('C:/Playground/ssh-persistant/vscodium/vscode/package.json');
const { chromium } = require('playwright-core');
const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
const pages = b.contexts().flatMap(c => c.pages());
let p; for (const x of pages) if ((await x.title()).includes(process.argv[2])) p = x;
const cdp = await p.context().newCDPSession(p);
await cdp.send('Runtime.enable');
const logs = [];
cdp.on('Runtime.consoleAPICalled', e => logs.push(e.type + ' ' + e.args.map(a => a.value ?? a.description ?? '').join(' ')));
cdp.on('Runtime.exceptionThrown', e => logs.push('EXC ' + (e.exceptionDetails.exception?.description ?? e.exceptionDetails.text)));
await p.waitForTimeout(Number(process.argv[3] ?? 3000));
console.log(logs.filter(l => /error|warn|EXC|terminal|pty/i.test(l)).slice(-40).join('\n'));
process.exit(0);
