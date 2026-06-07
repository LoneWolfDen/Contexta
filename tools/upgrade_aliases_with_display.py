import json
from pathlib import Path

ALIASES_FILE = Path("tools/contexta_runs/aliases.json")


# =========================================================
# Helpers
# =========================================================

def load_aliases():
    if not ALIASES_FILE.exists():
        print("aliases.json not found")
        return {}

    with open(ALIASES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_aliases(data):
    with open(ALIASES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def backup_aliases(data):
    backup_file = ALIASES_FILE.with_suffix(".backup.json")
    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Backup saved: {backup_file}")


# =========================================================
# Naming Logic
# =========================================================

def extract_id(key):
    # "review:abcd" → "abcd"
    return key.split(":", 1)[1]


def get_type(key):
    return key.split(":", 1)[0]


def generate_display_names(alias_dict):
    """
    Build structured display naming
    """

    counters = {
        "project": 0,
        "version": 0,
        "review": 0,
        "reconciliation": 0,
        "proposal": 0,
        "learning": 0,
    }

    result = {}

    review_map = {}
    recon_map = {}
    prop_map = {}

    # Pass 1 → assign base numbering
    for key in alias_dict.keys():
        obj_type = get_type(key)
        counters[obj_type] += 1

        idx = counters[obj_type]

        if obj_type == "project":
            display = f"📁 Project{idx}"

        elif obj_type == "version":
            display = f"📦 V{idx}"

        elif obj_type == "review":
            display = f"📝 R[Base]-{idx:02d}"
            review_map[extract_id(key)] = f"R{idx}"

        elif obj_type == "reconciliation":
            display = f"🔗 Recon[V?-R?-R?]-{idx:02d}"
            recon_map[extract_id(key)] = f"Recon{idx:02d}"

        elif obj_type == "proposal":
            display = f"📄 Prop[Recon??]-{idx:02d}"
            prop_map[extract_id(key)] = f"Prop{idx:02d}"

        elif obj_type == "learning":
            display = f"📘 Learn[Prop??]-{idx:02d}"

        else:
            display = f"{obj_type}-{idx}"

        result[key] = {
            "display": display,
            "full": alias_dict[key] if isinstance(alias_dict[key], str)
                     else alias_dict[key].get("full", "")
        }

    return result


# =========================================================
# Main Migration
# =========================================================

def migrate_aliases():
    original = load_aliases()

    if not isinstance(original, dict):
        print("Invalid aliases.json")
        return

    backup_aliases(original)

    # Step 1 → normalize to simple strings
    base_map = {}

    for key, value in original.items():
        if isinstance(value, dict):
            base_map[key] = value.get("full", "")
        else:
            base_map[key] = value

    # Step 2 → generate structured display
    upgraded = generate_display_names(base_map)

    save_aliases(upgraded)

    print("✅ Migration complete")
    print("✅ Display names upgraded to structured format")


# =========================================================
# Run
# =========================================================

if __name__ == "__main__":
    migrate_aliases()
