use tauri::{
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Emitter, Manager, Runtime,
};
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState};
use tauri_plugin_positioner::{Position, WindowExt};

#[cfg(target_os = "macos")]
use tauri_nspanel::WebviewWindowExt as PanelWebviewWindowExt;

/// NSWindowStyleMaskNonactivatingPanel — a panel that never becomes the key
/// application window, so summoning Lyra does not disturb the app you're in.
#[cfg(target_os = "macos")]
const NONACTIVATING_PANEL_MASK: i32 = 1 << 7;

/// Horizontal safety margin (logical px) kept between the popover and a screen edge.
const EDGE_MARGIN: i32 = 8;

/// Convert the main window into a native NSPanel that floats above other
/// windows (including full-screen apps) and never steals focus.
#[cfg(target_os = "macos")]
fn promote_to_panel<R: Runtime>(app: &tauri::AppHandle<R>) {
    let Some(window) = app.get_webview_window("main") else {
        return;
    };
    match window.to_panel() {
        Ok(panel) => {
            panel.set_style_mask(NONACTIVATING_PANEL_MASK);
            // Float above normal windows; join every Space and stay visible over
            // full-screen apps (auxiliary), matching Control-Center behaviour.
            // 1 = CanJoinAllSpaces, 16 = Stationary, 256 = FullScreenAuxiliary
            panel.set_collection_behaviour(1 | 16 | 256);
        }
        Err(err) => eprintln!("[Lyra] NSPanel promotion failed: {err:?}"),
    }
}

/// Anchor the window beneath the tray icon, clamp it inside the active display,
/// reveal it, and tell the frontend where the caret should point.
fn position_and_show<R: Runtime>(app: &tauri::AppHandle<R>, tray_center_x: Option<f64>) {
    let Some(window) = app.get_webview_window("main") else {
        return;
    };

    // Positioner uses the tray rect cached by `on_tray_event` (see tray handler).
    let _ = window.move_window(Position::TrayBottomCenter);

    // ── Horizontal clamp: keep the panel fully on the active display ─────────
    if let (Ok(Some(monitor)), Ok(pos), Ok(size)) = (
        window.current_monitor(),
        window.outer_position(),
        window.outer_size(),
    ) {
        let scale = monitor.scale_factor();
        let mon_x = monitor.position().x;
        let mon_w = monitor.size().width as i32;
        let win_w = size.width as i32;
        let margin = (EDGE_MARGIN as f64 * scale) as i32;

        let min_x = mon_x + margin;
        let max_x = mon_x + mon_w - win_w - margin;
        let clamped_x = pos.x.max(min_x).min(max_x.max(min_x));

        if clamped_x != pos.x {
            let mut new_pos = pos;
            new_pos.x = clamped_x;
            let _ = window.set_position(tauri::PhysicalPosition::new(new_pos.x, new_pos.y));
        }

        // ── Caret offset: where the tray icon sits relative to the panel ─────
        if let (Some(center_phys), Ok(final_pos)) = (tray_center_x, window.outer_position()) {
            let caret_logical = (center_phys - final_pos.x as f64) / scale;
            let _ = window.emit("tray-caret", caret_logical);
        }
    }

    let _ = window.show();
    let _ = window.set_focus();
}

fn toggle_window<R: Runtime>(app: &tauri::AppHandle<R>, tray_center_x: Option<f64>) {
    let Some(window) = app.get_webview_window("main") else {
        return;
    };
    if window.is_visible().unwrap_or(false) {
        let _ = window.hide();
    } else {
        position_and_show(app, tray_center_x);
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // ⌥Space (Option+Space) summons / dismisses the popover from anywhere.
    let summon_shortcut = Shortcut::new(Some(Modifiers::ALT), Code::Space);

    let builder = tauri::Builder::default()
        .plugin(tauri_plugin_positioner::init())
        .plugin(tauri_plugin_opener::init());

    #[cfg(target_os = "macos")]
    let builder = builder.plugin(tauri_nspanel::init());

    builder
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler({
                    let summon_shortcut = summon_shortcut.clone();
                    move |app, shortcut, event| {
                        if shortcut == &summon_shortcut && event.state() == ShortcutState::Pressed {
                            toggle_window(app, None);
                        }
                    }
                })
                .build(),
        )
        .setup(move |app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            if let Err(err) = app.global_shortcut().register(summon_shortcut.clone()) {
                eprintln!("[Lyra] Failed to register global shortcut: {err}");
            }

            // ── macOS: run as an accessory (no Dock icon) + promote to NSPanel ──
            #[cfg(target_os = "macos")]
            {
                app.set_activation_policy(tauri::ActivationPolicy::Accessory);
                promote_to_panel(app.handle());
            }

            // ── Tray icon ────────────────────────────────────────────────────
            let icon = tauri::include_image!("icons/32x32.png");
            let handle = app.handle().clone();

            TrayIconBuilder::new()
                .icon(icon)
                .icon_as_template(true)
                .tooltip("Lyra Assistant")
                .on_tray_icon_event(move |tray, event| {
                    // CRITICAL: cache the tray rect so Position::TrayBottomCenter
                    // can anchor the popover beneath the icon (fixes centering).
                    tauri_plugin_positioner::on_tray_event(tray.app_handle(), &event);

                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        position,
                        ..
                    } = event
                    {
                        // The click position (physical px) approximates the icon
                        // centre — good enough to aim the caret.
                        toggle_window(&handle, Some(position.x));
                    }
                })
                .build(app)?;

            // ── Auto-hide on blur ──────────────────────────────────────────────
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
