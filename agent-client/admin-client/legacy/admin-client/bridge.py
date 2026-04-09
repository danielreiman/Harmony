import socket
import threading

from helpers import send, recv

server_host = "localhost"

UDP_DISCOVERY_PORT = 3030
HARMONY_BEACON = b"HARMONY_SERVER"
API_SERVER_PORT = 1223


def _watch_for_server():
    global server_host
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.bind(("", UDP_DISCOVERY_PORT))

    while True:
        try:
            packet, sender_address = udp_socket.recvfrom(1024)
            if packet == HARMONY_BEACON:
                server_host = sender_address[0]
        except:
            break


threading.Thread(target=_watch_for_server, daemon=True).start()


def request(payload):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(10)
        sock.connect((server_host, API_SERVER_PORT))
        send(sock, payload)
        return recv(sock) or {}
    except:
        return {}
    finally:
        sock.close()
