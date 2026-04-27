# How this works (no jargon):
#
# The server has a private lock that only it can open, plus a matching
# public lock that anyone can close. When we connect, the server gives
# us the public lock. We pick a random password, close it inside the
# public lock, and send it back. Only the server can open it, so now
# both sides know the password — and nobody else does. From then on,
# every message is scrambled with that password before being sent,
# and unscrambled on the other side.

import json
import os

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM as Scrambler


LOCK = padding.OAEP(padding.MGF1(hashes.SHA256()), hashes.SHA256(), None)


def _write(connection, data):
    connection.sendall(len(data).to_bytes(8, "big") + data)


def _read(connection):
    def take(count):
        buffer = b""
        while len(buffer) < count:
            piece = connection.recv(count - len(buffer))
            if not piece:
                return None
            buffer += piece
        return buffer
    header = take(8)
    return take(int.from_bytes(header, "big")) if header else None


class Channel:
    # A connection where every message is scrambled with the shared password.
    def __init__(self, connection, password):
        self.connection = connection
        self.scrambler = Scrambler(password)

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
        marker = os.urandom(12)
        _write(self.connection, marker + self.scrambler.encrypt(marker, data, None))

    def _get(self):
        package = _read(self.connection)
        if not package:
            return None
        return self.scrambler.decrypt(package[:12], package[12:], None)


def client_handshake(connection):
    # Receive the public lock, pick a password, send it back sealed inside.
    public_lock = _read(connection)
    if not public_lock:
        return None
    lock = serialization.load_pem_public_key(public_lock)
    password = os.urandom(32)
    _write(connection, lock.encrypt(password, LOCK))
    return Channel(connection, password)
