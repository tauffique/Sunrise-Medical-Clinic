(() => {
  "use strict";
  if (!window.EventSource) return;

  const KEY = "clinic-seen-requests";
  const seen = loadSeen();
  let latestIds = [];
  let banner = null;
  let timer = null;

  function loadSeen() {
    try {
      return new Set(JSON.parse(sessionStorage.getItem(KEY) || "[]"));
    } catch (_) {
      return new Set();
    }
  }

  function saveSeen() {
    try {
      sessionStorage.setItem(KEY, JSON.stringify([...seen]));
    } catch (_) {
      // Private mode: the banner may come back after a reload, which is harmless.
    }
  }

  function unseenIds() {
    return latestIds.filter((id) => !seen.has(id));
  }

  function showBanner(count) {
    if (!banner) {
      banner = document.createElement("div");
      banner.className = "alert";
      banner.setAttribute("role", "alert");
      document.body.prepend(banner);
    }
    banner.textContent = "";
    const text = document.createElement("span");
    text.textContent = `${count} new appointment request${count === 1 ? "" : "s"} waiting for review.`;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "btn small";
    button.textContent = "Got it";
    button.addEventListener("click", () => {
      latestIds.forEach((id) => seen.add(id));
      saveSeen();
      window.location.reload();
    });
    banner.append(text, " ", button);
  }

  async function fetchRequests() {
    try {
      const res = await fetch("/staff/requests", { credentials: "same-origin" });
      if (!res.ok) return false;
      const data = await res.json();
      latestIds = data.ids;
      return true;
    } catch (_) {
      return false;
    }
  }

  // reloadIfQuiet: after a change with nothing new to show, refresh the list so it stays current.
  async function check(reloadIfQuiet) {
    if (!(await fetchRequests())) return;
    const unseen = unseenIds();
    if (unseen.length) {
      showBanner(unseen.length);
    } else if (reloadIfQuiet) {
      window.location.reload();
    }
  }

  const stream = new EventSource("/api/stream");
  stream.addEventListener("change", () => {
    clearTimeout(timer);
    timer = setTimeout(() => check(true), 400);
  });

  check(false);
})();
