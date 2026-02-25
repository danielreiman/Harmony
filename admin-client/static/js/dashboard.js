// ── State ──────────────────────────────────────────────────────────────────────
function el(id) { return document.getElementById(id) }

let currentAgent = null, lastScreenshotUrl = null, currentView = 'single'
let researchModeEnabled = false, agentsList = [], lastAgentData = []
let agentTileElements = {}, isInitialized = false
let shuttingDown = false, serverUnavailable = false, errorCount = 0
let currentResearchTaskId = null, researchPollInterval = null, tasksPanelPollInterval = null

const THEME_KEY = 'harmonyTheme'
if (!localStorage.getItem('token')) window.location.href = '/login'


// ── API Bases ──────────────────────────────────────────────────────────────────
const apiBases = (() => {
  const bases = []
  const serverParam = new URLSearchParams(location.search).get('server')
  if (serverParam) {
    const t = serverParam.trim().replace(/\/+$/, '')
    bases.push(/^https?:\/\//i.test(t) ? t : `http://${t}`)
  }
  if (location.protocol === 'file:') {
    bases.push('http://localhost:1234', 'http://127.0.0.1:1234')
  } else {
    bases.push(location.origin)
    if (location.port !== '1234' && location.hostname)
      bases.push(`${location.protocol}//${location.hostname}:1234`)
  }
  return [...new Set(bases)]
})()


// ── Theme ──────────────────────────────────────────────────────────────────────
function applyTheme(t) { document.body.classList.toggle('theme-carbon', t === 'carbon') }
function initTheme() { try { applyTheme(localStorage.getItem(THEME_KEY) || 'carbon') } catch { applyTheme('carbon') } }
window.setHarmonyTheme = t => {
  t === 'default' ? localStorage.removeItem(THEME_KEY) : localStorage.setItem(THEME_KEY, t)
  applyTheme(t)
}
initTheme()


// ── Fetch ──────────────────────────────────────────────────────────────────────
async function apiFetch(path, opts = {}) {
  opts.headers = opts.headers || {}
  const token = localStorage.getItem('token')
  if (token) opts.headers['Authorization'] = 'Bearer ' + token
  let lastErr
  for (const base of apiBases) {
    try {
      const res = await fetch(`${base}${path}`, opts)
      if (res.status === 401) { localStorage.removeItem('token'); if (!shuttingDown) location.href = '/login' }
      return res
    } catch (e) { lastErr = e }
  }
  throw lastErr || new Error('Network error')
}


// ── Helpers ────────────────────────────────────────────────────────────────────
function escapeHtml(t) {
  return String(t || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}
function truncateText(t, max) { return !t ? '' : t.length > max ? t.slice(0, max - 1) + '…' : t }
function formatRelativeTime(unix) {
  const s = Math.floor(Date.now() / 1000) - unix
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86400) return `${Math.floor(s / 3600)} hr ago`
  if (s < 172800) return 'yesterday'
  return `${Math.floor(s / 86400)} days ago`
}
function refreshLucideIcons() { if (typeof lucide !== 'undefined') lucide.createIcons() }
function showToast(msg, type) { console.log(`[${type}] ${msg}`) }

function stripTaskMetadata(text) {
  if (!text) return ''
  const markers = ['\n\nCollaboration:', '\n\nAssigned agent:', '\n\nOther agents:', '\n\nRole:']
  const positions = markers.map(m => text.indexOf(m)).filter(p => p !== -1)
  return positions.length ? text.slice(0, Math.min(...positions)).trim() : text.trim()
}

function describeStep(step) {
  if (!step || !step.action) return 'Waiting…'
  const a = step.action.toLowerCase()
  const [x, y] = Array.isArray(step.coordinate) && step.coordinate.length === 2 ? step.coordinate : [null, null]
  if (['left_click', 'click', 'double_click', 'right_click'].includes(a))
    return x != null ? `${a.replace('_', ' ')} at ${x}, ${y}` : 'Clicking'
  if (a === 'scroll') return `Scrolling ${step.value || ''}`.trim()
  if (a === 'type') return `Typing "${(step.value || '').slice(0, 30)}${(step.value || '').length > 30 ? '...' : ''}"`
  if (a === 'press_key') return `Pressing ${step.value || 'key'}`
  if (a === 'hotkey') return `Hotkey ${Array.isArray(step.value) ? step.value.join('+') : step.value || ''}`
  return { scroll_down: 'Scrolling down', scroll_up: 'Scrolling up', wait: 'Waiting...', none: 'Done' }[a] || step.action
}


// ── Connection Overlay ─────────────────────────────────────────────────────────
function showConnectionOverlay() {
  if (serverUnavailable || shuttingDown) return
  el('connectionOverlay').classList.remove('error')
  el('connectionOverlay').classList.add('active')
  refreshLucideIcons()
}
function hideConnectionOverlay() {
  if (serverUnavailable || shuttingDown) return
  el('connectionOverlay').classList.remove('active', 'error')
}

const GH_BTN = `<a href="https://github.com/danielreiman/Harmony" target="_blank" class="goodbyeBtn"><svg viewBox="0 0 16 16" style="width:18px;height:18px;fill:currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>View on GitHub</a>`

function setOverlayMessage(title, subtitle) {
  const ov = el('connectionOverlay')
  ov.querySelector('.connectionOverlayTitle').textContent = title
  ov.querySelector('.connectionOverlaySubtitle').innerHTML = subtitle
  ov.querySelector('.connectionOverlayBody').style.display = 'none'
  const a = ov.querySelector('.connectionActions'), t = ov.querySelector('.connectionOverlayTopActions')
  if (a) a.style.display = 'none'
  if (t) t.style.display = 'none'
  ov.classList.remove('error')
  ov.classList.add('active', 'goodbye')
  refreshLucideIcons()
}

function showGoodbye() {
  shuttingDown = true
  setOverlayMessage('See you next time!',
    `Harmony server has been shut down<div class="goodbyeActions"><button class="goodbyeBtn" onclick="location.reload()"><i data-lucide="refresh-cw"></i>Reconnect</button>${GH_BTN}</div><div style="margin-top:32px;color:rgba(255,255,255,0.6);font-size:13px;">To restart: <code style="background:rgba(255,255,255,0.1);padding:4px 8px;border-radius:4px;">python server/server.py</code></div>`)
}

function showServerUnavailable() {
  if (shuttingDown) return
  serverUnavailable = true
  setOverlayMessage('Server unavailable',
    `Cannot reach the Harmony server. Make sure it is running.<div class="goodbyeActions"><button class="goodbyeBtn" onclick="checkServerStatus()"><i data-lucide="refresh-cw"></i>Retry</button>${GH_BTN}</div><div style="margin-top:32px;color:rgba(255,255,255,0.6);font-size:13px;">To start: <code style="background:rgba(255,255,255,0.1);padding:4px 8px;border-radius:4px;">python server/server.py</code></div>`)
}

function hideServerUnavailable() {
  if (!serverUnavailable) return
  serverUnavailable = false
  const ov = el('connectionOverlay')
  ov.querySelector('.connectionOverlayTitle').textContent = 'Harmony'
  ov.querySelector('.connectionOverlaySubtitle').textContent = 'Distributed automation system for parallel task execution across multiple computers'
  ov.querySelector('.connectionOverlayBody').style.display = ''
  const t = ov.querySelector('.connectionOverlayTopActions')
  if (t) t.style.display = ''
  ov.classList.remove('goodbye', 'active')
}

async function checkServerStatus() {
  if (shuttingDown) return
  try {
    const data = await (await apiFetch('/api/status')).json()
    data.ok ? hideServerUnavailable() : showServerUnavailable()
  } catch { showServerUnavailable() }
}


// ── Screen ─────────────────────────────────────────────────────────────────────
async function refreshScreen() {
  const frame = document.querySelector('.browserFrame')
  const top = document.querySelector('.browserTop')
  function waiting() {
    el('screen').style.display = 'none'
    el('waitingState').style.display = 'flex'
    el('waitingAgentId').textContent = currentAgent || 'No agent selected'
    el('viewport').classList.add('empty')
    frame.classList.add('waiting')
    top.style.display = 'none'
    el('statusCap').style.display = 'none'
  }
  if (!currentAgent) return waiting()
  try {
    const res = await apiFetch(`/screen/${currentAgent}?t=${Date.now()}`, { cache: 'no-store' })
    if (!res.ok) throw new Error()
    const url = URL.createObjectURL(await res.blob())
    if (lastScreenshotUrl) URL.revokeObjectURL(lastScreenshotUrl)
    lastScreenshotUrl = url
    el('screen').src = url
    el('screen').style.display = 'block'
    el('waitingState').style.display = 'none'
    el('viewport').classList.remove('empty')
    frame.classList.remove('waiting')
    top.style.display = 'flex'
    el('statusCap').style.display = 'block'
  } catch { waiting() }
}


// ── Agent State ────────────────────────────────────────────────────────────────
function renderAgentState(data) {
  const task = stripTaskMetadata(data.task)
  el('taskStatusText').textContent = task || 'No active task'
  el('statusCap').textContent = data.status_text || data.status || 'Idle'
  el('actionTop').textContent = describeStep(data.step)
  const panel = el('taskStatusPanel')
  if (panel) panel.style.display = task && data.status === 'working' ? 'flex' : 'none'
  el('singleReasoningText').textContent = (data.step && data.step.reasoning) || data.status_text || 'Waiting for agent activity...'
}

async function updateState() {
  if (!currentAgent) {
    el('taskStatusText').textContent = 'No active task'
    el('statusCap').textContent = 'Idle'
    el('actionTop').textContent = 'Select an agent...'
    el('singleReasoningText').textContent = 'Waiting for agent activity...'
    const p = el('taskStatusPanel')
    if (p) p.style.display = 'none'
    return
  }
  try {
    const res = await apiFetch(`/agent/${currentAgent}`, { cache: 'no-store' })
    if (res.ok) renderAgentState(await res.json())
  } catch {}
}


// ── Agents List ────────────────────────────────────────────────────────────────
async function fetchAgents() {
  try {
    const res = await apiFetch('/agents', { cache: 'no-store' })
    if (!res.ok) throw new Error()
    agentsList = await res.json()
    if (!agentsList.length) { el('selectedAgent').textContent = 'No agents'; showConnectionOverlay(); return }
    hideConnectionOverlay()
    hideSingleEmptyState()
    if (!currentAgent) currentAgent = agentsList[0].id
    updateAgentDropdown()
  } catch { showToast('Connection lost - server may be down', 'error') }
}

function updateAgentDropdown() {
  if (!agentsList.length) return
  el('selectedAgent').textContent = currentAgent || 'No agent'
  el('agentDropdownMenu').innerHTML =
    `<div class="agentDropdownHeader">Select Agent</div><div class="agentDropdownDivider"></div>` +
    agentsList.map(a =>
      `<div class="agentOption${a.id === currentAgent ? ' active' : ''}" onclick="currentAgent='${a.id}';updateAgentDropdown();updateState();refreshScreen();updatePromptPlaceholder();closeAgentDropdown()">
        <div class="agentOptionTitle">${escapeHtml(a.id)}</div>
        <svg class="agentOptionCheck" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
      </div>`
    ).join('')
}

function toggleAgentDropdown() { el('agentSelector').classList.toggle('open'); el('agentDropdownMenu').classList.toggle('open') }
function closeAgentDropdown() { el('agentSelector').classList.remove('open'); el('agentDropdownMenu').classList.remove('open') }

el('agentSelector').onclick = e => { e.stopPropagation(); toggleAgentDropdown() }
document.addEventListener('click', e => { if (!e.target.closest('.agentDropdown')) closeAgentDropdown() })


// ── View Switching ─────────────────────────────────────────────────────────────
function switchView(view) {
  document.querySelectorAll('.viewToggleBtn').forEach(b => {
    b.classList.toggle('active',
      (view === 'single' && b.textContent.includes('Single')) ||
      (view === 'supervisor' && b.textContent.includes('Supervisor')))
  })
  el('singleView').classList.toggle('active', view === 'single')
  el('supervisorView').classList.toggle('active', view === 'supervisor')
  el('agentDropdown').style.display = view === 'single' ? 'flex' : 'none'
  const meta = el('promptMeta')
  if (meta) meta.style.display = view === 'supervisor' ? 'flex' : 'none'
  currentView = view
  if (view === 'supervisor') updateSupervisorGrid()
  updatePromptPlaceholder()
  refreshLucideIcons()
}

function updatePromptPlaceholder() {
  el('promptInput').placeholder = currentView === 'single'
    ? (currentAgent ? `Send task to ${currentAgent}...` : 'Select an agent first...')
    : 'Enter task instructions for all agents...'
}


// ── Send Task ──────────────────────────────────────────────────────────────────
function buildTaskWithContext({ task, agentId, agents, isCollab }) {
  if (!isCollab) return task
  const ordered = agents.length ? agents : (agentId ? [agentId] : [])
  const others = ordered.filter(id => id !== agentId)
  const isOnly = ordered.length === 1 || (agentId === ordered[0] && agentId === ordered[ordered.length - 1])
  const role = isOnly ? 'Complete the entire task.'
    : agentId === ordered[0] ? 'Lead agent: start the task and handle the first part.'
    : agentId === ordered[ordered.length - 1] ? 'Wrap-up agent: complete the final part of the task.'
    : 'Work on your assigned part of the task.'
  return [task, '', 'Collaboration: yes', `Assigned agent: ${agentId || 'queue'}`, `Other agents: ${others.join(', ') || 'none'}`, `Role: ${role}`].join('\n')
}

async function sendTask() {
  const input = el('promptInput')
  const taskText = input.value.trim()
  if (!taskText) return showToast('Please enter a task', 'error')
  const post = body => apiFetch('/api/send-task', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  try {
    if (researchModeEnabled) {
      const data = await (await post({ task: taskText, research_mode: true })).json()
      if (data.success) { input.value = ''; showToast('Research task queued', 'success'); openTasksPanel() }
      else showToast(data.error || 'Failed to queue task', 'error')
      return
    }
    let targets = [], allAgents = [], isCollab = false
    if (currentView === 'single') {
      if (!currentAgent) return showToast('Please select an agent first', 'error')
      targets = allAgents = [currentAgent]
    } else {
      const res = await apiFetch('/agents', { cache: 'no-store' })
      if (!res.ok) throw new Error()
      allAgents = (await res.json()).map(a => a.id)
      if (!allAgents.length) return showToast('No agents connected', 'error')
      targets = allAgents
      isCollab = true
    }
    const originalValue = input.value
    input.value = ''
    const responses = await Promise.all(targets.map(agentId =>
      post({ task: buildTaskWithContext({ task: taskText, agentId, agents: allAgents, isCollab }), agent_id: agentId, research_mode: false })
    ))
    const failures = []
    let successes = 0
    for (const res of responses) {
      let result = null
      try { result = await res.json() } catch {}
      if (result && result.success) { successes++ }
      else { failures.push((result && result.error) || `Server error: ${res.status}`) }
    }
    if (failures.length) { showToast(failures[0], 'error'); input.value = originalValue; return }
    showToast(successes > 1 ? `Task sent to ${successes} agents` : 'Task sent successfully', 'success')
  } catch { showToast('Network error - check server connection', 'error') }
}

el('promptSend').onclick = sendTask
el('promptInput').addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); sendTask() } })


