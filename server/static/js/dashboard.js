const $=id=>document.getElementById(id)
let currentAgent=null
let lastImgUrl=null
const serviceAccountInfo = (window.harmonyServiceAccount || {hasKey:false,email:""})

function normalizeServerBase(raw) {
  if(!raw) return null
  const trimmed = raw.trim().replace(/\/+$/, '')
  if(!trimmed) return null
  if(/^https?:\/\//i.test(trimmed)) return trimmed
  return `http://${trimmed}`
}

const apiBases = (() => {
  const bases = []
  const serverParam = new URLSearchParams(window.location.search).get('server')
  const normalized = normalizeServerBase(serverParam)
  if(normalized) {
    bases.push(normalized)
  }

  if(window.location.protocol !== 'file:') {
    bases.push(window.location.origin)
    if(window.location.port !== '1234' && window.location.hostname) {
      bases.push(`${window.location.protocol}//${window.location.hostname}:1234`)
    }
  } else {
    bases.push('http://localhost:1234')
    bases.push('http://127.0.0.1:1234')
  }
  return Array.from(new Set(bases))
})()

const THEME_STORAGE_KEY = 'harmonyTheme'
const DEFAULT_THEME = 'carbon'

function applyTheme(theme) {
  const useAlt = theme === 'carbon'
  document.body.classList.toggle('theme-carbon', useAlt)
}

function initTheme() {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY)
    applyTheme(stored || DEFAULT_THEME)
  } catch(e) {
    applyTheme(DEFAULT_THEME)
  }
}

window.setHarmonyTheme = function(theme) {
  const normalized = theme === 'default' ? 'default' : 'carbon'
  if(normalized === 'default') {
    localStorage.removeItem(THEME_STORAGE_KEY)
  } else {
    localStorage.setItem(THEME_STORAGE_KEY, normalized)
  }
  applyTheme(normalized)
}

initTheme()

async function apiFetch(path, options) {
  let lastError = null
  for(const base of apiBases) {
    try {
      return await fetch(`${base}${path}`, options)
    } catch (e) {
      lastError = e
    }
  }
  throw lastError || new Error('Network error')
}

function coord(c){return Array.isArray(c)&&c.length===2?{x:c[0],y:c[1]}:{x:null,y:null}}

function sentence(s){
  if(!s||!s.action)return "Waiting…"
  const a=s.action.toLowerCase()
  const {x,y}=coord(s.coordinate)
  if(a==="left_click"||a==="click"||a==="double_click"||a==="right_click")return x!=null?`${a.replace("_"," ")} at ${x}, ${y}`:"Clicking"
  if(a==="scroll_down")return "Scrolling down"
  if(a==="scroll_up")return "Scrolling up"
  if(a==="scroll")return `Scrolling ${s.value||""}`.trim()
  if(a==="type")return `Typing "${(s.value||"").substring(0,30)}${(s.value||"").length>30?"...":""}"`
  if(a==="press_key")return `Pressing ${s.value||"key"}`
  if(a==="hotkey")return `Hotkey ${Array.isArray(s.value)?s.value.join("+"):s.value||""}`
  if(a==="wait")return "Waiting..."
  if(a==="none")return "Done"
  return s.action
}

function stripTaskMeta(taskText) {
  if(!taskText) return ""
  const markers = ["\n\nCollaboration:", "\n\nAssigned agent:", "\n\nOther agents:", "\n\nShared workspace:", "\n\nRole:"]
  const cutPoints = markers.map(marker => taskText.indexOf(marker)).filter(index => index !== -1)
  if(!cutPoints.length) return taskText.trim()
  return taskText.slice(0, Math.min(...cutPoints)).trim()
}

function extractDocId(url) {
  if(!url) return null
  const match = url.match(/\/document\/d\/([a-zA-Z0-9_-]+)/)
  return match ? match[1] : null
}

