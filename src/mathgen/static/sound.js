/* Environment sound: white/pink/brown noise + imported music (WebAudio + HTMLAudio). */
(function () {
  var ctx = null;
  var noiseSource = null, noiseGain = null;
  var musicAudio = null;
  var musicLoaded = false, musicPaused = false;
  var noiseBuffer = { white: null, pink: null, brown: null };

  function ensureCtx() {
    var AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    if (!ctx) ctx = new AC();
    if (ctx.state === 'suspended') ctx.resume();
    return ctx;
  }

  function makeNoiseBuffer(type) {
    var c = ensureCtx();
    if (!c) return null;
    if (noiseBuffer[type]) return noiseBuffer[type];
    var len = c.sampleRate * 2;
    var buf = c.createBuffer(1, len, c.sampleRate);
    var data = buf.getChannelData(0);
    var amp = 0.22; // 统一压幅，避免削波刺耳
    if (type === 'white') {
      for (var i = 0; i < len; i++) data[i] = (Math.random() * 2 - 1) * amp;
    } else if (type === 'pink') {
      var b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0;
      for (var i = 0; i < len; i++) {
        var w = Math.random() * 2 - 1;
        b0 = 0.99886 * b0 + w * 0.0555179;
        b1 = 0.99332 * b1 + w * 0.0750759;
        b2 = 0.96900 * b2 + w * 0.1538520;
        b3 = 0.86650 * b3 + w * 0.3104856;
        b4 = 0.55000 * b4 + w * 0.5329522;
        b5 = -0.7616 * b5 - w * 0.0168980;
        data[i] = (b0 + b1 + b2 + b3 + b4 + b5 + b6 + w * 0.5362) * 0.11 * amp;
        b6 = w * 0.115926;
      }
    } else { /* brown */
      var last = 0;
      for (var i = 0; i < len; i++) {
        var w = Math.random() * 2 - 1;
        last = (last + 0.02 * w) / 1.02;
        data[i] = last * amp;
      }
    }
    noiseBuffer[type] = buf;
    return buf;
  }

  window.Sound = {
    startNoise: function (type, vol) {
      var c = ensureCtx();
      if (!c) return false;
      this.stopNoise();
      var buf = makeNoiseBuffer(type);
      if (!buf) return false;
      var src = c.createBufferSource();
      src.buffer = buf;
      src.loop = true;
      var gain = c.createGain();
      gain.gain.value = (typeof vol === 'number') ? vol : 0.3;
      src.connect(gain).connect(c.destination);
      src.start();
      noiseSource = src;
      noiseGain = gain;
      return true;
    },
    stopNoise: function () {
      try { if (noiseSource) noiseSource.stop(); } catch (e) {}
      noiseSource = null;
      noiseGain = null;
    },
    setNoiseVolume: function (vol) {
      if (noiseGain) noiseGain.gain.value = vol;
    },
    loadMusic: function (url) {
      this.stopMusic();
      var a = new Audio(url);
      a.loop = true;
      a.volume = 0.5;
      a.play().catch(function () {});
      musicAudio = a;
      musicLoaded = true;
      musicPaused = false;
    },
    pauseMusic: function () {
      if (musicAudio) {
        musicAudio.pause();
        musicPaused = true;
      }
    },
    resumeMusic: function () {
      if (musicAudio && musicPaused) {
        musicAudio.play().catch(function () {});
        musicPaused = false;
      }
    },
    stopMusic: function () {
      if (musicAudio) {
        musicAudio.pause();
        musicAudio.src = '';
      }
      musicAudio = null;
      musicLoaded = false;
      musicPaused = false;
    },
    setMusicVolume: function (vol) {
      if (musicAudio) musicAudio.volume = vol;
    },
    isMusicLoaded: function () { return musicLoaded; },
    isMusicPaused: function () { return musicPaused; },
    isNoiseOn: function () { return noiseSource !== null; },
    stopAll: function () { this.stopNoise(); this.stopMusic(); }
  };

  function bindControls() {
    var play = document.getElementById('noisePlay');
    var sel = document.getElementById('noiseType');
    var noiseVol = document.getElementById('noiseVol');
    var musicVol = document.getElementById('musicVol');
    var file = document.getElementById('musicFile');
    var musicPlay = document.getElementById('musicPlay');
    var noiseOn = false;
    function syncPlayLabel() {
      if (!play) return;
      play.setAttribute('data-i18n', noiseOn ? 'sound.stop' : 'sound.play');
      play.textContent = noiseOn ? play.getAttribute('data-stop-label') || '停止' : play.getAttribute('data-play-label') || '播放';
    }
    function syncMusicLabel() {
      if (!musicPlay) return;
      var paused = !musicLoaded || window.Sound.isMusicPaused();
      musicPlay.setAttribute('data-i18n', paused ? 'sound.play' : 'sound.pause');
      musicPlay.textContent = paused ? (musicPlay.getAttribute('data-play-label') || '播放')
                                      : (musicPlay.getAttribute('data-pause-label') || '暂停');
    }
    if (play && sel) {
      play.addEventListener('click', function () {
        if (noiseOn) {
          window.Sound.stopNoise();
          noiseOn = false;
        } else {
          if (window.Sound.startNoise(sel.value, parseFloat(noiseVol && noiseVol.value) || 0.3)) {
            noiseOn = true;
          }
        }
        syncPlayLabel();
      });
      // 播放中切换噪音类型 → 立即重启
      sel.addEventListener('change', function () {
        if (noiseOn) {
          window.Sound.startNoise(sel.value, parseFloat(noiseVol && noiseVol.value) || 0.3);
        }
      });
    }
    if (noiseVol) {
      noiseVol.addEventListener('input', function () { window.Sound.setNoiseVolume(parseFloat(noiseVol.value) || 0); });
    }
    if (musicVol) {
      musicVol.addEventListener('input', function () { window.Sound.setMusicVolume(parseFloat(musicVol.value) || 0); });
    }
    if (musicPlay) {
      musicPlay.addEventListener('click', function () {
        if (!musicLoaded) return;
        if (window.Sound.isMusicPaused()) window.Sound.resumeMusic();
        else window.Sound.pauseMusic();
        syncMusicLabel();
      });
    }
    if (file) {
      file.addEventListener('change', function () {
        if (file.files && file.files[0]) {
          window.Sound.loadMusic(URL.createObjectURL(file.files[0]));
          syncMusicLabel();
        }
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindControls);
  } else {
    bindControls();
  }
})();
