def main():
    print("Harmony Server Setup\n")

    api_key = input("Ollama API key: ").strip()
    if not api_key:
        print("Error: API key required")
        return

    with open(".env", "w") as f:
        f.write(f"OLLAMA_API_KEY={api_key}\n")

    print("\n✓ Configuration saved to .env\n")


if __name__ == "__main__":
    main()
