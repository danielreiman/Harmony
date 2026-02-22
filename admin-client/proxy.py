import json
import os
import socket
import threading

SERVER_PORT = 1223
CONNECT_TIMEOUT_SECONDS = 2
REQUEST_TIMEOUT_SECONDS = 10
UDP_DISCOVERY_PORT = 3030
HARMONY_BEACON = b"HARMONY_SERVER"

_discovered_server_host = None
_server_host_lock = threading.Lock()


def _watch_for_server():
    """Listens on UDP for server beacon packets and updates the discovered host address so the proxy knows where to connect."""
    global _discovered_server_host
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp_socket.bind(("", UDP_DISCOVERY_PORT))
    while True:
        try:
            packet, sender_address = udp_socket.recvfrom(1024)
            if packet == HARMONY_BEACON:
                with _server_host_lock:
                    _discovered_server_host = sender_address[0]
        except Exception:
            break


_FIXED_SERVER = os.environ.get("HARMONY_SERVER", "")

if _FIXED_SERVER:
    _discovered_server_host = _FIXED_SERVER
else:
    threading.Thread(target=_watch_for_server, daemon=True).start()


def _machine_ip():
    """Determines the dashboard machine's outbound LAN IP address."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def _server_host():
    """Returns the best known server host, substituting localhost if the server is running on this machine."""
    with _server_host_lock:
        discovered_host = _discovered_server_host
    host = discovered_host or "localhost"

    if host == _machine_ip():
        return "127.0.0.1"

    return host


def _read_exact(sock, byte_count):
    """Reads an exact number of bytes from the socket, returning None if the connection closes early."""
    received = b""
    while len(received) < byte_count:
        chunk = sock.recv(byte_count - len(received))
        if not chunk:
            return None
        received += chunk
    return received


def ping():
    """Attempts a TCP connection to the server to check whether it is currently reachable."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(CONNECT_TIMEOUT_SECONDS)
        sock.connect((_server_host(), SERVER_PORT))
        sock.close()
        return True
    except Exception:
        return False


def request(action, **params):
    """Sends a JSON request to the API server and returns the parsed response — used by every dashboard route."""
    request_payload = {"action": action}
    request_payload.update(params)
    request_body = json.dumps(request_payload).encode()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(REQUEST_TIMEOUT_SECONDS)
        sock.connect((_server_host(), SERVER_PORT))

        length_prefix = len(request_body).to_bytes(4, "big")
        sock.sendall(length_prefix + request_body)

        response_length_bytes = _read_exact(sock, 4)
        if response_length_bytes is None:
            return {}

        response_length = int.from_bytes(response_length_bytes, "big")

        response_body = _read_exact(sock, response_length)
        if response_body is None:
            return {}

        return json.loads(response_body)
    except Exception as error:
        print(f"[Proxy] {action} failed: {error}")
        return {}
    finally:
        sock.close()
