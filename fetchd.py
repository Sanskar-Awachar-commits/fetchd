#!/usr/bin/env python3
import os
import sys
import json
import time
import shutil
import argparse
import platform
import subprocess
import tempfile
import urllib.request
from pathlib import Path

__version__ = "1.0.0"

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    EXEC_ARGS = [str(Path(sys.executable).resolve())]
    EXEC_CMD = f'"{Path(sys.executable).resolve()}"'
else:
    BASE_DIR = Path(__file__).resolve().parent
    EXEC_ARGS = [sys.executable, str(Path(__file__).resolve())]
    EXEC_CMD = f'"{sys.executable}" "{Path(__file__).resolve()}"'

CONFIG_PATH = BASE_DIR / "config.json"
EXAMPLE_CONFIG_PATH = BASE_DIR / "config.example.json"
ENV_PATH = BASE_DIR / ".env"
LOCK_PATH = BASE_DIR / "fetchd.lock"


def acquire_lock():
    lock_file = open(LOCK_PATH, "a+")
    if platform.system().lower() == "windows":
        import msvcrt
        try:
            lock_file.seek(0)
            if LOCK_PATH.stat().st_size == 0:
                lock_file.write("0")
                lock_file.flush()
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            print("[fetchd] Another instance is already running. Exiting.")
            sys.exit(0)
    else:
        import fcntl
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            print("[fetchd] Another instance is already running. Exiting.")
            sys.exit(0)
    return lock_file


def detect_platform_keyword():
    system = platform.system().lower()
    if "windows" in system:
        return "windows"
    elif "darwin" in system:
        return "macos"
    return "linux"


