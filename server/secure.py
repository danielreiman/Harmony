# Secure channel.
#
# The server keeps a long-term lock (RSA private key). When a client
# connects, the server hands out the matching public lock. The client
# picks a random shared key, locks it with the public lock, and sends
# it back — only the server can unlock it. After that, both sides
# scramble every message with that shared key (AES-GCM).

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
    def __init__(self, sock, shared_key):
        self.sock = sock
        self.box = AESGCM(shared_key)

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
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "rb") as f:
            priv = serialization.load_pem_private_key(f.read(), None)
    else:
        priv = rsa.generate_private_key(65537, 2048)
        with open(KEY_FILE, "wb") as f:
            f.write(priv.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption()))
    public_lock = priv.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo)
    return priv, public_lock


def server_handshake(sock, priv, public_lock):
    try:
        _send(sock, public_lock)
        sealed = _recv(sock)
        if not sealed:
            return None
        return Channel(sock, priv.decrypt(sealed, LOCK))
    except (OSError, ValueError):
        return None


def client_handshake(sock):
    public_lock = _recv(sock)
    if not public_lock:
        return None
    pub_key = serialization.load_pem_public_key(public_lock)
    shared_key = os.urandom(32)
    _send(sock, pub_key.encrypt(shared_key, LOCK))
    return Channel(sock, shared_key)
