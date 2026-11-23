"""Local labeling page for the AI-relatedness review sample.

    python3 -I pipeline/run.py label [port]      # serves http://127.0.0.1:8794 (this Mac only)

Reads the private packet the build writes (titles and ad text, outside the repo) and saves each label to
data/ai-job-map/labels/<packet>.labels.csv as soon as it is clicked, keyed by posting id (so a rebuilt packet
never moves a label onto a different role). The page never receives the measure's
scores, flags or firm ids, so the labeler stays blind to omega. Standard library only.
"""
import csv
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
CODEBOOK_VERSION = "ai-role-v1"
CODEBOOK = [
    {"key": "builds", "short": "Builds AI",
     "rule": "The job needs AI or machine-learning skills: building, training, evaluating or deploying models, or AI research."},
    {"key": "works_with", "short": "Works with AI",
     "rule": "The job uses, integrates, sells or supports AI products, models or tools, but building AI is not the job."},
    {"key": "none", "short": "No AI",
     "rule": "AI is not part of the job, even if the company works on AI."},
    {"key": "cant_tell", "short": "Can't tell",
     "rule": "The text is not enough to decide."},
]
KEYS = {c["key"] for c in CODEBOOK}
FIELDS = ["n", "posting_id", "label", "note", "seconds_on_role", "labeled_at", "codebook_version"]
LOCK = threading.Lock()


def load_config():
    with open(os.path.join(HERE, "config", "config.json")) as fh:
        return json.load(fh)


def paths(cfg, name="roles-sample-50"):
    inp = cfg["inputs"]
    return (os.path.join(inp["private_review_dir"], f"{name}.packet.json"),
            os.path.join(inp["labels_dir"], f"{name}.labels.csv"))


def read_labels(path):
    if not os.path.exists(path):
        return {}
    with open(path, newline="") as fh:
        return {r["posting_id"]: r for r in csv.DictReader(fh)}


def write_labels(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=FIELDS)
        wr.writeheader()
        for pid in sorted(rows, key=lambda p: int(rows[p]["n"])):
            wr.writerow({k: rows[pid].get(k, "") for k in FIELDS})
    os.replace(tmp, path)


