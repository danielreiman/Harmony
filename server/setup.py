def main():
    print("Harmony Server Setup\n")

    api_key = input("Ollama API key: ").strip()
    if not api_key:
        print("Error: API key required")
        return

    service_account_path = input("Google service-account JSON path (leave blank to skip): ").strip()

    with open(".env", "w") as f:
        f.write(f"OLLAMA_API_KEY={api_key}\n")
        if service_account_path:
            f.write(f"GOOGLE_SERVICE_ACCOUNT_FILE={service_account_path}\n")

    print("\n✓ Configuration saved to .env\n")


if __name__ == "__main__":
    main()
