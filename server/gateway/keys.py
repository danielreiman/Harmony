import os
from nacl.public import PrivateKey

KEYS_FILE = os.path.join(os.path.dirname(__file__), "resources", "server_keys.bin")


def load_keys():
    # Reuse the saved keypair, or make one the first time and save it.
    if os.path.exists(KEYS_FILE):
        private = PrivateKey(open(KEYS_FILE, "rb").read())
    else:
        private = PrivateKey.generate()
        with open(KEYS_FILE, "wb") as f:
            f.write(bytes(private))
    public = bytes(private.public_key)           # public key is shared with clients
    return private, public
