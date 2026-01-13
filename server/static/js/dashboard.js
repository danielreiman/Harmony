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
  const browserFrame = document.querySelector('.browserFrame')
  const browserTop = document.querySelector('.browserTop')
  const taskPanel = $("taskStatusPanel")
  const statusCap = $("statusCap")

  function showWaiting() {
    $("screen").style.display='none'
    $("waitingState").style.display='flex'
    $("waitingAgentId").textContent = currentAgent || 'No agent selected'
    $("viewport").classList.add('empty')
    browserFrame.classList.add('waiting')
    browserTop.style.display='none'
    statusCap.style.display='none'
    // Keep task panel visible
    if(taskPanel) taskPanel.style.display='flex'
  }

  if(!currentAgent) {
    showWaiting()
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
    $("waitingState").style.display='none'
    $("viewport").classList.remove('empty')
    browserFrame.classList.remove('waiting')
    browserTop.style.display='flex'
    statusCap.style.display='block'
    if(taskPanel) taskPanel.style.display='flex'
  } catch(e) {
    console.warn('Screen refresh failed:', e.message)
    showWaiting()
  }
}

$("screen").onload=()=>{
  imgNat.w=$("screen").naturalWidth||imgNat.w
  imgNat.h=$("screen").naturalHeight||imgNat.h
}

async function updateState(){
  if(!currentAgent) {
    $("taskStatusText").textContent="No active task"
    $("statusCap").textContent="Idle"
    $("actionTop").textContent="Select an agent..."
    $("singleReasoningText").textContent="Waiting for agent activity..."
    return
  }

  try {
    const r=await fetch(`/agent/${currentAgent}`,{cache:"no-store"})
    if(!r.ok) throw new Error(`Agent state fetch failed: ${r.status}`)

    const d=await r.json()

    // Update task
    $("taskStatusText").textContent=d.task||"No active task"
    $("statusCap").textContent=d.status_text||d.status||"Idle"
    $("actionTop").textContent=sentence(d.step)

    // Update single view reasoning panel
    if(d.step?.reasoning) {
      $("singleReasoningText").textContent=d.step.reasoning
    } else {
      $("singleReasoningText").textContent=d.status_text || "Waiting for agent activity..."
    }
  } catch(e) {
    console.warn('State update failed:', e.message)
  }
}

let agentsList = []

