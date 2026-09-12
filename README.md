# fetchd

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg?style=flat-square)](https://github.com/Sanskar-Awachar-commits/fetchd/releases)
[![Build Status](https://github.com/Sanskar-Awachar-commits/fetchd/actions/workflows/release.yml/badge.svg)](https://github.com/Sanskar-Awachar-commits/fetchd/actions/workflows/release.yml)
[![License](https://img.shields.io/badge/license-MIT-green.svg?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg?style=flat-square)](https://www.python.org/)

Lightweight background utility to sync personal CLI tools and GitHub release binaries across machines.

## Features

- Downloads latest precompiled binaries from GitHub Releases
- Automatic fallback to git clone & source build if release binary is missing
- Safe in-place binary replacement (supports active executables on Windows/POSIX)
- Non-blocking lock to prevent overlapping runs
- Native background scheduler setup (Windows Task Scheduler, macOS launchd, Linux systemd/cron)
- Whitelist (`env`) to control which tools are added to PATH and `.env`

---

## Installation

### Binaries

Download the latest binary from [Releases](https://github.com/Sanskar-Awachar-commits/fetchd/releases/latest):

**Linux / macOS:**
```bash
curl -L -o fetchd https://github.com/Sanskar-Awachar-commits/fetchd/releases/latest/download/fetchd-linux
chmod +x fetchd
./fetchd
```
*(On macOS, use `fetchd-macos`)*

**Windows (PowerShell):**
```powershell
Invoke-WebRequest -Uri https://github.com/Sanskar-Awachar-commits/fetchd/releases/latest/download/fetchd-windows.exe -OutFile fetchd.exe
.\fetchd.exe
```

### From Source

```bash
git clone https://github.com/Sanskar-Awachar-commits/fetchd.git
cd fetchd
python fetchd.py
```

---

## Usage

```bash
# Run sync once
fetchd

# Print version
fetchd --version

# Install daily background service
fetchd --install-service

# Remove background service
fetchd --uninstall-service

# Run as daemon (default interval: 86400s / 1 day)
fetchd --daemon --interval 86400
```

---

## Configuration

On first run, `fetchd` creates `config.json` from `config.example.json`:

```json
{
  "install_dir": "~/programs",
  "projects": [
    {
      "repo": "Sanskar-Awachar-commits/fetchd",
      "binary_name": "fetchd",
      "env": true,
      "build_command": "pyinstaller --onefile --name fetchd fetchd.py && cp dist/fetchd ."
    },
    {
      "repo": "owner/example-tool",
      "binary_name": "example-tool",
      "env": false,
      "build_command": "g++ -O3 -std=c++20 main.cpp -o example-tool"
    }
  ]
}
```

### Options

| Field | Type | Default | Description |
|---|---|---|---|
| `install_dir` | string | `~/programs` | Directory where binaries are stored. |
| `projects` | list | `[]` | List of repositories to sync. |
| `projects[].repo` | string | *required* | `owner/repo` path on GitHub. |
| `projects[].binary_name` | string | *required* | Target executable name (`.exe` added automatically on Windows). |
| `projects[].env` | boolean | `false` | When `true`, links binary to `install_dir/bin` and exports to `.env` / `PATH`. |
| `projects[].build_command` | string | `null` | Build command to run if no release binary is found. |

---

## Authentication

Optional. Public repos use GitHub's unauthenticated API (60 req/hr). For private repos or higher limits:

```bash
# Linux / macOS
export GITHUB_TOKEN="ghp_xxx"

# Windows (PowerShell)
$env:GITHUB_TOKEN="ghp_xxx"
```

---

## License

MIT
