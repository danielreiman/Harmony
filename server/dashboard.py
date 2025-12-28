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
<script src="https://unpkg.com/lucide@latest/dist/umd/lucide.js"></script>

<style>
:root{
  --bg:#F5F1EA;
  --panel:#FFFFFF;
  --border:#E4DED4;
  --soft:#EFE9DE;
  --text:#2B2A27;
  --muted:#8B857B;
  --accent:#8B6F47;
  --shadow:0 10px 26px rgba(0,0,0,0.08);
  --shadow-hover:0 20px 40px rgba(0,0,0,0.12);
  --transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

*{box-sizing:border-box}
html,body{height:100%;margin:0;padding:0}
body{
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif;
  background:var(--bg);
  color:var(--text);
  overflow:hidden;
  -webkit-font-smoothing:antialiased;
  -moz-osx-font-smoothing:grayscale;
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
  font-size:24px;
  font-weight:700;
  letter-spacing:-0.02em;
  margin-bottom:2px;
}
.brandSubtitle{
  font-size:13px;
  color:var(--muted);
  font-weight:500;
  max-width:42vw;
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap;
  line-height:1.4;
}

/* ===== Agent Picker (centered) ===== */

.agentPicker{
  position:relative;
  justify-self:center;
}

.agentBtn{
  height:56px;
  padding:0 24px;
  border-radius:28px;
  border:1px solid var(--border);
  background:rgba(255,255,255,0.95);
  backdrop-filter:blur(12px);
  box-shadow:var(--shadow);
  display:flex;
  align-items:center;
  gap:12px;
  cursor:pointer;
  font-size:14px;
  font-weight:600;
  transition:var(--transition);
  position:relative;
}

.agentBtn:hover{
  transform:translateY(-1px);
  box-shadow:var(--shadow-hover);
  border-color:var(--accent);
}

.agentBtn span{
  color:var(--muted);
  font-weight:600;
  font-family:ui-monospace, "SF Mono", Monaco, monospace;
}

.agentBtn::before{
  content:'';
  width:8px;
  height:8px;
  border-radius:50%;
  background:var(--accent);
  opacity:0.7;
  flex-shrink:0;
}

.agentMenu{
  position:absolute;
  top:64px;
  left:50%;
  transform:translateX(-50%);
  min-width:220px;
  background:var(--panel);
  border:1px solid var(--border);
  border-radius:16px;
  box-shadow:var(--shadow-hover);
  display:none;
  overflow:hidden;
  z-index:200;
  opacity:0;
  transform:translateX(-50%) translateY(-8px);
  transition:var(--transition);
}

.agentMenu.open{
  display:block;
  opacity:1;
  transform:translateX(-50%) translateY(0);
}

.agentItem{
  padding:14px 18px;
  font-size:14px;
  font-family:ui-monospace, "SF Mono", Monaco, monospace;
  cursor:pointer;
  transition:var(--transition);
  border-bottom:1px solid var(--soft);
  display:flex;
  align-items:center;
  gap:12px;
}

.agentItem:last-child{
  border-bottom:none;
}

.agentItem:hover{
  background:var(--soft);
  color:var(--accent);
}

.agentItem::before{
  content:'';
  width:6px;
  height:6px;
  border-radius:50%;
  background:var(--accent);
  opacity:0.6;
  flex-shrink:0;
}

/* ===== GitHub ===== */

.rightNav{justify-self:end}

.githubBtn{
  width:56px;
  height:56px;
  border-radius:50%;
  border:1px solid var(--border);
  background:var(--panel);
  display:flex;
  align-items:center;
  justify-content:center;
  box-shadow:var(--shadow);
  cursor:pointer;
  transition:var(--transition);
  text-decoration:none;
}

.githubBtn:hover{
  transform:translateY(-1px);
  box-shadow:var(--shadow-hover);
  border-color:var(--accent);
}

.githubBtn svg{
  width:24px;
  height:24px;
  fill:var(--text);
  transition:var(--transition);
}

.githubBtn:hover svg{
  fill:var(--accent);
}

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
  border-radius:20px;
  box-shadow:var(--shadow);
  transition:var(--transition);
  border:1px solid var(--border);
}

.browserFrame:hover{
  transform:translateY(-2px);
  box-shadow:var(--shadow-hover);
}

/* ===== Browser chrome ===== */

