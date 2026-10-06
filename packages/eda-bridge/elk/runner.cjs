#!/usr/bin/env node
'use strict';
/*
 * bodesign ELK layered runner (DD-15 / DD-9 clearance condition 3).
 *
 * Process model: ONE bounded Node child per emit. No service, no warm pool,
 * no web-worker (the in-process bundled ELK is used on purpose so the only
 * installed package is elkjs itself).
 *
 * Protocol:
 *   stdin  : one JSON document  {"graph": <ELK JSON graph>, "timeout_ms": <int>}
 *   stdout : one JSON document  {"ok": true, "elkjs": "<version>", "solution": <ELK JSON>}
 *            or                 {"ok": false, "code": "<E_*>", "message": "..."}
 *   exit   : 0 on ok, 2 on malformed input, 3 on layout failure, 4 on watchdog.
 *
 * The Python side (elk_layout.py) treats ANY non-zero exit, timeout or
 * non-JSON stdout as a typed refusal. Nothing here ever falls back.
 */

const path = require('path');

function fail(exitCode, code, message) {
  process.stdout.write(JSON.stringify({ ok: false, code, message }) + '\n');
  process.exit(exitCode);
}

function readStdin() {
  return new Promise((resolve, reject) => {
    const chunks = [];
    process.stdin.on('data', (c) => chunks.push(c));
    process.stdin.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    process.stdin.on('error', reject);
  });
}

async function main() {
  const raw = await readStdin();
  let request;
  try {
    request = JSON.parse(raw);
  } catch (e) {
    return fail(2, 'E_ELK_INPUT_NOT_JSON', String(e && e.message));
  }
  if (!request || typeof request !== 'object' || !request.graph || typeof request.graph !== 'object') {
    return fail(2, 'E_ELK_INPUT_SHAPE', 'expected {"graph": {...}}');
  }
  const timeoutMs = Number.isFinite(request.timeout_ms) && request.timeout_ms > 0
    ? Math.floor(request.timeout_ms)
    : 30000;

  // Internal watchdog: the parent also enforces a wall clock, but a stuck layout
  // must not depend on the parent being alive to be reported as a failure.
  const watchdog = setTimeout(() => {
    fail(4, 'E_ELK_WATCHDOG', `layout exceeded ${timeoutMs} ms inside the runner`);
  }, timeoutMs);
  watchdog.unref();

  let ELK;
  try {
    // elk.bundled.js = API + worker in one file, executed in-process.
    ELK = require('elkjs/lib/elk.bundled.js');
  } catch (e) {
    clearTimeout(watchdog);
    return fail(3, 'E_ELK_REQUIRE', String(e && e.message));
  }
  const pkg = require(path.join(path.dirname(require.resolve('elkjs/package.json')), 'package.json'));

  const elk = new ELK();
  let solution;
  try {
    solution = await elk.layout(request.graph);
  } catch (e) {
    clearTimeout(watchdog);
    return fail(3, 'E_ELK_LAYOUT', String(e && (e.message || e)));
  }
  clearTimeout(watchdog);
  process.stdout.write(JSON.stringify({ ok: true, elkjs: pkg.version, solution }) + '\n');
  process.exit(0);
}

main().catch((e) => fail(3, 'E_ELK_RUNNER', String(e && (e.stack || e.message || e))));
