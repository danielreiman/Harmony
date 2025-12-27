import json, socket, time

def broadcast():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    while True:
        s.sendto(b"HARMONY_SERVER", ("255.255.255.255", 3030))
        time.sleep(1)

def send(obj, conn):
    try:
        conn.sendall(json.dumps(obj).encode())
        return True
    except (ConnectionError, BrokenPipeError, OSError):
        return False

def recv(conn):
    try:
        data = conn.recv(4096)
        if not data:
            return None
        return json.loads(data.decode())
    except (ConnectionError, BrokenPipeError, OSError, json.JSONDecodeError):
        return None

def recv_file(path, conn):
    try:
        size_bytes = conn.recv(8)
        if len(size_bytes) < 8:
            return False
        size = int.from_bytes(size_bytes, "big")
        data = b""
        while len(data) < size:
            chunk = conn.recv(min(4096, size - len(data)))
            if not chunk:
                return False
            data += chunk

        with open(path, "wb") as f:
            f.write(data)
        return True
    except (ConnectionError, BrokenPipeError, OSError):
        return False