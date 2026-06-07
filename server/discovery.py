import socket, time

BROADCAST_PORT = 3030


def broadcast():
    # Shout "I'm here" on the LAN once a second so agents/admins can find us.
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    while True:
        try:
            sock.sendto(b"HARMONY_SERVER", ("255.255.255.255", BROADCAST_PORT))
        except OSError:
            pass  # network briefly unavailable — try again next second
        time.sleep(1)
