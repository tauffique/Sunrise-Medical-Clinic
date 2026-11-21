(() => {
  "use strict";

  const I18N = JSON.parse(document.getElementById("i18n").textContent);
  const LANG = document.documentElement.lang || "en";
  const LOCALE = LANG === "de" ? "de-DE" : "en-GB";
  const CSRF = document.querySelector('meta[name="csrf-token"]').content;
  const SID_KEY = "clinic-chat-sid";
  const $ = (sel) => document.querySelector(sel);
  const pad = (n) => String(n).padStart(2, "0");
  const iso = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

  function t(key, vars = {}) {
    let text = I18N[key] || key;
    for (const [name, value] of Object.entries(vars)) {
      text = text.split(`{${name}}`).join(String(value));
    }
    return text;
  }

  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  async function request(url, options = {}) {
    try {
      const res = await fetch(url, {
        ...options,
        headers: { "Content-Type": "application/json", "X-CSRF-Token": CSRF, ...(options.headers || {}) },
      });
      let data = {};
      try {
        data = await res.json();
      } catch (_) {
        data = {};
      }
      return { ok: res.ok, status: res.status, data };
    } catch (_) {
      return { ok: false, status: 0, data: { error: t("network_error") } };
    }
  }

  // ---------- Live updates: one Server-Sent Events connection instead of polling ----------
  const listeners = new Set();
  const refreshAll = () => listeners.forEach((fn) => fn());

  // Registers a widget to reload when the server reports a change. Drops it once it leaves the page.
  function keepLive(root, reload, isActive = () => true) {
    const handler = () => {
      if (!root.isConnected) {
        listeners.delete(handler);
        return;
      }
      if (isActive()) reload();
    };
    listeners.add(handler);
  }

  if (window.EventSource) {
    const stream = new EventSource("/api/stream");
    stream.addEventListener("change", refreshAll);
    stream.addEventListener("ready", refreshAll); // after a reconnect, refresh everything once
  } else {
    setInterval(refreshAll, 15000); // very old browsers: fall back to polling
  }

  // ---------- Calendar: days with free slots are clickable, others are greyed out ----------
  function createCalendar(root, { getDoctor, onPick, isActive = () => true }) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const firstMonth = new Date(today.getFullYear(), today.getMonth(), 1);
    let view = new Date(firstMonth);
    let days = {};
    let selected = "";
    let updated = "";

    function render() {
      root.textContent = "";
      const head = el("div", "cal-head");
      const prev = el("button", "cal-nav", "‹");
      prev.type = "button";
      prev.disabled = view <= firstMonth;
      prev.addEventListener("click", () => {
        view = new Date(view.getFullYear(), view.getMonth() - 1, 1);
        load();
      });
      const next = el("button", "cal-nav", "›");
      next.type = "button";
      next.addEventListener("click", () => {
        view = new Date(view.getFullYear(), view.getMonth() + 1, 1);
        load();
      });
      const title = new Intl.DateTimeFormat(LOCALE, { month: "long", year: "numeric" }).format(view);
      head.append(prev, el("span", "cal-title", title), next);
      root.append(head);

      const grid = el("div", "cal-grid");
      for (let i = 0; i < 7; i++) {
        // 1 Jan 2024 was a Monday, so these are Monday to Sunday in the page language.
        grid.append(el("div", "cal-wd", new Intl.DateTimeFormat(LOCALE, { weekday: "short" }).format(new Date(2024, 0, 1 + i))));
      }
      const offset = (view.getDay() + 6) % 7;
      for (let i = 0; i < offset; i++) grid.append(el("div"));

      const count = new Date(view.getFullYear(), view.getMonth() + 1, 0).getDate();
      for (let d = 1; d <= count; d++) {
        const key = iso(new Date(view.getFullYear(), view.getMonth(), d));
        const cell = el("button", "cal-day", String(d));
        cell.type = "button";
        if (key === iso(today)) cell.classList.add("today");
        if (key === selected) cell.classList.add("selected");
        const free = days[key];
        if (free === undefined) {
          cell.classList.add("off");
          cell.disabled = true;
          cell.title = t("not_available");
        } else if (free === 0) {
          cell.classList.add("full");
          cell.disabled = true;
          cell.title = t("fully_booked");
        } else {
          cell.title = t("free_slots", { n: free });
          cell.addEventListener("click", () => {
            selected = key;
            render();
            onPick(key);
          });
        }
        grid.append(cell);
      }
      root.append(grid);
      if (updated) root.append(el("p", "live", t("live_updated", { time: updated })));
    }

    async function load() {
      const doctor = getDoctor();
      if (!doctor) {
        root.textContent = t("choose_doctor_first");
        return;
      }
      const month = `${view.getFullYear()}-${pad(view.getMonth() + 1)}`;
      const { ok, data } = await request(`/api/availability?doctor_id=${encodeURIComponent(doctor)}&month=${month}`);
      if (!ok) {
        root.textContent = data.error || t("calendar_error");
        return;
      }
      days = data.days;
      updated = data.updated_at;
      render();
    }

    load();
    keepLive(root, load, isActive);
    return {
      reload: load,
      reset() {
        selected = "";
        return load();
      },
    };
  }

  // ---------- Time slots for one day ----------
  function createSlots(root, { getDoctor, getDate, getSelectedTime = () => "", onPick, isActive = () => true }) {
    async function load() {
      const doctor = getDoctor();
      const date = getDate();
      if (!doctor || !date) {
        root.textContent = t("pick_date_slots");
        return;
      }
      const { ok, data } = await request(
        `/api/slots?doctor_id=${encodeURIComponent(doctor)}&date=${encodeURIComponent(date)}`,
      );
      root.textContent = "";
      if (!ok) {
        root.textContent = data.error || t("generic_error");
        return;
      }
      if (!data.slots.length) {
        root.textContent = t("no_free_day");
        return;
      }
      const chosen = getSelectedTime();
      for (const time of data.slots) {
        const button = el("button", "slot", time);
        button.type = "button";
        if (time === chosen) button.classList.add("selected");
        button.addEventListener("click", () => onPick(time));
        root.append(button);
      }
      root.append(el("p", "live", t("live_updated", { time: data.updated_at })));
    }

    load();
    keepLive(root, load, isActive);
    return { reload: load };
  }

  // ---------- Booking dialog on the website ----------
  const dialog = $("#book-dialog");
  const doctorSel = $("#doctor-select");
  const form = $("#book-form");
  const msg = $("#book-msg");
  const submitBtn = $("#submit-book");
  const selection = $("#selection");
  const dateField = form.elements.date;
  const timeField = form.elements.time;

  function updateSelection() {
    const hasDate = Boolean(dateField.value);
    const hasTime = Boolean(timeField.value);
    submitBtn.disabled = !(hasDate && hasTime);
    if (hasDate && hasTime) selection.textContent = t("selected_fmt", { date: dateField.value, time: timeField.value });
    else if (hasDate) selection.textContent = t("date_only_fmt", { date: dateField.value });
    else selection.textContent = t("selected_none");
  }

  const siteCalendar = createCalendar($("#calendar"), {
    getDoctor: () => doctorSel.value,
    isActive: () => dialog.open,
    onPick: (day) => {
      dateField.value = day;
      timeField.value = "";
      updateSelection();
      siteSlots.reload();
    },
  });

  const siteSlots = createSlots($("#slots"), {
    getDoctor: () => doctorSel.value,
    getDate: () => dateField.value,
    getSelectedTime: () => timeField.value,
    isActive: () => dialog.open,
    onPick: (time) => {
      timeField.value = time;
      updateSelection();
      siteSlots.reload();
    },
  });

  function resetSelection() {
    dateField.value = "";
    timeField.value = "";
    updateSelection();
    siteCalendar.reset();
    siteSlots.reload();
  }

  function openBook(doctorId) {
    if (doctorId) doctorSel.value = doctorId;
    msg.textContent = "";
    if (!dialog.open) dialog.showModal();
    resetSelection();
  }

  $("#open-book").addEventListener("click", () => openBook());
  $("#nav-book").addEventListener("click", () => openBook());
  document.querySelectorAll("[data-book]").forEach((button) => {
    button.addEventListener("click", () => openBook(button.dataset.book));
  });
  $("#close-book").addEventListener("click", () => dialog.close());
  $("#cancel-book").addEventListener("click", () => dialog.close());
  doctorSel.addEventListener("change", () => {
    msg.textContent = "";
    resetSelection();
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fields = form.elements;
    msg.textContent = "";
    if (!fields.consent.checked) {
      msg.textContent = t("err_consent");
      return;
    }
    if (fields.name.value.trim().length < 2) {
      msg.textContent = t("err_name");
      return;
    }
    if (!fields.contact.value.trim()) {
      msg.textContent = t("err_contact");
      return;
    }

    submitBtn.disabled = true;
    msg.textContent = t("sending");
    const body = {
      doctor_id: doctorSel.value,
      date: dateField.value,
      time: timeField.value,
      name: fields.name.value.trim(),
      contact: fields.contact.value.trim(),
      reason: fields.reason.value.trim(),
      consent: true,
      intake: {
        conditions: fields.conditions.value.trim(),
        medications: fields.medications.value.trim(),
        allergies: fields.allergies.value.trim(),
        insurance: fields.insurance.value.trim(),
      },
    };
    const { ok, data } = await request("/api/appointments", { method: "POST", body: JSON.stringify(body) });

    if (ok) {
      msg.textContent = data.message;
      setTimeout(() => {
        if (dialog.open) dialog.close();
      }, 2500);
      form.reset();
      dateField.value = "";
      timeField.value = "";
    } else {
      msg.textContent = data.error || t("generic_error");
      if (data.key === "err_slot_taken" || data.key === "err_slot_unavailable") timeField.value = "";
    }
    updateSelection();
    siteCalendar.reload();
    siteSlots.reload();
  });

  // ---------- Chatbot ----------
  const chat = $("#chat");
  const log = $("#chat-log");
  const chatForm = $("#chat-form");
  const input = $("#chat-input");

  function newSessionId() {
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  }
  function storedSessionId() {
    try {
      return localStorage.getItem(SID_KEY);
    } catch (_) {
      return null;
    }
  }
  function saveSessionId(id) {
    try {
      localStorage.setItem(SID_KEY, id);
    } catch (_) {
      // Private mode: the conversation still works, it just will not survive a restart.
    }
  }

  let sessionId = storedSessionId() || newSessionId();
  saveSessionId(sessionId);
  let opened = false;

  function scrollLog() {
    log.scrollTop = log.scrollHeight;
  }

  function addMsg(text, who) {
    const node = el("div", `msg ${who}`, text);
    log.append(node);
    scrollLog();
    return node;
  }

  function addChip(label, onClick) {
    const button = el("button", "chip", label);
    button.type = "button";
    button.addEventListener("click", () => {
      button.disabled = true;
      onClick();
    });
    log.append(button);
    scrollLog();
  }

  // Calendar or time-slot picker inside the chat. Picking a value sends it as the next chat message.
  function addWidget(ui) {
    if (!ui || !ui.doctor_id) return;
    const box = el("div", "widget");
    log.append(box);
    scrollLog();
    let done = false;
    const isActive = () => !done;
    const pick = (value) => {
      done = true;
      box.querySelectorAll("button").forEach((b) => {
        b.disabled = true;
      });
      send(value);
    };
    if (ui.type === "calendar") {
      createCalendar(box, { getDoctor: () => ui.doctor_id, onPick: pick, isActive });
    } else if (ui.type === "slots") {
      createSlots(box, { getDoctor: () => ui.doctor_id, getDate: () => ui.date, onPick: pick, isActive });
    }
  }

  async function send(text) {
    addMsg(text, "user");
    const pending = addMsg("…", "bot");
    const { ok, data } = await request("/api/chat", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, message: text, lang: LANG }),
    });
    pending.textContent = ok ? data.reply : data.error || t("generic_error");
    if (ok && data.suggested_doctor && !data.booking) {
      addChip(t("book_with", { name: data.suggested_doctor.name }), () => send(LANG === "de" ? "ja" : "yes"));
    }
    if (ok) addWidget(data.ui);
  }

  // Restores the saved conversation after a page reload or a server restart.
  async function restoreHistory() {
    const { ok, data } = await request(`/api/chat/history?session_id=${encodeURIComponent(sessionId)}`);
    if (!ok || !data.messages || !data.messages.length) return false;
    for (const message of data.messages) {
      addMsg(message.text, message.role === "user" ? "user" : "bot");
    }
    return true;
  }

  function timeGreeting() {
    const hour = new Date().getHours();
    const part = hour < 12 ? "bot_greet_morning" : hour < 18 ? "bot_greet_afternoon" : "bot_greet_evening";
    return t(part) + " " + t("chat_greeting");
  }

  async function openChat() {
    chat.classList.remove("hidden");
    if (!opened) {
      opened = true;
      const restored = await restoreHistory();
      if (!restored) addMsg(timeGreeting(), "bot");
    }
    input.focus();
  }

  $("#open-chat").addEventListener("click", openChat);
  $("#chat-fab").addEventListener("click", openChat);
  $("#close-chat").addEventListener("click", () => chat.classList.add("hidden"));
  $("#chat-reset").addEventListener("click", () => {
    sessionId = newSessionId();
    saveSessionId(sessionId);
    log.textContent = "";
    addMsg(timeGreeting(), "bot");
  });

  chatForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    send(text);
  });
})();