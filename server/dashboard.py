from flask import Flask, send_file, jsonify, make_response
import os, json

RUNTIME_DIR = "./runtime"
app = Flask(__name__)


# ---------- NO CACHE ----------
@app.after_request
def add_no_cache_headers(resp):
    resp.headers["Cache-Control"] = "no-store, no-cache, max-age=0, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@app.route("/")
def index():
    return r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Harmony</title>

<style>
:root{
  --bg:#F5F1EA;
  --panel:#FFFFFF;
  --border:#E4DED4;
  --soft:#EFE9DE;
  --text:#2B2A27;
  --muted:#8B857B;
  --shadow:0 10px 26px rgba(0,0,0,0.08);
}

*{box-sizing:border-box}
html,body{height:100%;margin:0}
body{
  font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
  background:var(--bg);
  color:var(--text);
  overflow:hidden;
}

/* ================= HEADER ================= */

.topRow{
  position:fixed;
  top:20px;
  left:28px;
  right:28px;
  z-index:100;
  display:grid;
  grid-template-columns:1fr auto 1fr;
  align-items:center;
}

/* Left brand */
.brandTitle{
  font-size:22px;
  font-weight:950;
  letter-spacing:.01em;
}
.brandSubtitle{
  font-size:12px;
  color:var(--muted);
  max-width:42vw;
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap;
}

/* ===== Agent Picker (centered) ===== */

.agentPicker{
  position:relative;
  justify-self:center;
}

.agentBtn{
  height:56px;
  padding:0 22px;
  border-radius:999px;
  border:1px solid var(--border);
  background:rgba(255,255,255,0.88);
  backdrop-filter:blur(10px);
  box-shadow:var(--shadow);
  display:flex;
  align-items:center;
  gap:10px;
  cursor:pointer;
  font-size:13px;
  font-weight:900;
}

.agentBtn span{
  color:var(--muted);
  font-weight:700;
}

.agentMenu{
  position:absolute;
  top:64px;
  left:50%;
  transform:translateX(-50%);
  min-width:180px;
  background:var(--panel);
  border:1px solid var(--border);
  border-radius:16px;
  box-shadow:var(--shadow);
  display:none;
  overflow:hidden;
  z-index:200;
}

.agentMenu.open{display:block}

.agentItem{
  padding:12px 16px;
  font-size:13px;
  cursor:pointer;
}
.agentItem:hover{background:var(--soft)}

/* ===== GitHub ===== */

.rightNav{justify-self:end}

