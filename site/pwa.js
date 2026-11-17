/* Android install affordance; optional enhancement to existing Football AI Lab. */
const installButton = document.getElementById("pwaInstallButton");
const helpBox = document.getElementById("pwaInstallHelp");
const helpText = document.getElementById("pwaInstallHelpText");
const helpClose = document.getElementById("pwaHelpClose");
const connectionBanner = document.getElementById("pwaOfflineBanner");
let installEvent = null;

function standalone() {
  return window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true;
}
function refreshInstallButton() {
  if (!installButton) return;
  installButton.hidden = standalone() || !("serviceWorker" in navigator);
}
function updateConnectionBanner() {
  if (connectionBanner) connectionBanner.hidden = navigator.onLine !== false;
}
function showInstructions() {
  if (!helpBox || !helpText) return;
  const isIOS = /iPad|iPhone|iPod/i.test(navigator.userAgent);
  helpText.textContent = isIOS
    ? "En Safari pulsa Compartir y elige «Añadir a pantalla de inicio»."
    : "En Chrome para Android abre el menú ⋮ y elige «Instalar aplicación» o «Añadir a pantalla de inicio».";
  helpBox.hidden = false;
  helpClose?.focus();
}

window.addEventListener("beforeinstallprompt", event => {
  // Browsers may choose not to fire this; the menu remains a valid fallback.
  event.preventDefault();
  installEvent = event;
  refreshInstallButton();
});
window.addEventListener("appinstalled", () => {
  installEvent = null;
  if (helpBox) helpBox.hidden = true;
  refreshInstallButton();
});
window.matchMedia("(display-mode: standalone)")
  .addEventListener?.("change", refreshInstallButton);

installButton?.addEventListener("click", async () => {
  if (!installEvent) {
    showInstructions();
    return;
  }
  const pending = installEvent;
  installEvent = null;
  try {
    await pending.prompt();
    await pending.userChoice;
  } catch {
    showInstructions();
  }
  refreshInstallButton();
});
helpClose?.addEventListener("click", () => {
  helpBox.hidden = true;
  installButton?.focus();
});
document.addEventListener("keydown", event => {
  if (event.key === "Escape" && helpBox && !helpBox.hidden) {
    helpBox.hidden = true;
    installButton?.focus();
  }
});
window.addEventListener("offline", updateConnectionBanner);
window.addEventListener("online", () => {
  updateConnectionBanner();
  // A previous offline screen must not remain stale after reconnecting.
  document.getElementById("refreshButton")?.click();
});

refreshInstallButton();
updateConnectionBanner();
if ("serviceWorker" in navigator && window.isSecureContext) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("./sw.js", {
      scope: "./", updateViaCache: "none"
    }).catch(() => {
      // On restrictive/private browsers the site still works normally online.
    });
  });
}