async function refreshScreen(){
  const browserFrame = document.querySelector('.browserFrame')
  const browserTop = document.querySelector('.browserTop')
  const statusCap = $("statusCap")

  function showWaiting() {
    $("screen").style.display='none'
    $("waitingState").style.display='flex'
    $("waitingAgentId").textContent = currentAgent || 'No agent selected'
    $("viewport").classList.add('empty')
    browserFrame.classList.add('waiting')
    browserTop.style.display='none'
    statusCap.style.display='none'
    // Task panel visibility is controlled by updateState()
  }

  if(!currentAgent) {
    showWaiting()
    return
  }

  try {
    const r=await apiFetch(`/screen/${currentAgent}?t=${Date.now()}`,{cache:"no-store"})
    if(!r.ok) throw new Error(`Screen fetch failed: ${r.status}`)

    const b=await r.blob()
    const u=URL.createObjectURL(b)
    if(lastImgUrl)URL.revokeObjectURL(lastImgUrl)
    lastImgUrl=u

    $("screen").src=u
    $("screen").style.display='block'
    $("waitingState").style.display='none'
    $("viewport").classList.remove('empty')
    browserFrame.classList.remove('waiting')
    browserTop.style.display='flex'
    statusCap.style.display='block'
    // Task panel visibility is controlled by updateState()
  } catch(e) {
    console.warn('Screen refresh failed:', e.message)
    showWaiting()
  }
}

function renderAgentState(data){
  const taskPanel = $("taskStatusPanel")
  const displayTask = stripTaskMeta(data.task)
  $("taskStatusText").textContent=displayTask||"No active task"
  $("statusCap").textContent=data.status_text||data.status||"Idle"
  $("actionTop").textContent=sentence(data.step)

  if(taskPanel) {
    if(displayTask && data.status === 'working') {
      taskPanel.style.display='flex'
    } else {
      taskPanel.style.display='none'
    }
  }

  if(data.step?.reasoning) {
    $("singleReasoningText").textContent=data.step.reasoning
  } else {
    $("singleReasoningText").textContent=data.status_text || "Waiting for agent activity..."
  }
}

async function updateState(){
  const taskPanel = $("taskStatusPanel")

  if(!currentAgent) {
    $("taskStatusText").textContent="No active task"
    $("statusCap").textContent="Idle"
    $("actionTop").textContent="Select an agent..."
    $("singleReasoningText").textContent="Waiting for agent activity..."
    if(taskPanel) taskPanel.style.display='none'
    return
  }

  try {
    const r=await apiFetch(`/agent/${currentAgent}`,{cache:"no-store"})
    if(!r.ok) throw new Error(`Agent state fetch failed: ${r.status}`)

    const d=await r.json()
    renderAgentState(d)
  } catch(e) {
    console.warn('State update failed:', e.message)
  }
}

let agentsList = []

async function fetchAgents(){
  try {
    const r=await apiFetch("/agents",{cache:"no-store"})
    if(!r.ok) throw new Error(`Agents fetch failed: ${r.status}`)

    const agents=await r.json()
    agentsList = agents

    if(agents.length === 0) {
      $("selectedAgent").textContent = "No agents"
      showConnectionOverlay()
      return
    } else {
      hideConnectionOverlay()
      hideSingleEmptyState()
    }

    // Auto-select first agent if none selected
    if(!currentAgent && agents.length > 0){
      currentAgent=agents[0].id
    }

    updateAgentDropdown()
  } catch(e) {
    console.error('Failed to fetch agents:', e.message)
    showToast('Connection lost - server may be down', 'error')
  }
}

function updateAgentDropdown(){
  if(agentsList.length === 0) return

  // Update selected agent display
  $("selectedAgent").textContent = currentAgent || "No agent"

  // Populate dropdown menu
  const menu = $("agentDropdownMenu")
  menu.innerHTML = ""

  // Add header
  const header = document.createElement("div")
  header.className = "agentDropdownHeader"
  header.textContent = "Select Agent"
  menu.appendChild(header)

  // Add divider
  const divider = document.createElement("div")
  divider.className = "agentDropdownDivider"
  menu.appendChild(divider)

  agentsList.forEach(agent => {
    const option = document.createElement("div")
    option.className = "agentOption"
    if(agent.id === currentAgent) option.classList.add("active")

    const title = document.createElement("div")
    title.className = "agentOptionTitle"
    title.textContent = agent.id

    const check = document.createElementNS("http://www.w3.org/2000/svg", "svg")
    check.classList.add("agentOptionCheck")
    check.setAttribute("viewBox", "0 0 24 24")
    check.setAttribute("fill", "none")
    check.setAttribute("stroke", "currentColor")
    check.setAttribute("stroke-width", "3")
    check.setAttribute("stroke-linecap", "round")
    check.setAttribute("stroke-linejoin", "round")
    const path = document.createElementNS("http://www.w3.org/2000/svg", "polyline")
    path.setAttribute("points", "20 6 9 17 4 12")
    check.appendChild(path)

    option.appendChild(title)
    option.appendChild(check)

    option.onclick = () => {
      currentAgent = agent.id
      updateAgentDropdown()
      updateState()
      refreshScreen()
      updatePromptPlaceholder()
      closeAgentDropdown()
    }
    menu.appendChild(option)
  })
}

