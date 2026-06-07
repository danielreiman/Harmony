import json, socket, threading
from keys import load_keys
from transport import server_secure
from handlers import route_request


def handle_connection(conn, our_key, open_key):
    # One admin request per connection: read it, answer it, close.
    try:
        security = server_secure(conn, our_key, open_key)  # encrypt channel
        if security is None:
            return

        data = security.recv(conn)
        request = json.loads(data) if data else None

        if request is not None:
            security.send(conn, route_request(request))  # run it and reply

    except Exception as error:
        print(f"[Gateway] Connection error: {error}")

    finally:
        conn.close()


def run_gateway(host="0.0.0.0", port=1223):
    our_key, open_key = load_keys()

    try:
        gateway_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        gateway_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        gateway_sock.bind((host, port))
        gateway_sock.listen()
        print(f"[✓] Gateway is listening for admin-clients (TCP port {port})")
    except Exception as error:
        print(f"[✗] Gateway failed to start on port {port}: {error}")
        return

    while True:
        try:
            conn, client_addr = gateway_sock.accept()  # wait for an admin client

            # Handle each request on its own thread so many admins can talk at once.
            t = threading.Thread(target=handle_connection, args=(conn, our_key, open_key), daemon=True)
            t.start()
        except Exception:
            break
