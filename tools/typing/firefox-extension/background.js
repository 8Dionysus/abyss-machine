"use strict";

const nativeHost = "org.abyss_machine.typing_intake";
const runtimeApi = typeof browser !== "undefined" ? browser : chrome;

runtimeApi.runtime.onMessage.addListener((message) => {
  if (!message || ![
    "abyss_machine_browser_extension_message_v1",
    "abyss_machine_browser_ai_transcript_message_v1"
  ].includes(message.schema)) {
    return false;
  }
  try {
    const response = runtimeApi.runtime.sendNativeMessage(nativeHost, message);
    if (response && typeof response.then === "function") {
      response.catch(() => undefined);
    }
  } catch (_error) {
    return false;
  }
  return false;
});