// ── Modals ─────────────────────────────────────────────────────────────────────
function closeCustomAlert() { el('customAlert').classList.remove('open') }
function showCustomAlert(title, message) {
  el('customAlertTitle').textContent = title
  el('customAlertBody').textContent = message
  refreshLucideIcons()
  el('customAlert').classList.add('open')
}
function showTaskModal(agentId, task) { showCustomAlert(`${agentId} - Task`, task) }


// ── Research Modal ─────────────────────────────────────────────────────────────
function openResearchModal(taskId) {
  currentResearchTaskId = taskId
  el('researchModal').classList.add('open')
  fetchAndRenderResearch()
  researchPollInterval = setInterval(fetchAndRenderResearch, 3000)
}

function closeResearchModal() {
  currentResearchTaskId = null
  el('researchModal').classList.remove('open')
  clearInterval(researchPollInterval)
  researchPollInterval = null
}

async function fetchAndRenderResearch() {
  if (!currentResearchTaskId) return
  try {
    const res = await apiFetch('/api/research/' + currentResearchTaskId)
    if (!res.ok) return
    const data = await res.json()
    renderResearchPanel(data)
    const allDone = data.subtasks && data.subtasks.length > 0 && data.subtasks.every(s => s.status === 'complete')
    if (allDone && researchPollInterval) { clearInterval(researchPollInterval); researchPollInterval = null }
  } catch {}
}

