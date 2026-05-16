/**
 * Mirror critical sessionStorage keys to localStorage so opening a new tab
 * (or restoring after browser restart) doesn't kick the user back to the
 * /config or /login screen.
 *
 * Keep the rest of the codebase using sessionStorage as the working store —
 * this module only rehydrates from localStorage on boot and intercepts the
 * three mutating methods to forward persistent keys to localStorage.
 */

const PERSIST_KEYS = new Set([
  "Token",
  "baseUrl",
  "retail_code",
  "state_code",
  "state_name",
  "user",
  "erpSetupComplete",
  "default_country_code",
]);

// Rehydrate sessionStorage from localStorage on every page load (new tabs included).
try {
  PERSIST_KEYS.forEach((k) => {
    const sv = sessionStorage.getItem(k);
    const lv = localStorage.getItem(k);
    if (!sv && lv != null) sessionStorage.setItem(k, lv);
  });
} catch (_) {
  /* ignore — storage may be disabled (private mode, etc.) */
}

// Wrap mutators so writes to persistent keys also land in localStorage.
try {
  const proto = Object.getPrototypeOf(sessionStorage);
  const origSet    = proto.setItem.bind(sessionStorage);
  const origRemove = proto.removeItem.bind(sessionStorage);
  const origClear  = proto.clear.bind(sessionStorage);

  sessionStorage.setItem = function (key, value) {
    origSet(key, value);
    if (PERSIST_KEYS.has(key)) {
      try { localStorage.setItem(key, value); } catch (_) {}
    }
  };
  sessionStorage.removeItem = function (key) {
    origRemove(key);
    if (PERSIST_KEYS.has(key)) {
      try { localStorage.removeItem(key); } catch (_) {}
    }
  };
  sessionStorage.clear = function () {
    origClear();
    try {
      PERSIST_KEYS.forEach((k) => localStorage.removeItem(k));
    } catch (_) {}
  };
} catch (_) {
  /* ignore */
}
