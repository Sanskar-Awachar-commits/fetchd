---
name: fetchd-sync
description: >-
  Guides the registration and configuration of projects with the fetchd utility
  (https://github.com/Sanskar-Awachar-commits/fetchd). Use this skill when creating
  or finalizing CLI utilities or tools to generate fetchd project configuration snippets
  and GitHub Actions release workflows.
---

# fetchd Project Integration Skill

`fetchd` is a personal binary sync daemon that automatically keeps CLI tools and utilities up to date across machines.

## How fetchd Works
- Downloads compiled binaries from GitHub Releases (`fetchd-linux`, `fetchd-macos`, `fetchd-windows.exe`).
- Falls back to `git clone` and `build_command` if no release binary exists.
- Hot-swaps running binaries atomically.
- Whitelists utilities marked with `"env": true` into `~/programs/bin` and exports them in `.env` and `PATH`.

---

## Adding a Project to fetchd

When a user creates a new project or asks to add/register a tool with `fetchd`:

### 1. Inquire / Determine Environment Whitelist (`env`)
Ask the user (or determine from context):
- **CLI Utilities** (e.g. `ax`, `wifidot`, `ppar`, `dotdot`, `xc`): Set `"env": true` to expose in `PATH` and `.env`.
- **GUI Tools / Standalone Programs** (e.g. `code-graph-visualizer`): Set `"env": false` so they stay isolated in the install directory.

### 2. Format the Configuration Snippet
Generate the project entry for the user's `config.json`:

```json
{
  "repo": "Sanskar-Awachar-commits/<repo-name>",
  "binary_name": "<binary-name>",
  "env": true,
  "build_command": "<build-command>"
}
```

#### Build Command Cheatsheet
- **C++ (single-file / g++)**: `g++ -O3 -std=c++20 main.cpp -o <binary_name>`
- **C++ (CMake)**: `cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build && cp build/<binary_name> .`
- **Rust (Cargo)**: `cargo build --release && cp target/release/<binary_name> .`
- **Go**: `go build -o <binary_name> .`
- **Python (PyInstaller)**: `pyinstaller --onefile --name <binary_name> <main_file>.py && cp dist/<binary_name> .`

---

### 3. GitHub Actions Release Workflow Template
To enable automatic binary builds in the cloud, create `.github/workflows/release.yml` in the project:

```yaml
name: Build and Release

on:
  push:
    tags:
      - 'v*'
  workflow_dispatch:

permissions:
  contents: write

jobs:
  build:
    name: Build (${{ matrix.os }})
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        include:
          - os: ubuntu-latest
            artifact_name: <binary_name>-linux
            binary_name: <binary_name>
          - os: macos-latest
            artifact_name: <binary_name>-macos
            binary_name: <binary_name>
          - os: windows-latest
            artifact_name: <binary_name>-windows.exe
            binary_name: <binary_name>.exe

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      # Add language setup step (e.g., actions/setup-python, actions-rust-lang/setup-rust-toolchain, actions/setup-go)

      - name: Build Binary
        run: |
          <build-steps-here>

      - name: Stage Binary (Linux / macOS)
        if: runner.os != 'Windows'
        run: |
          mv ${{ matrix.binary_name }} ${{ matrix.artifact_name }}
          chmod +x ${{ matrix.artifact_name }}

      - name: Stage Binary (Windows)
        if: runner.os == 'Windows'
        run: |
          Move-Item -Path "${{ matrix.binary_name }}" -Destination "${{ matrix.artifact_name }}"

      - name: Upload Artifact
        uses: actions/upload-artifact@v4
        with:
          name: ${{ matrix.artifact_name }}
          path: ${{ matrix.artifact_name }}

  release:
    name: Publish Release
    needs: build
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Download all build artifacts
        uses: actions/download-artifact@v4
        with:
          path: release_assets
          merge-multiple: true

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          files: release_assets/*
          generate_release_notes: true
```