def make_handler(packet, labels_path, port):
    roles = {r["n"]: r for r in packet["roles"]}
    n_of = {r["posting_id"]: r["n"] for r in packet["roles"]}
    public_roles = [{"n": r["n"], "title": r["title"], "requirement_text": r["requirement_text"], "full_ad": r["full_ad"]}
                    for r in packet["roles"]]
    allowed_origins = {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            sys.stderr.write("label: " + (fmt % args) + "\n")

        def _send(self, code, body, ctype="application/json"):
            data = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _state(self):
            labs = read_labels(labels_path)
            return json.dumps({"name": packet["name"], "snapshot_date": packet["snapshot_date"], "codebook": CODEBOOK,
                               "codebook_version": CODEBOOK_VERSION, "roles": public_roles,
                               "labels": {str(n_of[pid]): {"label": r["label"], "note": r["note"]} for pid, r in labs.items() if pid in n_of}})

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                return self._send(200, PAGE, "text/html")
            if self.path == "/api/state":
                return self._send(200, self._state())
            self._send(404, '{"error": "not found"}')

        def do_POST(self):
            origin = self.headers.get("Origin")
            if origin and origin not in allowed_origins:
                return self._send(403, '{"error": "origin"}')
            if self.path != "/api/label" or not self.headers.get("Content-Type", "").startswith("application/json"):
                return self._send(400, '{"error": "bad request"}')
            try:
                body = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", 0)), 20000)))
                n, label = int(body["n"]), body["label"]
                note = str(body.get("note", ""))[:2000]
                seconds = max(0, min(int(body.get("seconds", 0)), 86400))
            except (ValueError, KeyError, TypeError):
                return self._send(400, '{"error": "bad body"}')
            if n not in roles or label not in KEYS:
                return self._send(400, '{"error": "unknown role or label"}')
            with LOCK:
                labs = read_labels(labels_path)
                pid = roles[n]["posting_id"]
                prev = labs.get(pid, {})
                labs[pid] = {"n": n, "posting_id": pid, "label": label, "note": note,
                           "seconds_on_role": int(prev.get("seconds_on_role") or 0) + seconds,
                           "labeled_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "codebook_version": CODEBOOK_VERSION}
                write_labels(labels_path, labs)
            self._send(200, self._state())

    return Handler


def main(argv):
    port = int(argv[0]) if argv else 8794
    cfg = load_config()
    packet_path, labels_path = paths(cfg)
    if not os.path.exists(packet_path):
        sys.exit(f"no packet at {packet_path}; run `python3 -I pipeline/run.py build` first")
    with open(packet_path) as fh:
        packet = json.load(fh)
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(packet, labels_path, port))
    print(f"labeling {len(packet['roles'])} roles at http://127.0.0.1:{port}  (labels -> {labels_path})", flush=True)
    srv.serve_forever()


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Label AI Roles</title>
<style>
:root{--bg:#f7f5f1;--panel:#fff;--ink:#1c1a17;--muted:#6b665e;--line:#e2ddd4;--accent:#7a4a1f;--accent-ink:#fff;
 --builds:#2f6f4f;--works:#3d5a8a;--none:#8a8378;--cant:#a8641c;--chip:#efebe4;--focus:#c98a3a}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#171513;--panel:#211e1b;--ink:#ece7df;--muted:#a39c91;
 --line:#38332d;--accent:#d49a5c;--accent-ink:#1c1a17;--builds:#5fae86;--works:#7f9fd6;--none:#9d968b;--cant:#d9954d;--chip:#2b2723;--focus:#d9954d}}
:root[data-theme="dark"]{--bg:#171513;--panel:#211e1b;--ink:#ece7df;--muted:#a39c91;--line:#38332d;--accent:#d49a5c;--accent-ink:#1c1a17;
 --builds:#5fae86;--works:#7f9fd6;--none:#9d968b;--cant:#d9954d;--chip:#2b2723;--focus:#d9954d}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
header{position:sticky;top:0;z-index:2;background:var(--bg);border-bottom:1px solid var(--line);padding:12px 16px}
.wrap{max-width:1120px;margin:0 auto}
h1{font-size:17px;margin:0 0 2px}
.sub{color:var(--muted);font-size:13px;margin:0}
.bar{height:6px;background:var(--chip);border-radius:3px;margin-top:10px;overflow:hidden}
.bar>i{display:block;height:100%;background:var(--accent);width:0;transition:width .2s}
.grid{display:grid;grid-template-columns:220px 1fr;gap:20px;padding:16px}
nav{position:sticky;top:96px;align-self:start;display:flex;flex-wrap:wrap;gap:6px}
nav button{width:36px;height:32px;border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:6px;cursor:pointer;font-size:13px}
nav button.on{outline:2px solid var(--focus);outline-offset:1px}
nav button[data-l=builds]{background:var(--builds);color:#fff;border-color:transparent}
nav button[data-l=works_with]{background:var(--works);color:#fff;border-color:transparent}
nav button[data-l=none]{background:var(--none);color:#fff;border-color:transparent}
nav button[data-l=cant_tell]{background:var(--cant);color:#fff;border-color:transparent}
main{min-width:0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:20px}
.num{color:var(--muted);font-size:13px}
h2{font-size:22px;line-height:1.25;margin:4px 0 14px}
h3{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin:18px 0 6px}
.text p{margin:0 0 8px;white-space:pre-wrap;overflow-wrap:anywhere}
.full{border-top:1px dashed var(--line);margin-top:12px;padding-top:8px;color:var(--muted)}
.linkish{background:none;border:0;color:var(--accent);cursor:pointer;padding:0;font:inherit;text-decoration:underline}
.dock{position:sticky;bottom:0;z-index:1;background:var(--panel);border-top:1px solid var(--line);margin:16px -20px -20px;padding:12px 20px 16px;border-radius:0 0 10px 10px}
.labels{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}
.lab{text-align:left;border:2px solid var(--line);background:var(--panel);color:var(--ink);border-radius:8px;padding:10px 12px;cursor:pointer;font:inherit}
.lab b{display:block;font-size:15px}
.lab span{display:block;font-size:13px;color:var(--muted);line-height:1.35}
.lab kbd{float:right;font:12px ui-monospace,Menlo,monospace;border:1px solid var(--line);border-radius:4px;padding:0 5px;color:var(--muted)}
.lab.sel[data-k=builds]{border-color:var(--builds)} .lab.sel[data-k=works_with]{border-color:var(--works)}
.lab.sel[data-k=none]{border-color:var(--none)} .lab.sel[data-k=cant_tell]{border-color:var(--cant)}
.lab.sel{box-shadow:inset 0 0 0 1px currentColor}
textarea{width:100%;min-height:56px;border:1px solid var(--line);border-radius:8px;background:var(--panel);color:var(--ink);padding:8px;font:inherit;font-size:14px}
.row{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-top:10px;flex-wrap:wrap}
.btn{border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:8px;padding:8px 14px;cursor:pointer;font:inherit}
.btn.primary{background:var(--accent);color:var(--accent-ink);border-color:transparent}
.status{font-size:13px;color:var(--muted)}
.done{border-color:var(--builds)}
.help{font-size:13px;color:var(--muted);margin-top:12px}
@media (max-width:900px){.labels{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:720px){.grid{grid-template-columns:1fr;padding:12px 16px}nav{position:static}}
</style></head>
<body>
<header><div class="wrap">
 <h1>Does this role need AI skills?</h1>
 <p class="sub" id="sub">Loading.</p>
 <div class="bar"><i id="bar"></i></div>
</div></header>
<div class="wrap grid">
 <nav id="nav" aria-label="Roles"></nav>
 <main>
  <div class="card" id="card"></div>
  <p class="help">Keys: <b>1 to 4</b> pick a label and move on, <b>←</b> and <b>→</b> move between roles. Each click saves to disk at once.
  Scores, flags and the firm's name are hidden so they don't sway the label; the full ad may still name the firm.</p>
 </main>
</div>
<script>
let S=null,cur=1,shownAt=Date.now(),showFull=false;
const $=id=>document.getElementById(id);
function el(tag,attrs,...kids){const e=document.createElement(tag);for(const[k,v]of Object.entries(attrs||{})){if(k==="class")e.className=v;else if(k.startsWith("on"))e.addEventListener(k.slice(2),v);else e.setAttribute(k,v)}for(const c of kids)e.append(c);return e}
function paras(text){const d=el("div",{class:"text"});for(const b of(Array.isArray(text)?text:text.split("\n")))if(b.trim())d.append(el("p",{},b));return d}
async function load(){const r=await fetch("/api/state");S=await r.json();const firstOpen=S.roles.find(x=>!S.labels[x.n]);cur=firstOpen?firstOpen.n:1;render()}
function labeled(){return Object.keys(S.labels).length}
function render(){
 const total=S.roles.length,done=labeled();
 $("sub").textContent=`${done} of ${total} labeled · ad text from the ${S.snapshot_date} snapshot · codebook ${S.codebook_version}`;
 $("bar").style.width=(100*done/total)+"%";
 const nav=$("nav");nav.replaceChildren();
 for(const r of S.roles){const L=S.labels[r.n];const b=el("button",{title:r.title,onclick:()=>go(r.n)},String(r.n));if(L)b.dataset.l=L.label;if(r.n===cur)b.classList.add("on");nav.append(b)}
 const role=S.roles.find(x=>x.n===cur),L=S.labels[cur]||{};
 const card=$("card");card.replaceChildren();card.classList.toggle("done",done===total);
 if(done===total)card.append(el("p",{class:"status"},"All roles are labeled. Tell Claude the labels are done. You can still change any label."));
 card.append(el("div",{class:"num"},`Role ${cur} of ${total}`),el("h2",{},role.title));
 card.append(el("h3",{},"Responsibilities and requirements (what the measure reads)"),paras(role.requirement_text));
 const tog=el("button",{class:"linkish",onclick:()=>{showFull=!showFull;render()}},showFull?"Hide the full ad":"Show the full ad");
 card.append(tog);
 if(showFull){const f=el("div",{class:"full"});f.append(paras(role.full_ad));card.append(f)}
 card.append(el("h3",{},"Note (optional)"));
 const ta=el("textarea",{id:"note",placeholder:"Why, if it was a close call"});ta.value=L.note||"";
 ta.addEventListener("blur",()=>{if(S.labels[cur]&&ta.value!==(S.labels[cur].note||""))save(S.labels[cur].label,false)});
 card.append(ta);
 const grid=el("div",{class:"labels"});
 S.codebook.forEach((c,i)=>{const b=el("button",{class:"lab"+(L.label===c.key?" sel":""),"data-k":c.key,onclick:()=>pick(c.key)},el("kbd",{},String(i+1)),el("b",{},c.short),el("span",{},c.rule));grid.append(b)});
 card.append(el("div",{class:"dock"},grid,el("div",{class:"row"},
  el("button",{class:"btn",onclick:()=>go(cur-1)},"← Previous"),
  el("span",{class:"status",id:"st"},L.label?"Saved":"Not labeled yet"),
  el("button",{class:"btn primary",onclick:()=>go(cur+1)},"Next →"))));
 window.scrollTo({top:0});
}
function go(n){if(n<1||n>S.roles.length)return;cur=n;showFull=false;shownAt=Date.now();render()}
async function save(label,advance){
 const secs=Math.round((Date.now()-shownAt)/1000);shownAt=Date.now();
 const note=$("note")?$("note").value:"";
 const r=await fetch("/api/label",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({n:cur,label,note,seconds:secs})});
 if(!r.ok){$("st").textContent="Not saved: "+r.status;return}
 S=await r.json();
 if(advance){const next=S.roles.find(x=>x.n>cur&&!S.labels[x.n])||S.roles.find(x=>!S.labels[x.n]);if(next){go(next.n);return}}
 render()
}
function pick(k){save(k,true)}
document.addEventListener("keydown",e=>{
 if(!S||e.target.tagName==="TEXTAREA"||e.metaKey||e.ctrlKey||e.altKey)return;
 if(e.key>="1"&&e.key<=String(S.codebook.length)){pick(S.codebook[+e.key-1].key);e.preventDefault()}
 else if(e.key==="ArrowRight"){go(cur+1);e.preventDefault()}
 else if(e.key==="ArrowLeft"){go(cur-1);e.preventDefault()}
});
load();
</script>
</body></html>
"""

if __name__ == "__main__":
    main(sys.argv[1:])