.browserTop{
  height:52px;
  border-bottom:1px solid var(--border);
  border-radius:20px 20px 0 0;
  background:linear-gradient(135deg, #fbf9f6 0%, #f8f5f1 100%);
  display:flex;
  align-items:center;
  gap:14px;
  padding:0 18px;
}

.win{
  width:14px;
  height:14px;
  border-radius:50%;
  transition:all 0.2s ease;
  cursor:pointer;
  position:relative;
  box-shadow:inset 0 1px 0 rgba(255,255,255,0.3), 0 1px 2px rgba(0,0,0,0.1);
}

.win::before{
  content:'';
  position:absolute;
  top:2px;
  left:3px;
  width:3px;
  height:3px;
  border-radius:50%;
  background:rgba(255,255,255,0.6);
}

.win.red{
  background:linear-gradient(135deg, #ff6b5a 0%, #ff4533 100%);
  border:1px solid rgba(255,95,86,0.5);
}
.win.yellow{
  background:linear-gradient(135deg, #ffcd3c 0%, #ffb02e 100%);
  border:1px solid rgba(255,189,46,0.5);
}
.win.green{
  background:linear-gradient(135deg, #34d058 0%, #28a745 100%);
  border:1px solid rgba(39,202,63,0.5);
}

.win:hover{
  transform:scale(1.15);
  filter:brightness(1.1);
  box-shadow:inset 0 1px 0 rgba(255,255,255,0.4), 0 2px 4px rgba(0,0,0,0.15);
}

.address{
  flex:1;
  height:32px;
  border:1px solid var(--border);
  border-radius:16px;
  display:flex;
  align-items:center;
  padding:0 16px;
  font-size:13px;
  font-weight:600;
  background:rgba(255,255,255,0.9);
  backdrop-filter:blur(8px);
  overflow:hidden;
  white-space:nowrap;
  text-overflow:ellipsis;
  color:var(--muted);
  transition:var(--transition);
}

.address:hover{
  border-color:var(--accent);
  background:rgba(255,255,255,1);
}

/* ===== Viewport ===== */

.viewport{
  position:relative;
  border-radius:0 0 20px 20px;
  background:#fff;
  overflow:hidden;
  min-height:300px;
  display:flex;
  align-items:center;
  justify-content:center;
}

.screenImg{
  display:block;
  max-width:820px;
  max-height:520px;
  width:auto;
  height:auto;
  border-radius:0 0 20px 20px;
  transition:var(--transition);
}

.viewport.empty{
  background:linear-gradient(135deg, var(--soft) 0%, var(--bg) 100%);
}

.viewport.empty::before{
  content:'Monitor';
  font-size:16px;
  font-weight:600;
  opacity:0.4;
  position:absolute;
  color:var(--muted);
}

.viewport.empty::after{
  content:'Select an agent to view screen';
  position:absolute;
  bottom:20px;
  font-size:14px;
  color:var(--muted);
  font-weight:500;
}

/* ===== Floating status ===== */

.statusCap{
  position:absolute;
  top:16px;
  right:16px;
  padding:10px 16px;
  border-radius:20px;
  border:1px solid var(--border);
  background:rgba(255,255,255,0.95);
  backdrop-filter:blur(12px);
  font-size:12px;
  font-weight:700;
  box-shadow:var(--shadow);
  pointer-events:none;
  color:var(--accent);
  transition:var(--transition);
}

/* ===== Reasoning bubble ===== */

.thought{
  position:absolute;
  max-width:300px;
  padding:12px 16px;
  border-radius:16px;
  border:1px solid var(--border);
  background:rgba(255,255,255,0.95);
  backdrop-filter:blur(12px);
  font-size:13px;
  line-height:1.4;
  transform:translate(var(--tx,0),var(--ty,0));
  transition:all 250ms cubic-bezier(.2,.9,.2,1);
  box-shadow:var(--shadow);
  color:var(--text);
}

.thought.hidden{
  opacity:0;
  transform:translate(var(--tx,0),var(--ty,-8px)) scale(0.95);
}

.thought::before{
  content:'';
  position:absolute;
  top:-5px;
  left:20px;
  width:10px;
  height:10px;
  background:rgba(255,255,255,0.95);
  border:1px solid var(--border);
  border-right:none;
  border-bottom:none;
  transform:rotate(45deg);
}

/* ================= REASONING PANEL ================= */

.reasoningPanel{
  position:absolute;
  top:390px;
  left:0;
  right:0;
  background:rgba(255, 255, 255, 0.98);
  backdrop-filter:blur(16px);
  border:1px solid var(--border);
  border-radius:16px;
  box-shadow:0 8px 32px rgba(0, 0, 0, 0.12);
  padding:16px 20px 32px;
  transform:translateY(0);
  transition:all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  z-index:30;
  max-height:130px;
  overflow:hidden;
  width:380px;
}

.reasoningPanel.visible{
  transform:translateY(0);
}


.reasoningPanelHeader{
  display:flex;
  align-items:center;
  justify-content:space-between;
  margin-bottom:12px;
  padding-bottom:8px;
  border-bottom:1px solid var(--soft);
}

.reasoningPanelTitle{
  font-size:12px;
  font-weight:600;
  color:var(--accent);
  text-transform:uppercase;
  letter-spacing:0.5px;
}

.reasoningPanelIcon{
  width:16px;
  height:16px;
  color:var(--accent);
}

.showAllBtn{
  font-size:11px;
  color:var(--muted);
  background:none;
  border:none;
  cursor:pointer;
  padding:4px 8px;
  border-radius:8px;
  transition:var(--transition);
  text-transform:uppercase;
  letter-spacing:0.3px;
  font-weight:600;
}

.showAllBtn:hover{
  background:var(--soft);
  color:var(--accent);
}

.reasoningPanelText{
  font-size:13px;
  line-height:1.4;
  color:var(--text);
  margin:0;
  display:-webkit-box;
  -webkit-line-clamp:2;
  -webkit-box-orient:vertical;
  overflow:hidden;
}

.reasoningPanelAction{
  display:flex;
  align-items:center;
  gap:6px;
  margin-top:8px;
  font-size:11px;
  color:var(--muted);
  opacity:0.8;
}

.reasoningActionIcon{
  width:14px;
  height:14px;
  color:var(--muted);
}

.cursorPosition{
  position:absolute;
  width:4px;
  height:4px;
  background:var(--accent);
  border-radius:50%;
  transform:translate(-50%, -50%);
  z-index:99;
  box-shadow:0 0 0 2px rgba(255, 255, 255, 0.8), 0 0 8px rgba(139, 111, 71, 0.6);
  animation:pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.8), 0 0 8px rgba(139, 111, 71, 0.6); }
  50% { box-shadow: 0 0 0 6px rgba(139, 111, 71, 0.3), 0 0 16px rgba(139, 111, 71, 0.4); }
}

/* ================= TASK STATUS PANEL ================= */

.taskStatusPanel{
  position:absolute;
  top:0px;
  right:-300px;
  transform:translateY(0);
  background:rgba(255,255,255,0.98);
  backdrop-filter:blur(16px);
  border:1px solid var(--border);
  border-radius:16px;
  box-shadow:var(--shadow);
  padding:16px 20px;
  z-index:20;
  min-width:220px;
  max-width:280px;
  transition:var(--transition);
}

.taskStatusPanel:hover{
  transform:translateY(-2px) translateX(-4px);
  box-shadow:var(--shadow-hover);
  border-color:var(--accent);
}

.taskStatusContent{
  text-align:left;
}

.taskStatusLabel{
  font-size:11px;
  font-weight:700;
  color:var(--muted);
  text-transform:uppercase;
  letter-spacing:0.5px;
  margin-bottom:6px;
}

.taskStatusText{
  font-size:13px;
  font-weight:600;
  color:var(--text);
  line-height:1.4;
}

/* ================= FLOATING ACTIONS ================= */

.floatingActions{
  position:fixed;
  bottom:32px;
  right:32px;
  display:flex;
  flex-direction:row;
  gap:16px;
  z-index:50;
}

.actionButton{
  height:52px;
  padding:0 20px;
  border-radius:26px;
  border:1px solid var(--border);
  background:rgba(255,255,255,0.98);
  backdrop-filter:blur(16px);
  box-shadow:var(--shadow);
  cursor:pointer;
  transition:var(--transition);
  display:flex;
  align-items:center;
  justify-content:center;
  color:var(--accent);
  font-size:14px;
  font-weight:600;
  text-decoration:none;
  white-space:nowrap;
  box-sizing:border-box;
}

.actionButton:hover{
  transform:translateY(-3px) scale(1.05);
  box-shadow:0 20px 50px rgba(0,0,0,0.15);
  border-color:var(--accent);
  color:var(--accent);
}

.actionButton.primary{
  background:var(--accent);
  color:white;
  border-color:var(--accent);
}

.actionButton.primary:hover{
  background:#7a5f3f;
  color:white;
}

/* ================= SINGLE VIEW EMPTY STATE ================= */

.singleEmptyState{
  position:absolute;
  top:0;
  left:0;
  right:0;
  bottom:0;
  display:flex;
  align-items:center;
  justify-content:center;
  background:linear-gradient(135deg, var(--soft) 0%, var(--bg) 100%);
  border-radius:0 0 20px 20px;
}

.singleEmptyContent{
  text-align:center;
  padding:40px 20px;
}

.singleEmptyIcon{
  width:48px;
  height:48px;
  color:var(--muted);
  opacity:0.6;
  margin-bottom:20px;
}

.singleEmptyTitle{
  font-size:20px;
  font-weight:700;
  color:var(--text);
  margin-bottom:8px;
}

.singleEmptyText{
  font-size:14px;
  color:var(--muted);
  margin-bottom:24px;
}

.singleEmptyButton{
  height:40px;
  padding:0 20px;
  border-radius:20px;
  border:1px solid var(--accent);
  background:var(--accent);
  color:white;
  cursor:pointer;
  transition:var(--transition);
  font-size:14px;
  font-weight:600;
  display:inline-flex;
  align-items:center;
  justify-content:center;
}

.singleEmptyButton:hover{
  background:#7a5f3f;
  border-color:#7a5f3f;
  transform:translateY(-1px);
  box-shadow:0 4px 12px rgba(139,111,71,0.3);
}

/* ================= EMPTY STATE VIEW ================= */

.emptyState{
  display:flex;
  align-items:center;
  justify-content:center;
  min-height:600px;
  padding:80px 40px;
  flex:1;
}

.emptyStateContent{
  text-align:center;
  max-width:600px;
  padding:60px 40px;
  background:rgba(255,255,255,0.7);
  border:1px solid var(--border);
  border-radius:24px;
  backdrop-filter:blur(12px);
  box-shadow:0 20px 60px rgba(0,0,0,0.08);
}

.emptyStateIcon{
  position:relative;
  display:inline-flex;
  align-items:center;
  justify-content:center;
  margin-bottom:32px;
}

.emptyStateIconLarge{
  width:64px;
  height:64px;
  color:var(--accent);
  opacity:0.8;
}

.emptyStateIconPlus{
  width:24px;
  height:24px;
  color:var(--accent);
  position:absolute;
  top:-8px;
  right:-8px;
  background:var(--panel);
  border-radius:50%;
  padding:4px;
  box-shadow:0 2px 8px rgba(0,0,0,0.1);
}

.emptyStateTitle{
  font-size:32px;
  font-weight:700;
  color:var(--text);
  margin-bottom:12px;
  letter-spacing:-0.02em;
}

.emptyStateSubtitle{
  font-size:18px;
  color:var(--muted);
  margin-bottom:48px;
  line-height:1.5;
  font-weight:500;
}

.emptyStateInstructions{
  display:flex;
  flex-direction:column;
  gap:24px;
  margin-bottom:40px;
  text-align:left;
}

.emptyStateStep{
  display:flex;
  align-items:flex-start;
  gap:20px;
  padding:20px 24px;
  background:rgba(255,255,255,0.6);
  border:1px solid var(--soft);
  border-radius:16px;
  transition:var(--transition);
}

.emptyStateStep:hover{
  transform:translateY(-2px);
  box-shadow:0 8px 20px rgba(0,0,0,0.1);
  border-color:var(--accent);
}

.emptyStateStepNumber{
  width:32px;
  height:32px;
  background:var(--accent);
  color:white;
  border-radius:50%;
  display:flex;
  align-items:center;
  justify-content:center;
  font-weight:700;
  font-size:14px;
  flex-shrink:0;
  margin-top:2px;
}

.emptyStateStepContent{
  flex:1;
}

.emptyStateStepTitle{
  font-size:16px;
  font-weight:700;
  color:var(--text);
  margin-bottom:4px;
}

.emptyStateStepText{
  font-size:14px;
  color:var(--muted);
  line-height:1.5;
}

.emptyStateStepText code{
  background:rgba(139,111,71,0.1);
  color:var(--accent);
  padding:2px 6px;
  border-radius:4px;
  font-family:ui-monospace, "SF Mono", Monaco, monospace;
  font-size:13px;
  font-weight:600;
}

.emptyStateFooter{
  margin-top:32px;
  padding-top:24px;
  border-top:1px solid var(--soft);
}

.emptyStateNote{
  display:flex;
  align-items:center;
  justify-content:center;
  gap:12px;
  padding:16px 20px;
  background:rgba(139,111,71,0.05);
  border:1px solid rgba(139,111,71,0.1);
  border-radius:12px;
  color:var(--muted);
  font-size:14px;
  line-height:1.5;
  font-style:italic;
}

.emptyStateNoteIcon{
  width:18px;
  height:18px;
  color:var(--accent);
  flex-shrink:0;
}

/* ================= SUPERVISOR VIEW ================= */

.viewModeToggle{
  position:fixed;
  bottom:32px;
  left:32px;
  height:52px;
  display:flex;
  align-items:center;
  gap:4px;
  background:rgba(255,255,255,0.98);
  backdrop-filter:blur(16px);
  border:1px solid var(--border);
  border-radius:24px;
  padding:4px;
  box-shadow:var(--shadow);
  z-index:60;
  transition:var(--transition);
  box-sizing:border-box;
}

.viewModeToggle:hover{
  transform:translateY(-2px);
  border-color:var(--accent);
  box-shadow:0 8px 30px rgba(0,0,0,0.12);
}

.viewToggleBtn{
  height:44px;
  padding:0 16px;
  border:none;
  background:transparent;
  color:var(--muted);
  font-size:11px;
  font-weight:700;
  cursor:pointer;
  border-radius:20px;
  transition:all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  text-transform:uppercase;
  letter-spacing:0.8px;
  position:relative;
  overflow:hidden;
  display:flex;
  align-items:center;
}

.viewToggleBtn::before{
  content:'';
  position:absolute;
  top:0;
  left:0;
  right:0;
  bottom:0;
  background:var(--accent);
  opacity:0;
  transition:var(--transition);
  border-radius:20px;
}

.viewToggleBtn.active{
  color:white;
  transform:scale(1.05);
}

.viewToggleBtn.active::before{
  opacity:1;
}

.viewToggleBtn span{
  position:relative;
  z-index:1;
}

.viewToggleBtn:hover:not(.active){
  background:var(--soft);
  color:var(--text);
  transform:scale(1.02);
}

.singleView{
  display:none;
}

.singleView.active{
  display:block;
}

.supervisorView{
  display:none;
  padding:60px 40px 160px;
  height:100vh;
  background:linear-gradient(135deg, var(--bg) 0%, #f0ebe0 100%);
  display:flex;
  flex-direction:column;
  justify-content:flex-start;
  overflow-y:auto;
  overflow-x:hidden;
}

.supervisorView.active{
  display:flex;
}

.supervisorHeader{
  text-align:center;
  margin-bottom:20px;
  max-width:600px;
  margin-left:auto;
  margin-right:auto;
  flex-shrink:0;
}

.supervisorTitle{
  font-size:36px;
  font-weight:700;
  letter-spacing:-0.03em;
  margin-bottom:12px;
  background:linear-gradient(135deg, var(--text) 0%, var(--accent) 100%);
  -webkit-background-clip:text;
  -webkit-text-fill-color:transparent;
  background-clip:text;
}

.supervisorSubtitle{
  font-size:18px;
  color:var(--muted);
  font-weight:500;
  line-height:1.6;
  max-width:480px;
  margin:0 auto;
}

.supervisorStats{
  display:flex;
  justify-content:center;
  gap:32px;
  margin:32px 0 24px;
  flex-wrap:wrap;
}


.supervisorStat{
  text-align:center;
  padding:16px 24px;
  background:rgba(255,255,255,0.7);
  border-radius:16px;
  border:1px solid var(--border);
  backdrop-filter:blur(8px);
  min-width:120px;
}

.supervisorStatNumber{
  font-size:28px;
  font-weight:700;
  color:var(--accent);
  margin-bottom:4px;
  font-family:ui-monospace, "SF Mono", Monaco, monospace;
}

.supervisorStatLabel{
  font-size:12px;
  color:var(--muted);
  font-weight:600;
  text-transform:uppercase;
  letter-spacing:0.5px;
}

/* ================= CONNECTION OVERLAY ================= */

.connectionOverlay{
  position:fixed;
  top:0;
  left:0;
  right:0;
  bottom:0;
  background:linear-gradient(135deg, var(--bg) 0%, #f0ebe0 50%, var(--soft) 100%);
  z-index:2000;
  display:none;
  align-items:center;
  justify-content:center;
  padding:20px;
  overflow-y:auto;
}

.connectionOverlay.active{
  display:flex;
}

.connectionOverlayContent{
  background:rgba(255,255,255,0.95);
  backdrop-filter:blur(20px);
  border:1px solid var(--border);
  border-radius:20px;
  box-shadow:0 24px 48px rgba(0,0,0,0.12);
  padding:48px;
  max-width:750px;
  width:100%;
  text-align:center;
  animation:overlayFadeIn 0.8s cubic-bezier(0.4, 0, 0.2, 1);
  max-height:90vh;
  overflow-y:auto;
  position:relative;
}

@media (max-width: 768px) {
  .connectionOverlayContent{
    padding:30px 20px;
    margin:10px;
  }
}

@keyframes overlayFadeIn {
  from { opacity: 0; transform: translateY(20px) scale(0.95); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.connectionOverlayHeader{
  margin-bottom:32px;
}

.connectionOverlayIcon{
  margin-bottom:16px;
}

.connectionOverlayIconMain{
  width:56px;
  height:56px;
  color:var(--accent);
  opacity:1;
}

.connectionOverlayTitle{
  font-size:32px;
  font-weight:700;
  color:var(--text);
  margin-bottom:8px;
  letter-spacing:-0.02em;
}

@media (max-width: 768px) {
  .connectionOverlayTitle{
    font-size:28px;
  }
}

.connectionOverlaySubtitle{
  font-size:18px;
  color:var(--muted);
  font-weight:500;
}

@media (max-width: 768px) {
  .connectionOverlaySubtitle{
    font-size:16px;
  }
}

.connectionOverlayBody{
  margin-bottom:0;
}

.connectionInstructions{
  display:flex;
  flex-direction:column;
  gap:20px;
  margin-bottom:0;
}

.connectionStep{
  display:flex;
  align-items:flex-start;
  gap:20px;
  padding:24px;
  background:rgba(255,255,255,0.9);
  border:1px solid rgba(228,222,212,0.6);
  border-radius:16px;
  transition:var(--transition);
  text-align:left;
  position:relative;
  overflow:hidden;
}


.connectionStepNumber{
  width:36px;
  height:36px;
  background:var(--accent);
  color:white;
  border-radius:50%;
  display:flex;
  align-items:center;
  justify-content:center;
  font-weight:700;
  font-size:16px;
  flex-shrink:0;
}

.connectionStepContent{
  flex:1;
}

.connectionStepTitle{
  font-size:16px;
  font-weight:700;
  color:var(--text);
  margin-bottom:4px;
}

.connectionStepCommand{
  font-family:ui-monospace, "SF Mono", Monaco, monospace;
  font-size:14px;
  font-weight:600;
  color:var(--accent);
  background:rgba(139,111,71,0.1);
  padding:6px 10px;
  border-radius:6px;
  margin-bottom:6px;
  display:inline-block;
  border:1px solid rgba(139,111,71,0.2);
}

.connectionStepDescription{
  font-size:14px;
  color:var(--muted);
  line-height:1.5;
}

.connectionTip{
  display:flex;
  align-items:center;
  gap:12px;
  padding:16px 20px;
  background:rgba(139,111,71,0.05);
  border:1px solid rgba(139,111,71,0.1);
  border-radius:10px;
  text-align:left;
  margin-top:16px;
}

.connectionTipIcon{
  width:20px;
  height:20px;
  color:var(--accent);
  flex-shrink:0;
}

.connectionTipContent{
  font-size:14px;
  color:var(--muted);
  line-height:1.5;
}

.connectionOverlayFooter{
  padding-top:32px;
  border-top:1px solid var(--soft);
}

.connectionStatus{
  display:flex;
  align-items:center;
  justify-content:center;
  gap:12px;
  font-size:14px;
  color:var(--muted);
  font-weight:500;
}

.connectionStatusDot{
  width:8px;
  height:8px;
  background:var(--accent);
  border-radius:50%;
  animation:pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.agentsGrid{
  display:flex;
  gap:40px;
  padding:40px 40px 160px;
  overflow-x:auto;
  overflow-y:visible;
  flex:none;
  align-items:flex-start;
  scroll-behavior:smooth;
  height:auto;
  min-height:600px;
}

.agentsGrid::-webkit-scrollbar{
  height:8px;
}

.agentsGrid::-webkit-scrollbar-track{
  background:rgba(255,255,255,0.3);
  border-radius:4px;
}

.agentsGrid::-webkit-scrollbar-thumb{
  background:rgba(139,111,71,0.4);
  border-radius:4px;
}

.agentsGrid::-webkit-scrollbar-thumb:hover{
  background:rgba(139,111,71,0.6);
}


.agentTile{
  background:rgba(255,255,255,0.9);
  border:1px solid var(--border);
  border-radius:20px;
  overflow:visible;
  transition:all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  cursor:pointer;
  backdrop-filter:blur(12px);
  position:relative;
  flex-shrink:0;
  width:380px;
  height:380px;
  margin-bottom:140px;
}

.agentTile::before{
  content:'';
  position:absolute;
  top:0;
  left:0;
  right:0;
  bottom:0;
  background:linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(139,111,71,0.05) 100%);
  opacity:0;
  transition:var(--transition);
  pointer-events:none;
}

.agentTile:hover{
  transform:translateY(-4px) scale(1.02);
  box-shadow:0 15px 50px rgba(0,0,0,0.12);
  border-color:var(--accent);
}

.agentTile:hover::before{
  opacity:1;
}

.agentTileContent{
  padding:20px;
  display:flex;
  flex-direction:column;
  gap:16px;
  height:100%;
  box-sizing:border-box;
}

.agentTileHeader{
  display:flex;
  justify-content:space-between;
  align-items:flex-start;
  gap:12px;
  flex-shrink:0;
}

.agentMiniWindow{
  width:100%;
  height:260px;
  border-radius:12px;
  overflow:hidden;
  background:var(--panel);
  border:1px solid var(--soft);
  box-shadow:0 4px 12px rgba(0,0,0,0.08);
  transition:var(--transition);
  flex-shrink:0;
}

.agentMiniWindow:hover{
  transform:translateY(-2px);
  box-shadow:0 8px 20px rgba(0,0,0,0.12);
}

.agentMiniTop{
  height:32px;
  background:linear-gradient(135deg, #f8f5f1 0%, #f0ebe0 100%);
  border-bottom:1px solid var(--soft);
  display:flex;
  align-items:center;
  gap:8px;
  padding:0 12px;
}

.agentMiniWin{
  width:10px;
  height:10px;
  border-radius:50%;
  transition:all 0.2s ease;
  cursor:pointer;
  position:relative;
}

.agentMiniWin::before{
  content:'';
  position:absolute;
  top:1px;
  left:2px;
  width:2px;
  height:2px;
  border-radius:50%;
  background:rgba(255,255,255,0.7);
}

.agentMiniWin.red{
  background:linear-gradient(135deg, #ff6b5a 0%, #ff4533 100%);
  box-shadow:0 0 0 1px rgba(255,95,86,0.3);
}
.agentMiniWin.yellow{
  background:linear-gradient(135deg, #ffcd3c 0%, #ffb02e 100%);
  box-shadow:0 0 0 1px rgba(255,189,46,0.3);
}
.agentMiniWin.green{
  background:linear-gradient(135deg, #34d058 0%, #28a745 100%);
  box-shadow:0 0 0 1px rgba(39,202,63,0.3);
}

.agentMiniAddress{
  flex:1;
  height:20px;
  margin-left:12px;
  background:rgba(255,255,255,0.9);
  border-radius:10px;
  display:flex;
  align-items:center;
  padding:0 8px;
  font-size:9px;
  color:var(--muted);
  font-weight:500;
  font-family:ui-monospace, "SF Mono", Monaco, monospace;
}

.agentMiniViewport{
  flex:1;
  position:relative;
  overflow:hidden;
  display:flex;
  align-items:center;
  justify-content:center;
  height:227px;
  background:var(--soft);
}

.agentTileScreenImg{
  width:100%;
  height:100%;
  object-fit:cover;
  border-radius:0 0 12px 12px;
}

.agentTileInfo{
  display:flex;
  justify-content:space-between;
  align-items:center;
  margin-bottom:8px;
}

.agentTileId{
  font-family:ui-monospace, "SF Mono", Monaco, monospace;
  font-size:16px;
  font-weight:700;
  color:var(--text);
}

.agentTileStatusBadge{
  padding:4px 12px;
  border-radius:12px;
  font-size:11px;
  font-weight:700;
  text-transform:uppercase;
  letter-spacing:0.5px;
}

.agentTileStatusBadge.working{
  background:rgba(34,197,94,0.1);
  color:#059669;
}

.agentTileStatusBadge.idle{
  background:rgba(139,133,123,0.1);
  color:var(--muted);
}

.agentTileTask{
  font-size:14px;
  color:var(--muted);
  font-style:italic;
}


.agentTileScreenPlaceholder{
  display:flex;
  flex-direction:column;
  align-items:center;
  justify-content:center;
  height:100%;
  color:var(--muted);
  font-size:16px;
  font-weight:500;
  opacity:0.4;
}

.agentTileScreenPlaceholder::after{
  content:'Connecting...';
  font-size:13px;
  font-weight:500;
  margin-top:8px;
  opacity:0.6;
}

.agentTileStatus{
  display:flex;
  flex-direction:column;
  gap:8px;
  align-items:flex-end;
}

.agentTileReasoning{
  font-size:11px;
  color:var(--muted);
  font-style:italic;
  max-width:200px;
  text-align:right;
  line-height:1.3;
  margin-top:4px;
}

.agentTileAction{
  font-size:12px;
  color:var(--accent);
  font-weight:600;
  max-width:200px;
  text-align:right;
  line-height:1.3;
}

.agentFloatingStatus{
  position:absolute;
  top:-32px;
  right:16px;
  background:rgba(139,111,71,0.95);
  color:white;
  padding:6px 16px;
  border-radius:20px;
  font-size:12px;
  font-weight:700;
  text-transform:uppercase;
  letter-spacing:0.5px;
  box-shadow:0 4px 12px rgba(0,0,0,0.15);
  backdrop-filter:blur(8px);
  z-index:20;
  white-space:nowrap;
}

.agentFloatingStatus.working{
  background:rgba(34,197,94,0.95);
}

.agentFloatingStatus.idle{
  background:rgba(139,133,123,0.95);
}


/* ================= CUSTOM ALERT MODAL ================= */

.customAlert{
  position:fixed;
  top:0;
  left:0;
  right:0;
  bottom:0;
  background:rgba(0,0,0,0.4);
  backdrop-filter:blur(8px);
  z-index:1500;
  display:none;
  align-items:center;
  justify-content:center;
  opacity:0;
  transition:all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.customAlert.open{
  display:flex;
  opacity:1;
}

.customAlertContent{
  background:var(--panel);
  border:1px solid var(--border);
  border-radius:20px;
  box-shadow:0 20px 60px rgba(0,0,0,0.15);
  padding:0;
  max-width:500px;
  width:90%;
  max-height:70vh;
  overflow:hidden;
  transform:translateY(20px) scale(0.95);
  transition:var(--transition);
}

.customAlert.open .customAlertContent{
  transform:translateY(0) scale(1);
}

.customAlertHeader{
  display:flex;
  align-items:center;
  justify-content:center;
  padding:24px 28px 20px;
  border-bottom:1px solid var(--soft);
  background:linear-gradient(135deg, var(--panel) 0%, var(--soft) 100%);
  border-radius:20px 20px 0 0;
}

.customAlertTitleSection{
  display:flex;
  align-items:center;
  gap:12px;
}

.customAlertIcon{
  width:20px;
  height:20px;
  color:var(--accent);
}

.customAlertTitle{
  font-size:18px;
  font-weight:700;
  color:var(--text);
  margin:0;
}


.customAlertBody{
  padding:20px 28px;
  color:var(--text);
  line-height:1.6;
  max-height:40vh;
  overflow-y:auto;
  font-size:14px;
}

.customAlertBody::-webkit-scrollbar{
  width:6px;
}

.customAlertBody::-webkit-scrollbar-track{
  background:var(--soft);
  border-radius:3px;
}

.customAlertBody::-webkit-scrollbar-thumb{
  background:var(--border);
  border-radius:3px;
}

.customAlertBody::-webkit-scrollbar-thumb:hover{
  background:var(--accent);
}

.customAlertFooter{
  padding:20px 28px 24px;
  border-top:1px solid var(--soft);
  background:var(--bg);
  border-radius:0 0 20px 20px;
  display:flex;
  justify-content:flex-end;
}

.customAlertOk{
  height:44px;
  padding:0 24px;
  border-radius:22px;
  border:1px solid var(--accent);
  background:var(--accent);
  color:white;
  cursor:pointer;
  transition:var(--transition);
  font-size:14px;
  font-weight:600;
  min-width:80px;
}

.customAlertOk:hover{
  background:#7a5f3f;
  border-color:#7a5f3f;
  transform:translateY(-1px);
  box-shadow:0 4px 12px rgba(139,111,71,0.3);
}

/* ================= REASONING MODAL ================= */

.reasoningModal{
  position:fixed;
  top:0;
  left:0;
  right:0;
  bottom:0;
  background:rgba(0,0,0,0.4);
  backdrop-filter:blur(8px);
  z-index:1000;
  display:none;
  align-items:center;
  justify-content:center;
  opacity:0;
  transition:all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.reasoningModal.open{
  display:flex;
  opacity:1;
}

.reasoningModalContent{
  background:var(--panel);
  border:1px solid var(--border);
  border-radius:20px;
  box-shadow:0 20px 60px rgba(0,0,0,0.15);
  padding:32px;
  max-width:600px;
  width:90%;
  max-height:80vh;
  overflow:auto;
  transform:translateY(20px) scale(0.95);
  transition:var(--transition);
}

.reasoningModal.open .reasoningModalContent{
  transform:translateY(0) scale(1);
}

.reasoningModalHeader{
  display:flex;
  align-items:center;
  justify-content:space-between;
  margin-bottom:20px;
  padding-bottom:16px;
  border-bottom:1px solid var(--soft);
}

.reasoningModalTitleSection{
  display:flex;
  align-items:center;
  gap:12px;
}

.reasoningModalIcon{
  width:24px;
  height:24px;
  color:var(--accent);
}

.reasoningModalTitle{
  font-size:24px;
  font-weight:700;
  color:var(--text);
  margin:0;
}

.reasoningModalClose{
  width:32px;
  height:32px;
  border-radius:50%;
  border:none;
  background:var(--soft);
  color:var(--muted);
  cursor:pointer;
  transition:var(--transition);
  display:flex;
  align-items:center;
  justify-content:center;
  font-size:16px;
}

.reasoningModalClose:hover{
  background:var(--accent);
  color:white;
  transform:scale(1.1);
}

.reasoningModalBody{
  color:var(--text);
  line-height:1.6;
}

.reasoningEntry{
  padding:16px 20px;
  background:var(--soft);
  border-radius:12px;
  margin:12px 0;
  border-left:4px solid var(--accent);
}

.reasoningEntry .timestamp{
  font-size:12px;
  color:var(--muted);
  font-weight:600;
  margin-bottom:8px;
}

.reasoningEntry .content{
  font-size:14px;
  line-height:1.5;
}

/* ================= RESULTS MODAL ================= */

.resultsModal{
  position:fixed;
  top:0;
  left:0;
  right:0;
  bottom:0;
  background:rgba(0,0,0,0.4);
  backdrop-filter:blur(8px);
  z-index:1000;
  display:none;
  align-items:center;
  justify-content:center;
  opacity:0;
  transition:all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.resultsModal.open{
  display:flex;
  opacity:1;
}

.resultsModalContent{
  background:var(--panel);
  border:1px solid var(--border);
  border-radius:20px;
  box-shadow:0 20px 60px rgba(0,0,0,0.15);
  padding:32px;
  max-width:480px;
  width:90%;
  max-height:80vh;
  overflow:auto;
  transform:translateY(20px) scale(0.95);
  transition:var(--transition);
}

.resultsModal.open .resultsModalContent{
  transform:translateY(0) scale(1);
}

.resultsModalHeader{
  display:flex;
  align-items:center;
  justify-content:space-between;
  margin-bottom:20px;
  padding-bottom:16px;
  border-bottom:1px solid var(--soft);
}

.resultsModalTitle{
  font-size:24px;
  font-weight:700;
  color:var(--text);
  margin:0;
}

.resultsModalClose{
  width:32px;
  height:32px;
  border-radius:50%;
  border:none;
  background:var(--soft);
  color:var(--muted);
  cursor:pointer;
  transition:var(--transition);
  display:flex;
  align-items:center;
  justify-content:center;
  font-size:16px;
}

.resultsModalClose:hover{
  background:var(--accent);
  color:white;
  transform:scale(1.1);
}

.resultsModalBody{
  color:var(--text);
  line-height:1.6;
}

.resultsModalBody p{
  margin:0 0 16px;
  font-size:16px;
}

.resultsModalBody p:last-child{
  margin-bottom:0;
}

.resultsFeature{
  padding:16px 20px;
  background:var(--soft);
  border-radius:12px;
  margin:12px 0;
  border-left:4px solid var(--accent);
}

.resultsFeature strong{
  color:var(--accent);
  font-weight:600;
}

/* ================= FLOATING ACTION CAPSULES ================= */

.agentActionCapsule{
  position:absolute;
  top:-28px;
  left:16px;
  background:rgba(139,111,71,0.9);
  color:white;
  padding:4px 12px;
  border-radius:16px;
  font-size:10px;
  font-weight:700;
  text-transform:uppercase;
  letter-spacing:0.3px;
  box-shadow:0 2px 8px rgba(0,0,0,0.15);
  backdrop-filter:blur(8px);
  z-index:25;
  white-space:nowrap;
}

.agentActionCapsule.click{
  background:rgba(139,111,71,0.95);
}

.agentActionCapsule.type{
  background:rgba(139,111,71,0.95);
}

.agentActionCapsule.scroll{
  background:rgba(139,111,71,0.95);
}

.agentReasoningOverlay{
  position:absolute;
  bottom:16px;
  left:16px;
  right:16px;
  background:rgba(0,0,0,0.8);
  color:white;
  padding:8px 12px;
  border-radius:8px;
  font-size:11px;
  font-style:italic;
  line-height:1.3;
  backdrop-filter:blur(4px);
  max-height:60px;
  overflow:hidden;
  z-index:10;
}


/* ================= PROMPT BOX ================= */

.promptSection{
  position:fixed;
  bottom:32px;
  left:50%;
  transform:translateX(-50%);
  z-index:40;
  display:flex;
  gap:12px;
  align-items:center;
  transition:var(--transition);
}

.promptInput{
  height:52px;
  padding:0 20px;
  border-radius:26px;
  border:1px solid var(--border);
  background:rgba(255,255,255,0.98);
  backdrop-filter:blur(16px);
  box-shadow:var(--shadow);
  cursor:pointer;
  transition:var(--transition);
  color:var(--text);
  font-size:14px;
  font-weight:600;
  box-sizing:border-box;
  outline:none;
  font-family:-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif;
  width:520px;
}

.promptInput:hover{
  transform:translateY(-3px) scale(1.05);
  box-shadow:0 20px 50px rgba(0,0,0,0.15);
  border-color:var(--accent);
}

.promptInput:focus{
  border-color:var(--accent);
  box-shadow:0 0 0 3px rgba(139,111,71,0.1);
  transform:none;
}

.promptInput::placeholder{
  color:var(--muted);
  font-style:italic;
}


.promptSend{
  height:52px !important;
  padding:0 20px;
  border-radius:26px !important;
  border:1px solid var(--border);
  background:rgba(255,255,255,0.98);
  backdrop-filter:blur(16px);
  box-shadow:var(--shadow);
  cursor:pointer;
  transition:var(--transition);
  display:flex;
  align-items:center;
  justify-content:center;
  color:var(--accent);
  font-size:14px;
  font-weight:600;
  text-decoration:none;
  white-space:nowrap;
  box-sizing:border-box;
}

.promptSend:hover{
  transform:translateY(-3px) scale(1.05);
  box-shadow:0 20px 50px rgba(0,0,0,0.15);
  border-color:var(--accent);
  color:var(--accent);
}

.promptSend.primary{
  background:var(--accent);
  color:white;
  border-color:var(--accent);
}

.promptSend.primary:hover{
  background:#7a5f3f;
  color:white;
}

.mentionDropdown{
  position:fixed;
  bottom:60px;
  left:calc(50% - 260px - 6px);
  width:440px;
  background:var(--panel);
  border:1px solid var(--border);
  border-radius:12px;
  box-shadow:var(--shadow-hover);
  display:none;
  overflow:hidden;
  z-index:1000;
  max-height:150px;
  overflow-y:auto;
}

.mentionDropdown.open{
  display:block;
}

.mentionItem{
  padding:12px 16px;
  font-size:14px;
  font-family:ui-monospace, "SF Mono", Monaco, monospace;
  cursor:pointer;
  transition:var(--transition);
  border-bottom:1px solid var(--soft);
  display:flex;
  align-items:center;
  gap:12px;
}

.mentionItem:last-child{
  border-bottom:none;
}

.mentionItem:hover{
  background:var(--soft);
  color:var(--accent);
}

.mentionItem.selected{
  background:var(--accent);
  color:white;
}

.mentionItem::before{
  content:'';
  width:6px;
  height:6px;
  border-radius:50%;
  background:var(--accent);
  opacity:0.6;
  flex-shrink:0;
}

.mentionItem.selected::before{
  background:white;
  opacity:1;
}


.promptActions{
  display:flex;
  justify-content:space-between;
  align-items:center;
}


.promptInfo{
  font-size:11px;
  color:var(--muted);
  font-weight:500;
}

.mention{
  background:rgba(139,111,71,0.15);
  color:var(--accent);
  padding:2px 6px;
  border-radius:6px;
  font-weight:600;
  font-family:ui-monospace, "SF Mono", Monaco, monospace;
}

.promptInput .mention{
  background:rgba(139,111,71,0.2);
  color:var(--accent);
  padding:3px 8px;
  border-radius:8px;
  font-weight:700;
  font-family:ui-monospace, "SF Mono", Monaco, monospace;
  border:1px solid rgba(139,111,71,0.3);
}
</style>
</head>

<body>

<!-- View Mode Toggle -->
<div class="viewModeToggle">
  <button class="viewToggleBtn active" onclick="switchView('single')"><span>Single</span></button>
  <button class="viewToggleBtn" onclick="switchView('supervisor')"><span>Supervisor</span></button>
</div>

<!-- Single Agent View -->
<div id="singleView" class="singleView active">
  <div class="topRow">
    <div>
      <div class="brandTitle">Harmony</div>
      <div class="brandSubtitle">Parallel Agents, One Purpose</div>
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
    <div class="browserFrame" style="position: relative;">
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
        
        <!-- Single View Empty State -->
        <div class="singleEmptyState" id="singleEmptyState" style="display: none;">
          <div class="singleEmptyContent">
            <i data-lucide="monitor-off" class="singleEmptyIcon"></i>
            <div class="singleEmptyTitle">No Agents Available</div>
            <div class="singleEmptyText">Connect agents to start automation</div>
            <button class="singleEmptyButton" onclick="switchView('supervisor')">
              <i data-lucide="grid-3x3" style="width: 16px; height: 16px; margin-right: 8px;"></i>
              View Supervisor Mode
            </button>
          </div>
        </div>
      </div>
      
      <!-- Task Status Panel -->
      <div class="taskStatusPanel" id="taskStatusPanel">
        <div class="taskStatusContent">
          <div class="taskStatusLabel">Current Task</div>
          <div class="taskStatusText" id="taskStatusText">No active task</div>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- Supervisor View -->
<div id="supervisorView" class="supervisorView">
  
  <div class="supervisorHeader">
    <div class="supervisorTitle">Agent Supervisor</div>
    <div class="supervisorSubtitle">Parallel Agents, One Purpose</div>
    
    <div class="supervisorStats" id="supervisorStats">
      <div class="supervisorStat">
        <div class="supervisorStatNumber" id="totalAgents">0</div>
        <div class="supervisorStatLabel">Total Agents</div>
      </div>
      <div class="supervisorStat">
        <div class="supervisorStatNumber" id="activeAgents">0</div>
        <div class="supervisorStatLabel">Active</div>
      </div>
      <div class="supervisorStat">
        <div class="supervisorStatNumber" id="idleAgents">0</div>
        <div class="supervisorStatLabel">Idle</div>
      </div>
    </div>
    
    
  </div>
  
  <div class="agentsGrid" id="supervisorGrid">
    <!-- Agent tiles will be populated here -->
  </div>
  
  <!-- Empty State View -->
  <div class="emptyState" id="emptyState" style="display: none;">
    <div class="emptyStateContent">
      <div class="emptyStateIcon">
        <i data-lucide="monitor" class="emptyStateIconLarge"></i>
        <i data-lucide="plus" class="emptyStateIconPlus"></i>
      </div>
      
      <div class="emptyStateTitle">No Agents Connected</div>
      <div class="emptyStateSubtitle">Ready to orchestrate intelligent automation across your network</div>
      
      <div class="emptyStateInstructions">
        <div class="emptyStateStep">
          <div class="emptyStateStepNumber">1</div>
          <div class="emptyStateStepContent">
            <div class="emptyStateStepTitle">Launch Client</div>
            <div class="emptyStateStepText">Run <code>python client/client.py</code> on target computers</div>
          </div>
        </div>
        
        <div class="emptyStateStep">
          <div class="emptyStateStepNumber">2</div>
          <div class="emptyStateStepContent">
            <div class="emptyStateStepTitle">Auto-Discovery</div>
            <div class="emptyStateStepText">Agents will automatically discover and connect to this server</div>
          </div>
        </div>
        
        <div class="emptyStateStep">
          <div class="emptyStateStepNumber">3</div>
          <div class="emptyStateStepContent">
            <div class="emptyStateStepTitle">Deploy Tasks</div>
            <div class="emptyStateStepText">Assign intelligent automation tasks to connected agents</div>
          </div>
        </div>
      </div>
      
      <div class="emptyStateFooter">
        <div class="emptyStateNote">
          <i data-lucide="info" class="emptyStateNoteIcon"></i>
          <span>Each connected computer becomes an intelligent agent capable of autonomous task execution</span>
        </div>
      </div>
    </div>
  </div>
</div>


<!-- Floating Actions -->
<div class="floatingActions">
  <button class="actionButton primary" title="View Results" id="viewResultsBtn">
    View Results
  </button>
</div>

<!-- Prompt Section -->
<div class="promptSection" id="promptSection">
  <div class="mentionDropdown" id="mentionDropdown"></div>
  <input type="text" class="promptInput" id="promptInput" placeholder="Enter task instructions...">
  <button class="promptSend primary" id="promptSend">Send</button>
</div>

<!-- Results Modal -->
<div class="resultsModal" id="resultsModal">
  <div class="resultsModalContent">
    <div class="resultsModalHeader">
      <h2 class="resultsModalTitle">Automation Results</h2>
      <button class="resultsModalClose" onclick="closeResultsModal()">✕</button>
    </div>
    <div class="resultsModalBody">
      <p>Your automation session results will be displayed here once the feature is fully implemented.</p>
      
      <div class="resultsFeature">
        <strong>Coming Soon:</strong> Detailed automation reports with step-by-step execution logs, screenshots, and performance metrics.
      </div>
      
      <div class="resultsFeature">
        <strong>Future Features:</strong> Export results as PDF, CSV, or JSON formats for further analysis and record keeping.
      </div>
      
      <p>This comprehensive results view will help you analyze the effectiveness of your automation tasks and optimize future workflows.</p>
    </div>
  </div>
</div>

<!-- Custom Alert Modal -->
<div class="customAlert" id="customAlert">
  <div class="customAlertContent">
    <div class="customAlertHeader">
      <div class="customAlertTitleSection">
        <i data-lucide="message-square" class="customAlertIcon"></i>
        <h3 class="customAlertTitle" id="customAlertTitle">Agent Reasoning</h3>
      </div>
    </div>
    <div class="customAlertBody" id="customAlertBody">
      <!-- Content will be populated by JavaScript -->
    </div>
    <div class="customAlertFooter">
      <button class="customAlertOk" onclick="closeCustomAlert()">OK</button>
    </div>
  </div>
</div>

<!-- Full Screen Connection Overlay -->
<div class="connectionOverlay" id="connectionOverlay">
  <div class="connectionOverlayContent">
    <div class="connectionOverlayHeader">
      <div class="connectionOverlayIcon">
        <i data-lucide="command" class="connectionOverlayIconMain"></i>
      </div>
      <div class="connectionOverlayTitle">Harmony Control Center</div>
      <div class="connectionOverlaySubtitle">Connect agents to operate computers remotely</div>
    </div>
    
    <div class="connectionOverlayBody">
      <div class="connectionInstructions">
        <div class="connectionStep">
          <div class="connectionStepNumber">1</div>
          <div class="connectionStepContent">
            <div class="connectionStepTitle">Launch Terminal</div>
            <div class="connectionStepDescription">Open Command Prompt (Windows) or Terminal (Mac/Linux) on the computer you want the agent to operate</div>
          </div>
        </div>
        
        <div class="connectionStep">
          <div class="connectionStepNumber">2</div>
          <div class="connectionStepContent">
            <div class="connectionStepTitle">Deploy Agent</div>
            <div class="connectionStepCommand">python client/client.py</div>
            <div class="connectionStepDescription">Execute the command to deploy an agent that will operate this computer</div>
          </div>
        </div>
        
        <div class="connectionStep">
          <div class="connectionStepNumber">3</div>
          <div class="connectionStepContent">
            <div class="connectionStepTitle">Agent Online</div>
            <div class="connectionStepDescription">The agent will automatically connect and appear in your dashboard, ready to operate the computer based on your instructions.</div>
          </div>
        </div>
      </div>
      
      <div class="connectionTip">
        <i data-lucide="lightbulb" class="connectionTipIcon"></i>
        <div class="connectionTipContent">
          <strong>Note:</strong> Deploy agents across multiple computers to operate an entire fleet from this central dashboard.
        </div>
      </div>
    </div>
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
  if(!currentAgent) {
    $("screen").style.display='none'
    $("viewport").classList.add('empty')
    return
  }
  
  try {
    const r=await fetch(`/screen/${currentAgent}?t=${Date.now()}`,{cache:"no-store"})
    if(!r.ok) throw new Error(`Screen fetch failed: ${r.status}`)
    
    const b=await r.blob()
    const u=URL.createObjectURL(b)
    if(lastImgUrl)URL.revokeObjectURL(lastImgUrl)
    lastImgUrl=u
    
    $("screen").src=u
    $("screen").style.display='block'
    $("viewport").classList.remove('empty')
  } catch(e) {
    console.warn('Screen refresh failed:', e.message)
    $("screen").style.display='none'
    $("viewport").classList.add('empty')
  }
}

$("screen").onload=()=>{
  imgNat.w=$("screen").naturalWidth||imgNat.w
  imgNat.h=$("screen").naturalHeight||imgNat.h
}

async function updateState(){
  if(!currentAgent) {
    $("agentValue").textContent="—"
    $("taskStatusText").textContent="No active task"
    $("statusCap").textContent="Idle"
    $("actionTop").textContent="Select an agent..."
    $("thought").classList.add("hidden")
    return
  }
  
  try {
    const r=await fetch(`/agent/${currentAgent}`,{cache:"no-store"})
    if(!r.ok) throw new Error(`Agent state fetch failed: ${r.status}`)
    
    const d=await r.json()
    $("agentValue").textContent=d.id||"—"
    $("taskStatusText").textContent=d.task||"No active task"
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
  } catch(e) {
    console.warn('State update failed:', e.message)
  }
}

async function fetchAgents(){
  try {
    const r=await fetch("/agents",{cache:"no-store"})
    if(!r.ok) throw new Error(`Agents fetch failed: ${r.status}`)
    
    const agents=await r.json()
    const menu=$("agentMenu")
    menu.innerHTML=""
    
    if(agents.length === 0) {
      const emptyItem=document.createElement("div")
      emptyItem.className="agentItem"
      emptyItem.style.opacity="0.6"
      emptyItem.style.cursor="default"
      emptyItem.style.fontStyle="italic"
      emptyItem.textContent="No agents connected"
      menu.appendChild(emptyItem)
      
      // Show connection overlay
      showConnectionOverlay()
      
      return
    } else {
      // Hide connection overlay when agents are available
      hideConnectionOverlay()
      hideSingleEmptyState()
    }
    
    agents.forEach(agent=>{
      const item=document.createElement("div")
      item.className="agentItem"
      item.textContent=agent.id
      item.onclick=()=>{
        currentAgent=agent.id
        $("agentValue").textContent=agent.id
        menu.classList.remove("open")
        updateState()
        refreshScreen()
        updatePromptPlaceholder()
      }
      menu.appendChild(item)
    })
    
    // Auto-select first agent if none selected
    if(!currentAgent && agents.length > 0){
      currentAgent=agents[0].id
      $("agentValue").textContent=currentAgent
    }
  } catch(e) {
    console.error('Failed to fetch agents:', e.message)
    $("agentValue").textContent="Error"
  }
}

// View Management
let currentView = 'single'

function switchView(viewName) {
  // Update toggle buttons
  document.querySelectorAll('.viewToggleBtn').forEach(btn => {
    btn.classList.remove('active')
    if((viewName === 'single' && btn.textContent.includes('Single')) || 
       (viewName === 'supervisor' && btn.textContent.includes('Supervisor'))) {
      btn.classList.add('active')
    }
  })
  
  // Show/hide views
  if(viewName === 'single') {
    $("singleView").classList.add('active')
    $("supervisorView").classList.remove('active')
    currentView = 'single'
    updatePromptPlaceholder()
  } else {
    $("singleView").classList.remove('active')
    $("supervisorView").classList.add('active')
    currentView = 'supervisor'
    updateSupervisorGrid()
    updatePromptPlaceholder()
  }
}

function updatePromptPlaceholder() {
  const input = $("promptInput")
  if(currentView === 'single') {
    input.placeholder = currentAgent ? 
      `Send task to ${currentAgent}...` : 
      'Select an agent first...'
  } else {
    input.placeholder = 'Enter task instructions. Use @agent-id for specific assignments...'
  }
}

// Mention System Variables
let mentionDropdownOpen = false
let availableAgents = []
let selectedMentionIndex = -1

// Mention System Functions
async function loadAvailableAgents() {
  try {
    const r = await fetch("/agents", {cache: "no-store"})
    availableAgents = await r.json()
  } catch(e) {
    console.warn('Failed to load agents for mentions:', e)
    availableAgents = []
  }
}

function showMentionDropdown(searchTerm = '', isSuperview = false) {
  const dropdownId = isSuperview ? "supervisorMentionDropdown" : "mentionDropdown"
  const dropdown = $(dropdownId)
  dropdown.innerHTML = ""
  
  const filteredAgents = availableAgents.filter(agent => 
    agent.id.toLowerCase().includes(searchTerm.toLowerCase())
  )
  
  if(filteredAgents.length === 0) {
    dropdown.classList.remove('open')
    mentionDropdownOpen = false
    return
  }
  
  filteredAgents.forEach((agent, index) => {
    const item = document.createElement("div")
    item.className = "mentionItem"
    item.textContent = agent.id
    item.onclick = () => insertMention(agent.id, isSuperview)
    if(index === selectedMentionIndex) {
      item.classList.add('selected')
    }
    dropdown.appendChild(item)
  })
  
  // Position the single view dropdown
  if(!isSuperview) {
    dropdown.className = "mentionDropdown single-view"
  }
  
  dropdown.classList.add('open')
  mentionDropdownOpen = true
  selectedMentionIndex = Math.max(0, Math.min(selectedMentionIndex, filteredAgents.length - 1))
  updateMentionSelection(isSuperview)
}

function hideMentionDropdown(isSuperview = false) {
  const dropdownId = isSuperview ? "supervisorMentionDropdown" : "mentionDropdown"
  $(dropdownId).classList.remove('open')
  mentionDropdownOpen = false
  selectedMentionIndex = -1
}

function updateMentionSelection(isSuperview = false) {
  const dropdownId = isSuperview ? "supervisorMentionDropdown" : "mentionDropdown"
  const items = $(dropdownId).querySelectorAll('.mentionItem')
  items.forEach((item, index) => {
    item.classList.toggle('selected', index === selectedMentionIndex)
  })
}

function insertMention(agentId, isSuperview = false) {
  const inputId = isSuperview ? "supervisorTaskInput" : "promptInput"
  const input = $(inputId)
  const value = input.value
  const cursorPos = input.selectionStart
  
  // Find the @ symbol position
  let atPos = cursorPos - 1
  while(atPos >= 0 && value[atPos] !== '@') {
    atPos--
  }
  
  if(atPos >= 0) {
    const beforeAt = value.substring(0, atPos)
    const afterCursor = value.substring(cursorPos)
    const mention = `@${agentId}`
    
    input.value = beforeAt + mention + ' ' + afterCursor
    input.selectionStart = input.selectionEnd = atPos + mention.length + 1
  }
  
  hideMentionDropdown(isSuperview)
  input.focus()
}

function extractMentions(text) {
  const mentionRegex = /@([a-zA-Z0-9-]+)/g
  const mentions = []
  let match
  
  while((match = mentionRegex.exec(text)) !== null) {
    mentions.push(match[1])
  }
  
  return mentions
}

function sendTask() {
  const input = $("promptInput")
  const task = input.value.trim()
  
  if(!task) {
    alert('Please enter a task')
    return
  }
  
  let message
  if(currentView === 'single') {
    // Single view - send to current agent
    if(!currentAgent) {
      alert('Please select an agent first')
      return
    }
    message = `Task sent to agent ${currentAgent}`
  } else {
    // Supervisor view - check for mentions
    const mentions = extractMentions(task)
    if(mentions.length > 0) {
      message = `Task sent to agents: ${mentions.join(', ')}`
    } else {
      message = 'General task sent for auto-assignment to available agents'
    }
  }
  
  alert(message)
  input.value = ''
}

// Enhanced UX interactions
$("agentBtn").onclick=(e)=>{
  e.stopPropagation()
  $("agentMenu").classList.toggle("open")
}

document.addEventListener("click",e=>{
  if(!e.target.closest(".agentPicker")) {
    $("agentMenu").classList.remove("open")
  }
})

// Keyboard shortcuts
document.addEventListener("keydown", e => {
  if(e.key === 'Escape') {
    $("agentMenu").classList.remove("open")
  }
  if(e.key === 's' && (e.metaKey || e.ctrlKey)) {
    e.preventDefault()
    switchView(currentView === 'single' ? 'supervisor' : 'single')
  }
})

// View Results functionality
$("viewResultsBtn").onclick = () => {
  openResultsModal()
}

function openResultsModal() {
  const modal = $("resultsModal")
  modal.classList.add('open')
}

function closeResultsModal() {
  const modal = $("resultsModal")
  modal.classList.remove('open')
}

// Close modal when clicking outside or pressing Escape
document.addEventListener('click', e => {
  if(e.target.id === 'resultsModal') {
    closeResultsModal()
  }
  if(e.target.id === 'reasoningModal') {
    closeReasoningModal()
  }
  if(e.target.id === 'customAlert') {
    closeCustomAlert()
  }
})

document.addEventListener('keydown', e => {
  if(e.key === 'Escape') {
    if($("resultsModal").classList.contains('open')) {
      closeResultsModal()
    }
    if($("reasoningModal").classList.contains('open')) {
      closeReasoningModal()
    }
    if($("customAlert").classList.contains('open')) {
      closeCustomAlert()
    }
  }
})

// Prompt functionality
$("promptSend").onclick = sendTask

$("promptInput").addEventListener('keydown', e => {
  if(mentionDropdownOpen) {
    if(e.key === 'ArrowDown') {
      e.preventDefault()
      selectedMentionIndex = Math.min(selectedMentionIndex + 1, document.querySelectorAll('.mentionItem').length - 1)
      updateMentionSelection()
    } else if(e.key === 'ArrowUp') {
      e.preventDefault()
      selectedMentionIndex = Math.max(selectedMentionIndex - 1, 0)
      updateMentionSelection()
    } else if(e.key === 'Enter' || e.key === 'Tab') {
      e.preventDefault()
      const items = document.querySelectorAll('.mentionItem')
      if(items[selectedMentionIndex]) {
        items[selectedMentionIndex].click()
      }
    } else if(e.key === 'Escape') {
      e.preventDefault()
      hideMentionDropdown()
    }
    return
  }
  
  if(e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
    e.preventDefault()
    sendTask()
  }
})

$("promptInput").addEventListener('input', e => {
  // Only allow mentions in supervisor view
  if(currentView !== 'supervisor') return
  
  const value = e.target.value
  const cursorPos = e.target.selectionStart
  
  // Check if we just typed @
  if(value[cursorPos - 1] === '@') {
    showMentionDropdown('')
    selectedMentionIndex = 0
  } else if(mentionDropdownOpen) {
    // Find the current @ mention being typed
    let atPos = cursorPos - 1
    while(atPos >= 0 && value[atPos] !== '@' && value[atPos] !== ' ') {
      atPos--
    }
    
    if(atPos >= 0 && value[atPos] === '@') {
      const searchTerm = value.substring(atPos + 1, cursorPos)
      showMentionDropdown(searchTerm)
    } else {
      hideMentionDropdown()
    }
  }
})

$("promptInput").addEventListener('click', e => {
  if(mentionDropdownOpen) {
    hideMentionDropdown()
  }
})

// Click outside to close mention dropdown
document.addEventListener('click', e => {
  if(!e.target.closest('.promptInputSection')) {
    hideMentionDropdown()
  }
})

// Update placeholder when agent changes
function updateAgentSelection() {
  updatePromptPlaceholder()
}

// Add loading states
function showLoading() {
  $("agentValue").textContent = "Loading..."
  $("statusCap").textContent = "Connecting..."
}

function hideLoading() {
  // Loading states will be overwritten by actual data
}

// Enhanced initialization
let isInitialized = false

async function initialize() {
  if(isInitialized) return
  
  showLoading()
  
  try {
    await Promise.all([fetchAgents(), loadAvailableAgents()])
    if(currentAgent) {
      await Promise.all([updateState(), refreshScreen()])
    }
    updatePromptPlaceholder()
    isInitialized = true
    hideLoading()
  } catch(e) {
    console.error('Initialization failed:', e)
  }
}

// Smooth polling with exponential backoff on errors
let errorCount = 0
const maxErrors = 3

function scheduleUpdate(fn, interval) {
  const execute = async () => {
    try {
      await fn()
      errorCount = 0 // Reset on success
      setTimeout(execute, interval)
    } catch(e) {
      errorCount++
      const delay = Math.min(interval * Math.pow(2, errorCount-1), 10000)
      console.warn(`Function failed, retrying in ${delay}ms:`, e.message)
      setTimeout(execute, delay)
    }
  }
  execute()
}

// Supervisor Grid Management
let lastAgentData = []
let agentTileElements = {}

async function updateSupervisorGrid() {
  if(currentView !== 'supervisor') return
  
  try {
    const r = await fetch("/agents", {cache: "no-store"})
    if(!r.ok) throw new Error(`Agents fetch failed: ${r.status}`)
    
    const agents = await r.json()
    const grid = $("supervisorGrid")
    const emptyState = $("emptyState")
    
    if(agents.length === 0) {
      grid.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; padding: 60px 20px; color: var(--muted); font-size: 16px; font-style: italic;">No agents connected</div>`
      emptyState.style.display = 'none'
      
      // Show connection overlay
      showConnectionOverlay()
      
      return
    } else {
      grid.style.display = 'flex'
      emptyState.style.display = 'none'
      
      // Hide connection overlay
      hideConnectionOverlay()
    }
    
    // Only fetch data for agents we don't have or need updates
    const agentPromises = agents.map(async agent => {
      try {
        const [stateRes] = await Promise.allSettled([
          fetch(`/agent/${agent.id}`, {cache: "no-store"})
        ])
        
        let agentData = {id: agent.id, status: 'idle', task: null, status_text: 'Idle'}
        if(stateRes.status === 'fulfilled' && stateRes.value.ok) {
          agentData = await stateRes.value.json()
        }
        
        return agentData
      } catch(e) {
        return {id: agent.id, status: 'error', status_text: 'Connection Error'}
      }
    })
    
    const agentDetails = await Promise.all(agentPromises)
    
    // Update stats
    updateSupervisorStats(agentDetails)
    
    // Only update tiles if agent list changed
    const currentAgentIds = agentDetails.map(a => a.id).sort().join(',')
    const lastAgentIds = lastAgentData.map(a => a.id).sort().join(',')
    
    if(currentAgentIds !== lastAgentIds) {
      // Recreate all tiles
      grid.innerHTML = ""
      agentTileElements = {}
      
      agentDetails.forEach(agent => createAgentTile(agent, grid))
    } else {
      // Just update existing tiles
      agentDetails.forEach(agent => updateAgentTile(agent))
    }
    
    lastAgentData = agentDetails
    
  } catch(e) {
    console.warn('Supervisor grid update failed:', e.message)
    const grid = $("supervisorGrid")
    grid.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; padding: 40px; color: var(--muted);">Failed to load agents</div>`
  }
}

function createAgentTile(agent, grid) {
  const tile = document.createElement("div")
  tile.className = "agentTile"
  tile.id = `tile-${agent.id}`
  tile.onclick = () => {
    currentAgent = agent.id
    switchView('single')
    updateState()
    refreshScreen()
  }
  
  agentTileElements[agent.id] = tile
  updateAgentTileContent(agent, tile)
  grid.appendChild(tile)
  
  // Initialize Lucide icons
  if (typeof lucide !== 'undefined') {
    lucide.createIcons()
  }
}

function updateAgentTile(agent) {
  const tile = agentTileElements[agent.id]
  if(tile) {
    updateAgentTileContent(agent, tile)
  }
}

async function updateAgentTileContent(agent, tile) {
  const statusClass = agent.status === 'working' ? 'working' : 'idle'
  const lastSeen = new Date().toLocaleTimeString()
  
  // Fetch screenshot only when needed
  let screenshotUrl = null
  try {
    const screenRes = await fetch(`/screen/${agent.id}?t=${Date.now()}`, {cache: "no-store"})
    if(screenRes.ok) {
      const blob = await screenRes.blob()
      screenshotUrl = URL.createObjectURL(blob)
    }
  } catch(e) {
    // Screenshot failed, use placeholder
  }
  
  // Create action capsule content
  let actionText = agent.status_text || 'Unknown'
  if(agent.step?.action) {
    if(agent.step.action === 'click' && agent.step.coordinate) {
      actionText = `Click ${agent.step.coordinate[0]}, ${agent.step.coordinate[1]}`
    } else if(agent.step.action === 'type' && agent.step.value) {
      actionText = `Type "${agent.step.value}"`
    } else if(agent.step.action === 'scroll') {
      actionText = `Scroll ${agent.step.value || ''}`
    } else {
      actionText = agent.step.action
    }
  }

  tile.innerHTML = `
    ${agent.step?.action ? `<div class="agentActionCapsule ${agent.step.action}">${actionText}</div>` : ''}
    <div class="agentTileContent">
      <div class="agentTileHeader">
        <div>
          <div class="agentTileId">${agent.id || 'Unknown'}</div>
          <div class="agentTileTask">${agent.task || 'No active task'}</div>
        </div>
      </div>
      
      <div class="agentMiniWindow">
        <div class="agentMiniTop">
          <div class="agentMiniWin red"></div>
          <div class="agentMiniWin yellow"></div>
          <div class="agentMiniWin green"></div>
          <div class="agentMiniAddress">${agent.id}</div>
        </div>
        <div class="agentMiniViewport" style="position: relative;">
          ${screenshotUrl ? 
            `<img src="${screenshotUrl}" class="agentTileScreenImg" alt="Agent screen">` : 
            `<div class="agentTileScreenPlaceholder">Monitor</div>`
          }
        </div>
      </div>
      
      ${agent.step?.reasoning || agent.step?.action ? createReasoningPanel(agent) : ''}
      
    </div>
  `
  
  // Initialize Lucide icons after content update
  setTimeout(() => {
    if (typeof lucide !== 'undefined') {
      lucide.createIcons()
    }
  }, 100)
}

function createReasoningPanel(agent) {
  if (!agent.step?.reasoning && !agent.step?.action) return ''
  
  // Get action icon based on action type
  const actionIcons = {
    'left_click': 'mouse-pointer-click',
    'double_click': 'mouse-pointer-click', 
    'right_click': 'mouse-pointer-click',
    'type': 'keyboard',
    'hotkey': 'command',
    'scroll_down': 'arrow-down',
    'scroll_up': 'arrow-up',
    'wait': 'clock'
  }
  
  const actionIcon = actionIcons[agent.step.action] || 'mouse-pointer'
  const actionText = agent.step.action || 'Processing'
  
  return `
    <div class="reasoningPanel visible">
      <div class="reasoningPanelHeader">
        <div class="reasoningPanelTitle">
          Thoughts
        </div>
        <button class="showAllBtn" onclick="expandReasoning('${agent.id}', event)">Show all</button>
      </div>
      
      <p class="reasoningPanelText">${agent.step.reasoning || 'Analyzing current state...'}</p>
      
      <div class="reasoningPanelAction">
        <i data-lucide="${actionIcon}" class="reasoningActionIcon"></i>
        <span>Next: ${actionText}</span>
        ${agent.step.coordinate ? `<span>at (${agent.step.coordinate[0]}, ${agent.step.coordinate[1]})</span>` : ''}
      </div>
    </div>
  `
}

// Show full reasoning in custom alert
function expandReasoning(agentId, event) {
  // Prevent event bubbling to parent elements
  if (event) {
    event.stopPropagation()
    event.preventDefault()
  }
  
  const panel = document.querySelector(`#tile-${agentId} .reasoningPanel`)
  const textElement = panel.querySelector('.reasoningPanelText')
  
  if (!panel || !textElement) {
    showCustomAlert('No Reasoning Available', 'No reasoning data is available for this agent at this time.')
    return
  }
  
  // Get the full reasoning text from the element
  const fullReasoning = textElement.textContent || textElement.innerText || 'No reasoning available.'
  
  // Show custom alert with full reasoning
  showCustomAlert(`${agentId} Full Reasoning`, fullReasoning)
}

// Custom alert functions
function showCustomAlert(title, message) {
  const modal = $("customAlert")
  const titleElement = $("customAlertTitle")
  const bodyElement = $("customAlertBody")
  
  titleElement.textContent = title
  bodyElement.textContent = message
  
  // Initialize Lucide icons
  if (typeof lucide !== 'undefined') {
    lucide.createIcons()
  }
  
  modal.classList.add('open')
}

function closeCustomAlert() {
  const modal = $("customAlert")
  modal.classList.remove('open')
}

// Connection overlay functions
function showConnectionOverlay() {
  const overlay = $("connectionOverlay")
  overlay.classList.add('active')
  
  // Initialize Lucide icons
  if (typeof lucide !== 'undefined') {
    lucide.createIcons()
  }
}

function hideConnectionOverlay() {
  const overlay = $("connectionOverlay")
  overlay.classList.remove('active')
}

// Single view empty state functions
function showSingleEmptyState() {
  if (currentView === 'single') {
    const screen = $("screen")
    const singleEmpty = $("singleEmptyState")
    const viewport = $("viewport")
    
    screen.style.display = 'none'
    viewport.classList.add('empty')
    singleEmpty.style.display = 'flex'
    
    // Initialize Lucide icons
    if (typeof lucide !== 'undefined') {
      lucide.createIcons()
    }
  }
}

function hideSingleEmptyState() {
  const screen = $("screen")
  const singleEmpty = $("singleEmptyState")
  const viewport = $("viewport")
  
  singleEmpty.style.display = 'none'
  viewport.classList.remove('empty')
}

function closeReasoningModal() {
  $("reasoningModal").classList.remove('open')
}

// Helper functions for supervisor controls
function selectAgent(agentId) {
  currentAgent = agentId
  $("agentValue").textContent = agentId
  
  // Update the view toggle buttons properly
  document.querySelectorAll('.viewToggleBtn').forEach(btn => {
    btn.classList.remove('active')
    if(btn.textContent.includes('Single')) {
      btn.classList.add('active')
    }
  })
  
  switchView('single')
  updateState()
  refreshScreen()
}

function refreshAgent(agentId) {
  if(currentView === 'supervisor') {
    updateSupervisorGrid()
  }
}

function updateSupervisorStats(agents) {
  const total = agents.length
  const active = agents.filter(agent => agent.status === 'working').length
  const idle = total - active
  
  $("totalAgents").textContent = total
  $("activeAgents").textContent = active
  $("idleAgents").textContent = idle
}



// Initialize and start polling
initialize()
scheduleUpdate(() => Promise.all([fetchAgents(), loadAvailableAgents()]), 2000)
scheduleUpdate(updateState, 300)
scheduleUpdate(() => currentAgent && refreshScreen(), 500)
scheduleUpdate(() => {
  if(currentView === 'supervisor') {
    updateSupervisorGrid()
  }
}, 1500)
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