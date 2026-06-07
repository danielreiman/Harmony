import json
from nacl.public import PrivateKey, PublicKey, SealedBox
from cryptography.fernet import Fernet


def send_frame(sock, data):
    sock.sendall(len(data).to_bytes(8) + data)  # 8-byte length header, then the bytes


def recv_frame(sock):
    header = b""
    while len(header) < 8:                       # read the full 8-byte length prefix
        chunk = sock.recv(8 - len(header))
        if not chunk:
            return None
        header += chunk
    size = int.from_bytes(header)                # how many bytes the body has
    data = b""
    while len(data) < size:                      # keep reading until we have the whole body
        chunk = sock.recv(size - len(data))
        if not chunk:
            return None
        data += chunk
    return data


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
    # Wraps a socket so every message is encrypted with the shared session key.
    def __init__(self, key):
        self.cipher = Fernet(key)

    def send(self, sock, data):
        if isinstance(data, dict):
            data = json.dumps(data).encode()  # dicts are sent as JSON
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
        try:
            return self.cipher.decrypt(encrypted)   # 2 decrypt
        except Exception:
            return None                             # corrupt/garbage frame
