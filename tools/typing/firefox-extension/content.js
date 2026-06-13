"use strict";

(() => {
  const runtimeApi = typeof browser !== "undefined" ? browser : chrome;
  const maxChars = 4000;
  const transcriptMaxChars = 12000;
  const debounceMs = 900;
  const transcriptDebounceMs = 1800;
  const transcriptMaxMessages = 18;
  const hardSkipHosts = [
    "web.telegram.org",
    "t.me",
    "signal.org",
    "web.whatsapp.com",
    "discord.com",
    "app.slack.com"
  ];
  const sensitiveUrl = /\b(login|sign[\s_-]?in|auth|oauth|sso|password|passwd|reset|account|billing|checkout|payment|bank|2fa|mfa|otp|card|cvv|token)\b/i;
  const sensitiveField = /\b(password|passwd|passphrase|secret|token|api|credential|cookie|otp|2fa|mfa|cvv|card|billing|bank|email|phone|login|auth)\b/i;
  const skippedInputTypes = new Set([
    "password",
    "hidden",
    "file",
    "email",
    "tel",
    "number",
    "url",
    "date",
    "datetime-local",
    "month",
    "time",
    "week",
    "color"
  ]);
  const timers = new WeakMap();
  let transcriptTimer = null;
  let transcriptLastRun = 0;

  const aiOrigins = [
    {
      id: "ai:openai:chatgpt",
      provider: "OpenAI",
      product: "ChatGPT",
      family: "gpt",
      hosts: ["chatgpt.com", "chat.openai.com"]
    },
    {
      id: "ai:google:gemini",
      provider: "Google",
      product: "Gemini",
      family: "gemini",
      hosts: ["gemini.google.com", "bard.google.com"]
    },
    {
      id: "ai:anthropic:claude",
      provider: "Anthropic",
      product: "Claude",
      family: "claude",
      hosts: ["claude.ai"]
    },
    {
      id: "ai:perplexity:perplexity",
      provider: "Perplexity",
      product: "Perplexity",
      family: "perplexity",
      hosts: ["perplexity.ai"]
    },
    {
      id: "ai:microsoft:copilot",
      provider: "Microsoft",
      product: "Copilot",
      family: "copilot",
      hosts: ["copilot.microsoft.com"]
    }
  ];

  function urlAllowed() {
    const url = String(location.href || "");
    if (!/^https?:\/\//i.test(url)) {
      return false;
    }
    if (hardSkipHosts.some((host) => location.hostname === host || location.hostname.endsWith(`.${host}`))) {
      return false;
    }
    return !sensitiveUrl.test(`${url} ${document.title || ""}`);
  }

  function aiPageIdentity() {
    if (!urlAllowed()) {
      return null;
    }
    const host = String(location.hostname || "").toLowerCase();
    for (const rule of aiOrigins) {
      if (rule.hosts.some((candidate) => host === candidate || host.endsWith(`.${candidate}`))) {
        return {
          kind: "ai_counterpart",
          id: rule.id,
          provider: rule.provider,
          product: rule.product,
          family: rule.family,
          surface: "ai_chat",
          origin: `${location.protocol}//${host}`,
          host,
          confidence: "host"
        };
      }
    }
    return null;
  }

  function fieldDescriptor(target) {
    if (!target || target.nodeType !== Node.ELEMENT_NODE) {
      return { safe: false, kind: "unknown", type: "" };
    }
    const element = target;
    const tag = String(element.tagName || "").toLowerCase();
    const type = tag === "input" ? String(element.getAttribute("type") || "text").toLowerCase() : tag;
    if (tag === "input" && skippedInputTypes.has(type)) {
      return { safe: false, kind: tag, type };
    }
    const editable = Boolean(element.isContentEditable);
    if (!(tag === "textarea" || tag === "input" || editable)) {
      return { safe: false, kind: tag || "unknown", type };
    }
    const probeParts = [
      element.getAttribute("name"),
      element.getAttribute("id"),
      element.getAttribute("class"),
      element.getAttribute("aria-label"),
      element.getAttribute("placeholder"),
      element.getAttribute("autocomplete"),
      element.closest("form") ? element.closest("form").getAttribute("action") : ""
    ];
    const probe = probeParts.map((value) => String(value || "")).join(" ");
    if (sensitiveField.test(probe)) {
      return { safe: false, kind: editable ? "contenteditable" : tag, type };
    }
    const form = element.closest("form");
    if (form && form.querySelector("input[type='password']")) {
      return { safe: false, kind: editable ? "contenteditable" : tag, type };
    }
    return { safe: true, kind: editable ? "contenteditable" : tag, type };
  }

  function textValue(target) {
    if (!target || target.nodeType !== Node.ELEMENT_NODE) {
      return "";
    }
    if (target.isContentEditable) {
      return String(target.innerText || target.textContent || "").trim();
    }
    return String(target.value || "").trim();
  }

  function frameKind() {
    try {
      return window.top === window ? "top" : "iframe";
    } catch (_error) {
      return "iframe";
    }
  }

  function send(target, eventKind) {
    if (!urlAllowed()) {
      return;
    }
    const field = fieldDescriptor(target);
    if (!field.safe) {
      return;
    }
    const text = textValue(target);
    if (!text) {
      return;
    }
    const message = {
      schema: "abyss_machine_browser_extension_message_v1",
      event_kind: eventKind,
      browser_name: "firefox",
      url: String(location.href || ""),
      title: String(document.title || ""),
      text: text.slice(0, maxChars),
      text_length: text.length,
      text_truncated: text.length > maxChars,
      field,
      frame_kind: frameKind(),
      policy: {
        raw_keylogging: false,
        keydown_keyup_keypress_captured: false,
        password_fields_captured: false,
        form_values_captured: false,
        cookies_captured: false,
        local_storage_captured: false
      }
    };
    try {
      runtimeApi.runtime.sendMessage(message);
    } catch (_error) {
      return;
    }
  }

  function visibleElement(element) {
    if (!element || element.nodeType !== Node.ELEMENT_NODE) {
      return false;
    }
    const style = window.getComputedStyle(element);
    if (!style || style.display === "none" || style.visibility === "hidden") {
      return false;
    }
    const rect = element.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function transcriptRole(element) {
    const attrRole = String(element.getAttribute("data-message-author-role") || "").toLowerCase();
    if (["user", "assistant", "system"].includes(attrRole)) {
      return attrRole;
    }
    const marker = [
      element.tagName,
      element.getAttribute("class"),
      element.getAttribute("aria-label"),
      element.getAttribute("data-test-id"),
      element.getAttribute("data-testid")
    ].map((value) => String(value || "").toLowerCase()).join(" ");
    if (/\b(user|human|query|prompt|ваш запрос|мой запрос)\b/.test(marker)) {
      return "user";
    }
    if (/\b(assistant|model|response|answer|gemini|chatgpt|claude|ответ)\b/.test(marker)) {
      return "assistant";
    }
    return "unknown";
  }

  function transcriptText(element) {
    const clone = element.cloneNode(true);
    for (const noisy of clone.querySelectorAll("button, input, textarea, select, option, nav, menu, svg, [role='button'], [contenteditable='true']")) {
      noisy.remove();
    }
    return String(clone.innerText || clone.textContent || "")
      .replace(/\uFFFC/g, " ")
      .replace(/[ \t]+\n/g, "\n")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  function transcriptCandidates() {
    const selector = [
      "[data-message-author-role]",
      "user-query",
      "model-response",
      ".user-query",
      ".query-text",
      ".model-response",
      ".message-content",
      ".response-content",
      ".markdown"
    ].join(",");
    const seen = new Set();
    const candidates = [];
    for (const element of document.querySelectorAll(selector)) {
      if (!visibleElement(element)) {
        continue;
      }
      if (element.closest("textarea,input,[contenteditable='true']")) {
        continue;
      }
      const role = transcriptRole(element);
      const text = transcriptText(element);
      if (text.length < 8) {
        continue;
      }
      const key = `${role}\n${text}`;
      if (seen.has(key)) {
        continue;
      }
      seen.add(key);
      candidates.push({ element, role, text });
    }
    return candidates.slice(-transcriptMaxMessages);
  }

  function transcriptLooksPartial(element) {
    if (element.closest("[aria-busy='true'], [data-streaming='true']")) {
      return true;
    }
    return Boolean(document.querySelector("[aria-label*='Stop'], [aria-label*='Останов'], [data-testid*='stop']"));
  }

  function sendTranscriptSnapshot(reason) {
    const identity = aiPageIdentity();
    if (!identity) {
      return;
    }
    const now = Date.now();
    if (now - transcriptLastRun < transcriptDebounceMs) {
      return;
    }
    transcriptLastRun = now;
    const messages = transcriptCandidates();
    messages.forEach((item, index) => {
      const text = item.text.slice(0, transcriptMaxChars);
      const message = {
        schema: "abyss_machine_browser_ai_transcript_message_v1",
        event_kind: "ai_transcript_message",
        browser_name: "firefox",
        url: String(location.href || ""),
        title: String(document.title || ""),
        text,
        text_length: item.text.length,
        text_truncated: item.text.length > transcriptMaxChars,
        frame_kind: frameKind(),
        browser: {
          transcript_safe: true,
          event_kind: "ai_transcript_message"
        },
        ai_transcript: {
          safe: true,
          message_role: item.role,
          message_index: index,
          message_order: index,
          partial: transcriptLooksPartial(item.element),
          reason: String(reason || "snapshot").slice(0, 80),
          selector_basis: "known_ai_chat_dom",
          ai_counterpart: identity
        },
        policy: {
          raw_keylogging: false,
          keydown_keyup_keypress_captured: false,
          password_fields_captured: false,
          form_values_captured: false,
          cookies_captured: false,
          local_storage_captured: false,
          transcript_visible_dom_only: true
        }
      };
      try {
        runtimeApi.runtime.sendMessage(message);
      } catch (_error) {
        return;
      }
    });
  }

  function scheduleTranscript(reason) {
    if (!aiPageIdentity()) {
      return;
    }
    if (transcriptTimer) {
      clearTimeout(transcriptTimer);
    }
    transcriptTimer = setTimeout(() => sendTranscriptSnapshot(reason), transcriptDebounceMs);
  }

  function schedule(target) {
    if (!target || target.nodeType !== Node.ELEMENT_NODE) {
      return;
    }
    const previous = timers.get(target);
    if (previous) {
      clearTimeout(previous);
    }
    timers.set(target, setTimeout(() => send(target, "input_idle"), debounceMs));
  }

  document.addEventListener("input", (event) => schedule(event.target), true);
  document.addEventListener("change", (event) => send(event.target, "change"), true);
  document.addEventListener("blur", (event) => send(event.target, "blur"), true);
  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (!form || !form.querySelectorAll) {
      return;
    }
    for (const element of form.querySelectorAll("textarea,input,[contenteditable='true']")) {
      send(element, "submit");
    }
  }, true);
  if (aiPageIdentity()) {
    scheduleTranscript("load");
    const observer = new MutationObserver(() => scheduleTranscript("mutation"));
    observer.observe(document.documentElement, { childList: true, subtree: true, characterData: true });
  }
})();
