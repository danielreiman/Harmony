function getElementById(id) {
  return document.getElementById(id)
}

let currentAgent = null
let lastScreenshotUrl = null
let currentView = 'single'
let researchModeEnabled = false
let agentsList = []
let lastAgentData = []
let agentTileElements = {}
let isInitialized = false
let shuttingDown = false
let serverUnavailable = false
let errorCount = 0
let toastTimeout = null
let lastToastMessage = null
let lastToastAt = 0

const maxErrors = 3
const THEME_STORAGE_KEY = 'harmonyTheme'
const DEFAULT_THEME = 'carbon'

const serviceAccountInfo = window.harmonyServiceAccount || { hasKey: false, email: "" }


function normalizeServerBase(raw) {
  if (!raw) return null

  const trimmed = raw.trim().replace(/\/+$/, '')
  if (!trimmed) return null

  const alreadyHasProtocol = /^https?:\/\//i.test(trimmed)
  if (alreadyHasProtocol) return trimmed

  return `http://${trimmed}`
}


const apiBases = (function buildApiBases() {
  const bases = []

  const serverParam = new URLSearchParams(window.location.search).get('server')
  const normalizedServerParam = normalizeServerBase(serverParam)
  if (normalizedServerParam) {
    bases.push(normalizedServerParam)
  }

  const isFileProtocol = window.location.protocol === 'file:'
  if (isFileProtocol) {
    bases.push('http://localhost:1234')
    bases.push('http://127.0.0.1:1234')
  } else {
    bases.push(window.location.origin)
    const isNotOnDashboardPort = window.location.port !== '1234'
    const hasHostname = !!window.location.hostname
    if (isNotOnDashboardPort && hasHostname) {
      bases.push(`${window.location.protocol}//${window.location.hostname}:1234`)
    }
  }

  return Array.from(new Set(bases))
})()


function applyTheme(theme) {
  const isCarbonTheme = theme === 'carbon'
  document.body.classList.toggle('theme-carbon', isCarbonTheme)
}

function initTheme() {
  try {
    const storedTheme = localStorage.getItem(THEME_STORAGE_KEY)
    applyTheme(storedTheme || DEFAULT_THEME)
  } catch (storageError) {
    applyTheme(DEFAULT_THEME)
  }
}

window.setHarmonyTheme = function(theme) {
  const normalizedTheme = theme === 'default' ? 'default' : 'carbon'
  const isDefaultTheme = normalizedTheme === 'default'
  if (isDefaultTheme) {
    localStorage.removeItem(THEME_STORAGE_KEY)
  } else {
    localStorage.setItem(THEME_STORAGE_KEY, normalizedTheme)
  }
  applyTheme(normalizedTheme)
}

initTheme()


async function apiFetch(path, options) {
  let lastError = null
  for (const base of apiBases) {
    try {
      const response = await fetch(`${base}${path}`, options)
      const isUnauthorized = response.status === 401
      const wasRedirectedToLogin = response.redirected && response.url.includes('/login')
      const sessionExpired = isUnauthorized || wasRedirectedToLogin
      if (sessionExpired) {
        if (!shuttingDown) {
          window.location.href = '/login'
        }
        return response
      }
      return response
    } catch (fetchError) {
      lastError = fetchError
    }
  }
  throw lastError || new Error('Network error')
}


function extractCoordinatesFromArray(coordinateArray) {
  const isValidArray = Array.isArray(coordinateArray) && coordinateArray.length === 2
  if (isValidArray) {
    return { x: coordinateArray[0], y: coordinateArray[1] }
  }
  return { x: null, y: null }
}


function describeStep(step) {
  if (!step || !step.action) return "Waiting…"

  const actionName = step.action.toLowerCase()
  const { x, y } = extractCoordinatesFromArray(step.coordinate)

  const isClickAction = actionName === "left_click"
    || actionName === "click"
    || actionName === "double_click"
    || actionName === "right_click"

  if (isClickAction) {
    const hasCoordinates = x != null
    if (hasCoordinates) {
      const friendlyName = actionName.replace("_", " ")
      return `${friendlyName} at ${x}, ${y}`
    }
    return "Clicking"
  }

  if (actionName === "scroll_down") return "Scrolling down"
  if (actionName === "scroll_up") return "Scrolling up"
  if (actionName === "scroll") return `Scrolling ${step.value || ""}`.trim()

  if (actionName === "type") {
    const valueText = step.value || ""
    const isTruncated = valueText.length > 30
    const displayValue = isTruncated ? `${valueText.substring(0, 30)}...` : valueText
    return `Typing "${displayValue}"`
  }

  if (actionName === "press_key") return `Pressing ${step.value || "key"}`

  if (actionName === "hotkey") {
    const isArray = Array.isArray(step.value)
    const hotkeyLabel = isArray ? step.value.join("+") : step.value || ""
    return `Hotkey ${hotkeyLabel}`
  }

  if (actionName === "wait") return "Waiting..."
  if (actionName === "none") return "Done"

  return step.action
}


function stripTaskMetadata(taskText) {
  if (!taskText) return ""

  const metadataMarkers = [
    "\n\nCollaboration:",
    "\n\nAssigned agent:",
    "\n\nOther agents:",
    "\n\nShared workspace:",
    "\n\nRole:"
  ]

  const markerPositions = metadataMarkers
    .map(marker => taskText.indexOf(marker))
    .filter(position => position !== -1)

  if (!markerPositions.length) return taskText.trim()

  const firstMarkerPosition = Math.min(...markerPositions)
  return taskText.slice(0, firstMarkerPosition).trim()
}


