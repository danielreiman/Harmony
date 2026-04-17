import json
import socket


def read_exact(sock, byte_count):
    data = b""
    while len(data) < byte_count:
        chunk = sock.recv(byte_count - len(data))
        if not chunk:
            return None
        data += chunk
    return data


def send(sock, message):
    data = json.dumps(message).encode()
    sock.sendall(len(data).to_bytes(8, "big") + data)


def recv(sock):
    size_bytes = read_exact(sock, 8)
    if not size_bytes:
        return None
    resp = read_exact(sock, int.from_bytes(size_bytes, "big"))
    return json.loads(resp) if resp else None
