import json
import socket
import time

BROADCAST_PORT = 3030
TIMEOUT = 120.0
CHUNK_SIZE = 4096


def broadcast():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    while True:
        try:
            sock.sendto(b"HARMONY_SERVER", ("255.255.255.255", 3030))
        except OSError:
            pass
        time.sleep(1)


def send(obj, conn):
    try:
        data = json.dumps(obj).encode("utf-8")
        conn.sendall(data)
        return True
    except (ConnectionError, BrokenPipeError, OSError):
        return False


def recv(conn):
    try:
        conn.settimeout(120.0)
        data = conn.recv(4096)
        if not data:
            return None
        return json.loads(data.decode("utf-8"))
    except socket.timeout:
        print("[Helpers] Receive timeout")
        return None
    except json.JSONDecodeError as e:
        print(f"[Helpers] Invalid JSON: {e}")
        return None
    except (ConnectionError, BrokenPipeError, OSError):
        return None


def recv_file(path, conn):
    try:
        conn.settimeout(120.0)

        size_bytes = conn.recv(8)
        if len(size_bytes) < 8:
            print("[Helpers] Failed to receive file size")
            return False

        size = int.from_bytes(size_bytes, "big")

        data = b""
        while len(data) < size:
            remaining = size - len(data)
            chunk_size = min(4096, remaining)
            chunk = conn.recv(chunk_size)
            if not chunk:
                print(f"[Helpers] Connection closed at {len(data)}/{size} bytes")
                return False
            data += chunk

        with open(path, "wb") as f:
            f.write(data)
        return True

    except socket.timeout:
        print("[Helpers] File timeout")
        return False
    except (ConnectionError, BrokenPipeError, OSError) as e:
        print(f"[Helpers] File error: {e}")
        return False
