# Social Distributor — Desktop shell (Tauri 2)

Native window for the dashboard, with:

- The existing web UI (`frontend/`) embedded in a webview
- A global shortcut (`Cmd/Ctrl+Shift+P`) that summons / focuses the window
  from any app
- A tray icon that toggles the window on click

Shipping as a Tauri app (Rust core + system webview) instead of Electron
keeps the install footprint at ~10 MB and uses your OS's stock webview, so
the daily-use loop is fast even on modest hardware.

## Status

This is **a scaffold, not a polished product**. It compiles and runs once
your toolchain is ready, but it's intentionally minimal — no auto-update,
no signing, no installer beyond `tauri build`'s defaults.

## Prerequisites (one-off)

| OS | What to install |
|---|---|
| All | [Rust](https://rustup.rs) (stable, ≥ 1.77) |
| All | [Node.js](https://nodejs.org) (≥ 18) — pnpm/npm both work |
| macOS | Xcode CLI tools: `xcode-select --install` |
| Windows | "Desktop development with C++" workload via Visual Studio Build Tools, plus the Windows 11 SDK and WebView2 runtime |
| Linux | `webkit2gtk-4.1`, `libayatana-appindicator3-dev`, `librsvg2-dev`, `build-essential` (apt) |

First-time `cargo build` downloads & compiles ~400 crates and takes
20–40 minutes depending on machine. Subsequent builds are seconds.

## Run in dev

```bash
cd desktop
pnpm install               # or npm install
pnpm tauri dev             # opens the native window pointing at http://localhost:8080
```

`devUrl` in `src-tauri/tauri.conf.json` defaults to `http://localhost:8080`,
which is what `docker-compose.yml` exposes the dashboard on. Change it
before running if your dev URL differs.

## Build a release bundle

```bash
# 1. Generate bundle icons from the bundled SVG (one-off):
pnpm tauri icon src-tauri/icons/icon.svg

# 2. Build:
pnpm tauri build
```

Output:

| Platform | Artefact path |
|---|---|
| macOS | `src-tauri/target/release/bundle/dmg/*.dmg` |
| Windows | `src-tauri/target/release/bundle/msi/*.msi` |
| Linux | `src-tauri/target/release/bundle/{deb,appimage}/*` |

## How it relates to the web frontend

The desktop app **does not duplicate the dashboard code**. `tauri.conf.json`
points `frontendDist` at `../../frontend`, so the same HTML/CSS/JS that
runs in your browser also runs inside the native window. Edit one place,
both surfaces update.

## What's deliberately NOT in this scaffold

- **Auto-update** — enable `tauri-plugin-updater` and host a manifest when
  you have a release pipeline.
- **Code-signing / notarisation** — add Apple Developer ID + Windows EV
  cert config when you have those.
- **Native menu bar** beyond the tray — add `tauri::menu` if you want File
  / Edit / Compose menu entries.
- **Push notifications** — you'd plug `tauri-plugin-notification` to
  surface SSE events on the OS notification centre. Sketch:

  ```rust
  // pseudocode in lib.rs setup
  app.notification().builder().title("發布完成").body(...).show()?;
  ```

- **Bundling the API server** — the desktop app still expects you to run
  the Flask backend (locally or remotely). If you want a single-binary
  experience, embed the Flask app via `tauri-plugin-shell` sidecar or
  rewrite that layer in Rust (substantial work, not recommended for v1).
