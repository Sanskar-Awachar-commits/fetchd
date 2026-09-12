# fetchd

`fetchd` is a lightweight, cross-platform background daemon/utility that keeps your custom tools and CLI utilities automatically synchronized. It fetches prebuilt binaries from GitHub Releases or automatically falls back to cloning and compiling from source.

## Features

- **GitHub Release Auto-Sync**: Automatically detects your OS (Linux, macOS, Windows) and downloads the corresponding binary release asset.
- **Source Build Fallback**: If no matching prebuilt release binary is found (or on private/unreleased commits), `fetchd` shallow clones the repository and executes your specified build command.
- **Atomic Binary Replacement**: Safely updates executables in-place without corrupting running processes (handles Windows file locking and POSIX atomic replacements).
- **Process Concurrency Lock**: Non-blocking lock prevents overlapping runs.
- **Automated Scheduling**: One-click native background service installation across Windows (Task Scheduler), macOS (Launchd), and Linux (systemd / cron).
- **Granular Environment & PATH Control (`env`)**: Whitelist only the tools you trust to be exposed to your shell's `PATH` and `.env` file.

## Installation

### Prerequisites
- Python 3.8+
- `git` (for fallback source builds)
- C++ compiler / PyInstaller / Go / Rust (depending on the build commands configured for your projects)

### Quick Start

1. Clone the repository:
   ```bash
   git clone https://github.com/Sanskar-Awachar-commits/fetchd.git
   cd fetchd
   ```

2. Copy the example configuration:
   ```bash
   cp config.example.json config.json
   ```
   *(If you run `python fetchd.py` without a `config.json`, it will automatically create one from `config.example.json`).*

3. Edit `config.json` with your repositories and build commands.

4. Run `fetchd` on demand:
   ```bash
   python fetchd.py
   ```

## Automated Background Scheduling

You don't need to manually configure cron jobs or Task Scheduler. `fetchd` includes built-in service installation:

### 1. Native Service Installation (Runs Daily by Default)
To register `fetchd` as a native daily background task on your operating system:
```bash
python fetchd.py --install-service
```
- **Windows**: Automatically creates a daily task in Windows Task Scheduler.
- **Linux**: Automatically creates and enables a user `systemd` timer (or `@daily` crontab entry).
- **macOS**: Automatically creates and loads a `launchd` LaunchAgent.

To remove the background task:
```bash
python fetchd.py --uninstall-service
```

### 2. Continuous Daemon Mode
To run `fetchd` continuously in a loop (e.g. inside `tmux` or a container):
```bash
python fetchd.py --daemon --interval 86400
```

## Configuration

Edit `config.json` to define your target installation directory and the repositories you want to synchronize:

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

GitHub provides **60 free API requests per hour** for unauthenticated requests. For daily syncing of your personal tools, **no token is required**. 

If you are syncing private repositories or wish to increase the rate limit:
```bash
export GITHUB_TOKEN="ghp_yourPersonalAccessToken"
```
On Windows (PowerShell):
```powershell
$env:GITHUB_TOKEN="ghp_yourPersonalAccessToken"
```

## License

MIT
