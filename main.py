import time
import keyboard
from agent.vision import Vision
from agent.operator import Operator
from agent.prompts import MAIN_PROMPT

def main():
    goal = "Calculate and return the following: 9+10 use only the apps in the computer not your brain"

    vision = Vision()
    operator = Operator("qwen3-vl:235b-cloud", vision)

    print("[LOG] Agent running. Press ESC to stop.")

    messages = [
        {"role": "system", "content": MAIN_PROMPT},
        {"role": "user", "content": f"Goal: {goal}"}
    ]

    while not keyboard.is_pressed("esc"):
        # ================= VISION =================
        (elements, screenshot_path, detected_path) = vision.look()

        messages.append({
            "role": "user",
            "content": "Current view",
            "images": [detected_path]
        })

        # ================= AI =================
        step, raw_ai_message = operator.think(messages)

        print("\n┌───────────────────────────────────── ACTION CORE ─────────────────────────────────────┐")
        print(f"│ REASONING  : {step.get('Reasoning', 'N/A')}")
        print(f"│ ACTION     : {step.get('Next Action', 'N/A')}")
        print(f"│ TARGET ID  : {step.get('Target_Box_ID', 'N/A')}")
        print(f"│ VALUE      : {step.get('Value', 'N/A')}")
        print("└────────────────────────────────────────────────────────────────────────────────────────┘\n")

        if messages and "images" in messages[-1]:
            messages[-1].pop("images", None)

        messages.append({"role": "assistant", "content": raw_ai_message})

        # ================= STEP VERIFICATION =================
        focus_element_path = vision.focus(step["Target_Box_ID"], elements, screenshot_path)
        verdict = operator.verify(goal, focus_element_path, messages[-1])

        print("\n┌──────────────────────────────────── HARMONY VERIFIER ──────────────────────────────────┐")
        print(f"│ STATUS  : {verdict.get('verdict', 'unknown').upper()}")
        print(f"│ REASON  : {verdict.get('reason', 'no reason provided')}")
        print("└────────────────────────────────────────────────────────────────────────────────────────┘\n")

        if verdict.get("verdict") != "accept":
            feedback = f"Verifier rejected action: {verdict.get('reason')}"
            messages.append({"role": "user", "content": f"System feedback: {feedback}"})
            time.sleep(1)
            continue

        if step.get("Next Action") in [None, "None"]:
            print("[LOG] Task complete.")
            break

        # ================= EXECUTION AND FEEDBACK =================
        feedback = operator.act(step, elements)
        messages.append({"role": "user", "content": f"System feedback: {feedback}"})

        time.sleep(1)

    print("[LOG] Program finished.")


if __name__ == "__main__":
    main()
