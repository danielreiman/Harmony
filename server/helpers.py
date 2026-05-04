import json
import os
import random
import socket
import time
from nacl.public import PrivateKey, PublicKey, SealedBox
from cryptography.fernet import Fernet
from PIL import Image, ImageOps

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


def send_frame(sock, data):
    sock.sendall(len(data).to_bytes(8, "big") + data)


def recv_frame(sock):
    size = sock.recv(8)
    if not size:
        return None
    size = int.from_bytes(size, "big")
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            return None
        data += chunk
    return data


def load_keys():
    if os.path.exists(KEYS_FILE):
        private = PrivateKey(open(KEYS_FILE, "rb").read())
    else:
        private = PrivateKey.generate()
        open(KEYS_FILE, "wb").write(bytes(private))
    public = bytes(private.public_key)
    return private, public


def server_secure(sock, private, public):
    try:
        send_frame(sock, public)                # 1 send public key
        sealed_key = recv_frame(sock)           # 2 receive sealed key
        if not sealed_key:
            return None
        key = SealedBox(private).decrypt(sealed_key)  # 3 open key
        return Secure(key)                      # 4 ready
    except Exception:
        return None


def client_secure(sock):
    try:
        public = recv_frame(sock)               # 1 receive public key
        if not public:
            return None
        key = Fernet.generate_key()             # 2 make session key
        sealed_key = SealedBox(PublicKey(public)).encrypt(key)  # 3 seal key
        send_frame(sock, sealed_key)            # 4 send sealed key
        return Secure(key)                      # 5 ready
    except Exception:
        return None


class Secure:
    def __init__(self, key):
        self.cipher = Fernet(key)

    def send(self, sock, data):
        if isinstance(data, dict):
            data = json.dumps(data).encode()
        try:
            encrypted = self.cipher.encrypt(data)   # 1 encrypt
            send_frame(sock, encrypted)             # 2 send
            return True
        except Exception:
            return False

    def recv(self, sock):
        encrypted = recv_frame(sock)                # 1 receive
        if not encrypted:
            return None
        return self.cipher.decrypt(encrypted)       # 2 decrypt


def prepare_screenshot_for_ai(source_path, output_path):
    MAX_BYTES   = 1_500_000
    MAX_SIDE    = 1280
    MIN_QUALITY = 35
    try:
        with Image.open(source_path) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
            if image.mode != "RGB":
                image = image.convert("RGB")
            quality = 70
            while quality >= MIN_QUALITY:
                image.save(output_path, format="JPEG", quality=quality, optimize=True)
                if os.path.getsize(output_path) <= MAX_BYTES:
                    return output_path
                quality -= 10
            image.save(output_path, format="JPEG", quality=MIN_QUALITY, optimize=True)
            return output_path
    except Exception as e:
        print(f"[Agent] Could not shrink screenshot: {e}")
        return source_path


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


def local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
