# Hybrid RSA + AES-GCM transport.
# Server publishes its RSA public key on connect; client returns an
# RSA-OAEP encrypted AES-256 key. All subsequent frames are AES-GCM.

import json
import os
import socket

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


KEY_FILE = os.path.join(os.path.dirname(__file__), "server_key.pem")


def load_or_create_keys():
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "rb") as f:
            priv = serialization.load_pem_private_key(f.read(), password=None)
    else:
        priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        with open(KEY_FILE, "wb") as f:
            f.write(priv.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption()))
    pub_pem = priv.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo)
    return priv, pub_pem


_OAEP = padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),
                     algorithm=hashes.SHA256(), label=None)


def _read_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def _send_frame(sock, data):
    sock.sendall(len(data).to_bytes(8, "big") + data)


def _recv_frame(sock):
    header = _read_exact(sock, 8)
    if header is None:
        return None
    return _read_exact(sock, int.from_bytes(header, "big"))


class Session:
    def __init__(self, sock, aes_key):
        self.sock = sock
        self.aead = AESGCM(aes_key)

    def send(self, message):
        try:
            self._send_bytes(json.dumps(message).encode("utf-8"))
            return True
        except (OSError, ConnectionError):
            return False

    def recv(self):
        try:
            data = self._recv_bytes()
            if data is None:
                return None
            return json.loads(data.decode("utf-8"))
        except (OSError, ConnectionError, ValueError):
            return None

    def send_bytes(self, data):
        self._send_bytes(data)

    def recv_bytes(self):
        return self._recv_bytes()

    def _send_bytes(self, data):
        nonce = os.urandom(12)
        ct = self.aead.encrypt(nonce, data, None)
        _send_frame(self.sock, nonce + ct)

    def _recv_bytes(self):
        frame = _recv_frame(self.sock)
        if frame is None or len(frame) < 13:
            return None
        return self.aead.decrypt(frame[:12], frame[12:], None)


def server_handshake(sock, priv_key, pub_pem):
    try:
        _send_frame(sock, pub_pem)
        encrypted_key = _recv_frame(sock)
        if encrypted_key is None:
            return None
        aes_key = priv_key.decrypt(encrypted_key, _OAEP)
        return Session(sock, aes_key)
    except (OSError, ConnectionError, ValueError):
        return None


def client_handshake(sock):
    pub_pem = _recv_frame(sock)
    if pub_pem is None:
        return None
    pub_key = serialization.load_pem_public_key(pub_pem)
    aes_key = os.urandom(32)
    encrypted_key = pub_key.encrypt(aes_key, _OAEP)
    _send_frame(sock, encrypted_key)
    return Session(sock, aes_key)
