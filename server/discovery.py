import socket, time

BROADCAST_PORT = 3030


def broadcast():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    while True:
        try:
            sock.sendto(b"HARMONY_SERVER", ("255.255.255.255", BROADCAST_PORT))
        except OSError:
            pass
        time.sleep(1)
