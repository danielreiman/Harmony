import json
import socket
import threading
import config

SERVER_PORT = 1223
CONNECT_TIMEOUT_SECONDS = 2
REQUEST_TIMEOUT_SECONDS = 10
UDP_DISCOVERY_PORT = 3030
HARMONY_BEACON = b"HARMONY_SERVER"

_discovered_server_host = None
_server_host_lock = threading.Lock()


def _listen_for_server_broadcasts():
    global _discovered_server_host
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp_socket.bind(("", UDP_DISCOVERY_PORT))
    while True:
        try:
            packet, sender_address = udp_socket.recvfrom(1024)
            packet_is_harmony_beacon = packet == HARMONY_BEACON
            if packet_is_harmony_beacon:
                with _server_host_lock:
                    _discovered_server_host = sender_address[0]
        except Exception:
            break


if config.HARMONY_SERVER:
    _discovered_server_host = config.HARMONY_SERVER
else:
    threading.Thread(target=_listen_for_server_broadcasts, daemon=True).start()


def _get_local_machine_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def _resolve_server_host() -> str:
    with _server_host_lock:
        discovered_host = _discovered_server_host
    host = discovered_host or "localhost"

    local_ip = _get_local_machine_ip()
    server_is_on_local_machine = host == local_ip
    if server_is_on_local_machine:
        return "127.0.0.1"

    return host


def _recv_exact(sock: socket.socket, byte_count: int) -> bytes | None:
    received = b""
    while len(received) < byte_count:
        chunk = sock.recv(byte_count - len(received))
        if not chunk:
            return None
        received += chunk
    return received


def ping() -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(CONNECT_TIMEOUT_SECONDS)
        sock.connect((_resolve_server_host(), SERVER_PORT))
        sock.close()
        return True
    except Exception:
        return False


def request(action: str, **params) -> dict:
    request_payload = {"action": action}
    request_payload.update(params)
    request_body = json.dumps(request_payload).encode()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(REQUEST_TIMEOUT_SECONDS)
        sock.connect((_resolve_server_host(), SERVER_PORT))

        length_prefix = len(request_body).to_bytes(4, "big")
        sock.sendall(length_prefix + request_body)

        response_length_bytes = _recv_exact(sock, 4)
        if response_length_bytes is None:
            return {}

        response_length = int.from_bytes(response_length_bytes, "big")

        response_body = _recv_exact(sock, response_length)
        if response_body is None:
            return {}

        return json.loads(response_body)
    except Exception as error:
        print(f"[Proxy] {action} failed: {error}")
        return {}
    finally:
        sock.close()
