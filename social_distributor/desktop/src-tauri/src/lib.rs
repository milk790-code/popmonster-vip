//! Native shell for the Social Distributor dashboard.
//!
//! Loads the existing web frontend (either at the dev URL or from
//! ``frontendDist``) inside a Tauri webview, registers a global shortcut
//! so the user can summon the window from any app, and exposes a tray
//! icon for quick toggling.

use tauri::{
    AppHandle, Manager,
    tray::{TrayIconBuilder, TrayIconEvent},
};
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let summon_shortcut = Shortcut::new(
        Some(Modifiers::SHIFT | Modifiers::SUPER),
        Code::KeyP,
    );

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(move |app, shortcut, event| {
                    if event.state == ShortcutState::Pressed && shortcut == &summon_shortcut {
                        toggle_main_window(app);
                    }
                })
                .build(),
        )
        .setup(move |app| {
            // Register the global shortcut at startup.
            app.global_shortcut().register(summon_shortcut.clone())?;

            // Tray: click toggles window, right-click placeholder for menu.
            let app_handle = app.handle().clone();
            let _tray = TrayIconBuilder::with_id("main-tray")
                .tooltip("Social Distributor")
                .on_tray_icon_event(move |_tray, event| {
                    if let TrayIconEvent::Click { .. } = event {
                        toggle_main_window(&app_handle);
                    }
                })
                .build(app)?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running social distributor desktop");
}

fn toggle_main_window(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let visible = window.is_visible().unwrap_or(false);
        if visible {
            // Bring to front instead of hiding when already visible.
            let _ = window.set_focus();
            return;
        }
        let _ = window.show();
        let _ = window.set_focus();
    }
}