function renderResearchPanel(data) {
  const parent = data.parent || {}
  const titleEl = el('researchModalTitle')
  if (titleEl) titleEl.textContent = stripTaskMetadata(parent.task) || parent.task || 'Research Report'
  const body = el('researchModalBody')
  if (!body) return
  let html = (data.subtasks || []).map(renderResearchSection).join('')
  if (parent.result_json) {
    try {
      const pd = JSON.parse(parent.result_json)
      if (pd.summary) html += `<div class="researchSection researchSummary"><div class="researchSectionLabel">Summary</div><div class="researchSectionBody">${escapeHtml(pd.summary)}</div></div>`
    } catch {}
  }
  body.innerHTML = html || '<div class="researchEmpty">Research in progress — results will appear here as agents complete their sections.</div>'
}

function renderResearchSection(s) {
  const label = escapeHtml(s.section_label || s.task || 'Section')
  const agent = escapeHtml(s.assigned_agent || '')
  if (s.status !== 'complete' || !s.result_json) {
    const dot = s.status === 'assigned'
      ? `<span class="researchStatusDot researching"></span>Researching — ${agent}`
      : `<span class="researchStatusDot queued"></span>Queued`
    return `<div class="researchSection researchSectionPending"><div class="researchSectionLabel">${label}</div><div class="researchSectionStatus">${dot}</div></div>`
  }
  let bodyText = '', sources = []
  try { const r = JSON.parse(s.result_json); bodyText = r.body || ''; sources = r.sources || [] } catch {}
  const srcs = sources.length
    ? `<div class="researchSources"><div class="researchSourcesLabel">Sources</div><ul class="researchSourcesList">${sources.map(src => {
        const name = escapeHtml(src.name || src.url || '')
        return src.url ? `<li><a href="${escapeHtml(src.url)}" target="_blank" rel="noreferrer">${name}</a></li>` : `<li>${name}</li>`
      }).join('')}</ul></div>`
    : ''
  return `<div class="researchSection"><div class="researchSectionLabel">${label}</div><div class="researchSectionAgent"><span class="researchStatusDot done"></span>${agent}</div><div class="researchSectionBody">${escapeHtml(bodyText)}</div>${srcs}</div>`
}