function extractDocIdFromUrl(url) {
  if (!url) return null
  const match = url.match(/\/document\/d\/([a-zA-Z0-9_-]+)/)
  return match ? match[1] : null
}


function truncateText(text, maxLength) {
  if (!text) return ''
  const isTooLong = text.length > maxLength
  if (isTooLong) {
    return `${text.slice(0, maxLength - 1)}…`
  }
  return text
}


function refreshLucideIcons() {
  if (typeof lucide !== 'undefined') {
    lucide.createIcons()
  }
}


function showToast(message, type) {
  console.log(`[${type}] ${message}`)
}


function showConnectionOverlay() {
  const isBlockedByShutdown = serverUnavailable || shuttingDown
  if (isBlockedByShutdown) return

  const overlay = getElementById("connectionOverlay")
  overlay.classList.remove('error')
  overlay.classList.add('active')

  refreshLucideIcons()
}

function hideConnectionOverlay() {
  const isBlockedByShutdown = serverUnavailable || shuttingDown
  if (isBlockedByShutdown) return

  const overlay = getElementById("connectionOverlay")
  overlay.classList.remove('active')
  overlay.classList.remove('error')
}


function showGoodbye() {
  shuttingDown = true

  const overlay = getElementById("connectionOverlay")
  const titleEl = overlay.querySelector('.connectionOverlayTitle')
  const subtitleEl = overlay.querySelector('.connectionOverlaySubtitle')
  const bodyEl = overlay.querySelector('.connectionOverlayBody')
  const actionsEl = overlay.querySelector('.connectionActions')
  const topActionsEl = overlay.querySelector('.connectionOverlayTopActions')

  titleEl.textContent = 'See you next time!'
  subtitleEl.innerHTML = 'Harmony server has been shut down<div class="goodbyeActions"><button class="goodbyeBtn" onclick="location.reload()"><i data-lucide="refresh-cw"></i>Reconnect</button><a href="https://github.com/danielreiman/Harmony" target="_blank" class="goodbyeBtn"><svg viewBox="0 0 16 16" style="width:18px;height:18px;fill:currentColor;"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>View on GitHub</a></div><div style="margin-top:32px;color:rgba(255,255,255,0.6);font-size:13px;">To restart: <code style="background:rgba(255,255,255,0.1);padding:4px 8px;border-radius:4px;">python server/server.py</code></div>'
  bodyEl.style.display = 'none'

  if (actionsEl) actionsEl.style.display = 'none'
  if (topActionsEl) topActionsEl.style.display = 'none'

  overlay.classList.remove('error')
  overlay.classList.add('active', 'goodbye')

  refreshLucideIcons()
}


function showServerUnavailable() {
  if (shuttingDown) return

  serverUnavailable = true

  const overlay = getElementById("connectionOverlay")
  const titleEl = overlay.querySelector('.connectionOverlayTitle')
  const subtitleEl = overlay.querySelector('.connectionOverlaySubtitle')
  const bodyEl = overlay.querySelector('.connectionOverlayBody')
  const actionsEl = overlay.querySelector('.connectionActions')
  const topActionsEl = overlay.querySelector('.connectionOverlayTopActions')

  titleEl.textContent = 'Server unavailable'
  subtitleEl.innerHTML = 'Cannot reach the Harmony server. Make sure it is running.<div class="goodbyeActions"><button class="goodbyeBtn" onclick="checkServerStatus()"><i data-lucide="refresh-cw"></i>Retry</button><a href="https://github.com/danielreiman/Harmony" target="_blank" class="goodbyeBtn"><svg viewBox="0 0 16 16" style="width:18px;height:18px;fill:currentColor;"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>View on GitHub</a></div><div style="margin-top:32px;color:rgba(255,255,255,0.6);font-size:13px;">To start: <code style="background:rgba(255,255,255,0.1);padding:4px 8px;border-radius:4px;">python server/server.py</code></div>'
  bodyEl.style.display = 'none'

  if (actionsEl) actionsEl.style.display = 'none'
  if (topActionsEl) topActionsEl.style.display = 'none'

  overlay.classList.remove('error')
  overlay.classList.add('active', 'goodbye')

  refreshLucideIcons()
}

function hideServerUnavailable() {
  if (!serverUnavailable) return

  serverUnavailable = false

  const overlay = getElementById("connectionOverlay")
  const titleEl = overlay.querySelector('.connectionOverlayTitle')
  const subtitleEl = overlay.querySelector('.connectionOverlaySubtitle')
  const bodyEl = overlay.querySelector('.connectionOverlayBody')
  const topActionsEl = overlay.querySelector('.connectionOverlayTopActions')

  titleEl.textContent = 'Harmony'
  subtitleEl.textContent = 'Distributed automation system for parallel task execution across multiple computers'
  bodyEl.style.display = ''

  if (topActionsEl) topActionsEl.style.display = ''

  overlay.classList.remove('goodbye')
  overlay.classList.remove('active')
}


async function checkServerStatus() {
  if (shuttingDown) return

  try {
    const response = await apiFetch('/api/status')
    const statusData = await response.json()
    const serverIsOnline = statusData.ok
    if (serverIsOnline) {
      hideServerUnavailable()
    } else {
      showServerUnavailable()
    }
  } catch (networkError) {
    showServerUnavailable()
  }
}


