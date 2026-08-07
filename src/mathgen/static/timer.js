(function () {
  var timerId = null, endTime = 0, remainingMs = 0, onTick = null, onEnd = null;
  window.Timer = {
    init: function (tick, end) { onTick = tick; onEnd = end; },
    start: function (sec) {
      if (timerId) return;
      remainingMs = sec * 1000;
      endTime = performance.now() + remainingMs;
      timerId = setInterval(tick, 200);
    },
    pause: function () {
      if (!timerId) return;
      clearInterval(timerId); timerId = null;
      remainingMs = Math.max(0, endTime - performance.now());
    },
    reset: function () {
      clearInterval(timerId); timerId = null; remainingMs = 0; endTime = 0;
      if (onTick) onTick(0);
    }
  };
  function tick() {
    var left = Math.max(0, endTime - performance.now());
    if (onTick) onTick(Math.ceil(left / 1000));
    if (left <= 0) { clearInterval(timerId); timerId = null; if (onEnd) onEnd(); }
  }
})();