// ── Global Events ──────────────────────────────────────────────────────────────
document.addEventListener('click', e => {
  if (e.target.id === 'customAlert') closeCustomAlert()
  const tp = el('tasksPanel')
  if (tp && tp.classList.contains('open') && !e.target.closest('#tasksPanel') && !e.target.closest('#tasksBtn')) closeTasksPanel()
  const rm = el('researchModal')
  if (rm && rm.classList.contains('open') && !e.target.closest('#researchModal') && !e.target.closest('.viewResultsBtn')) closeResearchModal()
})

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    if (el('researchModal').classList.contains('open')) closeResearchModal()
    if (el('tasksPanel').classList.contains('open')) closeTasksPanel()
    if (el('customAlert').classList.contains('open')) closeCustomAlert()
    return
  }
  if (e.key === 's' && (e.metaKey || e.ctrlKey)) {
    e.preventDefault()
    switchView(currentView === 'single' ? 'supervisor' : 'single')
  }
})


// ── Agent Controls ─────────────────────────────────────────────────────────────
async function stopAgent(agentId) {
  try {
    const r = await (await apiFetch(`/api/agent/${agentId}/stop`, { method: 'POST' })).json()
    showToast(r.message || r.error, r.success ? 'success' : 'error')
  } catch { showToast('Failed to connect to server', 'error') }
}

