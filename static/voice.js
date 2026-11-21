// Voice for the chat: speak your message (Chrome/Edge) and read replies aloud.
(function () {
  var form = document.getElementById("chat-form");
  var input = document.getElementById("chat-input");
  if (!form || !input) return;

  var isGerman = (document.documentElement.lang || "").toLowerCase().indexOf("de") === 0;
  var locale = isGerman ? "de-DE" : "en-US";
  var PREF_KEY = "clinic-voice-replies";
  var Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  var canSpeak = "speechSynthesis" in window;

  function readPref() {
    try { return localStorage.getItem(PREF_KEY) === "on"; } catch (e) { return false; }
  }
  function savePref(on) {
    try { localStorage.setItem(PREF_KEY, on ? "on" : "off"); } catch (e) { /* storage blocked */ }
  }
  var speakReplies = readPref();

  function speak(text) {
    if (!speakReplies || !canSpeak || !text) return;
    window.speechSynthesis.cancel();
    var utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = locale;
    window.speechSynthesis.speak(utterance);
  }

  // Read each new chatbot reply aloud, without changing the chat code.
  var originalFetch = window.fetch.bind(window);
  window.fetch = function (url, options) {
    var promise = originalFetch(url, options);
    var path = String(url);
    if (path.indexOf("/api/chat") === 0 && path.indexOf("history") === -1) {
      promise.then(function (res) {
        if (!res.ok) return;
        return res.clone().json().then(function (data) { speak(data.reply); });
      }).catch(function () { /* ignore: the chat shows its own errors */ });
    }
    return promise;
  };

  function makeButton(label, title) {
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "voice-btn";
    btn.textContent = label;
    btn.title = title;
    btn.setAttribute("aria-label", title);
    return btn;
  }

  var toggle = makeButton("🔊", isGerman ? "Antworten vorlesen" : "Read replies aloud");
  toggle.setAttribute("aria-pressed", String(speakReplies));
  toggle.addEventListener("click", function () {
    speakReplies = !speakReplies;
    savePref(speakReplies);
    toggle.setAttribute("aria-pressed", String(speakReplies));
    if (!speakReplies && canSpeak) window.speechSynthesis.cancel();
  });
  form.insertBefore(toggle, input.nextSibling);

  if (!Recognition) return;

  var mic = makeButton("🎤", isGerman ? "Per Sprache eingeben" : "Speak your message");
  var rec = new Recognition();
  rec.continuous = false;
  rec.interimResults = true;
  rec.lang = locale;
  var listening = false;

  function setListening(on) {
    listening = on;
    mic.classList.toggle("listening", on);
    mic.setAttribute("aria-pressed", String(on));
  }

  rec.onresult = function (event) {
    var text = "";
    var isFinal = false;
    for (var i = event.resultIndex; i < event.results.length; i++) {
      text += event.results[i][0].transcript;
      if (event.results[i].isFinal) isFinal = true;
    }
    input.value = text.trim();
    if (isFinal && input.value) form.requestSubmit();
  };
  rec.onend = function () { setListening(false); };
  rec.onerror = function (event) {
    setListening(false);
    input.placeholder = event.error === "not-allowed"
      ? (isGerman ? "Mikrofon ist blockiert." : "Microphone is blocked.")
      : (isGerman ? "Spracheingabe fehlgeschlagen." : "Voice input failed. Try again.");
  };

  mic.addEventListener("click", function () {
    if (listening) { rec.stop(); return; }
    input.value = "";
    try {
      rec.start();
      setListening(true);
    } catch (e) { /* already started */ }
  });
  form.insertBefore(mic, toggle);
})();
