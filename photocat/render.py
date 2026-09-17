"""Render a browsable HTML contact-sheet from catalog items.

Single self-contained index.html with the catalog embedded as JSON (so it opens
straight off disk — no server, no CORS). Thumbnails are referenced by relative
path under ./thumbs/. Lazy-loaded so thousands scroll smoothly.
"""

from __future__ import annotations

import html
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

_CSS = """
:root{--bg:#14110b;--panel:#1e1a12;--card:#241f16;--border:#3a3326;--text:#f3ead8;
--muted:#a99b80;--green:#6b8f6b;--terra:#d07a36;--brown:#caa46f;--radius:10px;
--font:'Segoe UI',system-ui,sans-serif}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:var(--font);line-height:1.5}
header{position:sticky;top:0;z-index:20;background:rgba(20,17,11,.96);backdrop-filter:blur(10px);
border-bottom:2px solid var(--border);padding:.7rem 1rem}
h1{font-size:1.1rem;font-weight:700;color:var(--terra);display:flex;gap:.5rem;align-items:baseline}
h1 small{color:var(--muted);font-size:.7rem;font-weight:400}
.controls{display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.6rem;align-items:center}
.chip{cursor:pointer;border:2px solid var(--border);background:var(--card);color:var(--text);
padding:.3rem .7rem;border-radius:20px;font-size:.78rem;font-weight:600;user-select:none;white-space:nowrap}
.chip:hover{border-color:var(--green)}
.chip.on{background:var(--green);border-color:var(--green);color:#0d0d08}
.chip .c{opacity:.7;font-weight:400;margin-left:.25rem}
#q{flex:1;min-width:160px;background:var(--card);border:2px solid var(--border);color:var(--text);
padding:.4rem .7rem;border-radius:8px;font-size:.85rem}
#q:focus{outline:none;border-color:var(--terra)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:.5rem;padding:1rem}
.tile{position:relative;background:var(--card);border:2px solid var(--border);border-radius:8px;
overflow:hidden;cursor:zoom-in;aspect-ratio:1}
.tile:hover{border-color:var(--terra)}
.tile img{width:100%;height:100%;object-fit:cover;display:block;background:#000}
.tile .tags{position:absolute;left:0;bottom:0;right:0;display:flex;gap:2px;padding:3px;flex-wrap:wrap;
background:linear-gradient(transparent,rgba(0,0,0,.75))}
.b{font-size:.58rem;font-weight:700;padding:1px 5px;border-radius:4px;letter-spacing:.02em}
.b.web{background:var(--green);color:#0d0d08}.b.reel{background:var(--terra);color:#0d0d08}
.b.post{background:#5a86c4;color:#0d0d08}.b.junk{background:#6b6256;color:#cdbfa6}
.b.maybe{background:#caa46f;color:#0d0d08}
.tile.miss{display:flex;align-items:center;justify-content:center;font-size:.6rem;color:var(--muted);padding:6px;text-align:center;cursor:default}
#empty{padding:3rem;text-align:center;color:var(--muted)}
/* lightbox */
#lb{position:fixed;inset:0;background:rgba(0,0,0,.93);display:none;z-index:50;
align-items:center;justify-content:center;padding:2rem 1rem;flex-direction:column;gap:1rem}
#lb.on{display:flex}
#lb img{max-width:min(92vw,900px);max-height:62vh;border:3px solid var(--border);border-radius:8px}
#lbinfo{max-width:760px;background:var(--panel);border:2px solid var(--border);border-radius:10px;padding:1rem 1.2rem;font-size:.85rem}
#lbinfo h3{color:var(--terra);font-size:.95rem;margin-bottom:.2rem;word-break:break-all}
#lbinfo .path{color:var(--muted);font-size:.72rem;margin-bottom:.6rem;word-break:break-all}
#lbinfo .row{margin:.3rem 0;display:flex;gap:.5rem}
#lbinfo .k{flex:0 0 78px;color:var(--brown);font-weight:600}
#lbclose{position:absolute;top:1rem;right:1.3rem;font-size:1.4rem;color:var(--text);background:none;
border:2px solid var(--text);border-radius:8px;width:40px;height:40px;cursor:pointer}
"""