async function disconnectAgent(agentId) {
  if (!confirm(`Remove ${agentId}? This will disconnect and delete its data.`)) return
  function finalize(msg, type) {
    showToast(msg, type)
    if (currentAgent === agentId) { currentAgent = null; updatePromptPlaceholder(); updateState(); refreshScreen() }
    fetchAgents()
    if (currentView === 'supervisor') updateSupervisorGrid()
  }
  try {
    const res = await apiFetch(`/api/agent/${encodeURIComponent(agentId)}/disconnect`, { method: 'POST' })
    let result = null
    try { result = await res.json() } catch {}
    if (!res.ok) {
      if (res.status === 404) { finalize(`Agent ${agentId} already disconnected`, 'success'); return }
      showToast((result && result.error) || 'Server rejected disconnect request', 'error')
      return
    }
    finalize((result && result.message) || `Agent ${agentId} disconnected`, 'success')
  } catch { showConnectionOverlay() }
}

async function logout() {
  try { await apiFetch('/logout', { method: 'POST' }) } catch {}
  localStorage.removeItem('token')
  location.href = '/login'
}

async function stopServer() {
  if (!confirm('Shutdown the Harmony server? All agents will be disconnected.')) return
  try { await apiFetch('/api/server/stop', { method: 'POST' }) } catch {}
  showGoodbye()
}


