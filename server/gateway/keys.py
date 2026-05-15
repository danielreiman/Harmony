import os
from nacl.public import PrivateKey

KEYS_FILE = os.path.join(os.path.dirname(__file__), "resources", "server_keys.bin")


def load_keys():
    if os.path.exists(KEYS_FILE):
        private = PrivateKey(open(KEYS_FILE, "rb").read())
    else:
        private = PrivateKey.generate()
        with open(KEYS_FILE, "wb") as f:
            f.write(bytes(private))
    public = bytes(private.public_key)
    return private, public
