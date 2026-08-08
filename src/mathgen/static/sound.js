/* Environment sound: white/pink/brown noise + imported music (WebAudio + HTMLAudio). */
(function () {
  var ctx = null;
  var noiseSource = null, noiseGain = null;
  var musicAudio = null;
  var musicLoaded = false, musicPaused = false;
  var playlist = [];
  var playlistIndex = -1;
  var serverMode = false; // 登录用户：歌单存储于服务器（/api/audio/*）
  var musicVolume = 0.5;
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

  // 播放歌单第 i 首：越界环绕，自动切歌，上一首停止时清空 Audio 资源
  function playIndex(i) {
    if (!playlist.length) return;
    if (i < 0) i = playlist.length - 1;
    if (i >= playlist.length) i = 0;
    if (musicAudio) {
      try { musicAudio.pause(); } catch (e) {}
      musicAudio.src = '';
    }
    var a = new Audio(playlist[i].url);
    a.volume = musicVolume;
    a.onended = function () {
      if (!musicPaused) {
        window.Sound.next();
        try { document.dispatchEvent(new CustomEvent('soundtrack')); } catch (e) {}
      }
    };
    a.play().catch(function () {});
    musicAudio = a;
    playlistIndex = i;
    musicLoaded = true;
    musicPaused = false;
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
    addTracks: function (fileList) {
      if (!fileList || !fileList.length) return 0;
      var added = 0;
      for (var i = 0; i < fileList.length; i++) {
        try {
          var f = fileList[i];
          if (!f) continue;
          var url = URL.createObjectURL(f);
          playlist.push({ url: url, name: f.name || ('song ' + (playlist.length + 1)) });
          added++;
        } catch (e) { /* 忽略单个文件导入失败 */ }
      }
      if (!musicAudio && playlist.length > 0) playIndex(0);
      return added;
    },
    addTrack: function (entry) {
      // 追加一条已构建好的歌单条目（服务器模式上传成功后使用），无播放时立即播放
      try {
        playlist.push({ url: entry.url, name: entry.name || ('song ' + (playlist.length + 1)), id: entry.id });
      } catch (e) { return -1; }
      if (!musicAudio) playIndex(playlist.length - 1);
      return playlist.length - 1;
    },
    next: function () { playIndex(playlistIndex + 1); },
    prev: function () { playIndex(playlistIndex - 1); },
    playCurrent: function () { if (!playlist.length) return; playIndex(playlistIndex >= 0 ? playlistIndex : 0); },
    hasCurrent: function () { return musicAudio !== null; },
    removeAt: function (i) {
      if (i < 0 || i >= playlist.length) return;
      var removed = playlist[i];
      var wasCurrent = (i === playlistIndex);
      var wasPlaying = wasCurrent && musicAudio && !musicPaused;
      if (wasCurrent && musicAudio) {
        try { musicAudio.pause(); } catch (e) {}
        musicAudio.src = '';
      }
      playlist.splice(i, 1);
      if (i < playlistIndex) {
        playlistIndex--;
      } else if (wasCurrent) {
        playlistIndex = Math.min(i, playlist.length - 1);
      }
      if (playlist.length === 0) {
        musicAudio = null;
        playlistIndex = -1;
        musicLoaded = false;
        musicPaused = false;
      } else if (wasCurrent && !wasPlaying) {
        musicAudio = null;
      } else if (wasCurrent && wasPlaying) {
        playIndex(playlistIndex);
      }
      // 服务器条目：静默删除服务器文件
      if (removed && removed.id) {
        try { fetch('/api/audio/' + removed.id + '/delete', { method: 'POST' }); } catch (e) {}
      }
    },
    getPlaylist: function () {
      return playlist.map(function (t, i) {
        return { name: t.name, playing: (i === playlistIndex && !!musicAudio && !musicPaused) };
      });
    },
    loadMusic: function (url, name) {
      try {
        playlist.push({ url: url, name: name || url });
      } catch (e) { return; }
      playIndex(playlist.length - 1);
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
      musicPaused = false;
      // 保留 playlist 与 musicLoaded（歌单仍在，仅停止当前曲目）
    },
    setMusicVolume: function (vol) {
      musicVolume = vol;
      if (musicAudio) musicAudio.volume = vol;
    },
    isMusicLoaded: function () { return playlist.length > 0; },
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
    var musicPrev = document.getElementById('musicPrev');
    var musicNext = document.getElementById('musicNext');
    var musicList = document.getElementById('musicList');
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
    function renderPlaylist() {
      if (!musicList) return;
      musicList.innerHTML = '';
      var items = window.Sound.getPlaylist();
      if (!items.length) {
        var hint = document.createElement('li');
        hint.className = 'hint';
        hint.textContent = musicList.getAttribute('data-empty') || '';
        musicList.appendChild(hint);
        return;
      }
      for (var i = 0; i < items.length; i++) {
        var li = document.createElement('li');
        var prefix = items[i].playing ? (musicList.getAttribute('data-now') || '▶ ') + ' ' : '· ';
        if (items[i].playing) li.className = 'music-current';
        var span = document.createElement('span');
        span.textContent = prefix + items[i].name;
        li.appendChild(span);
        var rm = document.createElement('button');
        rm.type = 'button';
        rm.className = 'music-remove';
        rm.setAttribute('data-i', i);
        rm.textContent = musicList.getAttribute('data-remove') || '×';
        li.appendChild(rm);
        musicList.appendChild(li);
      }
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
      document.addEventListener('soundtrack', function () { renderPlaylist(); syncMusicLabel(); });
      musicPlay.addEventListener('click', function () {
        if (!window.Sound.isMusicLoaded()) return;
        if (window.Sound.isMusicLoaded() && !window.Sound.hasCurrent()) {
          window.Sound.playCurrent();
          syncMusicLabel();
          return;
        }
        if (window.Sound.isMusicPaused()) window.Sound.resumeMusic();
        else window.Sound.pauseMusic();
        syncMusicLabel();
      });
    }
    if (musicPrev) {
      musicPrev.addEventListener('click', function () {
        window.Sound.prev();
        renderPlaylist();
        syncMusicLabel();
      });
    }
    if (musicNext) {
      musicNext.addEventListener('click', function () {
        window.Sound.next();
        renderPlaylist();
        syncMusicLabel();
      });
    }
    if (musicList) {
      musicList.addEventListener('click', function (e) {
        var t = e.target;
        if (!t || !t.dataset) return;
        var i = t.dataset.i;
        if (i === undefined) return;
        window.Sound.removeAt(parseInt(i, 10));
        renderPlaylist();
        syncMusicLabel();
      });
    }
    if (file) {
      file.addEventListener('change', function () {
        if (file.files && file.files.length) {
          if (serverMode) {
            // 服务器模式：逐首上传，成功后追加进歌单
            Array.prototype.forEach.call(file.files, function (f) {
              var fd = new FormData();
              fd.append('file', f);
              fetch('/api/audio/upload', { method: 'POST', body: fd })
                .then(function (r) { return r.ok ? r.json() : null; })
                .then(function (data) {
                  if (data && data.id) {
                    window.Sound.addTrack({ id: data.id, name: data.name, url: '/api/audio/' + data.id });
                    renderPlaylist();
                    syncMusicLabel();
                  }
                })
                .catch(function () {});
            });
          } else {
            window.Sound.addTracks(file.files);
            renderPlaylist();
            syncMusicLabel();
          }
        }
      });
    }
    // 登录用户：加载服务器端歌单（只填充列表，不自动播放）
    if (document.body && document.body.getAttribute('data-logged-in') === '1') {
      fetch('/api/audio/list')
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (items) {
          if (Array.isArray(items)) {
            serverMode = true;
            items.forEach(function (it) {
              playlist.push({ id: it.id, name: it.name, url: '/api/audio/' + it.id });
            });
            renderPlaylist();
            syncMusicLabel();
          }
        })
        .catch(function () {});
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindControls);
  } else {
    bindControls();
  }
})();
