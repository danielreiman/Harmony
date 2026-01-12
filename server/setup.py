def main():
    print("Harmony Server Setup\n")
    key = input("Ollama API key: ").strip()

    if not key:
        print("Error: API key required")
        return

    with open(".env", "w") as f:
        f.write(f"OLLAMA_API_KEY={key}\n")

    print("✓ Configuration saved to .env\n")


if __name__ == "__main__":
    main()
