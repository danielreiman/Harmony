import json, socket, time

def broadcast():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    while True:
        s.sendto(b"HARMONY_SERVER", ("255.255.255.255", 3030))
        time.sleep(1)

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