import json
from pathlib import Path

ALIASES_FILE = Path("tools/contexta_runs/aliases.json")


def migrate_alias_file():
    if not ALIASES_FILE.exists():
        print("aliases.json not found")
        return

    with open(ALIASES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        print("Invalid aliases.json format")
        return

    updated = {}
    converted_count = 0

    for key, value in data.items():
        if isinstance(value, dict):
            # already correct
            updated[key] = value
        elif isinstance(value, str):
            # convert old format
            updated[key] = {
                "display": value,
                "full": value
            }
            converted_count += 1
        else:
            # unexpected format
            print(f"Skipping invalid entry: {key}")

    # Save backup
    backup_file = ALIASES_FILE.with_suffix(".backup.json")
    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    # Save updated file
    with open(ALIASES_FILE, "w", encoding="utf-8") as f:
        json.dump(updated, f, indent=2)

    print(f"✅ Migration complete")
    print(f"Converted: {converted_count} entries")
    print(f"Backup saved: {backup_file}")


if __name__ == "__main__":
    migrate_alias_file()