def fetch_json(url, token=None):
    req = urllib.request.Request(url, headers={"User-Agent": "fetchd-agent"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download_file(url, dest_path: Path, token=None):
    req = urllib.request.Request(url, headers={"User-Agent": "fetchd-agent"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as resp, open(dest_path, "wb") as out:
        shutil.copyfileobj(resp, out)


def atomic_replace_binary(target_path: Path, new_binary_path: Path):
    target_path = target_path.resolve()
    old_backup = target_path.with_name(f"{target_path.name}.old")

    if old_backup.exists():
        try:
            old_backup.unlink()
        except OSError:
            pass

    if platform.system().lower() == "windows":
        try:
            if target_path.exists():
                target_path.rename(old_backup)
            shutil.move(str(new_binary_path), str(target_path))
        except Exception as e:
            if old_backup.exists() and not target_path.exists():
                old_backup.rename(target_path)
            raise RuntimeError(f"Failed to replace {target_path.name}: {e}")
    else:
        temp_target = target_path.with_name(f".{target_path.name}.tmp")
        if new_binary_path != temp_target:
            shutil.copy2(new_binary_path, temp_target)
            if new_binary_path.exists() and new_binary_path != target_path:
                try:
                    new_binary_path.unlink()
                except OSError:
                    pass
        temp_target.chmod(0o755)
        os.replace(temp_target, target_path)


def sync_project(item, install_dir: Path, os_key: str, token=None):
    repo = item.get("repo")
    bin_name = item.get("binary_name")
    build_cmd = item.get("build_command")
    enable_env = item.get("env", False)

    if not repo or not bin_name:
        print(f"[-] Invalid project entry in config: {item}. Skipping.")
        return

    if os_key == "windows" and not bin_name.endswith(".exe"):
        bin_name += ".exe"

    bin_dir = install_dir / "bin"
    target_path = install_dir / bin_name
    whitelisted_bin_path = bin_dir / bin_name
    temp_download_path = install_dir / f"{bin_name}.tmp"
    print(f"\n[+] Checking {repo}...")

    release_url = f"https://api.github.com/repos/{repo}/releases/latest"
    binary_found = False

    try:
        data = fetch_json(release_url, token)
        assets = data.get("assets", [])

        for asset in assets:
            name = asset.get("name", "").lower()
            if any(name.endswith(ext) for ext in [".sha256", ".sha512", ".md5", ".asc", ".sig", ".txt"]):
                continue

            is_match = False
            if os_key == "windows":
                if name.endswith(".exe") and ("windows" in name or "win" in name or len(assets) == 1):
                    is_match = True
                elif "windows" in name or "win64" in name or "win32" in name:
                    is_match = True
            elif os_key == "macos":
                if ("macos" in name or "darwin" in name or "osx" in name or "apple" in name) and not name.endswith(".exe"):
                    is_match = True
            elif os_key == "linux":
                if "linux" in name and not name.endswith(".exe") and not any(k in name for k in ["macos", "darwin", "windows", "win32", "win64"]):
                    is_match = True

            if is_match:
                download_url = asset["browser_download_url"]
                print(f"    Found release asset: {asset['name']}. Downloading...")
                download_file(download_url, temp_download_path, token)
                atomic_replace_binary(target_path, temp_download_path)
                binary_found = True
                print(f"    [OK] Installed {bin_name} to {install_dir}")
                break
    except Exception:
        print("    No prebuilt release matching OS or API limited. Trying source build...")

    if not binary_found:
        if not build_cmd:
            print(f"    [-] No prebuilt binary found and no build_command provided for {repo}. Skipping.")
            return

        print(f"    Compiling from source: {build_cmd}")
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_dir = Path(tmpdir) / "repo"
            try:
                subprocess.run(
                    ["git", "clone", "--depth", "1", f"https://github.com/{repo}.git", str(repo_dir)],
                    check=True,
                    capture_output=True
                )
                subprocess.run(build_cmd, shell=True, cwd=repo_dir, check=True)

                built_bin = repo_dir / bin_name
                if built_bin.exists():
                    atomic_replace_binary(target_path, built_bin)
                    binary_found = True
                    print(f"    [OK] Built and installed {bin_name} to {install_dir}")
                else:
                    print(f"    [-] Build finished, but expected binary '{bin_name}' was not found.")
            except subprocess.CalledProcessError as e:
                print(f"    [-] Build command failed: {e}")
            except Exception as e:
                print(f"    [-] Error during source compilation: {e}")

    if target_path.exists():
        if enable_env:
            bin_dir.mkdir(parents=True, exist_ok=True)
            temp_bin_target = bin_dir / f"{bin_name}.tmp"
            shutil.copy2(target_path, temp_bin_target)
            atomic_replace_binary(whitelisted_bin_path, temp_bin_target)
        elif whitelisted_bin_path.exists():
            try:
                whitelisted_bin_path.unlink()
            except OSError:
                pass


def update_env(install_dir: Path, projects: list, os_key: str):
    resolved = install_dir.resolve()
    bin_dir = (install_dir / "bin").resolve()
    is_win = os_key == "windows"

    env_lines = [
        f'PROGRAMS_DIR="{resolved}"\n'
    ]

    whitelisted_vars = []
    for item in projects:
        if not item.get("env", False):
            continue

        bin_name = item.get("binary_name", "")
        if is_win and not bin_name.endswith(".exe"):
            bin_name += ".exe"

        target_file = (bin_dir / bin_name)
        var_name = bin_name.upper().replace(".EXE", "").replace("-", "_").replace(".", "_") + "_BIN"
        whitelisted_vars.append(f'{var_name}="{target_file}"\n')

    if whitelisted_vars:
        if is_win:
            env_lines.append(f'PATH="%PATH%;{bin_dir}"\n')
        else:
            env_lines.append(f'PATH="$PATH:{bin_dir}"\n')
        env_lines.append("\n")
        env_lines.extend(whitelisted_vars)

    with open(ENV_PATH, "w") as f:
        f.writelines(env_lines)

    print(f"\n[v] Synced paths to {ENV_PATH}")


def install_service():
    os_key = detect_platform_keyword()

    if os_key == "windows":
        try:
            subprocess.run(
                ["schtasks", "/Create", "/TN", "fetchd", "/TR", EXEC_CMD, "/SC", "DAILY", "/F"],
                check=True,
                capture_output=True,
                text=True
            )
            print("[+] Registered 'fetchd' in Windows Task Scheduler (Daily).")
        except subprocess.CalledProcessError as e:
            print(f"[-] Failed to register task: {e.stderr.strip() if e.stderr else e}")

    elif os_key == "macos":
        plist_path = Path.home() / "Library" / "LaunchAgents" / "com.sanskar.fetchd.plist"
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        args_xml = "".join(f"<string>{arg}</string>\n        " for arg in EXEC_ARGS)
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sanskar.fetchd</string>
    <key>ProgramArguments</key>
    <array>
        {args_xml.strip()}
    </array>
    <key>StartInterval</key>
    <integer>86400</integer>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"""
        with open(plist_path, "w") as f:
            f.write(plist_content)
        subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
        subprocess.run(["launchctl", "load", str(plist_path)], check=True)
        print(f"[+] Loaded LaunchAgent at {plist_path} (Daily).")

    elif os_key == "linux":
        systemd_user_dir = Path.home() / ".config" / "systemd" / "user"
        if shutil.which("systemctl"):
            systemd_user_dir.mkdir(parents=True, exist_ok=True)
            service_file = systemd_user_dir / "fetchd.service"
            timer_file = systemd_user_dir / "fetchd.timer"

            service_content = f"""[Unit]
Description=fetchd sync service

[Service]
Type=oneshot
ExecStart={' '.join(EXEC_ARGS)}
"""
            timer_content = """[Unit]
Description=Run fetchd daily

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
"""
            with open(service_file, "w") as f:
                f.write(service_content)
            with open(timer_file, "w") as f:
                f.write(timer_content)

            subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
            subprocess.run(["systemctl", "--user", "enable", "--now", "fetchd.timer"], check=True)
            print("[+] Enabled systemd user timer 'fetchd.timer' (Daily).")
        else:
            cron_entry = f"@daily {' '.join(EXEC_ARGS)} >/dev/null 2>&1\n"
            try:
                res = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
                existing_cron = res.stdout if res.returncode == 0 else ""
                if EXEC_ARGS[0] not in existing_cron:
                    new_cron = existing_cron + cron_entry
                    subprocess.run(["crontab", "-"], input=new_cron, text=True, check=True)
                    print("[+] Added @daily entry to user crontab.")
                else:
                    print("[+] fetchd is already configured in crontab.")
            except Exception as e:
                print(f"[-] Failed to add crontab entry: {e}")


def uninstall_service():
    os_key = detect_platform_keyword()

    if os_key == "windows":
        try:
            subprocess.run(["schtasks", "/Delete", "/TN", "fetchd", "/F"], check=True, capture_output=True)
            print("[+] Removed 'fetchd' from Windows Task Scheduler.")
        except subprocess.CalledProcessError as e:
            print(f"[-] Task not found or failed to delete: {e.stderr.strip() if e.stderr else e}")

    elif os_key == "macos":
        plist_path = Path.home() / "Library" / "LaunchAgents" / "com.sanskar.fetchd.plist"
        if plist_path.exists():
            subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
            plist_path.unlink()
            print("[+] Removed LaunchAgent.")
        else:
            print("[-] No LaunchAgent found for fetchd.")

    elif os_key == "linux":
        systemd_user_dir = Path.home() / ".config" / "systemd" / "user"
        timer_file = systemd_user_dir / "fetchd.timer"
        service_file = systemd_user_dir / "fetchd.service"

        if shutil.which("systemctl") and timer_file.exists():
            subprocess.run(["systemctl", "--user", "disable", "--now", "fetchd.timer"], capture_output=True)
            if timer_file.exists():
                timer_file.unlink()
            if service_file.exists():
                service_file.unlink()
            subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
            print("[+] Removed systemd timer and service.")
        else:
            try:
                res = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
                if res.returncode == 0 and EXEC_ARGS[0] in res.stdout:
                    filtered = "\n".join(line for line in res.stdout.splitlines() if EXEC_ARGS[0] not in line) + "\n"
                    subprocess.run(["crontab", "-"], input=filtered, text=True, check=True)
                    print("[+] Removed fetchd from crontab.")
                else:
                    print("[-] No fetchd entry found in crontab.")
            except Exception as e:
                print(f"[-] Error removing crontab entry: {e}")


def add_project_wizard(save=False, env_flag=None):
    cwd = Path.cwd()
    repo = None

    try:
        remote_out = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            check=True
        ).stdout.strip()
        if "github.com" in remote_out:
            if remote_out.endswith(".git"):
                remote_out = remote_out[:-4]
            if ":" in remote_out and not remote_out.startswith("http"):
                repo = remote_out.split(":")[-1]
            elif "github.com/" in remote_out:
                repo = remote_out.split("github.com/")[-1]
    except Exception:
        pass

    if not repo:
        repo = f"Sanskar-Awachar-commits/{cwd.name}"

    binary_name = cwd.name
    build_cmd = None

    if (cwd / "Cargo.toml").exists():
        build_cmd = f"cargo build --release && cp target/release/{binary_name} ."
    elif (cwd / "go.mod").exists():
        build_cmd = f"go build -o {binary_name} ."
    elif (cwd / f"{binary_name}.cpp").exists():
        build_cmd = f"g++ -O3 -std=c++20 {binary_name}.cpp -o {binary_name}"
    elif (cwd / "main.cpp").exists():
        build_cmd = f"g++ -O3 -std=c++20 main.cpp -o {binary_name}"
    elif (cwd / f"{binary_name}.py").exists():
        build_cmd = f"pyinstaller --onefile --name {binary_name} {binary_name}.py && cp dist/{binary_name} ."
    elif (cwd / "main.py").exists():
        build_cmd = f"pyinstaller --onefile --name {binary_name} main.py && cp dist/{binary_name} ."

    if env_flag is not None:
        is_env = env_flag
    else:
        try:
            choice = input(f"Add '{binary_name}' to PATH / .env whitelist? [y/N]: ").strip().lower()
            is_env = choice in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            is_env = False

    entry = {
        "repo": repo,
        "binary_name": binary_name,
        "env": is_env
    }
    if build_cmd:
        entry["build_command"] = build_cmd

    print("\n[fetchd] Generated project configuration snippet:\n")
    print(json.dumps(entry, indent=2))

    if save:
        if not CONFIG_PATH.exists() and EXAMPLE_CONFIG_PATH.exists():
            shutil.copy(EXAMPLE_CONFIG_PATH, CONFIG_PATH)

        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r") as f:
                    cfg = json.load(f)
                projects = cfg.setdefault("projects", [])
                projects = [p for p in projects if p.get("repo") != repo]
                projects.append(entry)
                cfg["projects"] = projects
                with open(CONFIG_PATH, "w") as f:
                    json.dump(cfg, f, indent=2)
                print(f"\n[+] Successfully saved to {CONFIG_PATH}")
            except Exception as e:
                print(f"\n[-] Failed to save to {CONFIG_PATH}: {e}")


def run_sync():
    _lock = acquire_lock()

    if not CONFIG_PATH.exists():
        if EXAMPLE_CONFIG_PATH.exists():
            shutil.copy(EXAMPLE_CONFIG_PATH, CONFIG_PATH)
            print(f"[fetchd] Created {CONFIG_PATH.name} from {EXAMPLE_CONFIG_PATH.name}.")
            print(f"[fetchd] Please edit {CONFIG_PATH.name} to configure your repositories and rerun.")
            sys.exit(0)
        else:
            print(f"Error: Missing config at {CONFIG_PATH}")
            sys.exit(1)

    try:
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error reading {CONFIG_PATH}: {e}")
        sys.exit(1)

    install_dir = Path(os.path.expanduser(config.get("install_dir", "~/programs")))
    install_dir.mkdir(parents=True, exist_ok=True)

    token = os.getenv("GITHUB_TOKEN")
    os_key = detect_platform_keyword()
    projects = config.get("projects", [])

    for item in projects:
        sync_project(item, install_dir, os_key, token)

    update_env(install_dir, projects, os_key)


def main():
    parser = argparse.ArgumentParser(
        prog="fetchd",
        description="Sync CLI utilities and GitHub release binaries."
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "--daemon", "-d",
        action="store_true",
        help="Run continuously in daemon mode."
    )
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=86400,
        help="Daemon interval in seconds (default: 86400)."
    )
    parser.add_argument(
        "--install-service",
        action="store_true",
        help="Install native background daily service."
    )
    parser.add_argument(
        "--uninstall-service",
        action="store_true",
        help="Uninstall native background service."
    )
    parser.add_argument(
        "--add",
        action="store_true",
        help="Inspect current project directory and generate a fetchd config snippet."
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Automatically append/update current project in config.json (used with --add)."
    )
    parser.add_argument(
        "--env",
        dest="env_flag",
        action="store_true",
        default=None,
        help="Enable env whitelist for current project (used with --add)."
    )
    parser.add_argument(
        "--no-env",
        dest="env_flag",
        action="store_false",
        help="Disable env whitelist for current project (used with --add)."
    )

    args = parser.parse_args()

    if args.add:
        add_project_wizard(save=args.save, env_flag=args.env_flag)
    elif args.install_service:
        install_service()
    elif args.uninstall_service:
        uninstall_service()
    elif args.daemon:
        print(f"[fetchd] Daemon started (interval: {args.interval}s)")
        while True:
            run_sync()
            time.sleep(args.interval)
    else:
        run_sync()


if __name__ == "__main__":
    main()