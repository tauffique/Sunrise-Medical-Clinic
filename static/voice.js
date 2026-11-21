// Voice input for the chat (Chrome/Edge): speak your message and it is sent.
(function () {
  var form = document.getElementById("chat-form");
  var input = document.getElementById("chat-input");
  if (!form || !input) return;

  var Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Recognition) return;

  var isGerman = (document.documentElement.lang || "").toLowerCase().indexOf("de") === 0;
  var locale = isGerman ? "de-DE" : "en-US";
  var listening = false;

  var mic = document.createElement("button");
  mic.type = "button";
  mic.className = "voice-btn";
  mic.textContent = "🎤";
  mic.title = isGerman ? "Per Sprache eingeben" : "Speak your message";
  mic.setAttribute("aria-label", mic.title);
  mic.setAttribute("aria-pressed", "false");

  var rec = new Recognition();
  rec.continuous = false;
  rec.interimResults = true;
  rec.lang = locale;

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

  form.insertBefore(mic, input.nextSibling);
})();