function toggleAgentDropdown(){
  const selector = $("agentSelector")
  const menu = $("agentDropdownMenu")
  selector.classList.toggle("open")
  menu.classList.toggle("open")
}

function closeAgentDropdown(){
  $("agentSelector").classList.remove("open")
  $("agentDropdownMenu").classList.remove("open")
}

// Dropdown controls
$("agentSelector").onclick = (e) => {
  e.stopPropagation()
  toggleAgentDropdown()
}

document.addEventListener("click", (e) => {
  if(!e.target.closest(".agentDropdown")) {
    closeAgentDropdown()
  }
})

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

  // Show/hide views and agent dropdown
  const promptMeta = $("promptMeta")

  if(viewName === 'single') {
    $("singleView").classList.add('active')
    $("supervisorView").classList.remove('active')
    $("agentDropdown").style.display = 'flex'
    if(promptMeta) promptMeta.style.display = 'none'
    currentView = 'single'
    updatePromptPlaceholder()
  } else {
    $("singleView").classList.remove('active')
    $("supervisorView").classList.add('active')
    $("agentDropdown").style.display = 'none'
    if(promptMeta) promptMeta.style.display = 'flex'
    currentView = 'supervisor'
    updateSupervisorGrid()
    updatePromptPlaceholder()
  }

  // Reinitialize icons
  if(typeof lucide !== 'undefined') lucide.createIcons()
}

function updatePromptPlaceholder() {
  const input = $("promptInput")
  if(currentView === 'single') {
    input.placeholder = currentAgent ? 
      `Send task to ${currentAgent}...` : 
      'Select an agent first...'
  } else {
    input.placeholder = 'Enter task instructions for all agents...'
  }
}

function buildTaskWithContext({task, agentId, agents, workspaceUrl, isResearch, isCollab, docId}) {
  const orderedAgents = agents.length ? agents : (agentId ? [agentId] : [])
  const introAgent = orderedAgents[0]
  const closingAgent = orderedAgents[orderedAgents.length - 1]
  const otherAgents = orderedAgents.filter(id => id !== agentId)

  let roleNote = "Own a subject: pick a unique subtopic, write one findings paragraph with source credit."
  if(orderedAgents.length === 1) {
    roleNote = "Solo: write Instructions/Approach, all findings paragraphs (one per subject with citations), Conclusion, Bibliography, then clean grammar/formatting."
  } else if(agentId === introAgent && agentId === closingAgent) {
    roleNote = "Solo: write Instructions/Approach, all findings paragraphs (one per subject with citations), Conclusion, Bibliography, then clean grammar/formatting."
  } else if(agentId === introAgent) {
    roleNote = "Lead: write the Instructions/Approach paragraph. If only two agents, also take one findings paragraph."
  } else if(agentId === closingAgent) {
    roleNote = "Wrap-up: write the Conclusion paragraph, compile the Bibliography, then do a cleanup pass (grammar, spacing, headings/bold) without changing facts. If only two agents, also take one findings paragraph."
  }

  const docRules = [
    "- Google Doc is shared; agents use read_doc/write_doc API only (no UI opening).",
    "- Structure: Title (only heading), Notes (bullets, short, with source names), Introduction (short), Findings (one short paragraph per subject with inline source), Conclusion (short), Bibliography (Author or Org. (Year, Month Day). Title. Site. URL).",
    "- Keep paragraphs brief with blank lines; bullets start with '-'.",
    "- Start by reading the doc; do not overwrite existing text."
  ]

  const lines = [
    task,
    "",
    "Collaboration: " + (isCollab ? "yes" : "no"),
    "Assigned agent: " + (agentId || "queue"),
    "Other agents: " + (otherAgents.length ? otherAgents.join(", ") : "none"),
    "Shared workspace: " + (workspaceUrl || "not provided"),
    "Role: " + roleNote
  ]

  if(isCollab && isResearch) {
    lines.push(
      "",
      "Collab research instructions:",
      "- Use read_doc/write_doc only; do not open the doc UI.",
      "- Notes: bullets with source names; Findings: one short paragraph per subject; keep spacing clean.",
      "- Team split: first agent writes Instructions/Approach; middle agents each write one findings paragraph; last agent writes Conclusion + Bibliography + cleanup."
    )
  }

  if(isResearch) {
    lines.push(
      "",
      "Document setup:",
      workspaceUrl
        ? "- Shared Google Doc provided. Use API actions only; do not open the URL."
        : "- No shared doc provided. Ask once if a doc link is missing."
    )
    lines.push("", "Document rules:", ...docRules)
  }

  return lines.join("\n")
}

