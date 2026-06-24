Below is a working **Tauri v2** pattern for a macOS menu bar app: create the tray icon with `TrayIconBuilder`, set the app activation policy to `Accessory` so it stays out of the Dock, use the positioner plugin’s tray-relative positioning, and hide the popover on blur/toggle it on tray clicks. [qiita](https://qiita.com/Procrustes5/items/fb45c3ae0e42f7716d93)

The most important macOS-specific points are: use a template tray icon for dark/light mode, start with a hidden non-resizable utility-style window, and remember that tray-relative positioning only works after feeding tray events to the positioner plugin and enabling its permissions/cargo feature. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/images/50087095/d71c6fb6-b11c-400e-af19-40766dbd4312/image.jpg?AWSAccessKeyId=ASIA2F3EMEYE2OYEA543&Signature=cvPemvUx%2FZyIxHBzD6AhXTaRltc%3D&x-amz-security-token=IQoJb3JpZ2luX2VjEGgaCXVzLWVhc3QtMSJHMEUCIQC9E9Ztj0fup7gcsQWMVr4pBZQA0A75dzSs5twe6q2tKAIgKLr56bIYO1HG2OQdanPd%2BNYzCdLnVPVXERTi%2FscSOYIq8wQIMBABGgw2OTk3NTMzMDk3MDUiDMBkUeH1diyc1JeoqyrQBCwKx6UywhT8dDiRLTR4FDUG4blkMd6X8cY03K6uPNnFUE3v1%2BeQ3oSRIRRn7KXq8NH7QlYmvm6k1stBcOwKg6CM4m8EmbvKDFBhGTSQlg4E8S2yc3qpa5Vi3C96ELbw%2BSjQz5gKBh8d%2Bh01N%2BbMgdZvGuna9aHJr4TOSj2K9we%2BgRGrRZIzg9DOVGlZmdxzWgYpyrt01n7MzNlaKSTzfP3Mibp9nWr6VUWrU%2BK9CL80gItclzIJrV6efN%2F8%2BNClcmFNK0yCMI6tM5z%2BCHTl3PIDO09C1%2Bplqwc3%2Brq7T7GIzVroiJkPlKIp%2BizXfl9sAisqyUPBdpLk3pYS35CVY3dj4PzLyzIvr2ghE99omOxtV%2F%2FuLgaOhSDl1AoBbuQCAMUhgOti9kn%2BrtzRzYnpvnBqxRDg5e%2FsIfPXUBb6t%2Buhf3z9kudDec5rDwYjVRgqvKKEKVxWMh8DEfiyrRJr6LVOg2yHtAd6WlW4Vapxnkg7WsiYlZeinKCav5FFkZHhZqYfj4mj7sE4kKQVwjI7hgHTNGfCFulXs%2F867NIk%2B2DDvrjoMDNKPek%2B61bPsCG3HbpbJ0yNuuCAOx3xPLQv4DpgKIzSFzjcHw%2FHJMhABxh83nK4PZxkVwuymlBFYaQ0HntKZyipss2E4BFeeCWGybtEKb3vk1dGhb9WLcuV3HfAU4wK%2FPYz3svxUBkaDDsmf8cwmkAP6aHpbdHlfvJb7my32f5ehHUdhQ%2BJ8wyeUj7H%2B1NbawLGbz9P601%2FxVJ2gFeNT8%2F2%2B0lMgnr3G4mkl1UwmIPu0QY6mAGRAHyVVALj5J0tJG7i7zV6ihVQC6zZscm6T2JLw1L%2Ba6ciHzZKmkNVzLnWVv5uZgW5RsNTfvlgefyZnieNtckkA%2FHucFiwJMhwFHHychbKTNbKUUiKa%2ByCOl3VDd1uA9pVKH0o7W43EXSUkGJUUDr5J3kbZpGLCxrDUBBJqQ8HyeLStmzJwWkTqqnkyG8YzaVITRNnDRAKhQ%3D%3D&Expires=1782288235)

## Rust setup

