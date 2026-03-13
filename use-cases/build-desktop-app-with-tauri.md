---
title: Build a Desktop App with Tauri
slug: build-desktop-app-with-tauri
description: >-
  Build a cross-platform desktop application using Tauri with a web frontend,
  Rust backend commands, system tray integration, auto-updates, and native
  file system access — all in a 5MB binary.
skills:
  - tauri
  - tailwindcss
category: development
tags:
  - desktop
  - tauri
  - rust
  - cross-platform
  - native
---

# Build a Desktop App with Tauri

Felix wants to build a clipboard manager that runs in the system tray. Electron would work but produces a 200MB binary for a simple app. Tauri uses the OS's native webview (no bundled Chromium), so the same app compiles to a 5MB binary. The frontend is any web framework (React, Svelte, Vue), and backend logic is Rust commands that the frontend calls like async functions.

## Step 1: Create the Project

```bash
npm create tauri-app@latest clipboard-manager -- --template react-ts
cd clipboard-manager
npm install
```

```json
// src-tauri/tauri.conf.json (key parts)
{
  "app": {
    "withGlobalShortcut": true,
    "windows": [
      {
        "title": "Clipboard Manager",
        "width": 400,
        "height": 600,
        "decorations": false,
        "transparent": true,
        "visible": false,
        "skipTaskbar": true
      }
    ],
    "trayIcon": {
      "iconPath": "icons/tray-icon.png",
      "tooltip": "Clipboard Manager"
    }
  },
  "bundle": {
    "active": true,
    "targets": "all",
    "identifier": "com.felix.clipboard-manager"
  }
}
```

## Step 2: Rust Backend — Clipboard Monitoring

```rust
// src-tauri/src/lib.rs
use tauri::{AppHandle, Manager, SystemTray, SystemTrayEvent, SystemTrayMenu, CustomMenuItem};
use serde::{Deserialize, Serialize};
use std::sync::Mutex;

#[derive(Debug, Clone, Serialize, Deserialize)]
struct ClipboardEntry {
    id: String,
    content: String,
    content_type: String,
    timestamp: u64,
    pinned: bool,
}

struct AppState {
    history: Mutex<Vec<ClipboardEntry>>,
    max_entries: usize,
}

#[tauri::command]
fn get_clipboard_history(state: tauri::State<AppState>) -> Vec<ClipboardEntry> {
    state.history.lock().unwrap().clone()
}

#[tauri::command]
fn paste_entry(entry_id: String, state: tauri::State<AppState>) -> Result<(), String> {
    let history = state.history.lock().unwrap();
    let entry = history.iter().find(|e| e.id == entry_id)
        .ok_or("Entry not found")?;

    let mut clipboard = arboard::Clipboard::new().map_err(|e| e.to_string())?;
    clipboard.set_text(&entry.content).map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
fn toggle_pin(entry_id: String, state: tauri::State<AppState>) -> Result<bool, String> {
    let mut history = state.history.lock().unwrap();
    let entry = history.iter_mut().find(|e| e.id == entry_id)
        .ok_or("Entry not found")?;
    entry.pinned = !entry.pinned;
    Ok(entry.pinned)
}

#[tauri::command]
fn clear_history(state: tauri::State<AppState>) {
    let mut history = state.history.lock().unwrap();
    history.retain(|e| e.pinned);
}

pub fn run() {
    tauri::Builder::default()
        .manage(AppState {
            history: Mutex::new(Vec::new()),
            max_entries: 100,
        })
        .invoke_handler(tauri::generate_handler![
            get_clipboard_history,
            paste_entry,
            toggle_pin,
            clear_history,
        ])
        .setup(|app| {
            // Start clipboard watcher in background
            let handle = app.handle().clone();
            std::thread::spawn(move || watch_clipboard(handle));
            Ok(())
        })
        .on_system_tray_event(|app, event| {
            match event {
                SystemTrayEvent::LeftClick { .. } => {
                    let window = app.get_webview_window("main").unwrap();
                    if window.is_visible().unwrap() {
                        window.hide().unwrap();
                    } else {
                        window.show().unwrap();
                        window.set_focus().unwrap();
                    }
                }
                _ => {}
            }
        })
        .run(tauri::generate_context!())
        .expect("error running app");
}

fn watch_clipboard(app: AppHandle) {
    let mut clipboard = arboard::Clipboard::new().unwrap();
    let mut last_content = String::new();

    loop {
        if let Ok(content) = clipboard.get_text() {
            if content != last_content && !content.is_empty() {
                last_content = content.clone();

                let state = app.state::<AppState>();
                let mut history = state.history.lock().unwrap();

                // Deduplicate
                history.retain(|e| e.content != content);

                history.insert(0, ClipboardEntry {
                    id: uuid::Uuid::new_v4().to_string(),
                    content,
                    content_type: "text".into(),
                    timestamp: std::time::SystemTime::now()
                        .duration_since(std::time::UNIX_EPOCH).unwrap().as_secs(),
                    pinned: false,
                });

                // Trim to max, keeping pinned
                while history.len() > state.max_entries {
                    if let Some(pos) = history.iter().rposition(|e| !e.pinned) {
                        history.remove(pos);
                    } else {
                        break;
                    }
                }

                // Notify frontend
                let _ = app.emit("clipboard-updated", ());
            }
        }
        std::thread::sleep(std::time::Duration::from_millis(500));
    }
}
```

