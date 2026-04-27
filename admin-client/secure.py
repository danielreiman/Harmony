# Secure channel — client side.
#
# Server hands us its public lock. We pick a random shared key, lock it
# with that public lock, and send it back. Only the server can unlock
# it. From then on, every message is scrambled with that shared key.

import json
import os

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


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


def client_handshake(sock):
    public_lock = _recv(sock)
    if not public_lock:
        return None
    pub_key = serialization.load_pem_public_key(public_lock)
    shared_key = os.urandom(32)
    _send(sock, pub_key.encrypt(shared_key, LOCK))
    return Channel(sock, shared_key)
