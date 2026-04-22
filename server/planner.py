# ============================================================================
#  Planner
# ----------------------------------------------------------------------------
#  Turns a big user goal like "clean up my desktop and organise downloads"
#  into a small checklist of computer tasks, then queues them one by one.
#  Each step becomes a regular task the agent runs; when a step finishes,
#  the next step is queued automatically.
# ============================================================================


import json

from ollama import Client

import config
import database as db


# The AI we use to break a goal into steps. Small & fast is fine here.
PLANNING_MODEL = "gpt-oss:20b-cloud"


# Prompt shown to the AI. It must return JSON so we can parse it safely.
PLANNING_PROMPT = (
    "You are a planner for a computer-use agent.\n"
    "The user will give you one goal. Break it into a short ordered checklist\n"
    "of 2 to 6 concrete computer tasks that an agent can perform on a desktop.\n"
    "Each step must be a single, specific action (open an app, click a button,\n"
    "type some text, move files, etc.).\n"
    "\n"
    "Return JSON only, in this exact shape:\n"
    '{"steps": ["first step", "second step", "..."]}'
)


def _ask_ai_for_steps(goal):
    # Ask the AI to split the goal into a checklist of steps.
    # Returns a list of strings, or [] if the AI reply was unusable.
    api_key = config.OLLAMA_API_KEY
    if not api_key:
        raise RuntimeError("OLLAMA_API_KEY not found")

    ai = Client(
        host="https://ollama.com",
        headers={"Authorization": f"Bearer {api_key}"},
    )

    response = ai.chat(
        model=PLANNING_MODEL,
        format="json",
        messages=[
            {"role": "system", "content": PLANNING_PROMPT},
            {"role": "user",   "content": f"Goal: {goal}"},
        ],
    )

    raw = (response.get("message", {}).get("content") or "").strip()
    if not raw:
        return []

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []

    steps = parsed.get("steps") or []
    return [str(step).strip() for step in steps if str(step).strip()]


def create_plan(goal, user_id=None, agent_id=None):
    # Main entry point. Generates a checklist for `goal` and queues the
    # first step as a task. Returns the new plan_id (or None on failure).
    goal = (goal or "").strip()
    if not goal:
        return None

    steps = _ask_ai_for_steps(goal)
    if not steps:
        return None

    # Save the full checklist, starting at step 0.
    plan_id = db.create_plan(goal, steps, user_id=user_id, agent_id=agent_id)

    # Queue the first step for the agent to run.
    db.add_task(steps[0], user_id=user_id, agent_id=agent_id, plan_id=plan_id)

    return plan_id


def step_finished(plan_id, user_id=None, agent_id=None):
    # Called by the manager when the agent finishes a step that belonged
    # to a plan. Queues the next step, or marks the plan done.
    next_step = db.advance_plan(plan_id)
    if next_step is None:
        return  # plan is finished

    db.add_task(next_step, user_id=user_id, agent_id=agent_id, plan_id=plan_id)
