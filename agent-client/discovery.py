import socket

BROADCAST_PORT = 3030


def discover(timeout=30, server_port=1222):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", BROADCAST_PORT))
    sock.settimeout(timeout)
    try:
        while True:
            packet, (ip, _) = sock.recvfrom(1024)
            if packet == b"HARMONY_SERVER":
                return ip
    except socket.timeout:
        raise RuntimeError(f"No Harmony server found within {timeout}s")
    finally:
        sock.close()