async function sendTask() {
  const input = $("promptInput")
  if(!input) {
    console.error('Prompt input element not found')
    return
  }

  const task = input.value.trim()

  if(!task) {
    showToast('Please enter a task', 'error')
    return
  }

  let agentId = null
  let cleanTask = task

  try {
    const workspaceUrl = localStorage.getItem("harmonyWorkspaceUrl") || ""
    const docId = extractDocId(workspaceUrl) || localStorage.getItem("harmonyDocId") || null
    let targetAgents = []
    let collabAgents = []
    let isCollab = false

    if(currentView === 'single') {
      if(!currentAgent) {
        showToast('Please select an agent first', 'error')
        return
      }
      agentId = currentAgent
      targetAgents = [agentId]
      collabAgents = [agentId]
    } else {
      const r = await apiFetch("/agents", {cache: "no-store"})
      if(!r.ok) throw new Error(`Agents fetch failed: ${r.status}`)
      const agents = await r.json()
      collabAgents = agents.map(agent => agent.id)
      if(collabAgents.length === 0) {
        showToast('No agents connected', 'error')
        return
      }
      targetAgents = collabAgents
      isCollab = true
    }

    const payloads = targetAgents.map(targetId => ({
      task: buildTaskWithContext({
        task: cleanTask,
        agentId: targetId,
        agents: collabAgents.length ? collabAgents : (agentId ? [agentId] : []),
        workspaceUrl,
        isResearch: researchModeEnabled,
        isCollab,
        docId
      }),
      agent_id: targetId,
      research_mode: researchModeEnabled,
      doc_id: docId
    }))
    const responses = await Promise.all(payloads.map(body => apiFetch('/api/send-task', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)
    })))

    // Always clear input after sending (regardless of success/failure)
    // This provides better UX - user can retype if there was an error
    const originalTask = input.value
    input.value = ''

    const failures = []
    let successCount = 0

    for(const response of responses) {
      if(!response.ok) {
        let errorMsg = `Server error: ${response.status}`
        try {
          const errorData = await response.json()
          errorMsg = errorData.error || errorMsg
        } catch(e) {
          // Response wasn't JSON, use status code
        }
        failures.push(errorMsg)
        continue
      }

      let result = null
      try {
        const responseText = await response.text()
        result = responseText ? JSON.parse(responseText) : null
      } catch(e) {
        console.error('Task send response parse error:', e)
        failures.push('Unexpected server response')
        continue
      }

      if(result && result.success) {
        successCount += 1
      } else {
        failures.push((result && result.error) || 'Failed to send task')
      }
    }

    if(failures.length) {
      showToast(failures[0], 'error')
      input.value = originalTask
      return
    }

    if(successCount > 1) {
      showToast(`Task sent to ${successCount} agents`, 'success')
    } else {
      showToast('Task sent successfully', 'success')
    }
  } catch(e) {
    console.error('Task send error:', e)
    showToast('Network error - check server connection', 'error')
  }
}

// Keyboard shortcuts
document.addEventListener("keydown", e => {
  if(e.key === 's' && (e.metaKey || e.ctrlKey)) {
    e.preventDefault()
    switchView(currentView === 'single' ? 'supervisor' : 'single')
  }
})

function closeResultsModal() {
  const modal = $("resultsModal")
  modal.classList.remove('open')
}

// Workspace modal
function populateWorkspaceEmail() {
  const email = serviceAccountInfo.email || "service account email not found"
  const emailEl = $("workspaceEmail")
  if(emailEl) {
    emailEl.textContent = email
  }
  const info = $("workspaceKeyInfo")
  if(info) {
    if(serviceAccountInfo.hasKey && serviceAccountInfo.email) {
      info.className = ""
      info.innerHTML = ""
    } else {
      info.className = "workspaceInfoWarn"
      info.innerHTML = `Place <code>service-account.json</code> in <code>server/</code>, restart.`
    }
  }
}