// ── Empty States ───────────────────────────────────────────────────────────────
function showSingleEmptyState() {
  if (currentView !== 'single') return
  el('screen').style.display = 'none'
  el('viewport').classList.add('empty')
  el('singleEmptyState').style.display = 'flex'
  refreshLucideIcons()
}
function hideSingleEmptyState() { el('singleEmptyState').style.display = 'none'; el('viewport').classList.remove('empty') }


// ── Toggles ────────────────────────────────────────────────────────────────────
function toggleResearchMode() {
  researchModeEnabled = !researchModeEnabled
  el('researchToggle').classList.toggle('active', researchModeEnabled)
  el('researchToggle').title = researchModeEnabled ? 'Research mode ON - Click to disable' : 'Toggle research mode'
  refreshLucideIcons()
}

function toggleFullscreen() {
  const icon = document.querySelector('.fullscreenBtn i')
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().catch(() => showToast('Fullscreen not available', 'error'))
    if (icon) icon.setAttribute('data-lucide', 'minimize-2')
  } else {
    document.exitFullscreen()
    if (icon) icon.setAttribute('data-lucide', 'maximize-2')
  }
  refreshLucideIcons()
}
document.addEventListener('fullscreenchange', () => {
  const icon = document.querySelector('.fullscreenBtn i')
  if (icon) { icon.setAttribute('data-lucide', document.fullscreenElement ? 'minimize-2' : 'maximize-2'); refreshLucideIcons() }
})


// ── Supervisor View ────────────────────────────────────────────────────────────
function updateSupervisorStats(agents) {
  const active = agents.filter(a => a.status === 'working').length
  el('totalAgents').textContent = agents.length
  el('activeAgents').textContent = active
  el('idleAgents').textContent = agents.length - active
}

