import time
import keyboard
from agent.vision import Vision
from agent.operator import Operator
from agent.prompts import MAIN_PROMPT

def main():
    goal = "Open the first ever youtube video"

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

        print("=========== ACTION ===========")
        print(f"REASONING: {step["Reasoning"]}")
        print(f"ACTION: {step["Next Action"]}")
        print(f"TARGET BOX: {step["Target_Box_ID"]}")
        print(f"VALUE: {step["Value"]}")
        print("==============================\n")

        if messages and "images" in messages[-1]:
            messages[-1].pop("images", None)

        messages.append({"role": "assistant", "content": raw_ai_message})

        # ================= STEP VERIFICATION =================
        focus_element_path = vision.focus(step["Target_Box_ID"], elements, screenshot_path)
        verdict = operator.verify(goal, focus_element_path, messages[-1])

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