function openWorkspacePanel() {
  populateWorkspaceEmail()
  const panel = $("workspacePanel")
  if(!panel) return
  const input = $("workspaceUrlInput")
  if(input) {
    input.value = localStorage.getItem("harmonyWorkspaceUrl") || ""
    input.focus()
  }
  panel.classList.add("open")
}

function closeWorkspacePanel() {
  const panel = $("workspacePanel")
  if(!panel) return
  panel.classList.remove("open")
}

function toggleWorkspacePanel() {
  const panel = $("workspacePanel")
  if(!panel) return
  if(panel.classList.contains("open")) {
    closeWorkspacePanel()
  } else {
    openWorkspacePanel()
  }
}

function copyWorkspaceEmail() {
  const email = serviceAccountInfo.email
  if(!email) {
    showToast("No service account email found", "error")
    return
  }
  navigator.clipboard.writeText(email).then(() => {
    showToast("Email copied", "success")
  }).catch(() => showToast("Copy failed", "error"))
}

function saveWorkspace() {
  const input = $("workspaceUrlInput")
  if(!input) return
  const url = (input.value || "").trim()
  const docId = extractDocId(url)

  if(url && !docId) {
    showToast("Paste a valid Google Doc URL", "error")
    return
  }

  if(url) {
    localStorage.setItem("harmonyWorkspaceUrl", url)
    if(docId) {
      localStorage.setItem("harmonyDocId", docId)
    }
  } else {
    localStorage.removeItem("harmonyWorkspaceUrl")
    localStorage.removeItem("harmonyDocId")
  }

  showToast(url ? "Workspace saved" : "Workspace cleared", "success")
  closeWorkspacePanel()
}

// Close panel when clicking outside or pressing Escape
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
  const panel = $("workspacePanel")
  const btn = $("workspaceBtn")
  if(panel && panel.classList.contains("open") && !e.target.closest('#workspacePanel') && !e.target.closest('#workspaceBtn')) {
    closeWorkspacePanel()
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
    if($("workspacePanel").classList.contains('open')) {
      closeWorkspacePanel()
    }
  }
})

// Prompt functionality
$("promptSend").onclick = sendTask

$("promptInput").addEventListener('keydown', e => {
  if(e.key === 'Enter') {
    e.preventDefault()
    sendTask()
  }
})

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

function ensureLucideReady(retries = 30) {
  if (typeof lucide !== 'undefined') {
    lucide.createIcons()
    return
  }
  if (retries > 0) {
    setTimeout(() => ensureLucideReady(retries - 1), 100)
  }
}

async function initialize() {
  if(isInitialized) return
  
  showLoading()
  
  try {
    await Promise.all([fetchAgents()])
    if(currentAgent) {
      await Promise.all([updateState(), refreshScreen()])
    }
    updatePromptPlaceholder()
    ensureLucideReady()
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
    const r = await apiFetch("/agents", {cache: "no-store"})
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
          apiFetch(`/agent/${agent.id}`, {cache: "no-store"})
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
    showToast('Connection lost - server may be down', 'error')
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
    const screenRes = await apiFetch(`/screen/${agent.id}?t=${Date.now()}`, {cache: "no-store"})
    if(screenRes.ok) {
      const blob = await screenRes.blob()
      screenshotUrl = URL.createObjectURL(blob)
    }
  } catch(e) {
    // Screenshot failed, use placeholder
  }
  
  function truncateText(text, maxLen) {
    if(!text) return ''
    return text.length > maxLen ? `${text.slice(0, maxLen - 1)}…` : text
  }

  let stepText = 'No task'
  if(agent.step?.action) {
    stepText = sentence({
      action: agent.step.action,
      coordinate: agent.step.coordinate,
      value: agent.step.value
    })
  } else if(agent.status === 'working') {
    stepText = 'Working...'
  }

  stepText = truncateText(stepText, 44)
  const displayTask = stripTaskMeta(agent.task)

  tile.innerHTML = `
    <div class="agentTileContent">
      <div class="agentTileHeader">
        <div class="agentTileId">${agent.id || 'Unknown'}</div>
        <div class="agentTileTask" onclick="event.stopPropagation(); showTaskModal('${agent.id}', \`${(displayTask || 'No active task').replace(/`/g, '\\`').replace(/\$/g, '\\$')}\`)" title="Click to view task">${displayTask || 'No active task'}</div>
      </div>

      <div class="agentMiniWindow">
        <div class="agentMiniTop">
          <div class="agentMiniWin red"></div>
          <div class="agentMiniWin yellow"></div>
          <div class="agentMiniWin green"></div>
          <div class="agentMiniAddress" title="${stepText}">${stepText}</div>
        </div>
        <div class="agentMiniViewport" style="position: relative;">
          ${screenshotUrl ?
            `<img src="${screenshotUrl}" class="agentTileScreenImg" alt="Agent screen">` :
            `<div class="agentTileScreenPlaceholder"></div>`
          }
        </div>
      </div>
    </div>
    ${createTileControls(agent)}
  `
  
  // Initialize Lucide icons after content update
  setTimeout(() => {
    if (typeof lucide !== 'undefined') {
      lucide.createIcons()
    }
  }, 100)
}

