#!/usr/bin/env python3
import os
import sys
import json
import shutil
import platform
import subprocess
import tempfile
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
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


def main():
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


if __name__ == "__main__":
    main()