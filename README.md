# fetchd

`fetchd` is a lightweight, cross-platform background daemon/utility that keeps your personal CLI utilities and tools automatically synchronized. It automatically downloads precompiled binaries from GitHub Releases or falls back to compiling from source.

## Features

- **GitHub Release Auto-Sync**: Automatically detects your OS (Linux, macOS, Windows) and downloads the corresponding release binary.
- **Source Build Fallback**: If no matching release binary is found (or on private repos / direct commits), `fetchd` shallow clones the repository and executes your custom build command.
- **Atomic Binary Hot-Swapping**: Safely replaces binaries in-place without crashing running processes (handles Windows file locking and POSIX atomic replacements).
- **Process Concurrency Lock**: Non-blocking lock prevents overlapping runs.
- **Automated Scheduling**: One-click native background service installation across Windows (Task Scheduler), macOS (Launchd), and Linux (systemd / cron).
- **Granular Environment & PATH Control (`env`)**: Whitelist only the tools you trust to be exposed in your shell's `PATH` and `.env` file.

---

## Quick Start (Prebuilt Binary — No Python Required)

Download the standalone executable for your operating system from [Releases](https://github.com/Sanskar-Awachar-commits/fetchd/releases/latest):

### Linux / macOS
```bash
# 1. Download standalone binary (replace fetchd-linux with fetchd-macos on Mac)
curl -L -o fetchd https://github.com/Sanskar-Awachar-commits/fetchd/releases/latest/download/fetchd-linux
chmod +x fetchd

# 2. Run once to create config.json
./fetchd

# 3. (Optional) Install as daily background service
./fetchd --install-service
```

### Windows (PowerShell)
```powershell
# 1. Download standalone binary
Invoke-WebRequest -Uri https://github.com/Sanskar-Awachar-commits/fetchd/releases/latest/download/fetchd-windows.exe -OutFile fetchd.exe

# 2. Run once to create config.json
.\fetchd.exe

# 3. (Optional) Install as daily background service
.\fetchd.exe --install-service
```

---

## Running from Source / Development (Optional)

If you prefer running `fetchd` directly with Python:

```bash
git clone https://github.com/Sanskar-Awachar-commits/fetchd.git
cd fetchd
python fetchd.py
```

---

## Automated Background Scheduling

`fetchd` includes built-in service installation so you don't have to manually configure cron jobs:

### 1. Daily Background Task (Recommended)
Register `fetchd` as a native daily background task:
```bash
fetchd --install-service
```
- **Windows**: Automatically creates a daily task in Windows Task Scheduler.
- **Linux**: Automatically creates and enables a user `systemd` timer (or `@daily` crontab entry).
- **macOS**: Automatically creates and loads a `launchd` LaunchAgent.

To remove the scheduled task:
```bash
fetchd --uninstall-service
```

### 2. Daemon Mode
To run `fetchd` continuously in a loop (e.g. inside `tmux` or a container):
```bash
fetchd --daemon --interval 86400
```

---

## Configuration

Edit `config.json` (created automatically on first run) to define your target installation directory and the repositories you want to synchronize:

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

### Configuration Options

| Option | Type | Default | Description |
|---|---|---|---|
| `install_dir` | string | `~/programs` | Target directory where all downloaded/built binaries are placed. |
| `projects` | list | `[]` | List of project objects to synchronize. |
| `projects[].repo` | string | *required* | GitHub repository in `owner/repo` format. |
| `projects[].binary_name` | string | *required* | Target executable filename (`.exe` automatically appended on Windows). |
| `projects[].env` | boolean | `false` | When `true`, links the binary into `install_dir/bin` and exports it in `.env` / `PATH`. |
| `projects[].build_command` | string | `null` | Command to compile the project if no release binary is available. |

### Why `env: false` is the Default

Following the **principle of least privilege**, `"env"` defaults to `false`. All binaries are safely downloaded or compiled into `install_dir`, but only explicitly whitelisted tools (`"env": true`) are exposed in `install_dir/bin`, added to your shell's `PATH`, and exported in `.env`.

### GitHub Token (Optional)

GitHub provides **60 free API requests per hour** for unauthenticated requests. For personal daily syncing, **no token is needed**.

If you are syncing private repositories or want higher rate limits:
```bash
export GITHUB_TOKEN="ghp_yourPersonalAccessToken"
```
On Windows (PowerShell):
```powershell
$env:GITHUB_TOKEN="ghp_yourPersonalAccessToken"
```

## License

MIT
