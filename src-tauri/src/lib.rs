use std::io::{Read, Write};
use std::net::{TcpStream, ToSocketAddrs};
use std::sync::Mutex;
use std::time::Duration;

use tauri::Manager;
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

const BACKEND_SIDECAR: &str = "alphafoundry-backend";
const BACKEND_HOST: &str = "127.0.0.1";
const BACKEND_PORT: &str = "8765";
const BACKEND_PROBE_TIMEOUT: Duration = Duration::from_millis(500);

#[derive(Default)]
struct BackendState {
    child: Mutex<Option<CommandChild>>,
}

#[tauri::command]
fn backend_url() -> String {
    format!("http://{BACKEND_HOST}:{BACKEND_PORT}")
}

fn response_is_healthy(response: &[u8]) -> bool {
    response.starts_with(b"HTTP/1.1 200") || response.starts_with(b"HTTP/1.0 200")
}

fn backend_is_healthy(host: &str, port: &str) -> bool {
    let address = format!("{host}:{port}");
    let Some(socket_address) = address
        .to_socket_addrs()
        .ok()
        .and_then(|mut addresses| addresses.next())
    else {
        log::warn!("Unable to resolve AlphaFoundry backend address: {address}");
        return false;
    };

    let mut stream = match TcpStream::connect_timeout(&socket_address, BACKEND_PROBE_TIMEOUT) {
        Ok(stream) => stream,
        Err(error) => {
            log::debug!("AlphaFoundry backend is not reachable at {address}: {error}");
            return false;
        }
    };

    if let Err(error) = stream.set_read_timeout(Some(BACKEND_PROBE_TIMEOUT)) {
        log::warn!("Unable to set backend health read timeout: {error}");
        return false;
    }
    if let Err(error) = stream.set_write_timeout(Some(BACKEND_PROBE_TIMEOUT)) {
        log::warn!("Unable to set backend health write timeout: {error}");
        return false;
    }

    let request =
        format!("GET /health HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n");
    if let Err(error) = stream.write_all(request.as_bytes()) {
        log::debug!("Unable to send AlphaFoundry backend health request: {error}");
        return false;
    }

    let mut response = [0_u8; 256];
    match stream.read(&mut response) {
        Ok(bytes_read) => response_is_healthy(&response[..bytes_read]),
        Err(error) => {
            log::debug!("Unable to read AlphaFoundry backend health response: {error}");
            false
        }
    }
}

fn start_backend_sidecar(app: &tauri::AppHandle) {
    if cfg!(dev) {
        log::info!("Skipping backend sidecar in tauri dev; beforeDevCommand starts the backend");
        return;
    }

    if backend_is_healthy(BACKEND_HOST, BACKEND_PORT) {
        log::info!("Reusing healthy AlphaFoundry backend at {}", backend_url());
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
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(window) = app.get_webview_window("main") {
                if let Err(error) = window.show() {
                    log::warn!("Unable to show existing AlphaFoundry window: {error}");
                }
                if let Err(error) = window.set_focus() {
                    log::warn!("Unable to focus existing AlphaFoundry window: {error}");
                }
            } else {
                log::warn!("AlphaFoundry single-instance callback could not find the main window");
            }
        }))
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

#[cfg(test)]
mod tests {
    use super::{backend_is_healthy, response_is_healthy};
    use std::io::{Read, Write};
    use std::net::TcpListener;
    use std::thread;

    fn serve_once(response: &'static [u8]) -> String {
        let listener = TcpListener::bind("127.0.0.1:0").expect("bind local test server");
        let port = listener.local_addr().expect("read local address").port();
        thread::spawn(move || {
            let (mut stream, _) = listener.accept().expect("accept health request");
            let mut request = [0_u8; 256];
            let _ = stream.read(&mut request).expect("read health request");
            stream.write_all(response).expect("write health response");
        });
        port.to_string()
    }

    #[test]
    fn health_response_requires_success_status() {
        assert!(response_is_healthy(b"HTTP/1.1 200 OK\r\n\r\n"));
        assert!(!response_is_healthy(
            b"HTTP/1.1 503 Service Unavailable\r\n\r\n"
        ));
    }

    #[test]
    fn backend_probe_accepts_a_healthy_local_service() {
        let port = serve_once(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK");

        assert!(backend_is_healthy("127.0.0.1", &port));
    }

    #[test]
    fn backend_probe_rejects_an_unhealthy_local_service() {
        let port = serve_once(b"HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\n\r\n");

        assert!(!backend_is_healthy("127.0.0.1", &port));
    }
}
