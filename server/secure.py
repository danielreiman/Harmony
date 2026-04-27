# How this works (no jargon):
#
# The server keeps a private lock that only it can open. It hands out
# a matching public lock that anyone can close but no one else can
# open. When a client connects, the server gives it the public lock.
# The client picks a random secret password, closes it inside the
# public lock, and sends it back. Only the server can open it, so now
# both sides know the password — and nobody else does. From then on,
# every message is scrambled with that password before being sent,
# and unscrambled on the other side.

import json
import os

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


KEY_FILE = os.path.join(os.path.dirname(__file__), "server_key.pem")
LOCK = padding.OAEP(padding.MGF1(hashes.SHA256()), hashes.SHA256(), None)


def _send(sock, data):
    sock.sendall(len(data).to_bytes(8, "big") + data)


def _recv(sock):
    def read(n):
        buf = b""
        while len(buf) < n:
            chunk = sock.recv(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf
    header = read(8)
    return read(int.from_bytes(header, "big")) if header else None


class Channel:
    # A connection where every message is scrambled with the shared password.
    def __init__(self, sock, password):
        self.sock = sock
        self.box = AESGCM(password)

    def send(self, message):
        try:
            self._put(json.dumps(message).encode())
            return True
        except OSError:
            return False

    def recv(self):
        data = self._get()
        return json.loads(data) if data else None

    def send_bytes(self, data):
        self._put(data)

    def recv_bytes(self):
        return self._get()

    def _put(self, data):
        nonce = os.urandom(12)
        _send(self.sock, nonce + self.box.encrypt(nonce, data, None))

    def _get(self):
        blob = _recv(self.sock)
        return self.box.decrypt(blob[:12], blob[12:], None) if blob else None


def load_or_create_keys():
    # Make a private/public lock pair the first time, then keep reusing it.
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "rb") as f:
            private_lock = serialization.load_pem_private_key(f.read(), None)
    else:
        private_lock = rsa.generate_private_key(65537, 2048)
        with open(KEY_FILE, "wb") as f:
            f.write(private_lock.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption()))
    public_lock = private_lock.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo)
    return private_lock, public_lock


def server_handshake(sock, private_lock, public_lock):
    # Hand the client the public lock; receive the password it sent back.
    try:
        _send(sock, public_lock)
        sealed_password = _recv(sock)
        if not sealed_password:
            return None
        password = private_lock.decrypt(sealed_password, LOCK)
        return Channel(sock, password)
    except (OSError, ValueError):
        return None


def client_handshake(sock):
    # Receive the public lock, pick a password, send it back inside the lock.
    public_lock = _recv(sock)
    if not public_lock:
        return None
    lock = serialization.load_pem_public_key(public_lock)
    password = os.urandom(32)
    _send(sock, lock.encrypt(password, LOCK))
    return Channel(sock, password)
