import time
import keyboard
import pyautogui
from agent.operator import Operator
from agent.prompts import MAIN_PROMPT

def main():
    goal = "Calculate 9+10 without using reasoning and only using the computer"

    operator = Operator("qwen3-vl:235b-instruct-cloud", "qwen3-vl:235b-instruct-cloud")

    print("[LOG] Agent running. Press ESC to stop.")

    messages = [
        {"role": "system", "content": MAIN_PROMPT},
        {"role": "user", "content": f"Goal: {goal}"}
    ]

    while not keyboard.is_pressed("esc"):
        # ================= VISION =================
        screenshot_path = f"./runtime/screenshot.png"

        img = pyautogui.screenshot()
        img.save(screenshot_path)

        messages.append({
            "role": "user",
            "content": "Current view",
            "images": [screenshot_path]
        })

        # ================= AI =================
        step, raw_ai_message = operator.think(messages)

        print("\n┌──────────────────────────────────── HARMONY AGENT STEP ──────────────────────────────────┐")
        print(f"│ REASON  : {step.get('Reasoning', 'no reasoning provided')}")
        print(f"│ ACTION  : {step.get('Next Action', 'no action provided')}")
        print(f"│ TARGET  : {step.get('Coordinate', 'no coordinate provided')}")
        print(f"│ VALUE   : {step.get('Value', 'no value provided')}")
        print("└────────────────────────────────────────────────────────────────────────────────────────┘\n")

        if messages and "images" in messages[-1]:
            messages[-1].pop("images", None)

        messages.append({"role": "assistant", "content": raw_ai_message})

        if step.get("Next Action") in [None, "None"]:
            print("[LOG] Task complete.")
            break

        # ================= EXECUTION AND FEEDBACK =================
        feedback = operator.act(step)
        messages.append({"role": "user", "content": f"System feedback: {feedback}"})

        time.sleep(1)

    print("[LOG] Program finished.")


if __name__ == "__main__":
    main()


