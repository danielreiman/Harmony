import json, socket

def send(obj, conn):
    conn.sendall(json.dumps(obj).encode())


def recv(conn):
    data = conn.recv(4096)
    return json.loads(data.decode()) if data else None


def recv_file(path, conn):
    size = int.from_bytes(conn.recv(8), "big")
    data = b""
    while len(data) < size:
        data += conn.recv(4096)

    with open(path, "wb") as f:
        f.write(data)

    return True