async function updateSupervisorGrid() {
  if (currentView !== 'supervisor') return
  try {
    const res = await apiFetch('/agents', { cache: 'no-store' })
    if (!res.ok) throw new Error()
    const agents = await res.json()
    const grid = el('supervisorGrid')
    if (!agents.length) {
      grid.innerHTML = `<div style="grid-column:1/-1;text-align:center;padding:60px 20px;color:var(--muted);font-size:16px;font-style:italic;">No agents connected</div>`
      el('emptyState').style.display = 'none'
      showConnectionOverlay()
      return
    }
    grid.style.display = 'flex'
    el('emptyState').style.display = 'none'
    hideConnectionOverlay()
    const details = await Promise.all(agents.map(async a => {
      try {
        const r = await apiFetch(`/agent/${a.id}`, { cache: 'no-store' })
        return r.ok ? await r.json() : { id: a.id, status: 'idle', task: null, status_text: 'Idle' }
      } catch { return { id: a.id, status: 'error', status_text: 'Connection Error' } }
    }))
    updateSupervisorStats(details)
    const newIds = details.map(a => a.id).sort().join(',')
    const oldIds = lastAgentData.map(a => a.id).sort().join(',')
    if (newIds !== oldIds) { grid.innerHTML = ''; agentTileElements = {}; details.forEach(a => createAgentTile(a, grid)) }
    else details.forEach(a => updateAgentTile(a))
    lastAgentData = details
  } catch { showToast('Connection lost - server may be down', 'error') }
}

function createAgentTile(agent, grid) {
  const tile = document.createElement('div')
  tile.className = 'agentTile'
  tile.id = `tile-${agent.id}`
  tile.onclick = () => { currentAgent = agent.id; switchView('single'); updateState(); refreshScreen() }
  agentTileElements[agent.id] = tile
  updateAgentTileContent(agent, tile)
  grid.appendChild(tile)
  refreshLucideIcons()
}
function updateAgentTile(agent) { const t = agentTileElements[agent.id]; if (t) updateAgentTileContent(agent, t) }

