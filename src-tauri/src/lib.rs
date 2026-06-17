use std::sync::Mutex;

use tauri::Manager;
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

const BACKEND_SIDECAR: &str = "alphafoundry-backend";
const BACKEND_HOST: &str = "127.0.0.1";
const BACKEND_PORT: &str = "8765";

#[derive(Default)]
struct BackendState {
    child: Mutex<Option<CommandChild>>,
}

#[tauri::command]
fn backend_url() -> String {
    format!("http://{BACKEND_HOST}:{BACKEND_PORT}")
}

fn start_backend_sidecar(app: &tauri::AppHandle) {
    if cfg!(dev) {
        log::info!(
            "Skipping backend sidecar in tauri dev; beforeDevCommand starts the backend"
        );
        return;
    }

    match app.shell().sidecar(BACKEND_SIDECAR) {
        Ok(command) => match command
            .args(["--host", BACKEND_HOST, "--port", BACKEND_PORT])
            .spawn()
        {
            Ok((mut rx, child)) => {
                if let Ok(mut slot) = app.state::<BackendState>().child.lock() {
                    *slot = Some(child);
                }
                tauri::async_runtime::spawn(async move {
                    while let Some(event) = rx.recv().await {
                        match event {
                            CommandEvent::Stdout(line) => {
                                log::info!("backend: {}", String::from_utf8_lossy(&line).trim());
                            }
                            CommandEvent::Stderr(line) => {
                                log::warn!("backend: {}", String::from_utf8_lossy(&line).trim());
                            }
                            CommandEvent::Terminated(status) => {
                                log::warn!("backend exited: {:?}", status);
                            }
                            _ => {}
                        }
                    }
                });
                log::info!("AlphaFoundry backend sidecar started");
            }
            Err(error) => {
                log::warn!("Unable to start AlphaFoundry backend sidecar: {error}");
            }
        },
        Err(error) => {
            log::warn!(
                "AlphaFoundry backend sidecar is unavailable; use scripts/desktop/backend_launcher.py in development: {error}"
            );
        }
    }
}

fn stop_backend_sidecar(app: &tauri::AppHandle) {
    if let Ok(mut slot) = app.state::<BackendState>().child.lock() {
        if let Some(child) = slot.take() {
            if let Err(error) = child.kill() {
                log::warn!("Unable to stop AlphaFoundry backend sidecar: {error}");
            }
        }
    }
}

pub fn run() {
    tauri::Builder::default()
        .manage(BackendState::default())
        .plugin(tauri_plugin_log::Builder::default().build())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![backend_url])
        .setup(|app| {
            start_backend_sidecar(&app.handle());
            Ok(())
        })
        .on_window_event(|window, event| {
            if matches!(event, tauri::WindowEvent::Destroyed) {
                stop_backend_sidecar(&window.app_handle());
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running AlphaFoundry desktop shell");
}
