import json, socket, threading, os, sys

_here = os.path.dirname(__file__)
sys.path.insert(0, os.path.dirname(_here))

from transport import client_secure



server_host = "localhost"

UDP_DISCOVERY_PORT = 3030
HARMONY_BEACON = b"HARMONY_SERVER"
GATEWAY_SERVER_PORT = 1223


def watch_for_server():
    # Background listener: update server_host whenever we hear the LAN beacon.
    global server_host
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(socket, "SO_REUSEPORT"):  # share the port with other local components
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    udp_socket.bind(("", UDP_DISCOVERY_PORT))
    while True:
        try:
            packet, sender_address = udp_socket.recvfrom(1024)
            if packet == HARMONY_BEACON:
                server_host = sender_address[0]
        except Exception:
            continue  # keep listening so re-discovery survives transient errors


threading.Thread(target=watch_for_server, daemon=True).start()


def request(payload):
    # Send one request to the server and return its reply ({} on any failure).
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(10)
        sock.connect((server_host, GATEWAY_SERVER_PORT))
        security = client_secure(sock)            # encrypt the channel
        if security is None:
            return {}
        if not security.send(sock, payload):
            return {}
        data = security.recv(sock)
        return json.loads(data) if data else {}
    except Exception:
        return {}                                 # never crash the UI on a network error
    finally:
        sock.close()