.githubBtn{
  width:54px;height:54px;
  border-radius:50%;
  border:1px solid var(--border);
  background:var(--panel);
  display:flex;
  align-items:center;
  justify-content:center;
  box-shadow:var(--shadow);
  cursor:pointer;
}
.githubBtn svg{width:26px;height:26px;fill:#2B2A27}

/* ================= STAGE ================= */

.stage{
  height:100vh;
  padding:120px 28px 140px;
  display:flex;
  align-items:center;
  justify-content:center;
}

.browserFrame{
  display:inline-flex;
  flex-direction:column;
  border-radius:18px;
  box-shadow:var(--shadow);
}

/* ===== Browser chrome ===== */

.browserTop{
  height:48px;
  border:1px solid var(--border);
  border-bottom:none;
  border-radius:18px 18px 0 0;
  background:#FBF8F2;
  display:flex;
  align-items:center;
  gap:12px;
  padding:0 14px;
}

.win{width:10px;height:10px;border-radius:50%}
.win.red{background:#ff5f57}
.win.yellow{background:#febc2e}
.win.green{background:#28c840}

.address{
  flex:1;
  height:34px;
  border:1px solid var(--border);
  border-radius:999px;
  display:flex;
  align-items:center;
  padding:0 14px;
  font-size:12px;
  font-weight:900;
  background:rgba(255,255,255,0.85);
  overflow:hidden;
  white-space:nowrap;
  text-overflow:ellipsis;
}

/* ===== Viewport ===== */

.viewport{
  position:relative;
  border:1px solid var(--border);
  border-top:none;
  border-radius:0 0 18px 18px;
  background:#fff;
  overflow:hidden;
}

.screenImg{
  display:block;
  max-width:820px;
  max-height:520px;
  width:auto;
  height:auto;
}

/* ===== Floating status ===== */

.statusCap{
  position:absolute;
  top:12px;
  right:12px;
  padding:8px 14px;
  border-radius:999px;
  border:1px solid var(--border);
  background:rgba(255,255,255,0.88);
  backdrop-filter:blur(10px);
  font-size:12px;
  font-weight:900;
  box-shadow:var(--shadow);
  pointer-events:none;
}

/* ===== Reasoning bubble ===== */

.thought{
  position:absolute;
  max-width:280px;
  padding:10px 12px;
  border-radius:14px;
  border:1px solid var(--border);
  background:rgba(255,255,255,0.9);
  backdrop-filter:blur(10px);
  font-size:12.5px;
  line-height:1.35;
  transform:translate(var(--tx,0),var(--ty,0));
  transition:transform 220ms cubic-bezier(.2,.9,.2,1),opacity 160ms ease;
}
.thought.hidden{opacity:0}

/* ================= PROMPT ================= */

.promptWrap{
  position:fixed;
  left:50%;
  bottom:48px; /* higher */
  transform:translateX(-50%);
}

.promptBar{
  height:64px;
  display:flex;
  align-items:center;
  gap:14px;
  padding:0 22px;
  border-radius:999px;
  border:1px solid var(--border);
  background:rgba(255,255,255,0.96);
  box-shadow:var(--shadow);
}

.promptInput{
  width:380px;
  border:0;
  outline:none;
  font-size:14px;
  background:transparent;
}

.playBtn{
  border:0;
  background:var(--soft);
  border-radius:999px;
  padding:10px 18px;
  cursor:pointer;
  font-size:16px;
  font-weight:900;
}
.playBtn:hover{background:#e8e2d7}
</style>
</head>

<body>

<div class="topRow">
  <div>
    <div class="brandTitle">Harmony</div>
    <div class="brandSubtitle" id="taskLine">No active task</div>
  </div>

  <div class="agentPicker">
    <div class="agentBtn" id="agentBtn">
      Agent <span id="agentValue">—</span>
    </div>
    <div class="agentMenu" id="agentMenu"></div>
  </div>

  <div class="rightNav">
    <a class="githubBtn" href="https://github.com/danielreiman/Harmony" target="_blank" rel="noreferrer">
      <svg viewBox="0 0 24 24">
        <path d="M12 .5C5.73.5.5 5.73.5 12c0 5.1 3.29 9.41 7.86 10.94.58.11.79-.25.79-.56v-2.03c-3.2.7-3.87-1.54-3.87-1.54-.53-1.35-1.3-1.71-1.3-1.71-1.06-.72.08-.7.08-.7 1.17.08 1.78 1.2 1.78 1.2 1.04 1.78 2.73 1.27 3.4.97.1-.75.4-1.27.73-1.56-2.55-.29-5.23-1.27-5.23-5.66 0-1.25.45-2.27 1.19-3.07-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.18 1.17a11.1 11.1 0 012.9-.39c.98 0 1.97.13 2.9.39 2.2-1.48 3.17-1.17 3.17-1.17.63 1.59.23 2.76.11 3.05.74.8 1.18 1.82 1.18 3.07 0 4.4-2.69 5.36-5.25 5.65.41.35.78 1.05.78 2.12v3.14c0 .31.21.68.8.56A11.51 11.51 0 0023.5 12C23.5 5.73 18.27.5 12 .5z"/>
      </svg>
    </a>
  </div>
</div>

<div class="stage">
  <div class="browserFrame">
    <div class="browserTop">
      <div class="win red"></div>
      <div class="win yellow"></div>
      <div class="win green"></div>
      <div class="address" id="actionTop">Waiting…</div>
    </div>

    <div class="viewport" id="viewport">
      <img id="screen" class="screenImg"/>
      <div class="statusCap" id="statusCap">Idle</div>
      <div class="thought hidden" id="thought"></div>
    </div>
  </div>
</div>

<div class="promptWrap">
  <div class="promptBar">
    <input class="promptInput" placeholder="Give a task…" />
    <button class="playBtn">▶</button>
  </div>
</div>

<script>
const $=id=>document.getElementById(id)
let currentAgent=null
let lastCoord={x:null,y:null}
let imgNat={w:820,h:520}
let lastImgUrl=null

function coord(c){return Array.isArray(c)&&c.length===2?{x:c[0],y:c[1]}:{x:null,y:null}}

function sentence(s){
  if(!s||!s.action)return "Waiting…"
  const a=s.action.toLowerCase()
  const {x,y}=coord(s.coordinate)
  if(a==="click")return x!=null?`Clicking at ${x}, ${y}`:"Clicking"
  if(a==="scroll")return `Scrolling ${s.value||""}`.trim()
  if(a==="type")return `Typing "${s.value||""}"`
  return s.action
}

function placeBubble(vp,el,x,y){
  const off=14
  const w=vp.clientWidth,h=vp.clientHeight
  const r=el.getBoundingClientRect()
  let tx=x+off,ty=y+off
  if(tx+r.width>w)tx=x-off-r.width
  if(ty+r.height>h)ty=y-off-r.height
  el.style.setProperty("--tx",Math.max(12,tx)+"px")
  el.style.setProperty("--ty",Math.max(12,ty)+"px")
}

async function refreshScreen(){
  const r=await fetch(`/screen/${currentAgent}?t=${Date.now()}`,{cache:"no-store"})
  if(!r.ok)return
  const b=await r.blob()
  const u=URL.createObjectURL(b)
  if(lastImgUrl)URL.revokeObjectURL(lastImgUrl)
  lastImgUrl=u
  $("screen").src=u
}

$("screen").onload=()=>{
  imgNat.w=$("screen").naturalWidth||imgNat.w
  imgNat.h=$("screen").naturalHeight||imgNat.h
}

async function updateState(){
  const r=await fetch(`/agent/${currentAgent}`,{cache:"no-store"})
  const d=await r.json()
  $("agentValue").textContent=d.id||"—"
  $("taskLine").textContent=d.task?`Task: ${d.task}`:"No active task"
  $("statusCap").textContent=d.status_text||d.status||"Idle"
  $("actionTop").textContent=sentence(d.step)

  const th=$("thought")
  const vp=$("viewport")
  const {x,y}=coord(d.step?.coordinate)
  if(x!=null)lastCoord={x,y}

  if(d.step?.reasoning){
    th.textContent=d.step.reasoning
    th.classList.remove("hidden")
    const px=(lastCoord.x/imgNat.w)*$("screen").clientWidth
    const py=(lastCoord.y/imgNat.h)*$("screen").clientHeight
    placeBubble(vp,th,px,py)
  }else th.classList.add("hidden")
}

async function fetchAgents(){
  const r=await fetch("/agents",{cache:"no-store"})
  const a=await r.json()
  const menu=$("agentMenu")
  menu.innerHTML=""
  a.forEach(x=>{
    const d=document.createElement("div")
    d.className="agentItem"
    d.textContent=x.id
    d.onclick=()=>{
      currentAgent=x.id
      $("agentValue").textContent=x.id
      menu.classList.remove("open")
    }
    menu.appendChild(d)
  })
  if(!currentAgent&&a.length){
    currentAgent=a[0].id
    $("agentValue").textContent=currentAgent
  }
}

$("agentBtn").onclick=()=>$("agentMenu").classList.toggle("open")
document.addEventListener("click",e=>{
  if(!e.target.closest(".agentPicker")) $("agentMenu").classList.remove("open")
})

setInterval(fetchAgents,1200)
setInterval(updateState,200)
setInterval(()=>currentAgent&&refreshScreen(),350)

fetchAgents().then(()=>{updateState();refreshScreen()})
</script>

</body>
</html>
"""


@app.route("/agents")
def agents():
    out=[]
    if os.path.exists(RUNTIME_DIR):
        for f in os.listdir(RUNTIME_DIR):
            if f.endswith(".soul"):
                try:
                    with open(os.path.join(RUNTIME_DIR,f)) as jf:
                        d=json.load(jf)
                    if d.get("id"): out.append({"id":d["id"]})
                except: pass
    return jsonify(sorted(out,key=lambda x:x["id"]))


@app.route("/agent/<agent_id>")
def agent_state(agent_id):
    p=os.path.join(RUNTIME_DIR,f"{agent_id}.soul")
    if not os.path.exists(p): return jsonify({})
    try:
        with open(p) as f: return jsonify(json.load(f))
    except: return jsonify({})


@app.route("/screen/<agent_id>")
def screen_file(agent_id):
    p=os.path.join(RUNTIME_DIR,f"screenshot_{agent_id}.png")
    if not os.path.exists(p): return "No screenshot",404
    resp=make_response(send_file(p,mimetype="image/png"))
    resp.headers["Cache-Control"]="no-store"
    return resp


if __name__=="__main__":
    os.makedirs(RUNTIME_DIR,exist_ok=True)
    app.run(port=1234,debug=False)
