# Generating bundle icons

Tauri's bundler needs platform-specific raster icons (`32x32.png`,
`128x128.png`, `icon.ico` for Windows, `icon.icns` for macOS). The SVG
sources live alongside this file; convert them once before your first
production `tauri build`:

```bash
cd desktop/src-tauri
pnpm tauri icon icon.svg
```

That command writes the full set into this directory. Until you run it,
`tauri dev` works (icons are not required in dev) but `tauri build` will
complain about missing files.
