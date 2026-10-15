// Evaluates an expression in a Node process with --inspect (e.g. the pty host on nas, port 5877).
// Usage (on nas):  node inspect-eval.mjs <port> "<expression>"   or   node inspect-eval.mjs <port> @<file.js>
// Copy it over with:  ssh -p 2222 root@nas "cat > /tmp/inspect-eval.mjs" < poc/inspect-eval.mjs
const [port, arg] = process.argv.slice(2);
const expr = arg.startsWith('@') ? (await import('node:fs')).readFileSync(arg.slice(1), 'utf8') : arg;
const [t] = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
const ws = new WebSocket(t.webSocketDebuggerUrl);
await new Promise(r => ws.onopen = r);
ws.onmessage = m => { const d = JSON.parse(m.data); if (d.id === 1) { console.log(JSON.stringify(d.result?.result ?? d)); ws.close(); } };
ws.send(JSON.stringify({ id: 1, method: 'Runtime.evaluate', params: { expression: expr, returnByValue: true, awaitPromise: true } }));
