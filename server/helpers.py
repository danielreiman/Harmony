import json, os, random, socket, time

from nacl.public import PrivateKey
from PIL import Image, ImageOps

from shared import send_frame, recv_frame, Secure, server_secure

BROADCAST_PORT = 3030
KEYS_FILE = os.path.join(os.path.dirname(__file__), "server_keys.bin")

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


def load_keys():
    if os.path.exists(KEYS_FILE):
        private = PrivateKey(open(KEYS_FILE, "rb").read())
    else:
        private = PrivateKey.generate()
        with open(KEYS_FILE, "wb") as f:
            f.write(bytes(private))
    public = bytes(private.public_key)
    return private, public


def prepare_screenshot_for_ai(src, dst):
    try:
        img = Image.open(src)
        img = ImageOps.exif_transpose(img)
        img.thumbnail((1200, 1200))
        img = img.convert("RGB")

        img.save(dst, "JPEG", quality=60, optimize=True)
        return dst

    except:
        return src

def extract_json(text):
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


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
