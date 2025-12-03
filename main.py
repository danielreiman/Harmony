import time
import keyboard
from agent.vision import Vision
from agent.operator import Operator
from agent.prompts import MAIN_PROMPT

def main():
    goal = "Open the first ever youtube video"

    vision = Vision()
    operator = Operator("qwen3-vl:235b-instruct-cloud", "qwen3-vl:235b-instruct-cloud", vision)

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

        print("\n┌──────────────────────────────────── HARMONY AGENT STEP ──────────────────────────────────┐")
        print(f"│ REASON  : {step.get('Reasoning', 'no reasoning provided')}")
        print(f"│ ACTION  : {step.get('Next Action', 'no action provided')}")
        print(f"│ TARGET  : {step.get('Target_Box_ID', 'no target provided')}")
        print(f"│ VALUE   : {step.get('Value', 'no value provided')}")
        print("└────────────────────────────────────────────────────────────────────────────────────────┘\n")

        if messages and "images" in messages[-1]:
            messages[-1].pop("images", None)

        messages.append({"role": "assistant", "content": raw_ai_message})

        # ================= STEP VERIFICATION =================
        focus_element_path = vision.focus(step["Target_Box_ID"], elements, screenshot_path)
        if not focus_element_path:
            messages.append({
                "role": "user",
                "content": "System feedback: Invalid target ID."
            })
            continue

        verdict = operator.verify(goal, focus_element_path, step)

        print("\n┌──────────────────────────────────── HARMONY VERIFIER ──────────────────────────────────┐")
        print(f"│ STATUS  : {verdict.get('verdict', 'unknown').upper()}")
        print(f"│ VISUAL DESCRIPTION  : {verdict.get('visual_description', 'no visual description provided').upper()}")
        print(f"│ REASON  : {verdict.get('reason', 'no reason provided')}")
        print("└────────────────────────────────────────────────────────────────────────────────────────┘\n")

        if verdict.get("verdict") != "accept":
            feedback = f"Verifier rejected action: {verdict.get('reason')}"
            messages.append({"role": "user", "content": f"System feedback: {feedback}"})
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