function createTileControls(agent) {
  const hasThought = agent.step?.reasoning
  const hasTask = agent.task && agent.status === 'working'

  return `
    <div class="tileControlsRow">
      ${hasTask && hasThought ? `
        <button class="tileControlBtn" onclick="event.stopPropagation(); showCustomAlert('${agent.id} Thoughts', \`${(agent.step.reasoning || '').replace(/`/g, '\\`').replace(/\$/g, '\\$')}\`)">
          Show Thought
        </button>
      ` : ''}
      ${hasTask ? `
        <button class="tileControlBtn iconOnly" onclick="event.stopPropagation(); stopAgent('${agent.id}')" title="Pause">
          <i data-lucide="pause"></i>
        </button>
      ` : ''}
      <button class="tileControlBtn danger" onclick="event.stopPropagation(); disconnectAgent('${agent.id}')" title="Disconnect">
        <i data-lucide="x"></i>
        Disconnect
      </button>
    </div>
  `
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

function showTaskModal(agentId, taskText) {
  showCustomAlert(`${agentId} - Task`, taskText)
}

async function stopAgent(agentId) {
  try {
    const response = await apiFetch(`/api/agent/${agentId}/stop`, {method: 'POST'})
    const result = await response.json()
    showToast(result.message || result.error, result.success ? 'success' : 'error')
  } catch(e) {
    showToast('Failed to connect to server', 'error')
  }
}

async function disconnectAgent(agentId) {
  if(!confirm(`Remove ${agentId}? This will disconnect and delete its data.`)) return
  try {
    const response = await apiFetch(`/api/agent/${encodeURIComponent(agentId)}/disconnect`, {method: 'POST'})
    let result = null
    try {
      result = await response.json()
    } catch(e) {
      // ignore parse errors, we'll fall back to a generic message
    }

    const finalizeDisconnect = (message, toastType) => {
      showToast(message, toastType)

      if(currentAgent === agentId) {
        currentAgent = null
        updatePromptPlaceholder()
        updateState()
        refreshScreen()
      }

      fetchAgents()
      if(currentView === 'supervisor') {
        updateSupervisorGrid()
      }
    }

    if(!response.ok) {
      if(response.status === 404) {
        finalizeDisconnect(`Agent ${agentId} already disconnected`, 'success')
        return
      }
      showToast((result && result.error) || 'Server rejected disconnect request', 'error')
      return
    }

    finalizeDisconnect((result && result.message) || `Agent ${agentId} disconnected`, 'success')
  } catch(e) {
    console.error('Disconnect failed:', e)
    showConnectionOverlay()
  }
}

async function stopServer() {
  if(!confirm('Shutdown the Harmony server? All agents will be disconnected.')) return
  try {
    await apiFetch('/api/server/stop', {method: 'POST'})
  } catch(e) {
    // Expected - server is shutting down
  }
  showGoodbye()
}

// Connection overlay functions
function showConnectionOverlay() {
  const overlay = $("connectionOverlay")
  overlay.classList.remove('error')
  overlay.classList.add('active')

  // Initialize Lucide icons
  if (typeof lucide !== 'undefined') {
    lucide.createIcons()
  }
}

function hideConnectionOverlay() {
  const overlay = $("connectionOverlay")
  overlay.classList.remove('active')
  overlay.classList.remove('error')
}

let toastTimeout = null
let lastToastMessage = null
let lastToastAt = 0

function showToast(message, type = 'info') {
  // Disable popup toasts; log to console only
  console.log(`[${type}] ${message}`)
}

function showGoodbye() {
  const overlay = $("connectionOverlay")
  const titleEl = overlay.querySelector('.connectionOverlayTitle')
  const subtitleEl = overlay.querySelector('.connectionOverlaySubtitle')
  const bodyEl = overlay.querySelector('.connectionOverlayBody')
  const actionsEl = overlay.querySelector('.connectionActions')
  const topActions = overlay.querySelector('.connectionOverlayTopActions')

  titleEl.textContent = 'See you next time!'
  subtitleEl.innerHTML = 'Harmony server has been shut down<div class="goodbyeActions"><button class="goodbyeBtn" onclick="location.reload()"><i data-lucide="refresh-cw"></i>Reconnect</button><a href="https://github.com/danielreiman/Harmony" target="_blank" class="goodbyeBtn"><svg viewBox="0 0 16 16" style="width:18px;height:18px;fill:currentColor;"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>View on GitHub</a></div><div style="margin-top:32px;color:rgba(255,255,255,0.6);font-size:13px;">To restart: <code style="background:rgba(255,255,255,0.1);padding:4px 8px;border-radius:4px;">python server/server.py</code></div>'
  bodyEl.style.display = 'none'
  if(actionsEl) actionsEl.style.display = 'none'
  if(topActions) topActions.style.display = 'none'

  overlay.classList.remove('error')
  overlay.classList.add('active', 'goodbye')

  if (typeof lucide !== 'undefined') {
    lucide.createIcons()
  }
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

// Research mode toggle
let researchModeEnabled = false

function toggleResearchMode() {
  // Require a Google Doc workspace link before enabling research
  if(!researchModeEnabled) {
    const workspaceUrl = localStorage.getItem("harmonyWorkspaceUrl") || ""
    const docId = extractDocId(workspaceUrl) || localStorage.getItem("harmonyDocId")
    const hasKey = !!serviceAccountInfo.hasKey
    if(!workspaceUrl || !docId || !hasKey) {
      alert("To use research, add a Google Docs URL in Workspace and place service-account.json in server/ (shared as Editor).")
      return
    }
  }

  researchModeEnabled = !researchModeEnabled
  const btn = $("researchToggle")
  if(researchModeEnabled) {
    btn.classList.add("active")
    btn.title = "Research mode ON - Click to disable"
  } else {
    btn.classList.remove("active")
    btn.title = "Toggle research mode"
  }
  if(typeof lucide !== 'undefined') lucide.createIcons()
}

// Fullscreen toggle
function toggleFullscreen() {
  if(!document.fullscreenElement) {
    document.documentElement.requestFullscreen().catch(err => {
      showToast("Fullscreen not available", "error")
    })
    const btn = document.querySelector(".fullscreenBtn i")
    if(btn) btn.setAttribute("data-lucide", "minimize-2")
  } else {
    document.exitFullscreen()
    const btn = document.querySelector(".fullscreenBtn i")
    if(btn) btn.setAttribute("data-lucide", "maximize-2")
  }
  if(typeof lucide !== 'undefined') lucide.createIcons()
}

document.addEventListener("fullscreenchange", () => {
  const btn = document.querySelector(".fullscreenBtn i")
  if(btn) {
    btn.setAttribute("data-lucide", document.fullscreenElement ? "minimize-2" : "maximize-2")
    if(typeof lucide !== 'undefined') lucide.createIcons()
  }
})

function updateSupervisorStats(agents) {
  const total = agents.length
  const active = agents.filter(agent => agent.status === 'working').length
  const idle = total - active

  // Update individual stat spans
  $("totalAgents").textContent = total
  $("activeAgents").textContent = active
  $("idleAgents").textContent = idle
}



// Initialize and start polling
initialize()
window.addEventListener('load', ensureLucideReady)
scheduleUpdate(() => Promise.all([fetchAgents(), loadAvailableAgents()]), 2000)
scheduleUpdate(updateState, 300)
scheduleUpdate(() => currentAgent && refreshScreen(), 500)
scheduleUpdate(() => {
  if(currentView === 'supervisor') {
    updateSupervisorGrid()
  }
}, 1500)
