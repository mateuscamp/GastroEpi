// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    // WebKitGTK's DMABUF renderer crashes on Wayland with hybrid Intel/NVIDIA
    // GPUs ("Error 71 dispatching to Wayland display"). Disabling it before the
    // webview initializes keeps the window from closing on launch.
    #[cfg(target_os = "linux")]
    std::env::set_var("WEBKIT_DISABLE_DMABUF_RENDERER", "1");

    tauri_app_lib::run()
}
