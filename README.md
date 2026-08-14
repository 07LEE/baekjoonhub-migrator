# BaekjoonHub Migration Tool

[Language: [English](README.md) | [한국어](docs/README.ko.md)]

A migration tool designed to reorganize auto-pushed repository layouts from [BaekjoonHub](https://github.com/BaekjoonHub/BaekjoonHub) into a unified directory structure.

It reorganizes file paths while preserving commit timestamps, author metadata, and commit messages.

## Features

1. Git History Metadata Preservation
   - Retains original submission timestamps (`Author Date`, `Committer Date`), author details, and commit messages.

2. Flexible Directory Layouts
   - Platform-first: `백준/...`, `프로그래머스/...`, `SWEA/...`
   - Language-first: `Python/백준/...`, `Java/프로그래머스/...`
   - Flat: `백준/...` (Platform-focused flat layout)

3. Automatic Directory Normalization
   - Standardizes legacy `Python3/` directory names to `Python`.
   - Standardizes level directory names (e.g. `lv1` -> `1`, `2`, `3`) to align with BaekjoonHub specifications.

4. Execution Environments (Python & C++)
   - Provides both a Python script (`migrator.py`) and a standalone C++ binary (`baekjoonhub-migrator`).
   - Includes Dry-Run mode and automatic backup branch (`backup-before-migration`) creation.

## Usage

### 1. C++ Binary Execution (Pre-built Releases)

Download the pre-built binary for your platform from GitHub Releases.

Linux:
```bash
chmod +x baekjoonhub-migrator-linux
./baekjoonhub-migrator-linux --repo /path/to/your/repository
```

macOS:
```bash
chmod +x baekjoonhub-migrator-macos
./baekjoonhub-migrator-macos --repo /path/to/your/repository
```

Windows:
```cmd
baekjoonhub-migrator-windows.exe --repo C:\path\to\your\repository
```

Build from Source (CMake):
```bash
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
./build/baekjoonhub-migrator --repo /path/to/your/repository
```

### 2. Python Script Execution (`migrator.py`)

Run directly with Python 3 environment.

Preview Changes (Dry-Run Mode):
```bash
python3 src/migrator.py --repo /path/to/your/repository --mode platform_first --dry-run
```

Run Migration:
```bash
python3 src/migrator.py --repo /path/to/your/repository
```

### 3. Reflecting to Remote Repository

Since Git history is rewritten, a force push is required to update the remote repository:

```bash
git push origin main --force
```

> [!WARNING]
> GPG signatures on existing commits will be lost during history rewriting since new commit tree SHAs are generated.

> [!CAUTION]
> Force push overwrites remote repository history. Verify results locally before pushing. Original history is preserved in `backup-before-migration` (or timestamped backup branches on repeated runs).