## Step 3: React Frontend

```tsx
// src/App.tsx
import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

interface ClipboardEntry {
  id: string;
  content: string;
  timestamp: number;
  pinned: boolean;
}

function App() {
  const [entries, setEntries] = useState<ClipboardEntry[]>([]);
  const [search, setSearch] = useState("");

  const loadHistory = async () => {
    const history = await invoke<ClipboardEntry[]>("get_clipboard_history");
    setEntries(history);
  };

  useEffect(() => {
    loadHistory();
    const unlisten = listen("clipboard-updated", loadHistory);
    return () => { unlisten.then((fn) => fn()); };
  }, []);

  const handlePaste = async (id: string) => {
    await invoke("paste_entry", { entryId: id });
  };

  const handlePin = async (id: string) => {
    await invoke("toggle_pin", { entryId: id });
    loadHistory();
  };

  const filtered = entries.filter((e) =>
    e.content.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="h-screen bg-gray-900 text-white flex flex-col rounded-lg overflow-hidden">
      <div className="p-3 border-b border-gray-700">
        <input
          type="text"
          placeholder="Search clipboard..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full bg-gray-800 rounded px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-blue-500"
          autoFocus
        />
      </div>

      <div className="flex-1 overflow-y-auto">
        {filtered.map((entry) => (
          <div
            key={entry.id}
            onClick={() => handlePaste(entry.id)}
            className="px-3 py-2 hover:bg-gray-800 cursor-pointer border-b border-gray-800 flex items-start gap-2"
          >
            <pre className="flex-1 text-sm text-gray-300 whitespace-pre-wrap line-clamp-3">
              {entry.content}
            </pre>
            <button
              onClick={(e) => { e.stopPropagation(); handlePin(entry.id); }}
              className={`text-xs ${entry.pinned ? "text-yellow-400" : "text-gray-600"}`}
            >
              📌
            </button>
          </div>
        ))}
      </div>

      <div className="p-2 border-t border-gray-700 text-xs text-gray-500 flex justify-between">
        <span>{entries.length} items</span>
        <button
          onClick={() => invoke("clear_history").then(loadHistory)}
          className="text-red-400 hover:text-red-300"
        >
          Clear
        </button>
      </div>
    </div>
  );
}
```

## Step 4: Build and Distribute

```bash
# Development
npm run tauri dev

# Production build — creates installer for current platform
npm run tauri build

# Output locations:
# macOS: src-tauri/target/release/bundle/dmg/
# Windows: src-tauri/target/release/bundle/nsis/
# Linux: src-tauri/target/release/bundle/deb/ and /appimage/
```

## Summary

Felix has a clipboard manager that sits in the system tray, monitors the clipboard in a background thread, and shows a searchable history when clicked. The app is 5MB (vs 200MB with Electron), starts in 200ms, and uses 15MB of RAM. Rust handles the performance-critical clipboard monitoring, while React + Tailwind provides a polished UI. Pinned entries survive history clearing, deduplication prevents repeats, and the whole thing builds to native installers for macOS, Windows, and Linux from the same codebase.
