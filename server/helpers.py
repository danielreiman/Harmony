import json
import random
import socket
import time

BROADCAST_PORT = 3030


AGENT_NAMES = [
    "Sam", "Alex", "Jordan", "Taylor", "Casey", "Riley", "Morgan", "Quinn",
    "Avery", "Parker", "Rowan", "Sage", "Emery", "Finley", "Hayden", "Kai",
    "Reese", "Skyler", "Blake", "Drew", "Ellis", "Frankie", "Harper", "Jamie",
    "Kendall", "Logan", "Marley", "Noel", "Oakley", "Peyton", "Remy", "Shiloh",
    "Tatum", "Wren", "Zion", "Ari", "Bailey", "Charlie", "Dakota", "Eden",
    "Gray", "Hollis", "Indigo", "Juno", "Kit", "Lane", "Micah", "Nova",
    "Onyx", "Pax", "Quill", "Ryder", "Sawyer", "Toby", "Uri", "Vale",
    "Wes", "Xen", "York", "Zane", "Amari", "Bevan", "Corin", "Daryn",
    "Elian", "Faron", "Galen", "Haven", "Ira", "Joss", "Kyro", "Linden",
    "Merin", "Niko", "Orin", "Pell", "Quen", "Rune", "Soren", "Tarin",
    "Uma", "Vesper", "Wynn", "Xander", "Yael", "Zephyr",
]


def pick_agent_name(taken):
    taken = set(taken)
    free = [n for n in AGENT_NAMES if n not in taken]
    if free:
        return random.choice(free)
    base = random.choice(AGENT_NAMES)
    suffix = 2
    while f"{base} [{suffix}]" in taken:
        suffix += 1
    return f"{base} [{suffix}]"


def broadcast():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    while True:
        try:
            sock.sendto(b"HARMONY_SERVER", ("255.255.255.255", BROADCAST_PORT))
        except OSError:
            pass
        time.sleep(1)


def local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"


def extract_json(text):
    json_start = text.find("{")
    json_end = text.rfind("}")
    if json_start == -1 or json_end == -1:
        return None
    try:
        return json.loads(text[json_start:json_end + 1])
    except json.JSONDecodeError:
        return None