async function refreshScreen() {
  const browserFrame = document.querySelector('.browserFrame')
  const browserTop = document.querySelector('.browserTop')
  const statusCapEl = getElementById("statusCap")

  function showWaitingState() {
    getElementById("screen").style.display = 'none'
    getElementById("waitingState").style.display = 'flex'
    getElementById("waitingAgentId").textContent = currentAgent || 'No agent selected'
    getElementById("viewport").classList.add('empty')
    browserFrame.classList.add('waiting')
    browserTop.style.display = 'none'
    statusCapEl.style.display = 'none'
  }

  if (!currentAgent) {
    showWaitingState()
    return
  }

  try {
    const response = await apiFetch(`/screen/${currentAgent}?t=${Date.now()}`, { cache: "no-store" })
    if (!response.ok) throw new Error(`Screen fetch failed: ${response.status}`)

    const imageBlob = await response.blob()
    const newImageUrl = URL.createObjectURL(imageBlob)

    if (lastScreenshotUrl) {
      URL.revokeObjectURL(lastScreenshotUrl)
    }
    lastScreenshotUrl = newImageUrl

    getElementById("screen").src = newImageUrl
    getElementById("screen").style.display = 'block'
    getElementById("waitingState").style.display = 'none'
    getElementById("viewport").classList.remove('empty')
    browserFrame.classList.remove('waiting')
    browserTop.style.display = 'flex'
    statusCapEl.style.display = 'block'
  } catch (fetchError) {
    console.warn('Screen refresh failed:', fetchError.message)
    showWaitingState()
  }
}


function renderAgentState(agentData) {
  const taskPanel = getElementById("taskStatusPanel")
  const displayTask = stripTaskMetadata(agentData.task)

  getElementById("taskStatusText").textContent = displayTask || "No active task"
  getElementById("statusCap").textContent = agentData.status_text || agentData.status || "Idle"
  getElementById("actionTop").textContent = describeStep(agentData.step)

  const agentIsWorking = agentData.status === 'working'
  const shouldShowTaskPanel = displayTask && agentIsWorking
  if (taskPanel) {
    taskPanel.style.display = shouldShowTaskPanel ? 'flex' : 'none'
  }

  const hasReasoning = agentData.step && agentData.step.reasoning
  if (hasReasoning) {
    getElementById("singleReasoningText").textContent = agentData.step.reasoning
  } else {
    getElementById("singleReasoningText").textContent = agentData.status_text || "Waiting for agent activity..."
  }
}


async function updateState() {
  const taskPanel = getElementById("taskStatusPanel")

  if (!currentAgent) {
    getElementById("taskStatusText").textContent = "No active task"
    getElementById("statusCap").textContent = "Idle"
    getElementById("actionTop").textContent = "Select an agent..."
    getElementById("singleReasoningText").textContent = "Waiting for agent activity..."
    if (taskPanel) taskPanel.style.display = 'none'
    return
  }

  try {
    const response = await apiFetch(`/agent/${currentAgent}`, { cache: "no-store" })
    if (!response.ok) throw new Error(`Agent state fetch failed: ${response.status}`)

    const agentData = await response.json()
    renderAgentState(agentData)
  } catch (fetchError) {
    console.warn('State update failed:', fetchError.message)
  }
}


async function fetchAgents() {
  try {
    const response = await apiFetch("/agents", { cache: "no-store" })
    if (!response.ok) throw new Error(`Agents fetch failed: ${response.status}`)

    const agents = await response.json()
    agentsList = agents

    const noAgentsConnected = agents.length === 0
    if (noAgentsConnected) {
      getElementById("selectedAgent").textContent = "No agents"
      showConnectionOverlay()
      return
    }

    hideConnectionOverlay()
    hideSingleEmptyState()

    const noAgentSelected = !currentAgent
    if (noAgentSelected) {
      currentAgent = agents[0].id
    }

    updateAgentDropdown()
  } catch (fetchError) {
    console.error('Failed to fetch agents:', fetchError.message)
    showToast('Connection lost - server may be down', 'error')
  }
}


