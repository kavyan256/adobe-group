#!/usr/bin/env python3
"""Local verification UI for the audit — a dev tool, NOT part of the submission.

    python3 tools/audit_ui.py          # then open http://localhost:8000

Type a URL, run the audit, and check each finding against the real site. Every
finding shows its evidence, the exact pages it is about, and how to confirm it
by hand. Mark each one correct / false positive / unsure; the verdicts are
saved in your browser and can be exported as JSON.

Stdlib only, so it runs wherever the skills do. Lives outside the marketplace
root on purpose: it must never end up inside the submission zip.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# Which marketplace root to audit with, e.g. AUDIT_MARKETPLACE=brand-ai-readiness-audit-v2.1
MARKETPLACE = os.environ.get("AUDIT_MARKETPLACE", "brand-ai-readiness-audit-v4")
AUDIT = REPO / MARKETPLACE / "skills" / "audit-orchestrator" / "scripts" / "audit.py"
PORT = 8000
TIMEOUT_S = 330  # a little past the audit's own 5-minute budget

PAGE = r"""<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Audit Verifier</title>
<style>
  :root{
    --bg:#f6f7f9; --card:#fff; --ink:#14161a; --muted:#666e7a; --line:#e3e6ea;
    --critical:#b3261e; --high:#c2410c; --medium:#a16207; --low:#3f6212; --info:#475569;
    --good:#15803d; --bad:#b3261e;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
       font:15px/1.55 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
  .wrap{max-width:920px;margin:0 auto;padding:28px 20px 80px}
  h1{font-size:21px;margin:0 0 4px}
  .sub{color:var(--muted);font-size:13px;margin-bottom:22px}
  form{display:flex;gap:8px;flex-wrap:wrap;background:var(--card);padding:14px;
       border:1px solid var(--line);border-radius:10px}
  input[type=text]{flex:1;min-width:240px;padding:10px 12px;font-size:15px;
       border:1px solid var(--line);border-radius:7px;background:#fff;color:var(--ink)}
  input[type=number]{width:82px;padding:10px;border:1px solid var(--line);border-radius:7px;
       background:#fff;color:var(--ink)}
  button{padding:10px 18px;font-size:15px;font-weight:600;border:0;border-radius:7px;
       background:var(--ink);color:#fff;cursor:pointer}
  button:disabled{opacity:.5;cursor:default}
  .ghost{background:transparent;color:var(--muted);border:1px solid var(--line);font-weight:500}
  label.opt{display:flex;align-items:center;gap:6px;color:var(--muted);font-size:13px}
  #status{margin:18px 0;color:var(--muted);font-size:14px}
  .err{background:#fdf2f2;border:1px solid #f5c6c6;color:#8a1c1c;padding:12px;
       border-radius:8px;white-space:pre-wrap;font:12px/1.5 ui-monospace,monospace}
  .bar{display:flex;gap:8px;flex-wrap:wrap;margin:20px 0 10px}
  .pill{padding:5px 11px;border-radius:99px;font-size:12.5px;font-weight:600;color:#fff}
  .headline{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--ink);
       padding:12px 14px;border-radius:8px;margin-bottom:20px;font-size:14px}
  .f{background:var(--card);border:1px solid var(--line);border-radius:10px;
     padding:16px;margin-bottom:12px;border-left:4px solid var(--line)}
  .f h3{margin:0;font-size:16px;display:flex;gap:9px;align-items:baseline;flex-wrap:wrap}
  .sev{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;color:#fff;
       padding:2px 8px;border-radius:4px}
  .fid{color:var(--muted);font-size:12px;font-weight:500;font-family:ui-monospace,monospace}
  .hurts{font-size:11px;font-weight:700;padding:2px 8px;border-radius:4px;border:1px solid}
  .hurts.ai_discoverability{color:#6d28d9;border-color:#c4b5fd;background:#f5f3ff}
  .hurts.user_retention{color:#0f766e;border-color:#99f6e4;background:#f0fdfa}
  .hurts.both{color:#b45309;border-color:#fcd34d;background:#fffbeb}
  .hurts.unknown{color:var(--muted);border-color:var(--line)}
  .filters{display:flex;gap:7px;flex-wrap:wrap;margin:0 0 16px;align-items:center}
  .filters .q{font-size:12.5px;color:var(--muted);margin-right:3px}
  .filters button.hurts{cursor:pointer;font-size:12.5px;padding:5px 11px}
  .filters button.hurts.off{opacity:.4}
  .latent{background:#eef2f7;color:var(--muted);font-size:11px;padding:2px 7px;border-radius:4px;font-weight:600}
  .ev{margin:11px 0;font-size:14px}
  .lbl{font-size:11px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;
       color:var(--muted);margin-bottom:3px}
  .urls{font:12.5px/1.7 ui-monospace,monospace;word-break:break-all}
  .urls a{color:#1d4ed8}
  .act{background:#f8f9fb;border-radius:7px;padding:11px 13px;margin-top:11px;font-size:14px}
  .act ol{margin:7px 0 0;padding-left:19px}
  .act li{margin:3px 0}
  details{margin-top:9px}
  summary{cursor:pointer;color:var(--muted);font-size:12.5px}
  details .body{font-size:13px;color:var(--muted);margin-top:7px;
       white-space:pre-wrap;font-family:ui-monospace,monospace;line-height:1.55}
  .verdict{display:flex;gap:7px;align-items:center;margin-top:13px;padding-top:12px;
       border-top:1px dashed var(--line);flex-wrap:wrap}
  .verdict span.q{font-size:12.5px;color:var(--muted);margin-right:3px}
  .v{padding:5px 11px;font-size:12.5px;border:1px solid var(--line);background:#fff;
     border-radius:6px;cursor:pointer;color:var(--muted);font-weight:500}
  .v.on[data-v=correct]{background:var(--good);border-color:var(--good);color:#fff}
  .v.on[data-v=false]{background:var(--bad);border-color:var(--bad);color:#fff}
  .v.on[data-v=unsure]{background:var(--muted);border-color:var(--muted);color:#fff}
  .tally{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;
     margin:22px 0;font-size:14px;display:flex;gap:18px;align-items:center;flex-wrap:wrap}
  pre.raw{background:#14161a;color:#e6e6e6;padding:14px;border-radius:8px;overflow-x:auto;
     font-size:12px;line-height:1.5}
  h2.sec{font-size:14px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);
     margin:30px 0 12px}
  @media (prefers-color-scheme:dark){
    :root:not([data-theme=light]){--bg:#0f1115;--card:#171a1f;--ink:#e8eaed;--muted:#9aa3ad;--line:#282d35}
    :root:not([data-theme=light]) input,:root:not([data-theme=light]) input[type=number]{background:#0f1115;color:#e8eaed}
    :root:not([data-theme=light]) button{background:#e8eaed;color:#14161a}
    :root:not([data-theme=light]) .ghost{background:transparent;color:#9aa3ad}
    :root:not([data-theme=light]) .act{background:#1d2127}
    :root:not([data-theme=light]) .v{background:#171a1f}
    :root:not([data-theme=light]) .latent{background:#242a32}
    :root:not([data-theme=light]) .urls a{color:#7ea6ff}
  }
</style>

<div class="wrap">
  <h1>Audit Verifier</h1>
  <div class="sub">Run the audit on a real site, then check each finding against the actual page.
    Verdicts are saved in this browser.</div>

  <form id="f">
    <input type="text" id="url" placeholder="example.com" autocomplete="off" required>
    <label class="opt">pages <input type="number" id="mp" value="20" min="1" max="200"></label>
    <button id="go">Run audit</button>
  </form>

  <div id="status"></div>
  <div id="out"></div>
</div>

<script>
const SEV = ['critical','high','medium','low','info'];
const COLOR = {critical:'var(--critical)',high:'var(--high)',medium:'var(--medium)',
               low:'var(--low)',info:'var(--info)'};
const HURTS = {ai_discoverability:'AI discoverability', user_retention:'User retention',
               both:'Both', unknown:'Untagged'};
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const $ = id => document.getElementById(id);
let REPORT = null, SITE = '';

function vkey(site, id){ return 'verdict:' + site + ':' + id; }
function getV(site, id){ try { return localStorage.getItem(vkey(site,id)) || ''; } catch { return ''; } }
function setV(site, id, v){ try { v ? localStorage.setItem(vkey(site,id), v)
                                   : localStorage.removeItem(vkey(site,id)); } catch {} }

$('f').addEventListener('submit', async e => {
  e.preventDefault();
  const url = $('url').value.trim();
  if (!url) return;
  $('go').disabled = true;
  $('out').innerHTML = '';
  const t0 = Date.now();
  const tick = setInterval(() => {
    $('status').textContent = `Auditing ${url}… ${((Date.now()-t0)/1000).toFixed(0)}s`;
  }, 250);
  try {
    const r = await fetch('/api/audit', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({url, max_pages: Number($('mp').value) || 20})
    });
    const data = await r.json();
    clearInterval(tick);
    const secs = ((Date.now()-t0)/1000).toFixed(1);
    if (!r.ok || data.error) {
      $('status').textContent = '';
      $('out').innerHTML = `<div class="err">${esc(data.error || 'Audit failed')}\n\n${esc(data.stderr||'')}</div>`;
      return;
    }
    $('status').textContent = `Done in ${secs}s` + (secs > 300 ? '  ⚠ over the 5-minute limit' : '');
    REPORT = data.report; SITE = REPORT.site || url;
    render();
  } catch (err) {
    clearInterval(tick);
    $('status').textContent = '';
    $('out').innerHTML = `<div class="err">${esc(err)}</div>`;
  } finally {
    $('go').disabled = false;
  }
});

function render(){
  const rep = REPORT, s = rep.summary || {}, out = [];

  out.push('<div class="bar">' + SEV.map(k =>
    s[k] ? `<span class="pill" style="background:${COLOR[k]}">${s[k]} ${k}</span>` : ''
  ).join('') + (s.latent_findings ? `<span class="pill" style="background:var(--info)">${s.latent_findings} latent</span>` : '')
   + `<span class="pill" style="background:var(--info)">${rep.findings.length} total</span></div>`);

  if (s.headline) out.push(`<div class="headline">${esc(s.headline)}</div>`);

  const hc = {};
  rep.findings.forEach(f => { const h = f.hurts || 'unknown'; hc[h] = (hc[h]||0) + 1; });
  out.push('<div class="filters"><span class="q">Hurts:</span>' +
    Object.keys(HURTS).filter(h => hc[h]).map(h =>
      `<button class="hurts ${h}" data-h="${h}">${HURTS[h]} · ${hc[h]}</button>`).join('') +
    '</div>');

  out.push('<div class="tally" id="tally"></div>');

  const order = f => SEV.indexOf(f.severity);
  [...rep.findings].sort((a,b) => order(a)-order(b)).forEach(f => out.push(card(f)));

  if (rep.proactive_recommendations?.length) {
    out.push('<h2 class="sec">Proactive recommendations</h2>');
    rep.proactive_recommendations.forEach(p => {
      const t = p.title || p.summary || p;
      out.push(`<div class="f"><h3>${esc(t)}</h3>${
        p.rationale ? `<div class="ev">${esc(p.rationale)}</div>` : ''}</div>`);
    });
  }

  out.push('<h2 class="sec">Raw report</h2>');
  out.push('<button class="ghost" onclick="exportVerdicts()">Export my verdicts</button> ');
  out.push('<button class="ghost" onclick="document.getElementById(\'raw\').hidden=!document.getElementById(\'raw\').hidden">Toggle JSON</button>');
  out.push(`<pre class="raw" id="raw" hidden>${esc(JSON.stringify(rep,null,2))}</pre>`);

  $('out').innerHTML = out.join('');
  document.querySelectorAll('.v').forEach(b => b.addEventListener('click', onVerdict));
  document.querySelectorAll('.filters button').forEach(b => b.addEventListener('click', onFilter));
  paintVerdicts(); tally();
}

// Click a tag to show only that kind; click it again to show everything.
let FILTER = '';
function onFilter(e){
  const h = e.currentTarget.dataset.h;
  FILTER = FILTER === h ? '' : h;
  document.querySelectorAll('.filters button').forEach(b =>
    b.classList.toggle('off', !!FILTER && b.dataset.h !== FILTER));
  document.querySelectorAll('.f[data-id]').forEach(c =>
    c.hidden = !!FILTER && c.dataset.hurts !== FILTER);
}

function card(f){
  const urls = f.affected_urls || [];
  const shown = urls.slice(0,6);
  const a = f.suggested_action || {};
  const h = HURTS[f.hurts] ? f.hurts : 'unknown';
  return `<div class="f" data-id="${esc(f.id)}" data-hurts="${h}" style="border-left-color:${COLOR[f.severity]||'var(--line)'}">
    <h3>
      <span class="sev" style="background:${COLOR[f.severity]||'var(--info)'}">${esc(f.severity)}</span>
      <span class="hurts ${h}">${HURTS[h]}</span>
      <span>${esc(f.title)}</span>
      <span class="fid">${esc(f.id)}${f.check_id ? ' · '+esc(f.check_id) : ''}</span>
      ${f.status === 'latent' ? '<span class="latent">latent — hidden behind an access block</span>' : ''}
    </h3>

    <div class="ev"><div class="lbl">Evidence</div>${esc(f.evidence)}</div>

    ${shown.length ? `<div class="ev"><div class="lbl">Check these pages yourself
      ${urls.length > shown.length ? `(${shown.length} of ${urls.length})` : ''}</div>
      <div class="urls">${shown.map(u =>
        `<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(u)}</a>`
      ).join('<br>')}</div></div>` : ''}

    <div class="act">
      <div class="lbl">Suggested fix — ${esc(a.priority||'')} priority${a.effort ? ', '+esc(a.effort)+' effort' : ''}</div>
      ${esc(a.summary||'')}
      ${a.how?.length ? `<ol>${a.how.map(h => `<li>${esc(h)}</li>`).join('')}</ol>` : ''}
      ${a.verify ? `<div style="margin-top:8px"><span class="lbl">Confirm the fix worked</span>${esc(a.verify)}</div>` : ''}
    </div>

    ${(f.severity_rationale || f.mechanism || f.detail) ? `<details><summary>Why this severity / how it was measured</summary>
      <div class="body">${esc([
        f.mechanism && 'Mechanism: ' + f.mechanism,
        f.severity_rationale && 'Severity: ' + f.severity_rationale,
        f.confidence && 'Confidence: ' + f.confidence + (f.measurement_basis ? ' ('+f.measurement_basis+')' : ''),
        f.blast_radius && 'Blast radius: ' + f.blast_radius +
          (f.affected_url_count != null ? ' — '+f.affected_url_count+' page(s)' : ''),
        f.blocked_by && 'Blocked by: ' + (f.blocked_by.note || f.blocked_by.finding_check || '') +
          (f.blocked_by.agents_affected?.length ? ' [' + f.blocked_by.agents_affected.join(', ') + ']' : ''),
        f.detail && Object.keys(f.detail).length && 'Detail: ' + JSON.stringify(f.detail, null, 2)
      ].filter(Boolean).join('\n\n'))}</div></details>` : ''}

    <div class="verdict">
      <span class="q">Does this match the real site?</span>
      <button class="v" data-v="correct">Correct</button>
      <button class="v" data-v="false">False positive</button>
      <button class="v" data-v="unsure">Unsure</button>
    </div>
  </div>`;
}

function onVerdict(e){
  const btn = e.currentTarget;
  const id = btn.closest('.f').dataset.id;
  const cur = getV(SITE, id);
  setV(SITE, id, cur === btn.dataset.v ? '' : btn.dataset.v);
  paintVerdicts(); tally();
}

function paintVerdicts(){
  document.querySelectorAll('.f[data-id]').forEach(cardEl => {
    const v = getV(SITE, cardEl.dataset.id);
    cardEl.querySelectorAll('.v').forEach(b => b.classList.toggle('on', b.dataset.v === v));
  });
}

function tally(){
  const c = {correct:0, false:0, unsure:0, unjudged:0};
  REPORT.findings.forEach(f => { const v = getV(SITE, f.id); v ? c[v]++ : c.unjudged++; });
  const judged = c.correct + c['false'];
  const rate = judged ? ((c.correct/judged)*100).toFixed(0) + '% precision' : 'no verdicts yet';
  $('tally').innerHTML =
    `<b>${rate}</b><span style="color:var(--good)">✓ ${c.correct} correct</span>` +
    `<span style="color:var(--bad)">✗ ${c['false']} false positive</span>` +
    `<span style="color:var(--muted)">? ${c.unsure} unsure · ${c.unjudged} unjudged</span>`;
}

function exportVerdicts(){
  const rows = REPORT.findings.map(f => ({
    site: SITE, id: f.id, check_id: f.check_id, severity: f.severity, hurts: f.hurts,
    title: f.title, verdict: getV(SITE, f.id) || 'unjudged'
  }));
  const blob = new Blob([JSON.stringify(rows,null,2)], {type:'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `verdicts-${SITE.replace(/[^a-z0-9]/gi,'-')}.json`;
  a.click();
}
</script>
"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:
        if self.path != "/api/audit":
            self._send(404, b'{"error":"not found"}', "application/json")
            return

        try:
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(n) or b"{}")
        except (ValueError, json.JSONDecodeError) as e:
            self._send(400, json.dumps({"error": f"bad request: {e}"}).encode(), "application/json")
            return

        url = str(req.get("url", "")).strip()
        max_pages = int(req.get("max_pages") or 20)
        if not url:
            self._send(400, b'{"error":"no url"}', "application/json")
            return

        print(f"  -> auditing {url} (max {max_pages} pages)", flush=True)
        try:
            proc = subprocess.run(
                [sys.executable, str(AUDIT), url, "--max-pages", str(max_pages)],
                capture_output=True, text=True, timeout=TIMEOUT_S, cwd=AUDIT.parent,
            )
        except subprocess.TimeoutExpired:
            self._send(500, json.dumps({
                "error": f"Audit exceeded {TIMEOUT_S}s and was killed.",
                "stderr": "This is itself a finding: the run must fit the 5-minute budget.",
            }).encode(), "application/json")
            return

        if proc.returncode != 0:
            self._send(500, json.dumps({
                "error": f"audit.py exited {proc.returncode}",
                "stderr": proc.stderr[-4000:],
            }).encode(), "application/json")
            return

        try:
            report = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            self._send(500, json.dumps({
                "error": f"audit.py did not emit valid JSON: {e}",
                "stderr": (proc.stdout[:1500] + "\n---\n" + proc.stderr[-2000:]),
            }).encode(), "application/json")
            return

        print(f"     {len(report.get('findings', []))} finding(s)", flush=True)
        self._send(200, json.dumps({"report": report}).encode("utf-8"), "application/json")

    def log_message(self, *args) -> None:  # quiet the default per-request noise
        pass


def main() -> None:
    if not AUDIT.is_file():
        sys.exit(f"cannot find the entrypoint script at {AUDIT}")
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    print(f"Audit Verifier  ->  http://localhost:{port}   [{MARKETPLACE}]")
    print("Ctrl-C to stop.\n")
    try:
        ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