_JS = """
const DATA = __DATA__;
let filter='all', q='', matches=[], shown=0;
const BATCH=400;
const grid=document.getElementById('grid'), empty=document.getElementById('empty');
function vis(d){
  if(q){const h=(d.name+' '+(d.desc||'')+' '+d.folder).toLowerCase();if(!h.includes(q))return false;}
  switch(filter){
    case 'all': return true;
    case 'website': return d.website===true;
    case 'reel': return d.reel===true||d.reel===null;
    case 'post': return d.post===true||d.post===null;
    case 'junk': return d.junk===true;
    case 'cactus_plant': return d.category==='cactus_plant';
    case 'product': return d.category==='product';
    case 'sensitive': return d.category==='sensitive';
    default: return true;
  }
}
function badge(d){let b='';
  if(d.website===true)b+="<span class='b web'>WEB</span>";
  if(d.reel===true)b+="<span class='b reel'>REEL</span>"; else if(d.reel===null)b+="<span class='b maybe'>reel?</span>";
  if(d.post===true)b+="<span class='b post'>POST</span>";
  if(d.junk===true)b+="<span class='b junk'>junk</span>";
  return b;}
function makeTile(i){const d=DATA[i];
  const t=document.createElement('div'); t.className='tile'+(d.thumb?'':' miss');
  if(d.thumb){t.innerHTML=`<img loading="lazy" src="${d.thumb}" alt="">`+`<div class="tags">${badge(d)}</div>`;
    t.onclick=()=>openLb(i);}
  else{t.textContent=d.name+' (no preview)';}
  return t;}
function renderMore(){
  const end=Math.min(shown+BATCH, matches.length);
  const frag=document.createDocumentFragment();
  for(let k=shown;k<end;k++) frag.appendChild(makeTile(matches[k]));
  grid.appendChild(frag); shown=end;
  const more=document.getElementById('more');
  if(shown<matches.length){more.style.display='block';more.textContent=`Load more (${matches.length-shown} more)`;}
  else more.style.display='none';
}
function reset(){
  grid.innerHTML=''; shown=0; matches=[];
  for(let i=0;i<DATA.length;i++) if(vis(DATA[i])) matches.push(i);
  document.getElementById('shown').textContent=matches.length;
  empty.style.display=matches.length?'none':'block';
  renderMore();
}
function tri(v){return v===true?'yes':(v===null?'maybe':'no');}
function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function openLb(i){const d=DATA[i];
  document.getElementById('lbimg').src=d.thumb||'';
  document.getElementById('lbinfo').innerHTML=
    `<h3>${esc(d.name)}</h3><div class="path">${esc(d.folder)}</div>`+
    `<div class="row"><span class="k">Sees</span><span>${esc(d.desc||'(not AI-tagged yet)')}</span></div>`+
    `<div class="row"><span class="k">Category</span><span>${esc(d.category)} · quality ${esc(d.quality||'—')} · confidence ${esc(d.confidence||'—')}</span></div>`+
    `<div class="row"><span class="k">Website</span><span><b>${tri(d.website)}</b> — ${esc(d.website_why)}</span></div>`+
    `<div class="row"><span class="k">Reel</span><span><b>${tri(d.reel)}</b> — ${esc(d.reel_why)}</span></div>`+
    `<div class="row"><span class="k">Post</span><span><b>${tri(d.post)}</b> — ${esc(d.post_why)}</span></div>`+
    `<div class="row"><span class="k">Junk</span><span><b>${tri(d.junk)}</b> — ${esc(d.junk_why||'—')}</span></div>`;
  document.getElementById('lb').classList.add('on');
}
document.getElementById('lbclose').onclick=()=>document.getElementById('lb').classList.remove('on');
document.getElementById('lb').onclick=e=>{if(e.target.id==='lb')document.getElementById('lb').classList.remove('on');};
document.addEventListener('keydown',e=>{if(e.key==='Escape')document.getElementById('lb').classList.remove('on');});
document.querySelectorAll('.chip').forEach(c=>c.onclick=()=>{
  document.querySelectorAll('.chip').forEach(x=>x.classList.remove('on'));
  c.classList.add('on'); filter=c.dataset.f; reset();});
let qt=null;
document.getElementById('q').addEventListener('input',e=>{q=e.target.value.trim().toLowerCase();
  clearTimeout(qt); qt=setTimeout(reset,160);});
document.getElementById('more').onclick=renderMore;
window.addEventListener('scroll',()=>{
  if(shown<matches.length && (window.innerHeight+window.scrollY)>=document.body.offsetHeight-700) renderMore();});
reset();
"""


def _counts(items):
    c = {"all": len(items), "website": 0, "reel": 0, "post": 0, "junk": 0,
         "cactus_plant": 0, "product": 0, "sensitive": 0}
    for d in items:
        if d.get("category") == "sensitive":
            c["sensitive"] += 1
        if d.get("website") is True:
            c["website"] += 1
        if d.get("reel") in (True, None):
            c["reel"] += 1
        if d.get("post") in (True, None):
            c["post"] += 1
        if d.get("junk") is True:
            c["junk"] += 1
        if d.get("category") == "cactus_plant":
            c["cactus_plant"] += 1
        if d.get("category") == "product":
            c["product"] += 1
    return c


def render_html(items, label: str, out_html: Path) -> Path:
    """Write the gallery to out_html. items must already carry relative 'thumb'."""
    out_html = Path(out_html)
    c = _counts(items)
    chips = [("all", "All"), ("website", "Website"), ("reel", "Reel"),
             ("post", "Post"), ("cactus_plant", "Cactus/Plant"),
             ("product", "Product"), ("sensitive", "⚠ Sensitive"), ("junk", "Junk")]
    chip_html = "".join(
        f"<span class='chip{' on' if k=='all' else ''}' data-f='{k}'>{lbl}"
        f"<span class='c'>{c.get(k,0)}</span></span>" for k, lbl in chips)
    # Escape "</" so a "</script>" (or "</...") inside any string value can't
    # close the embedded <script> block early. Safe inside JS string/JSON.
    payload = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    body = f"""<!doctype html><html lang='en'><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Photo Catalog — {html.escape(label)}</title><style>{_CSS}</style></head><body>
<header><h1>📷 Photo Catalog <small>{html.escape(label)} · <span id='shown'>{c['all']}</span> shown</small></h1>
<div class='controls'>{chip_html}<input id='q' placeholder='search name / description / folder…'></div></header>
<div id='grid' class='grid'></div><div id='empty' style='display:none'>No photos match.</div>
<button id='more' style='display:none;margin:1rem auto 2rem;background:var(--card);color:var(--text);border:2px solid var(--border);border-radius:8px;padding:.6rem 1.4rem;font-size:.85rem;font-weight:600;cursor:pointer'></button>
<div id='lb'><button id='lbclose'>✕</button><img id='lbimg' alt=''><div id='lbinfo'></div></div>
<script>{_JS.replace('__DATA__', payload)}</script></body></html>"""
    try:
        out_html.parent.mkdir(parents=True, exist_ok=True)
        out_html.write_text(body, encoding="utf-8")
    except OSError as exc:
        log.error("failed to write gallery html %s: %s", out_html, exc)
        raise
    return out_html
