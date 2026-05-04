import os, sys, time
from cfonts import render


PURPLE = "\033[38;5;141m"
GRAY = "\033[38;5;245m"
GREEN = "\033[38;5;114m"
RED = "\033[38;5;203m"
WHITE = "\033[1;37m"
DIM = "\033[2m"
RESET = "\033[0m"
BOLD = "\033[1m"


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def banner():
    output = render(
        "Harmony",
        font="tiny",
        colors=["white"],
        align="left",
        space=False,
    )
    print(output)
    print(f"{GRAY}{'─' * 52}")
    print(f"{DIM}{'Server Setup'}{RESET}\n")


def typed(text, delay=0.02):
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(delay)
    print()


def prompt(label, secret=False):
    print(f"  {PURPLE}>{RESET} {WHITE}{label}{RESET}")
    print()
    value = input(f"    {DIM}→{RESET}  ").strip()
    print()
    return value


def success(text):
    print(f"  {GREEN}✓{RESET}  {text}")


def error(text):
    print(f"  {RED}✗{RESET}  {text}")


def step(number, text):
    print(f"  {PURPLE}[{number}]{RESET}  {GRAY}{text}{RESET}")
    print()


def main():
    clear()
    banner()

    step(1, "Configure Holo3 connection")
    typed(f"  {DIM}Enter your Holo3 API key to connect the AI engine.{RESET}", 0.015)
    print()

    api_key = prompt("Holo3 API Key")

    if not api_key:
        error("API key is required. Setup aborted.")
        print()
        return

    step(2, "Saving configuration")

    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    for i in range(12):
        sys.stdout.write(f"\r    {PURPLE}{frames[i % len(frames)]}{RESET}  Writing .env file...")
        sys.stdout.flush()
        time.sleep(0.08)

    with open(".env", "w") as f:
        f.write(f"HAI_API_KEY={api_key}\n")

    sys.stdout.write(f"\r    {GREEN}✓{RESET}  Configuration saved to .env    \n")
    print()

    print(f"{GRAY}{'─' * 52}".center(80))
    print()
    success("Setup complete!")
    print()
    typed(f"  {DIM}Run the server with:  {WHITE}python server.py{RESET}", 0.015)
    print()


if __name__ == "__main__":
    main()
