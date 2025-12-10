import requests

ollama_key = input("Enter Ollama API key: ").strip()
duck_token = input("Enter DuckDNS token: ").strip()

with open(".env", "w") as f:
    f.write(f"OLLAMA_API_KEY={ollama_key}\n")

requests.get(
    "https://www.duckdns.org/update",
    params={
        "domains": "harmony-server",
        "token": duck_token,
        "ip": ""
    }
)

print("Setup complete")
