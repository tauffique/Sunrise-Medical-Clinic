// Test call in the browser: a button that calls the clinic's phone flow over the internet.
(function () {
  if (!document.getElementById("chat-fab")) return; // home page only
  var isGerman = (document.documentElement.lang || "").toLowerCase().indexOf("de") === 0;
  var labels = {
    start: isGerman ? "📞 Testanruf" : "📞 Test call",
    hangup: isGerman ? "Auflegen" : "Hang up",
    failed: isGerman ? "Anruf fehlgeschlagen" : "Call failed"
  };
  var button = document.createElement("button");
  button.type = "button";
  button.className = "btn ghost small phone-test";
  button.textContent = labels.start;
  document.body.appendChild(button);

  var device = null;
  var call = null;

  function loadSdk() {
    if (window.Twilio && window.Twilio.Device) return Promise.resolve();
    return new Promise(function (resolve, reject) {
      var s = document.createElement("script");
      // Twilio Voice JavaScript SDK (UMD build). If this 404s, check the current path in Twilio's docs.
      s.src = "/static/twilio-voice.min.js";
      s.onload = resolve;
      s.onerror = function () { reject(new Error("sdk")); };
      document.head.appendChild(s);
    });
  }

  function fetchToken() {
    return fetch("/phone/token").then(function (res) {
      return res.json().then(function (data) {
        if (!res.ok) throw new Error(data.error || "token");
        return data.token;
      });
    });
  }

  function endCall() {
    if (call) call.disconnect();
  }

  button.addEventListener("click", function () {
    if (call) { endCall(); return; }
    loadSdk()
      .then(fetchToken)
      .then(function (token) {
        device = new window.Twilio.Device(token);
        return device.connect();
      })
      .then(function (newCall) {
        call = newCall;
        button.textContent = labels.hangup;
        call.on("disconnect", function () {
          call = null;
          button.textContent = labels.start;
          if (device) device.destroy();
        });
      })
      .catch(function () {
        call = null;
        button.textContent = labels.failed;
      });
  });
})();
