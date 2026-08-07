(function () {
  var timerId = null, endTime = 0, remainingMs = 0, elapsedMs = 0, startTime = 0;
  var countingUp = false, onTick = null, onEnd = null;
  window.Timer = {
    init: function (tick, end) { onTick = tick; onEnd = end; },
    start: function (sec) {
      // 重开语义：计时中再次 start（专注/休息切换、改时长后重开）以新时长重启
      clearInterval(timerId);
      countingUp = false;
      remainingMs = sec * 1000;
      endTime = performance.now() + remainingMs;
      timerId = setInterval(tick, 200);
    },
    startUp: function () {
      // 正计时（秒表）：一直累计，直到 reset/pause
      clearInterval(timerId);
      countingUp = true;
      elapsedMs = 0;
      startTime = performance.now();
      if (onTick) onTick(0);
      timerId = setInterval(tick, 200);
    },
    pause: function () {
      if (!timerId) return;
      clearInterval(timerId); timerId = null;
      if (countingUp) elapsedMs = performance.now() - startTime;
      else remainingMs = Math.max(0, endTime - performance.now());
    },
    resume: function () {
      if (timerId) return;
      if (countingUp) {
        startTime = performance.now() - elapsedMs;
        timerId = setInterval(tick, 200);
      } else if (remainingMs > 0) {
        endTime = performance.now() + remainingMs;
        timerId = setInterval(tick, 200);
      }
    },
    reset: function () {
      clearInterval(timerId); timerId = null;
      remainingMs = 0; endTime = 0; elapsedMs = 0; countingUp = false;
      if (onTick) onTick(0);
    },
    isRunning: function () { return timerId !== null; },
    fmt: function (sec) {
      // 负值/小数安全：钳 0、四舍五入，避免 % 对负数产生垃圾显示
      sec = Math.max(0, Math.round(sec));
      var m = Math.floor(sec / 60), s = sec % 60;
      return (m < 10 ? '0' + m : m) + ':' + (s < 10 ? '0' + s : s);
    },
    parseMinutesSeconds: function (minVal, secVal) {
      // 共享解析：分钟可小数，秒钳 [0,59]，负值归 0（两计时页共用，避免分叉）
      var m = parseFloat(minVal) || 0;
      var s = parseFloat(secVal) || 0;
      return Math.max(0, Math.round(Math.max(0, m) * 60 + Math.max(0, Math.min(59, s))));
    }
  };
  function tick() {
    if (countingUp) {
      if (onTick) onTick(Math.ceil((performance.now() - startTime) / 1000));
      return;
    }
    var left = Math.max(0, endTime - performance.now());
    if (onTick) onTick(Math.ceil(left / 1000));
    if (left <= 0) { clearInterval(timerId); timerId = null; remainingMs = 0; if (onEnd) onEnd(); }
  }
})();
