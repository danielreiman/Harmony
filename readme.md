# Harmony Desktop Agent

Harmony is a vision driven desktop automation agent. It observes the screen, understands interface elements, plans actions, and operates the computer through a large vision language model. The agent uses real time screenshots, UI detection, and a model controller that executes clicks, typing, scrolling, and system navigation with precision.

This README explains how to set up the environment, install the model, prepare the weights, and understand the core workflow of the system.

---

## ONE COMMAND SETUP AFTER CLONNING (Run Before Starting Harmony)

macOS and Linux:
```bash
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && python tools/download_weights.py
```

Windows PowerShell:
```bash
python -m venv .venv; ..venv\Scripts\Activate.ps1; pip install -r requirements.txt; python tools/download_weights.py
```

## Setup

### Create the Python environment

Create a clean virtual environment for the project:

```
python -m venv .venv
```

Activate it:

macOS and Linux:

```
source .venv/bin/activate
```

Windows:

```
.venv\Scripts\Activate.ps1
```

Install dependencies:

```
pip install -r requirements.txt
```

Your environment is now ready.

---

## Configure Ollama Cloud API Access

Harmony uses the **qwen3-vl:235b-cloud** model through the **Ollama Cloud API**.  
You do **not** need to install the Ollama desktop application or download any local models.

### Option 1. Use a `.env` file (recommended on personal machines)

Create a file named `.env` in the project root:
```
OLLAMA_API_KEY=your_api_key_here
```

This file is automatically loaded at runtime and must **not** be committed to GitHub.

---

### Option 2. Type the API key at runtime (recommended for school machines)

If no `.env` file is found, Harmony will safely prompt:

```
Enter Ollama API Key:
```

The key is used only for that session and is never stored on disk.

---

## Download OmniParser weights

Harmony relies on OmniParser for icon detection and screen captioning. These weights must be placed in the project directory.


Download the required model files from the Microsoft OmniParser repository:

```
python tools/download_weights.py
```

The detection and captioning weights are now ready for use.

---

## How Harmony works

Harmony processes the screen frame by frame and uses a structured interaction loop to complete tasks.

## Workflow

1. **Capture a screenshot** of the desktop environment.

2. **Detect UI elements** using the OmniParser icon-detection model.  
   The agent receives bounding boxes and a cropped view of the selected element.

3. **Generate a proposed action** by sending the screenshot, detections, and context history to the LLM.  
   The model returns a single JSON step describing the intended action.

4. **Verify the proposed action** using a secondary LLM check.  
   The verifier receives:
   - The goal  
   - The cropped target element  
   - The proposed JSON step  
   It returns a **verdict** of `"accept"` or `"reject"` with a short reason.

5. **Execute the action** only if the verifier returns `"accept"`.  
   The operator controller performs the input event such as click, type, or scroll.

6. **Record feedback** from verification and execution.  
   Rejections and failures are added to the agent’s message history to guide the next step.

7. **Repeat** the cycle until the task reaches a terminal state.

The result is a controlled automation loop that can open applications, navigate menus, search, type text, interact with elements, and complete multi step objectives.

---

## Ready to run

At this stage you have:

* A clean Python environment with all dependencies installed
* The Ollama runtime configured
* All OmniParser weights placed correctly under Harmony/models/weights


You can now start the project and watch Harmony operate your desktop in real time.

## To choose a task for the agent, enter the task into the `goal` variable in the `main.py` file, then run `main.py`.
