ollama_key = input("Enter Ollama API key: ").strip()

with open(".env", "w") as f:
    f.write(f"OLLAMA_API_KEY={ollama_key}\n")

print("Setup complete")