async function updateAgentTileContent(agent, tile) {
  let screenshotUrl = null
  try {
    const res = await apiFetch(`/screen/${agent.id}?t=${Date.now()}`, { cache: 'no-store' })
    if (res.ok) screenshotUrl = URL.createObjectURL(await res.blob())
  } catch {}
  const task = stripTaskMetadata(agent.task) || 'No active task'
  const step = agent.step && agent.step.action
    ? describeStep({ action: agent.step.action, coordinate: agent.step.coordinate, value: agent.step.value })
    : agent.status === 'working' ? 'Working...' : 'No task'
  const stepDesc = truncateText(step, 44)
  const eid = escapeHtml(agent.id)
  const escapedTask = task.replace(/`/g, '\\`').replace(/\$/g, '\\$')
  const hasTask = agent.task && agent.status === 'working'
  const escapedReason = (agent.step && agent.step.reasoning || '').replace(/`/g, '\\`').replace(/\$/g, '\\$')
  tile.innerHTML = `
    <div class="agentTileContent">
      <div class="agentTileHeader">
        <div class="agentTileId">${eid}</div>
        <div class="agentTileTask" onclick="event.stopPropagation();showTaskModal('${eid}',\`${escapedTask}\`)" title="Click to view task">${escapeHtml(task)}</div>
      </div>
      <div class="agentMiniWindow">
        <div class="agentMiniTop">
          <div class="agentMiniWin red"></div><div class="agentMiniWin yellow"></div><div class="agentMiniWin green"></div>
          <div class="agentMiniAddress" title="${escapeHtml(stepDesc)}">${escapeHtml(stepDesc)}</div>
        </div>
        <div class="agentMiniViewport" style="position:relative">
          ${screenshotUrl ? `<img src="${screenshotUrl}" class="agentTileScreenImg" alt="Agent screen">` : `<div class="agentTileScreenPlaceholder"></div>`}
        </div>
      </div>
    </div>
    <div class="tileControlsRow">
      ${hasTask && agent.step && agent.step.reasoning ? `<button class="tileControlBtn" onclick="event.stopPropagation();showCustomAlert('${eid} Thoughts',\`${escapedReason}\`)">Show Thought</button>` : ''}
      ${hasTask ? `<button class="tileControlBtn iconOnly" onclick="event.stopPropagation();stopAgent('${eid}')" title="Pause"><i data-lucide="pause"></i></button>` : ''}
      <button class="tileControlBtn danger" onclick="event.stopPropagation();disconnectAgent('${eid}')" title="Disconnect"><i data-lucide="x"></i>Disconnect</button>
    </div>`
  setTimeout(refreshLucideIcons, 100)
}


// ── Tasks Panel ────────────────────────────────────────────────────────────────
function openTasksPanel() {
  el('tasksPanel').classList.add('open')
  el('tasksBtn').classList.add('active')
  fetchAndRenderTasksPanel()
  tasksPanelPollInterval = setInterval(fetchAndRenderTasksPanel, 5000)
}
function closeTasksPanel() {
  el('tasksPanel').classList.remove('open')
  el('tasksBtn').classList.remove('active')
  clearInterval(tasksPanelPollInterval)
  tasksPanelPollInterval = null
}
function toggleTasksPanel() { el('tasksPanel').classList.contains('open') ? closeTasksPanel() : openTasksPanel() }

async function deleteTask(taskId) {
  const item = el('taskItem-' + taskId)
  if (item) item.style.opacity = '0.4'
  try {
    const res = await apiFetch('/api/tasks/' + taskId, { method: 'DELETE' })
    if (res.ok) { if (item) item.remove() }
    else if (item) item.style.opacity = '1'
  } catch { if (item) item.style.opacity = '1' }
}

async function fetchAndRenderTasksPanel() {
  try {
    const res = await apiFetch('/api/tasks', { cache: 'no-store' })
    if (res.ok) renderTasksList(await res.json())
  } catch {}
}

function renderTasksList(tasks) {
  const container = el('tasksPanelBody')
  if (!tasks || !tasks.length) { container.innerHTML = '<div class="tasksEmptyState">No tasks yet</div>'; return }
  container.innerHTML = tasks.map(task => {
    const status = task.status || 'queued'
    const icon = status === 'complete' ? '<span class="taskStatusIcon done">✓</span>'
      : status === 'assigned' ? '<span class="taskStatusIcon active"></span>'
      : '<span class="taskStatusIcon queued"></span>'
    const label = escapeHtml(stripTaskMetadata(task.task) || task.task || '')
    const isResearch = task.research_mode && !task.parent_task_id
    return `<div class="taskItem" id="taskItem-${task.id}">
      <div class="taskItemTop">${icon}<div class="taskItemText">${label}</div><button class="taskDeleteBtn" onclick="deleteTask(${task.id})" title="Delete task">✕</button></div>
      <div class="taskItemMeta">
        ${task.assigned_agent ? `<span class="taskItemAgent">${escapeHtml(task.assigned_agent)}</span>` : ''}
        ${task.created_at ? `<span class="taskItemTime">${formatRelativeTime(task.created_at)}</span>` : ''}
        ${isResearch ? `<button class="viewResultsBtn" onclick="openResearchModal(${task.id})">Results ↗</button>` : ''}
      </div>
    </div>`
  }).join('')
}


// ── Init & Poll ────────────────────────────────────────────────────────────────
function showLoading() { el('statusCap').textContent = 'Connecting...' }

function ensureLucideReady(retries) {
  retries = retries !== undefined ? retries : 30
  if (typeof lucide !== 'undefined') { lucide.createIcons(); return }
  if (retries > 0) setTimeout(() => ensureLucideReady(retries - 1), 100)
}

async function initialize() {
  if (isInitialized) return
  showLoading()
  try {
    await fetchAgents()
    if (currentAgent) await Promise.all([updateState(), refreshScreen()])
    updatePromptPlaceholder()
    ensureLucideReady()
    isInitialized = true
  } catch {}
}

function scheduleUpdate(fn, ms) {
  async function run() {
    try { await fn(); errorCount = 0; setTimeout(run, ms) }
    catch { errorCount++; setTimeout(run, Math.min(ms * Math.pow(2, errorCount - 1), 10000)) }
  }
  run()
}

initialize()
window.addEventListener('load', ensureLucideReady)
checkServerStatus()
scheduleUpdate(fetchAgents, 2000)
scheduleUpdate(updateState, 300)
scheduleUpdate(function() { if (currentAgent) return refreshScreen() }, 500)
scheduleUpdate(function() { if (currentView === 'supervisor') return updateSupervisorGrid() }, 1500)
scheduleUpdate(checkServerStatus, 5000)
