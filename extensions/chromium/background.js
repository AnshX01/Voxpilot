/**
 * VoxPilot Browser Accessibility Bridge Background Service Worker
 * Bridges Chrome Native Messaging host with active browser tab.
 */

const HOST_NAME = "com.voxpilot.host";
let port = null;

function connectNativeHost() {
  try {
    port = chrome.runtime.connectNative(HOST_NAME);
    port.onMessage.addListener(onNativeMessage);
    port.onDisconnect.addListener(onNativeDisconnect);
    console.log("[VoxPilot Extension] Connected to native host:", HOST_NAME);
  } catch (err) {
    console.error("[VoxPilot Extension] Failed to connect to native host:", err);
  }
}

function onNativeDisconnect() {
  console.warn("[VoxPilot Extension] Native host disconnected. Reconnecting in 3s...");
  port = null;
  setTimeout(connectNativeHost, 3000);
}

function onNativeMessage(msg) {
  if (msg.action === "QUERY_DOM_ELEMENTS") {
    // Query active tab
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (!tabs || tabs.length === 0) {
        port.postMessage({ status: "error", error: "No active tab" });
        return;
      }
      const activeTabId = tabs[0].id;
      chrome.tabs.sendMessage(
        activeTabId,
        { action: "GET_DOM_ELEMENTS" },
        (response) => {
          if (chrome.runtime.lastError) {
            port.postMessage({
              status: "error",
              error: chrome.runtime.lastError.message,
            });
            return;
          }
          port.postMessage({
            status: "ok",
            tab_id: activeTabId,
            url: tabs[0].url,
            elements: response ? response.elements : [],
          });
        }
      );
    });
  } else if (msg.action === "CLICK_DOM_ELEMENT") {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (!tabs || tabs.length === 0) return;
      chrome.tabs.sendMessage(
        tabs[0].id,
        { action: "CLICK_ELEMENT", bridge_id: msg.bridge_id },
        (response) => {
          port.postMessage({
            status: response ? response.status : "error",
            bridge_id: msg.bridge_id,
          });
        }
      );
    });
  }
}

// Initial connection on startup
connectNativeHost();
