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
            sock.sendto(b"HARMONY_SERVER", ("255.255.255.255", BROADCAST_PORT))
        except OSError:
            pass
        time.sleep(1)


def get_lan_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"


def _recv_exact(conn, size):
    data = b""
    while len(data) < size:
        chunk = conn.recv(size - len(data))
        if not chunk:
            return None
        data += chunk
    return data


def send(obj, conn):
    try:
        data = json.dumps(obj).encode("utf-8")
        conn.sendall(len(data).to_bytes(8, "big"))
        conn.sendall(data)
        return True
    except (ConnectionError, BrokenPipeError, OSError):
        return False


def recv(conn):
    try:
        conn.settimeout(TIMEOUT)
        size_bytes = _recv_exact(conn, 8)
        if not size_bytes:
            return None
        size = int.from_bytes(size_bytes, "big")
        if size <= 0:
            return None
        data = _recv_exact(conn, size)
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
        conn.settimeout(TIMEOUT)

        size_bytes = _recv_exact(conn, 8)
        if not size_bytes:
            print("[Helpers] Failed to receive file size")
            return False

        size = int.from_bytes(size_bytes, "big")
        if size <= 0:
            print("[Helpers] Invalid file size")
            return False

        received = 0
        with open(path, "wb") as f:
            while received < size:
                remaining = size - received
                chunk_size = min(CHUNK_SIZE, remaining)
                chunk = conn.recv(chunk_size)
                if not chunk:
                    print(f"[Helpers] Connection closed at {received}/{size} bytes")
                    return False
                f.write(chunk)
                received += len(chunk)
        return True

    except socket.timeout:
        print("[Helpers] File timeout")
        return False
    except (ConnectionError, BrokenPipeError, OSError) as e:
        print(f"[Helpers] File error: {e}")
        return False
