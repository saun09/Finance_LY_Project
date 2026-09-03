import os

# ==============================
# CONFIGURATION
# ==============================

PROJECT_PATH = r"C:\Users\woebe\Desktop\FINAL YEAR PROJECT FINAL"
OUTPUT_FILE = "project_structure.txt"

INCLUDE_EXTENSIONS = {
    ".py",
    ".md",
    ".ini",
    ".json"
}

EXCLUDED_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    "__pycache__",
    "venv",
    ".venv",
    "env",
    ".env",
    "node_modules",
    "dist",
    "build"
}


# ==============================
# GET PROJECT STRUCTURE
# ==============================

def get_structure(path, prefix=""):
    lines = []

    try:
        entries = sorted(
            os.listdir(path),
            key=lambda x: (not os.path.isdir(os.path.join(path, x)), x.lower())
        )
    except PermissionError:
        return lines

    # Remove excluded directories
    entries = [
        entry for entry in entries
        if not (
            os.path.isdir(os.path.join(path, entry))
            and entry in EXCLUDED_DIRS
        )
    ]

    for index, entry in enumerate(entries):
        full_path = os.path.join(path, entry)

        is_last = index == len(entries) - 1
        connector = "└── " if is_last else "├── "

        lines.append(prefix + connector + entry)

        if os.path.isdir(full_path):
            extension = "    " if is_last else "│   "
            lines.extend(
                get_structure(full_path, prefix + extension)
            )

    return lines


# ==============================
# GET FILE CONTENTS
# ==============================

def get_file_contents(path):
    contents = []

    for root, dirs, files in os.walk(path):

        # Don't enter excluded directories
        dirs[:] = [
            d for d in dirs
            if d not in EXCLUDED_DIRS
        ]

        for filename in sorted(files):
            extension = os.path.splitext(filename)[1].lower()

            if extension not in INCLUDE_EXTENSIONS:
                continue

            file_path = os.path.join(root, filename)

            relative_path = os.path.relpath(
                file_path,
                path
            )

            contents.append("\n")
            contents.append("=" * 80)
            contents.append(f"FILE: {relative_path}")
            contents.append("=" * 80)
            contents.append("\n")

            try:
                with open(
                    file_path,
                    "r",
                    encoding="utf-8",
                    errors="replace"
                ) as f:
                    contents.append(f.read())

            except Exception as e:
                contents.append(
                    f"[ERROR READING FILE: {e}]"
                )

            contents.append("\n")

    return contents


# ==============================
# CREATE OUTPUT
# ==============================

def main():

    if not os.path.isdir(PROJECT_PATH):
        print("Project folder does not exist:")
        print(PROJECT_PATH)
        return

    print("Scanning project...")

    structure = get_structure(PROJECT_PATH)
    file_contents = get_file_contents(PROJECT_PATH)

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as output:

        # Project structure
        output.write("=" * 80 + "\n")
        output.write("PROJECT STRUCTURE\n")
        output.write("=" * 80 + "\n\n")

        output.write("\n".join(structure))

        # File contents
        output.write("\n\n\n")
        output.write("=" * 80 + "\n")
        output.write("FILE CONTENTS\n")
        output.write("=" * 80 + "\n")

        output.write("".join(file_contents))

    print(f"\nDone!")
    print(f"Output created: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()