Tauri’s positioner plugin documents two key requirements for tray-relative placement: enable the `tray-icon` feature in `Cargo.toml`, and call `tauri_plugin_positioner::on_tray_event(...)` from your tray event handler so the plugin can cache the native tray geometry. The Tauri discussion on hiding the Dock icon confirms `app.set_activation_policy(tauri::ActivationPolicy::Accessory)` is the v2 approach on macOS. [support.apple](https://support.apple.com/guide/mac-help/open-apps-from-the-dock-mh35859/mac)

```toml
# src-tauri/Cargo.toml
[package]
name = "menubar-popover"
version = "0.1.0"
edition = "2021"

[dependencies]
tauri = { version = "2", features = [] }
tauri-plugin-positioner = { version = "2.3", features = ["tray-icon"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
```

```json
// src-tauri/capabilities/default.json
{
  "permissions": [
    "core:default",
    "positioner:default"
  ]
}
```

```json
// src-tauri/tauri.conf.json
{
  "$schema": "https://schema.tauri.app/config/2",
  "productName": "MenuBarPopover",
  "version": "0.1.0",
  "identifier": "com.example.menubarpopover",
  "app": {
    "windows": [
      {
        "label": "popover",
        "title": "Popover",
        "url": "index.html",
        "visible": false,
        "decorations": false,
        "resizable": false,
        "fullscreen": false,
        "alwaysOnTop": true,
        "skipTaskbar": true,
        "width": 360,
        "height": 420,
        "focus": false,
        "shadow": true
      }
    ]
  },
  "bundle": {
    "active": true,
    "targets": "all",
    "icon": [
      "icons/32x32.png",
      "icons/128x128.png",
      "icons/icon.icns"
    ]
  }
}
```

## Main code

This example builds one hidden window called `popover`, registers the positioner plugin, hides the Dock icon on macOS with `Accessory`, toggles on left-click, and hides instead of closing when the user presses the window close button. It also shows a manual fallback for positioning when you want to compute coordinates from the tray click rectangle yourself, which is a common macOS workaround when you want tighter control over offsets. [dev](https://dev.to/hiyoyok/building-a-menubar-app-with-tauri-v2-what-nobody-tells-you-2nae)

```rust
// src-tauri/src/lib.rs
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::{
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    ActivationPolicy, AppHandle, Manager, PhysicalPosition, PhysicalSize, WebviewWindow,
    WindowEvent,
};
use tauri_plugin_positioner::{Position, WindowExt};

const WINDOW_LABEL: &str = "popover";
const POPOVER_VERTICAL_GAP: i32 = 6;

fn show_and_focus(window: &WebviewWindow) -> tauri::Result<()> {
    if !window.is_visible()? {
        window.show()?;
    }
    window.set_focus()?;
    Ok(())
}

fn hide_window(window: &WebviewWindow) {
    let _ = window.hide();
}

fn toggle_window(window: &WebviewWindow) -> tauri::Result<()> {
    if window.is_visible()? && window.is_focused()? {
        window.hide()?;
    } else {
        show_and_focus(window)?;
    }
    Ok(())
}

fn move_with_positioner(window: &WebviewWindow) {
    let _ = window.as_ref().window().move_window(Position::TrayCenter);
}

fn move_manually_below_tray(
    window: &WebviewWindow,
    tray_pos: PhysicalPosition<f64>,
    tray_size: PhysicalSize<f64>,
) -> tauri::Result<()> {
    let win_size = window.outer_size()?;
    let x = tray_pos.x as i32 + ((tray_size.width as i32 - win_size.width as i32) / 2);
    let y = tray_pos.y as i32 + tray_size.height as i32 + POPOVER_VERTICAL_GAP;

    window.set_position(PhysicalPosition::new(x, y))?;
    Ok(())
}

fn position_popover(window: &WebviewWindow, event: &TrayIconEvent) {
    move_with_positioner(window);

    if let TrayIconEvent::Click {
        position,
        rect,
        button,
        button_state,
        ..
    } = event
    {
        let left_mouse_up = *button == MouseButton::Left && *button_state == MouseButtonState::Up;
        if left_mouse_up {
            let _ = move_manually_below_tray(window, *position, rect.size);
        }
    }
}

fn handle_tray_click(app: &AppHandle, event: &TrayIconEvent) {
    tauri_plugin_positioner::on_tray_event(app, event);

    let TrayIconEvent::Click {
        button,
        button_state,
        ..
    } = event
    else {
        return;
    };

    if *button != MouseButton::Left || *button_state != MouseButtonState::Up {
        return;
    }

    let Some(window) = app.get_webview_window(WINDOW_LABEL) else {
        return;
    };

    let was_visible = window.is_visible().unwrap_or(false);
    let was_focused = window.is_focused().unwrap_or(false);

    if was_visible && was_focused {
        hide_window(&window);
        return;
    }

    position_popover(&window, event);
    let _ = show_and_focus(&window);
}

#[tauri::command]
fn hide_popover(app: AppHandle) {
    if let Some(window) = app.get_webview_window(WINDOW_LABEL) {
        let _ = window.hide();
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_positioner::init())
        .setup(|app| {
            #[cfg(target_os = "macos")]
            app.set_activation_policy(ActivationPolicy::Accessory);

            let window = app.get_webview_window(WINDOW_LABEL).expect("popover window missing");
            let _ = window.hide();

            let tray_icon = app.default_window_icon().cloned().expect("default icon missing");

            TrayIconBuilder::with_id("menubar")
                .icon(tray_icon)
                .icon_as_template(true)
                .show_menu_on_left_click(false)
                .on_tray_icon_event(|tray, event| {
                    handle_tray_click(tray.app_handle(), &event);
                })
                .build(app)?;

            Ok(())
        })
        .on_window_event(|window, event| {
            if window.label() != WINDOW_LABEL {
                return;
            }

            match event {
                WindowEvent::Focused(false) => {
                    hide_window(window);
                }
                WindowEvent::CloseRequested { api, .. } => {
                    api.prevent_close();
                    hide_window(window);
                }
                _ => {}
            }
        })
        .invoke_handler(tauri::generate_handler![hide_popover])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

## Frontend blur bridge

Tauri exposes focus/blur style window events, but on macOS menu bar apps many teams still add a frontend fallback because the blur/hide behavior can be sensitive around native dialogs and focus transitions. This small frontend layer hides the window on browser blur and suppresses that behavior while a native dialog is intentionally open, which avoids the “popover disappears before file picker shows” issue described by practitioners. [github](https://github.com/tauri-apps/tauri/issues/2485)

```ts
// src/main.ts
import { getCurrentWindow } from "@tauri-apps/api/window";
import { invoke } from "@tauri-apps/api/core";

const appWindow = getCurrentWindow();

let suppressBlurHide = false;

window.addEventListener("blur", async () => {
  if (suppressBlurHide) return;
  await invoke("hide_popover");
});

export async function withNativeDialog<T>(fn: () => Promise<T>): Promise<T> {
  suppressBlurHide = true;
  try {
    return await fn();
  } finally {
    setTimeout(() => {
      suppressBlurHide = false;
    }, 150);
  }
}

// optional extra listener if you want native tauri blur too
const unlistenBlur = await appWindow.listen("tauri://blur", async () => {
  if (suppressBlurHide) return;
  await invoke("hide_popover");
});

// later on cleanup:
// unlistenBlur();
```

## Notes for macOS

For menu bar icons on macOS, `icon_as_template(true)` is important because template icons adapt automatically to light and dark menu bar appearances; colored icons often look wrong or disappear against the menu bar background. For a popover-like feel, the window should usually be hidden at startup, undecorated, non-resizable, skip the taskbar, and often `alwaysOnTop`, otherwise it behaves more like a normal app window than a menu bar panel. [tauritutorials](https://tauritutorials.com/blog/building-a-system-tray-app-with-tauri)

The positioner plugin supports macOS and its default permission set includes `allow-move-window`, but tray-relative placement depends on routing tray events into `tauri_plugin_positioner::on_tray_event(...)`, and some guidance notes that the tray position is only known after the user has clicked the tray icon at least once. Another subtle macOS pitfall is that hiding on blur can conflict with file pickers or other native dialogs, so guard those interactions with a temporary suppression flag as shown above. [github](https://github.com/orgs/tauri-apps/discussions/6023)

If you want the app to behave even more like a native macOS status-item panel, some maintainers point to converting the window to an `NSPanel` for deeper AppKit-style behavior, because a normal window still has limitations in how “panel-like” it can feel on macOS. [support.apple](https://support.apple.com/guide/mac-help/open-apps-from-the-dock-mh35859/mac)

## Common pitfalls

| Pitfall | What to do |
|---|---|
| Dock icon still appears | Call `app.set_activation_policy(ActivationPolicy::Accessory)` on macOS during setup. [support.apple](https://support.apple.com/guide/mac-help/open-apps-from-the-dock-mh35859/mac) |
| Tray positioning does nothing | Enable `tauri-plugin-positioner` with the `tray-icon` feature and call `tauri_plugin_positioner::on_tray_event(...)` in the tray handler. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/images/50087095/d71c6fb6-b11c-400e-af19-40766dbd4312/image.jpg?AWSAccessKeyId=ASIA2F3EMEYE2OYEA543&Signature=cvPemvUx%2FZyIxHBzD6AhXTaRltc%3D&x-amz-security-token=IQoJb3JpZ2luX2VjEGgaCXVzLWVhc3QtMSJHMEUCIQC9E9Ztj0fup7gcsQWMVr4pBZQA0A75dzSs5twe6q2tKAIgKLr56bIYO1HG2OQdanPd%2BNYzCdLnVPVXERTi%2FscSOYIq8wQIMBABGgw2OTk3NTMzMDk3MDUiDMBkUeH1diyc1JeoqyrQBCwKx6UywhT8dDiRLTR4FDUG4blkMd6X8cY03K6uPNnFUE3v1%2BeQ3oSRIRRn7KXq8NH7QlYmvm6k1stBcOwKg6CM4m8EmbvKDFBhGTSQlg4E8S2yc3qpa5Vi3C96ELbw%2BSjQz5gKBh8d%2Bh01N%2BbMgdZvGuna9aHJr4TOSj2K9we%2BgRGrRZIzg9DOVGlZmdxzWgYpyrt01n7MzNlaKSTzfP3Mibp9nWr6VUWrU%2BK9CL80gItclzIJrV6efN%2F8%2BNClcmFNK0yCMI6tM5z%2BCHTl3PIDO09C1%2Bplqwc3%2Brq7T7GIzVroiJkPlKIp%2BizXfl9sAisqyUPBdpLk3pYS35CVY3dj4PzLyzIvr2ghE99omOxtV%2F%2FuLgaOhSDl1AoBbuQCAMUhgOti9kn%2BrtzRzYnpvnBqxRDg5e%2FsIfPXUBb6t%2Buhf3z9kudDec5rDwYjVRgqvKKEKVxWMh8DEfiyrRJr6LVOg2yHtAd6WlW4Vapxnkg7WsiYlZeinKCav5FFkZHhZqYfj4mj7sE4kKQVwjI7hgHTNGfCFulXs%2F867NIk%2B2DDvrjoMDNKPek%2B61bPsCG3HbpbJ0yNuuCAOx3xPLQv4DpgKIzSFzjcHw%2FHJMhABxh83nK4PZxkVwuymlBFYaQ0HntKZyipss2E4BFeeCWGybtEKb3vk1dGhb9WLcuV3HfAU4wK%2FPYz3svxUBkaDDsmf8cwmkAP6aHpbdHlfvJb7my32f5ehHUdhQ%2BJ8wyeUj7H%2B1NbawLGbz9P601%2FxVJ2gFeNT8%2F2%2B0lMgnr3G4mkl1UwmIPu0QY6mAGRAHyVVALj5J0tJG7i7zV6ihVQC6zZscm6T2JLw1L%2Ba6ciHzZKmkNVzLnWVv5uZgW5RsNTfvlgefyZnieNtckkA%2FHucFiwJMhwFHHychbKTNbKUUiKa%2ByCOl3VDd1uA9pVKH0o7W43EXSUkGJUUDr5J3kbZpGLCxrDUBBJqQ8HyeLStmzJwWkTqqnkyG8YzaVITRNnDRAKhQ%3D%3D&Expires=1782288235) |
| Tray icon looks bad in dark mode | Use a monochrome template asset and set `.icon_as_template(true)`. [qiita](https://qiita.com/Procrustes5/items/fb45c3ae0e42f7716d93) |
| Popover closes when native dialog opens | Suppress blur-hiding while launching dialogs, then re-enable it after the dialog settles. [dev](https://dev.to/hiyoyok/building-a-menubar-app-with-tauri-v2-what-nobody-tells-you-2nae) |
| Close button quits app | Intercept `CloseRequested`, prevent it, and hide instead. [codegiz](https://www.codegiz.com/blog/h346wctn/) |

A good next step is to wire this to a tiny Solid/React/Vue frontend and add Escape-to-close plus outside-click polish.