/**
 * VoxPilot Browser Accessibility Bridge Content Script
 * Scans interactive DOM nodes and computes exact client coordinates.
 */

(function () {
  "use strict";

  const INTERACTIVE_SELECTORS = [
    "a[href]",
    "button",
    "input:not([type='hidden'])",
    "select",
    "textarea",
    "[role='button']",
    "[role='link']",
    "[role='checkbox']",
    "[role='menuitem']",
    "[role='tab']",
    "[role='combobox']",
    "[contenteditable='true']",
    "[tabindex]:not([tabindex='-1'])",
  ].join(",");

  function getElementLabel(el) {
    if (el.getAttribute("aria-label")) {
      return el.getAttribute("aria-label").trim();
    }
    if (el.getAttribute("aria-labelledby")) {
      const labeledById = el.getAttribute("aria-labelledby");
      const labelEl = document.getElementById(labeledById);
      if (labelEl && labelEl.innerText) {
        return labelEl.innerText.trim();
      }
    }
    if (el.placeholder) {
      return el.placeholder.trim();
    }
    if (el.innerText && el.innerText.trim().length > 0) {
      return el.innerText.trim().substring(0, 80);
    }
    if (el.title) {
      return el.title.trim();
    }
    if (el.value && typeof el.value === "string") {
      return el.value.trim().substring(0, 50);
    }
    return el.tagName.toLowerCase();
  }

  function isElementVisible(el) {
    if (!el.isConnected) return false;
    const style = window.getComputedStyle(el);
    if (
      style.display === "none" ||
      style.visibility === "hidden" ||
      style.opacity === "0"
    ) {
      return false;
    }
    const rect = el.getBoundingClientRect();
    if (rect.width <= 2 || rect.height <= 2) {
      return false;
    }
    // Check if element is within viewport
    if (
      rect.bottom < 0 ||
      rect.right < 0 ||
      rect.top > window.innerHeight ||
      rect.left > window.innerWidth
    ) {
      return false;
    }
    return true;
  }

  function collectInteractiveElements() {
    const rawNodes = document.querySelectorAll(INTERACTIVE_SELECTORS);
    const elements = [];
    let counter = 1;

    for (const node of rawNodes) {
      if (!isElementVisible(node)) continue;

      const rect = node.getBoundingClientRect();
      const label = getElementLabel(node);

      // Assign a temporary DOM bridge ID
      const bridgeId = `voxdom_${counter++}`;
      node.setAttribute("data-voxpilot-id", bridgeId);

      elements.push({
        bridge_id: bridgeId,
        tag: node.tagName.toLowerCase(),
        name: label,
        viewport_x: Math.round(rect.left),
        viewport_y: Math.round(rect.top),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
        screen_x: Math.round(window.screenX + rect.left),
        screen_y: Math.round(
          window.screenY +
            (window.outerHeight - window.innerHeight) +
            rect.top
        ),
      });
    }

    return elements;
  }

  function clickElementByBridgeId(bridgeId) {
    const target = document.querySelector(`[data-voxpilot-id="${bridgeId}"]`);
    if (!target) return false;

    target.scrollIntoView({ behavior: "instant", block: "nearest" });
    target.focus();

    const mouseEvents = ["pointerdown", "mousedown", "pointerup", "mouseup", "click"];
    for (const evType of mouseEvents) {
      const evt = new MouseEvent(evType, {
        bubbles: true,
        cancelable: true,
        view: window,
      });
      target.dispatchEvent(evt);
    }
    return true;
  }

  // Handle messages from background worker
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "GET_DOM_ELEMENTS") {
      const results = collectInteractiveElements();
      sendResponse({ status: "ok", elements: results, count: results.length });
    } else if (request.action === "CLICK_ELEMENT") {
      const success = clickElementByBridgeId(request.bridge_id);
      sendResponse({ status: success ? "ok" : "not_found" });
    }
    return true;
  });
})();
