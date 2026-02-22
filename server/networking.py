import json
import socket
import time

BROADCAST_PORT = 3030
SOCKET_TIMEOUT_SECONDS = 120.0
FILE_CHUNK_SIZE = 4096


def broadcast():
    """Continuously broadcasts a UDP beacon so clients can discover this server on the LAN."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    while True:
        try:
            sock.sendto(b"HARMONY_SERVER", ("255.255.255.255", BROADCAST_PORT))
        except OSError:
            pass
        time.sleep(1)


def local_ip():
    """Determines the machine's local network IP address for display and routing."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"


def _read_exact(conn, byte_count):
    """Reads an exact number of bytes from the connection, returning None if it closes early."""
    received = b""
    while len(received) < byte_count:
        chunk = conn.recv(byte_count - len(received))
        if not chunk:
            return None
        received += chunk
    return received


def send(message, conn):
    """Sends a JSON message with an 8-byte length prefix, returning True on success."""
    try:
        encoded = json.dumps(message).encode("utf-8")
        message_length = len(encoded).to_bytes(8, "big")
        conn.sendall(message_length)
        conn.sendall(encoded)
        return True
    except (ConnectionError, BrokenPipeError, OSError):
        return False


def recv(conn):
    """Reads and deserializes a length-prefixed JSON message from the connection."""
    try:
        conn.settimeout(SOCKET_TIMEOUT_SECONDS)

        size_bytes = _read_exact(conn, 8)
        if size_bytes is None:
            return None

        message_size = int.from_bytes(size_bytes, "big")
        if message_size <= 0:
            return None

        raw_data = _read_exact(conn, message_size)
        if raw_data is None:
            return None

        return json.loads(raw_data.decode("utf-8"))

    except socket.timeout:
        print("[Helpers] Receive timeout")
        return None
    except json.JSONDecodeError as error:
        print(f"[Helpers] Invalid JSON: {error}")
        return None
    except (ConnectionError, BrokenPipeError, OSError):
        return None


def receive_file(destination_path, conn):
    """Receives a length-prefixed file over the connection and writes it to disk, returning True on success."""
    try:
        conn.settimeout(SOCKET_TIMEOUT_SECONDS)

        size_bytes = _read_exact(conn, 8)
        if size_bytes is None:
            print("[Helpers] Failed to receive file size header")
            return False

        file_size = int.from_bytes(size_bytes, "big")
        if file_size <= 0:
            print("[Helpers] Invalid file size")
            return False

        bytes_received = 0
        with open(destination_path, "wb") as f:
            while bytes_received < file_size:
                remaining_bytes = file_size - bytes_received
                chunk_size = min(FILE_CHUNK_SIZE, remaining_bytes)
                chunk = conn.recv(chunk_size)
                if not chunk:
                    print(f"[Helpers] Connection closed after {bytes_received}/{file_size} bytes")
                    return False
                f.write(chunk)
                bytes_received += len(chunk)

        return True

    except socket.timeout:
        print("[Helpers] File transfer timeout")
        return False
    except (ConnectionError, BrokenPipeError, OSError) as error:
        print(f"[Helpers] File transfer error: {error}")
        return False