async function fetchAgents(){
  try {
    const r=await fetch("/agents",{cache:"no-store"})
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
  if(viewName === 'single') {
    $("singleView").classList.add('active')
    $("supervisorView").classList.remove('active')
    $("agentDropdown").style.display = 'flex'
    currentView = 'single'
    updatePromptPlaceholder()
  } else {
    $("singleView").classList.remove('active')
    $("supervisorView").classList.add('active')
    $("agentDropdown").style.display = 'none'
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

async function sendTask() {
  const input = $("promptInput")
  const task = input.value.trim()

  if(!task) {
    showToast('Please enter a task', 'error')
    return
  }

  let agentId = null
  let cleanTask = task

  if(currentView === 'single') {
    if(!currentAgent) {
      showToast('Please select an agent first', 'error')
      return
    }
    agentId = currentAgent
  } else {
    const mentions = extractMentions(task)
    if(mentions.length > 0) {
      agentId = mentions[0]
      cleanTask = task.replace(/@[\w-]+/g, '').trim()
    }
  }

  try {
    const response = await fetch('/api/send-task', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({task: cleanTask, agent_id: agentId, research_mode: researchModeEnabled})
    })
    if(!response.ok) {
      const errorText = await response.text()
      console.error('Task send failed:', response.status, errorText)
      showToast(`Server error: ${response.status}`, 'error')
      return
    }
    const result = await response.json()
    if(result.success) {
      showToast(result.message, 'success')
      input.value = ''
    } else {
      showToast(result.error || 'Failed to send task', 'error')
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
  
  if(e.key === 'Enter') {
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
        <div class="agentTileId">${agent.id || 'Unknown'}</div>
        <div class="agentTileTask" onclick="event.stopPropagation(); showTaskModal('${agent.id}', \`${(agent.task || 'No active task').replace(/`/g, '\\`').replace(/\$/g, '\\$')}\`)" title="Click to view full task">${agent.task || 'No active task'}</div>
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

  return `
    <div class="tileControlsRow">
      ${hasThought ? `
        <button class="tileControlBtn" onclick="event.stopPropagation(); showCustomAlert('${agent.id} Thoughts', \`${(agent.step.reasoning || '').replace(/`/g, '\\`').replace(/\$/g, '\\$')}\`)">
          Show Thought
        </button>
      ` : ''}
      <button class="tileControlBtn iconOnly" onclick="event.stopPropagation(); stopAgent('${agent.id}')" title="Pause">
        <i data-lucide="pause"></i>
      </button>
      <button class="tileControlBtn iconOnly danger" onclick="event.stopPropagation(); disconnectAgent('${agent.id}')" title="Remove">
        <i data-lucide="x"></i>
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
  showCustomAlert(`${agentId} - Full Task`, taskText)
}

async function stopAgent(agentId) {
  try {
    const response = await fetch(`/api/agent/${agentId}/stop`, {method: 'POST'})
    const result = await response.json()
    showToast(result.message || result.error, result.success ? 'success' : 'error')
  } catch(e) {
    showToast('Failed to connect to server', 'error')
  }
}

async function disconnectAgent(agentId) {
  if(!confirm(`Remove ${agentId}? This will disconnect and delete its data.`)) return
  try {
    const response = await fetch(`/api/agent/${agentId}/disconnect`, {method: 'POST'})
    const result = await response.json()
    showToast(result.message || result.error, result.success ? 'success' : 'error')
  } catch(e) {
    showToast('Failed to connect to server', 'error')
  }
}

async function stopServer() {
  if(!confirm('Shutdown the Harmony server? All agents will be disconnected.')) return
  try {
    await fetch('/api/server/stop', {method: 'POST'})
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

function showToast(message, type = 'info') {
  const toast = $("toast")
  const msgEl = $("toastMessage")
  const iconEl = toast.querySelector('i')

  msgEl.textContent = message
  toast.className = 'toast show ' + type

  const iconMap = {info: 'info', error: 'alert-circle', success: 'check-circle'}
  iconEl.setAttribute('data-lucide', iconMap[type] || 'info')

  if (typeof lucide !== 'undefined') {
    lucide.createIcons()
  }

  setTimeout(() => toast.classList.remove('show'), 2000)
}

function showGoodbye() {
  const overlay = $("connectionOverlay")
  const titleEl = overlay.querySelector('.connectionOverlayTitle')
  const subtitleEl = overlay.querySelector('.connectionOverlaySubtitle')
  const bodyEl = overlay.querySelector('.connectionOverlayBody')

  titleEl.textContent = 'See you next time!'
  subtitleEl.innerHTML = 'Harmony server has been shut down<div class="goodbyeActions"><button class="goodbyeBtn" onclick="location.reload()"><i data-lucide="refresh-cw"></i>Reconnect</button></div><div style="margin-top:32px;color:rgba(255,255,255,0.6);font-size:13px;">To restart: <code style="background:rgba(255,255,255,0.1);padding:4px 8px;border-radius:4px;">python server/server.py</code></div>'
  bodyEl.style.display = 'none'

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
scheduleUpdate(() => Promise.all([fetchAgents(), loadAvailableAgents()]), 2000)
scheduleUpdate(updateState, 300)
scheduleUpdate(() => currentAgent && refreshScreen(), 500)
scheduleUpdate(() => {
  if(currentView === 'supervisor') {
    updateSupervisorGrid()
  }
}, 1500)
