use tauri::{
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Manager, Runtime,
};
use tauri_plugin_positioner::{Position, WindowExt};
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState};

/// Toggle the popover window: position it below the tray icon then show/hide.
fn toggle_window<R: Runtime>(app: &tauri::AppHandle<R>) {
    let window = match app.get_webview_window("main") {
        Some(w) => w,
        None => return,
    };

    if window.is_visible().unwrap_or(false) {
        let _ = window.hide();
    } else {
        // Move to just below the tray icon
        let _ = window.move_window(Position::TrayBottomCenter);
        let _ = window.show();
        let _ = window.set_focus();
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // ⌥Space (Option+Space) summons / dismisses the popover from anywhere.
    let summon_shortcut = Shortcut::new(Some(Modifiers::ALT), Code::Space);

    tauri::Builder::default()
        .plugin(tauri_plugin_positioner::init())
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler({
                    let summon_shortcut = summon_shortcut.clone();
                    move |app, shortcut, event| {
                        if shortcut == &summon_shortcut && event.state() == ShortcutState::Pressed {
                            toggle_window(app);
                        }
                    }
                })
                .build(),
        )
        .setup(move |app| {
            // Debug logging (dev builds only)
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            // Register the global summon shortcut.
            if let Err(err) = app.global_shortcut().register(summon_shortcut.clone()) {
                eprintln!("[Lyra] Failed to register global shortcut: {err}");
            }

            // ── macOS: run as an accessory so we never appear in the Dock ──
            #[cfg(target_os = "macos")]
            {
                app.set_activation_policy(tauri::ActivationPolicy::Accessory);
            }

            // ── Build tray icon ──────────────────────────────────────────
            let icon = tauri::include_image!("icons/32x32.png");
            let handle = app.handle().clone();

            TrayIconBuilder::new()
                .icon(icon)
                .icon_as_template(true) // adapts to light/dark menu bar
                .tooltip("Lyra Assistant")
                .on_tray_icon_event(move |_tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        toggle_window(&handle);
                    }
                })
                .build(app)?;

            // ── Window blur → auto-hide ──────────────────────────────────
            let main_window = app
                .get_webview_window("main")
                .ok_or("Failed to get main window")?;

            let win_clone = main_window.clone();
            main_window.on_window_event(move |event| {
                if let tauri::WindowEvent::Focused(false) = event {
                    let _ = win_clone.hide();
                }
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