function updateAgentDropdown() {
  if (agentsList.length === 0) return

  getElementById("selectedAgent").textContent = currentAgent || "No agent"

  const menu = getElementById("agentDropdownMenu")
  menu.innerHTML = ""

  const header = document.createElement("div")
  header.className = "agentDropdownHeader"
  header.textContent = "Select Agent"
  menu.appendChild(header)

  const divider = document.createElement("div")
  divider.className = "agentDropdownDivider"
  menu.appendChild(divider)

  agentsList.forEach(function(agent) {
    const option = document.createElement("div")
    option.className = "agentOption"

    const agentIsSelected = agent.id === currentAgent
    if (agentIsSelected) {
      option.classList.add("active")
    }

    const titleEl = document.createElement("div")
    titleEl.className = "agentOptionTitle"
    titleEl.textContent = agent.id

    const checkIcon = document.createElementNS("http://www.w3.org/2000/svg", "svg")
    checkIcon.classList.add("agentOptionCheck")
    checkIcon.setAttribute("viewBox", "0 0 24 24")
    checkIcon.setAttribute("fill", "none")
    checkIcon.setAttribute("stroke", "currentColor")
    checkIcon.setAttribute("stroke-width", "3")
    checkIcon.setAttribute("stroke-linecap", "round")
    checkIcon.setAttribute("stroke-linejoin", "round")

    const checkPath = document.createElementNS("http://www.w3.org/2000/svg", "polyline")
    checkPath.setAttribute("points", "20 6 9 17 4 12")
    checkIcon.appendChild(checkPath)

    option.appendChild(titleEl)
    option.appendChild(checkIcon)

    option.onclick = function() {
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


function toggleAgentDropdown() {
  const selector = getElementById("agentSelector")
  const menu = getElementById("agentDropdownMenu")
  selector.classList.toggle("open")
  menu.classList.toggle("open")
}

function closeAgentDropdown() {
  getElementById("agentSelector").classList.remove("open")
  getElementById("agentDropdownMenu").classList.remove("open")
}

getElementById("agentSelector").onclick = function(event) {
  event.stopPropagation()
  toggleAgentDropdown()
}

document.addEventListener("click", function(event) {
  const clickedInsideDropdown = event.target.closest(".agentDropdown")
  if (!clickedInsideDropdown) {
    closeAgentDropdown()
  }
})


function switchView(viewName) {
  document.querySelectorAll('.viewToggleBtn').forEach(function(btn) {
    btn.classList.remove('active')

    const isSingleViewBtn = viewName === 'single' && btn.textContent.includes('Single')
    const isSupervisorViewBtn = viewName === 'supervisor' && btn.textContent.includes('Supervisor')
    if (isSingleViewBtn || isSupervisorViewBtn) {
      btn.classList.add('active')
    }
  })

  const promptMeta = getElementById("promptMeta")

  if (viewName === 'single') {
    getElementById("singleView").classList.add('active')
    getElementById("supervisorView").classList.remove('active')
    getElementById("agentDropdown").style.display = 'flex'
    if (promptMeta) promptMeta.style.display = 'none'
    currentView = 'single'
    updatePromptPlaceholder()
  } else {
    getElementById("singleView").classList.remove('active')
    getElementById("supervisorView").classList.add('active')
    getElementById("agentDropdown").style.display = 'none'
    if (promptMeta) promptMeta.style.display = 'flex'
    currentView = 'supervisor'
    updateSupervisorGrid()
    updatePromptPlaceholder()
  }

  refreshLucideIcons()
}


function updatePromptPlaceholder() {
  const input = getElementById("promptInput")

  if (currentView === 'single') {
    const hasAgentSelected = !!currentAgent
    input.placeholder = hasAgentSelected
      ? `Send task to ${currentAgent}...`
      : 'Select an agent first...'
  } else {
    input.placeholder = 'Enter task instructions for all agents...'
  }
}


function buildTaskWithContext(options) {
  const task = options.task
  const agentId = options.agentId
  const agents = options.agents
  const workspaceUrl = options.workspaceUrl
  const isResearch = options.isResearch
  const isCollab = options.isCollab
  const docId = options.docId

  const orderedAgents = agents.length ? agents : (agentId ? [agentId] : [])
  const leadAgent = orderedAgents[0]
  const wrapUpAgent = orderedAgents[orderedAgents.length - 1]
  const otherAgentIds = orderedAgents.filter(function(id) { return id !== agentId })

  let roleNote = "Own a subject: pick a unique subtopic, write one findings paragraph with source credit."

  const isSoloAgent = orderedAgents.length === 1
  const agentIsOnlyOne = agentId === leadAgent && agentId === wrapUpAgent

  if (isSoloAgent || agentIsOnlyOne) {
    roleNote = "Solo: write Instructions/Approach, all findings paragraphs (one per subject with citations), Conclusion, Bibliography, then clean grammar/formatting."
  } else if (agentId === leadAgent) {
    roleNote = "Lead: write the Instructions/Approach paragraph. If only two agents, also take one findings paragraph."
  } else if (agentId === wrapUpAgent) {
    roleNote = "Wrap-up: write the Conclusion paragraph, compile the Bibliography, then do a cleanup pass (grammar, spacing, headings/bold) without changing facts. If only two agents, also take one findings paragraph."
  }

  const docRules = [
    "- Google Doc is shared; agents use read_doc/write_doc API only (no UI opening).",
    "- Structure: Title (only heading), Notes (bullets, short, with source names), Introduction (short), Findings (one short paragraph per subject with inline source), Conclusion (short), Bibliography (Author or Org. (Year, Month Day). Title. Site. URL).",
    "- Keep paragraphs brief with blank lines; bullets start with '-'.",
    "- Start by reading the doc; do not overwrite existing text."
  ]

  const otherAgentsDisplay = otherAgentIds.length ? otherAgentIds.join(", ") : "none"
  const workspaceDisplay = workspaceUrl || "not provided"
  const collabDisplay = isCollab ? "yes" : "no"
  const agentDisplay = agentId || "queue"

  const lines = [
    task,
    "",
    "Collaboration: " + collabDisplay,
    "Assigned agent: " + agentDisplay,
    "Other agents: " + otherAgentsDisplay,
    "Shared workspace: " + workspaceDisplay,
    "Role: " + roleNote
  ]

  if (isCollab && isResearch) {
    lines.push(
      "",
      "Collab research instructions:",
      "- Use read_doc/write_doc only; do not open the doc UI.",
      "- Notes: bullets with source names; Findings: one short paragraph per subject; keep spacing clean.",
      "- Team split: first agent writes Instructions/Approach; middle agents each write one findings paragraph; last agent writes Conclusion + Bibliography + cleanup."
    )
  }

  if (isResearch) {
    const hasWorkspaceUrl = !!workspaceUrl
    const docSetupLine = hasWorkspaceUrl
      ? "- Shared Google Doc provided. Use API actions only; do not open the URL."
      : "- No shared doc provided. Ask once if a doc link is missing."

    lines.push("", "Document setup:", docSetupLine)
    lines.push("", "Document rules:", ...docRules)
  }

  return lines.join("\n")
}


async function sendTask() {
  const input = getElementById("promptInput")
  if (!input) {
    console.error('Prompt input element not found')
    return
  }

  const taskText = input.value.trim()
  if (!taskText) {
    showToast('Please enter a task', 'error')
    return
  }

  try {
    const workspaceUrl = localStorage.getItem("harmonyWorkspaceUrl") || ""
    const docId = extractDocIdFromUrl(workspaceUrl) || localStorage.getItem("harmonyDocId") || null

    let targetAgentIds = []
    let allParticipatingAgentIds = []
    let isCollab = false
    let primaryAgentId = null

    if (currentView === 'single') {
      if (!currentAgent) {
        showToast('Please select an agent first', 'error')
        return
      }
      primaryAgentId = currentAgent
      targetAgentIds = [currentAgent]
      allParticipatingAgentIds = [currentAgent]
    } else {
      const agentsResponse = await apiFetch("/agents", { cache: "no-store" })
      if (!agentsResponse.ok) throw new Error(`Agents fetch failed: ${agentsResponse.status}`)

      const connectedAgents = await agentsResponse.json()
      allParticipatingAgentIds = connectedAgents.map(function(agent) { return agent.id })

      if (allParticipatingAgentIds.length === 0) {
        showToast('No agents connected', 'error')
        return
      }

      targetAgentIds = allParticipatingAgentIds
      isCollab = true
    }

    const payloads = targetAgentIds.map(function(targetAgentId) {
      const contextualTaskText = buildTaskWithContext({
        task: taskText,
        agentId: targetAgentId,
        agents: allParticipatingAgentIds.length ? allParticipatingAgentIds : (primaryAgentId ? [primaryAgentId] : []),
        workspaceUrl: workspaceUrl,
        isResearch: researchModeEnabled,
        isCollab: isCollab,
        docId: docId
      })

      return {
        task: contextualTaskText,
        agent_id: targetAgentId,
        research_mode: researchModeEnabled,
        doc_id: docId
      }
    })

    const fetchOptions = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    }

    const sendRequests = payloads.map(function(payload) {
      return apiFetch('/api/send-task', Object.assign({}, fetchOptions, { body: JSON.stringify(payload) }))
    })

    const responses = await Promise.all(sendRequests)

    const originalInputValue = input.value
    input.value = ''

    const failures = []
    let successCount = 0

    for (const response of responses) {
      if (!response.ok) {
        let errorMessage = `Server error: ${response.status}`
        try {
          const errorData = await response.json()
          errorMessage = errorData.error || errorMessage
        } catch (parseError) {
          // Response was not JSON, keep the status code message
        }
        failures.push(errorMessage)
        continue
      }

      let result = null
      try {
        const responseText = await response.text()
        result = responseText ? JSON.parse(responseText) : null
      } catch (parseError) {
        console.error('Task send response parse error:', parseError)
        failures.push('Unexpected server response')
        continue
      }

      const taskWasSent = result && result.success
      if (taskWasSent) {
        successCount += 1
      } else {
        const errorMessage = (result && result.error) || 'Failed to send task'
        failures.push(errorMessage)
      }
    }

    if (failures.length) {
      showToast(failures[0], 'error')
      input.value = originalInputValue
      return
    }

    const sentToMultipleAgents = successCount > 1
    if (sentToMultipleAgents) {
      showToast(`Task sent to ${successCount} agents`, 'success')
    } else {
      showToast('Task sent successfully', 'success')
    }
  } catch (networkError) {
    console.error('Task send error:', networkError)
    showToast('Network error - check server connection', 'error')
  }
}


function closeResultsModal() {
  const modal = getElementById("resultsModal")
  modal.classList.remove('open')
}

function closeReasoningModal() {
  getElementById("reasoningModal").classList.remove('open')
}

function closeCustomAlert() {
  const modal = getElementById("customAlert")
  modal.classList.remove('open')
}

function showCustomAlert(title, message) {
  const modal = getElementById("customAlert")
  const titleElement = getElementById("customAlertTitle")
  const bodyElement = getElementById("customAlertBody")

  titleElement.textContent = title
  bodyElement.textContent = message

  refreshLucideIcons()
  modal.classList.add('open')
}

function showTaskModal(agentId, taskText) {
  showCustomAlert(`${agentId} - Task`, taskText)
}


function populateWorkspaceEmail() {
  const email = serviceAccountInfo.email || "service account email not found"
  const emailEl = getElementById("workspaceEmail")
  if (emailEl) {
    emailEl.textContent = email
  }

  const infoEl = getElementById("workspaceKeyInfo")
  if (infoEl) {
    const hasServiceAccount = serviceAccountInfo.hasKey && serviceAccountInfo.email
    if (hasServiceAccount) {
      infoEl.className = ""
      infoEl.innerHTML = ""
    } else {
      infoEl.className = "workspaceInfoWarn"
      infoEl.innerHTML = `Place <code>service-account.json</code> in <code>server/</code>, restart.`
    }
  }
}

function openWorkspacePanel() {
  populateWorkspaceEmail()

  const panel = getElementById("workspacePanel")
  if (!panel) return

  const input = getElementById("workspaceUrlInput")
  if (input) {
    input.value = localStorage.getItem("harmonyWorkspaceUrl") || ""
    input.focus()
  }

  panel.classList.add("open")
}

function closeWorkspacePanel() {
  const panel = getElementById("workspacePanel")
  if (!panel) return
  panel.classList.remove("open")
}

function toggleWorkspacePanel() {
  const panel = getElementById("workspacePanel")
  if (!panel) return

  const panelIsOpen = panel.classList.contains("open")
  if (panelIsOpen) {
    closeWorkspacePanel()
  } else {
    openWorkspacePanel()
  }
}

function copyWorkspaceEmail() {
  const email = serviceAccountInfo.email
  if (!email) {
    showToast("No service account email found", "error")
    return
  }
  navigator.clipboard.writeText(email).then(function() {
    showToast("Email copied", "success")
  }).catch(function() {
    showToast("Copy failed", "error")
  })
}

function saveWorkspace() {
  const input = getElementById("workspaceUrlInput")
  if (!input) return

  const url = (input.value || "").trim()
  const docId = extractDocIdFromUrl(url)

  const urlIsInvalid = url && !docId
  if (urlIsInvalid) {
    showToast("Paste a valid Google Doc URL", "error")
    return
  }

  if (url) {
    localStorage.setItem("harmonyWorkspaceUrl", url)
    if (docId) {
      localStorage.setItem("harmonyDocId", docId)
    }
  } else {
    localStorage.removeItem("harmonyWorkspaceUrl")
    localStorage.removeItem("harmonyDocId")
  }

  const toastMessage = url ? "Workspace saved" : "Workspace cleared"
  showToast(toastMessage, "success")
  closeWorkspacePanel()
}


document.addEventListener('click', function(event) {
  if (event.target.id === 'resultsModal') {
    closeResultsModal()
  }
  if (event.target.id === 'reasoningModal') {
    closeReasoningModal()
  }
  if (event.target.id === 'customAlert') {
    closeCustomAlert()
  }

  const panel = getElementById("workspacePanel")
  const workspaceBtn = getElementById("workspaceBtn")
  const panelIsOpen = panel && panel.classList.contains("open")
  const clickedOutsidePanel = !event.target.closest('#workspacePanel')
  const clickedOutsideButton = !event.target.closest('#workspaceBtn')
  if (panelIsOpen && clickedOutsidePanel && clickedOutsideButton) {
    closeWorkspacePanel()
  }
})

document.addEventListener('keydown', function(event) {
  if (event.key !== 'Escape') return

  const resultsModal = getElementById("resultsModal")
  const reasoningModal = getElementById("reasoningModal")
  const customAlert = getElementById("customAlert")
  const workspacePanel = getElementById("workspacePanel")

  if (resultsModal.classList.contains('open')) closeResultsModal()
  if (reasoningModal.classList.contains('open')) closeReasoningModal()
  if (customAlert.classList.contains('open')) closeCustomAlert()
  if (workspacePanel.classList.contains('open')) closeWorkspacePanel()
})

document.addEventListener("keydown", function(event) {
  const isViewToggleShortcut = event.key === 's' && (event.metaKey || event.ctrlKey)
  if (isViewToggleShortcut) {
    event.preventDefault()
    const nextView = currentView === 'single' ? 'supervisor' : 'single'
    switchView(nextView)
  }
})


getElementById("promptSend").onclick = sendTask

getElementById("promptInput").addEventListener('keydown', function(event) {
  if (event.key === 'Enter') {
    event.preventDefault()
    sendTask()
  }
})


async function stopAgent(agentId) {
  try {
    const response = await apiFetch(`/api/agent/${agentId}/stop`, { method: 'POST' })
    const result = await response.json()
    const toastType = result.success ? 'success' : 'error'
    const toastMessage = result.message || result.error
    showToast(toastMessage, toastType)
  } catch (networkError) {
    showToast('Failed to connect to server', 'error')
  }
}

async function disconnectAgent(agentId) {
  const userConfirmed = confirm(`Remove ${agentId}? This will disconnect and delete its data.`)
  if (!userConfirmed) return

  try {
    const encodedAgentId = encodeURIComponent(agentId)
    const response = await apiFetch(`/api/agent/${encodedAgentId}/disconnect`, { method: 'POST' })

    let result = null
    try {
      result = await response.json()
    } catch (parseError) {
      // Response was not JSON, result stays null
    }

    function finalizeDisconnect(message, toastType) {
      showToast(message, toastType)

      const disconnectedAgentWasSelected = currentAgent === agentId
      if (disconnectedAgentWasSelected) {
        currentAgent = null
        updatePromptPlaceholder()
        updateState()
        refreshScreen()
      }

      fetchAgents()

      if (currentView === 'supervisor') {
        updateSupervisorGrid()
      }
    }

    const requestFailed = !response.ok
    if (requestFailed) {
      const agentAlreadyGone = response.status === 404
      if (agentAlreadyGone) {
        finalizeDisconnect(`Agent ${agentId} already disconnected`, 'success')
        return
      }
      const errorMessage = (result && result.error) || 'Server rejected disconnect request'
      showToast(errorMessage, 'error')
      return
    }

    const successMessage = (result && result.message) || `Agent ${agentId} disconnected`
    finalizeDisconnect(successMessage, 'success')
  } catch (networkError) {
    console.error('Disconnect failed:', networkError)
    showConnectionOverlay()
  }
}

async function stopServer() {
  const userConfirmed = confirm('Shutdown the Harmony server? All agents will be disconnected.')
  if (!userConfirmed) return

  try {
    await apiFetch('/api/server/stop', { method: 'POST' })
  } catch (networkError) {
    // Expected — server is shutting down and connection will drop
  }
  showGoodbye()
}


function showSingleEmptyState() {
  const isInSingleView = currentView === 'single'
  if (!isInSingleView) return

  getElementById("screen").style.display = 'none'
  getElementById("viewport").classList.add('empty')
  getElementById("singleEmptyState").style.display = 'flex'

  refreshLucideIcons()
}

function hideSingleEmptyState() {
  getElementById("singleEmptyState").style.display = 'none'
  getElementById("viewport").classList.remove('empty')
}


function toggleResearchMode() {
  if (!researchModeEnabled) {
    const workspaceUrl = localStorage.getItem("harmonyWorkspaceUrl") || ""
    const docId = extractDocIdFromUrl(workspaceUrl) || localStorage.getItem("harmonyDocId")
    const hasServiceAccountKey = !!serviceAccountInfo.hasKey
    const hasWorkspaceUrl = !!workspaceUrl
    const hasDocId = !!docId

    const researchPrerequisitesMissing = !hasWorkspaceUrl || !hasDocId || !hasServiceAccountKey
    if (researchPrerequisitesMissing) {
      alert("To use research, add a Google Docs URL in Workspace and place service-account.json in server/ (shared as Editor).")
      return
    }
  }

  researchModeEnabled = !researchModeEnabled

  const btn = getElementById("researchToggle")
  if (researchModeEnabled) {
    btn.classList.add("active")
    btn.title = "Research mode ON - Click to disable"
  } else {
    btn.classList.remove("active")
    btn.title = "Toggle research mode"
  }

  refreshLucideIcons()
}


function toggleFullscreen() {
  const isCurrentlyFullscreen = !!document.fullscreenElement

  if (!isCurrentlyFullscreen) {
    document.documentElement.requestFullscreen().catch(function() {
      showToast("Fullscreen not available", "error")
    })
    const iconEl = document.querySelector(".fullscreenBtn i")
    if (iconEl) iconEl.setAttribute("data-lucide", "minimize-2")
  } else {
    document.exitFullscreen()
    const iconEl = document.querySelector(".fullscreenBtn i")
    if (iconEl) iconEl.setAttribute("data-lucide", "maximize-2")
  }

  refreshLucideIcons()
}

document.addEventListener("fullscreenchange", function() {
  const iconEl = document.querySelector(".fullscreenBtn i")
  if (iconEl) {
    const newIconName = document.fullscreenElement ? "minimize-2" : "maximize-2"
    iconEl.setAttribute("data-lucide", newIconName)
    refreshLucideIcons()
  }
})


function updateSupervisorStats(agents) {
  const totalCount = agents.length
  const activeCount = agents.filter(function(agent) { return agent.status === 'working' }).length
  const idleCount = totalCount - activeCount

  getElementById("totalAgents").textContent = totalCount
  getElementById("activeAgents").textContent = activeCount
  getElementById("idleAgents").textContent = idleCount
}


async function updateSupervisorGrid() {
  if (currentView !== 'supervisor') return

  try {
    const agentsResponse = await apiFetch("/agents", { cache: "no-store" })
    if (!agentsResponse.ok) throw new Error(`Agents fetch failed: ${agentsResponse.status}`)

    const agents = await agentsResponse.json()
    const grid = getElementById("supervisorGrid")
    const emptyState = getElementById("emptyState")

    const noAgentsConnected = agents.length === 0
    if (noAgentsConnected) {
      grid.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; padding: 60px 20px; color: var(--muted); font-size: 16px; font-style: italic;">No agents connected</div>`
      emptyState.style.display = 'none'
      showConnectionOverlay()
      return
    }

    grid.style.display = 'flex'
    emptyState.style.display = 'none'
    hideConnectionOverlay()

    const agentStatePromises = agents.map(async function(agent) {
      try {
        const stateResponse = await apiFetch(`/agent/${agent.id}`, { cache: "no-store" })
        if (stateResponse.ok) {
          return await stateResponse.json()
        }
        return { id: agent.id, status: 'idle', task: null, status_text: 'Idle' }
      } catch (fetchError) {
        return { id: agent.id, status: 'error', status_text: 'Connection Error' }
      }
    })

    const agentDetails = await Promise.all(agentStatePromises)

    updateSupervisorStats(agentDetails)

    const currentAgentIds = agentDetails.map(function(agent) { return agent.id }).sort().join(',')
    const lastAgentIds = lastAgentData.map(function(agent) { return agent.id }).sort().join(',')
    const agentListChanged = currentAgentIds !== lastAgentIds

    if (agentListChanged) {
      grid.innerHTML = ""
      agentTileElements = {}
      agentDetails.forEach(function(agent) { createAgentTile(agent, grid) })
    } else {
      agentDetails.forEach(function(agent) { updateAgentTile(agent) })
    }

    lastAgentData = agentDetails
  } catch (networkError) {
    console.warn('Supervisor grid update failed:', networkError.message)
    showToast('Connection lost - server may be down', 'error')
  }
}


function createAgentTile(agent, grid) {
  const tile = document.createElement("div")
  tile.className = "agentTile"
  tile.id = `tile-${agent.id}`

  tile.onclick = function() {
    currentAgent = agent.id
    switchView('single')
    updateState()
    refreshScreen()
  }

  agentTileElements[agent.id] = tile
  updateAgentTileContent(agent, tile)
  grid.appendChild(tile)

  refreshLucideIcons()
}

function updateAgentTile(agent) {
  const tile = agentTileElements[agent.id]
  if (tile) {
    updateAgentTileContent(agent, tile)
  }
}

async function updateAgentTileContent(agent, tile) {
  let screenshotUrl = null
  try {
    const screenResponse = await apiFetch(`/screen/${agent.id}?t=${Date.now()}`, { cache: "no-store" })
    if (screenResponse.ok) {
      const blob = await screenResponse.blob()
      screenshotUrl = URL.createObjectURL(blob)
    }
  } catch (fetchError) {
    // Screenshot failed, tile will show placeholder
  }

  let stepDescription = 'No task'
  const hasStepAction = agent.step && agent.step.action
  const agentIsWorking = agent.status === 'working'

  if (hasStepAction) {
    stepDescription = describeStep({
      action: agent.step.action,
      coordinate: agent.step.coordinate,
      value: agent.step.value
    })
  } else if (agentIsWorking) {
    stepDescription = 'Working...'
  }

  const truncatedStepDescription = truncateText(stepDescription, 44)
  const displayTask = stripTaskMetadata(agent.task)
  const taskDisplay = displayTask || 'No active task'
  const agentDisplay = agent.id || 'Unknown'

  const escapedTask = taskDisplay.replace(/`/g, '\\`').replace(/\$/g, '\\$')
  const escapedAgentId = agent.id

  const screenshotHtml = screenshotUrl
    ? `<img src="${screenshotUrl}" class="agentTileScreenImg" alt="Agent screen">`
    : `<div class="agentTileScreenPlaceholder"></div>`

  tile.innerHTML = `
    <div class="agentTileContent">
      <div class="agentTileHeader">
        <div class="agentTileId">${agentDisplay}</div>
        <div class="agentTileTask" onclick="event.stopPropagation(); showTaskModal('${escapedAgentId}', \`${escapedTask}\`)" title="Click to view task">${taskDisplay}</div>
      </div>

      <div class="agentMiniWindow">
        <div class="agentMiniTop">
          <div class="agentMiniWin red"></div>
          <div class="agentMiniWin yellow"></div>
          <div class="agentMiniWin green"></div>
          <div class="agentMiniAddress" title="${truncatedStepDescription}">${truncatedStepDescription}</div>
        </div>
        <div class="agentMiniViewport" style="position: relative;">
          ${screenshotHtml}
        </div>
      </div>
    </div>
    ${buildTileControlsHtml(agent)}
  `

  setTimeout(refreshLucideIcons, 100)
}


function buildTileControlsHtml(agent) {
  const hasThought = agent.step && agent.step.reasoning
  const hasActiveTask = agent.task && agent.status === 'working'

  const escapedReasoning = (agent.step && agent.step.reasoning || '').replace(/`/g, '\\`').replace(/\$/g, '\\$')
  const agentId = agent.id

  let thoughtButtonHtml = ''
  if (hasActiveTask && hasThought) {
    thoughtButtonHtml = `
      <button class="tileControlBtn" onclick="event.stopPropagation(); showCustomAlert('${agentId} Thoughts', \`${escapedReasoning}\`)">
        Show Thought
      </button>
    `
  }

  let pauseButtonHtml = ''
  if (hasActiveTask) {
    pauseButtonHtml = `
      <button class="tileControlBtn iconOnly" onclick="event.stopPropagation(); stopAgent('${agentId}')" title="Pause">
        <i data-lucide="pause"></i>
      </button>
    `
  }

  return `
    <div class="tileControlsRow">
      ${thoughtButtonHtml}
      ${pauseButtonHtml}
      <button class="tileControlBtn danger" onclick="event.stopPropagation(); disconnectAgent('${agentId}')" title="Disconnect">
        <i data-lucide="x"></i>
        Disconnect
      </button>
    </div>
  `
}


function selectAgent(agentId) {
  currentAgent = agentId
  getElementById("agentValue").textContent = agentId

  document.querySelectorAll('.viewToggleBtn').forEach(function(btn) {
    btn.classList.remove('active')
    const isSingleBtn = btn.textContent.includes('Single')
    if (isSingleBtn) {
      btn.classList.add('active')
    }
  })

  switchView('single')
  updateState()
  refreshScreen()
}

function refreshAgent(agentId) {
  const isInSupervisorView = currentView === 'supervisor'
  if (isInSupervisorView) {
    updateSupervisorGrid()
  }
}


function showLoading() {
  getElementById("agentValue").textContent = "Loading..."
  getElementById("statusCap").textContent = "Connecting..."
}

function hideLoading() {
  // Loading state will be overwritten by actual data on next update
}


function ensureLucideReady(remainingRetries) {
  const retries = remainingRetries !== undefined ? remainingRetries : 30

  if (typeof lucide !== 'undefined') {
    lucide.createIcons()
    return
  }

  if (retries > 0) {
    setTimeout(function() { ensureLucideReady(retries - 1) }, 100)
  }
}


async function initialize() {
  if (isInitialized) return

  showLoading()

  try {
    await fetchAgents()

    if (currentAgent) {
      await Promise.all([updateState(), refreshScreen()])
    }

    updatePromptPlaceholder()
    ensureLucideReady()
    isInitialized = true
    hideLoading()
  } catch (initError) {
    console.error('Initialization failed:', initError)
  }
}


function scheduleUpdate(updateFunction, intervalMs) {
  async function execute() {
    try {
      await updateFunction()
      errorCount = 0
      setTimeout(execute, intervalMs)
    } catch (executionError) {
      errorCount++
      const backoffExponent = errorCount - 1
      const backoffDelay = Math.min(intervalMs * Math.pow(2, backoffExponent), 10000)
      console.warn(`Function failed, retrying in ${backoffDelay}ms:`, executionError.message)
      setTimeout(execute, backoffDelay)
    }
  }
  execute()
}


initialize()
window.addEventListener('load', ensureLucideReady)
checkServerStatus()

scheduleUpdate(fetchAgents, 2000)
scheduleUpdate(updateState, 300)
scheduleUpdate(function() {
  if (currentAgent) {
    return refreshScreen()
  }
}, 500)
scheduleUpdate(function() {
  if (currentView === 'supervisor') {
    return updateSupervisorGrid()
  }
}, 1500)
scheduleUpdate(checkServerStatus, 5000)
