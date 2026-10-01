// player.js — a video element + a compact control row (play/pause, time, speed, mute).
// Timelines (filmstrip/waveform/markers) are built separately by the view that owns them.

import { fmtTime } from './util.js';

const FRAME = 1 / 24;

/**
 * createPlayer(container, {src, aspect='9/16', onTime, onPlayState})
 * -> {video, el, play, pause, toggle, seek, time, duration, setSrc, setRate, step, playRanges, destroy}
 */
export function createPlayer(container, opts = {}) {
  const { src = '', aspect = '9/16', onTime, onPlayState } = opts;

  const video = document.createElement('video');
  video.className = 'player-video';
  video.playsInline = true;
  video.preload = 'metadata';
  if (src) video.src = src;

  const frame = document.createElement('div');
  frame.className = `player-frame aspect-${aspect === '16/9' ? '16x9' : '9x16'}`;
  frame.appendChild(video);

  const playBtn = document.createElement('button');
  playBtn.type = 'button';
  playBtn.className = 'btn-icon player-play';
  playBtn.setAttribute('aria-label', 'Play / pause');
  playBtn.textContent = '▶';

  const timeEl = document.createElement('span');
  timeEl.className = 'player-time';
  timeEl.textContent = '0:00.0 / 0:00.0';

  const rateSel = document.createElement('select');
  rateSel.className = 'player-rate';
  rateSel.setAttribute('aria-label', 'Playback speed');
  [1, 1.5, 2].forEach((r) => {
    const opt = document.createElement('option');
    opt.value = String(r);
    opt.textContent = `${r}×`;
    rateSel.appendChild(opt);
  });

  const muteBtn = document.createElement('button');
  muteBtn.type = 'button';
  muteBtn.className = 'btn-icon player-mute';
  muteBtn.setAttribute('aria-label', 'Mute / unmute');
  muteBtn.textContent = '🔊';

  const controls = document.createElement('div');
  controls.className = 'player-controls';
  controls.append(playBtn, timeEl, rateSel, muteBtn);

  const el = document.createElement('div');
  el.className = 'player';
  el.append(frame, controls);
  container.appendChild(el);

  let rangeQueue = null;
  let rangeRaf = null;
  let internalSeek = false;

  function updateTimeLabel() {
    timeEl.textContent = `${fmtTime(video.currentTime)} / ${fmtTime(video.duration || 0)}`;
  }

  function cancelRanges() {
    if (rangeRaf) {
      cancelAnimationFrame(rangeRaf);
      rangeRaf = null;
    }
    rangeQueue = null;
  }

  video.addEventListener('timeupdate', () => {
    updateTimeLabel();
    if (onTime) onTime(video.currentTime);
  });
  video.addEventListener('play', () => {
    playBtn.textContent = '⏸';
    if (onPlayState) onPlayState(true);
  });
  video.addEventListener('pause', () => {
    playBtn.textContent = '▶';
    if (onPlayState) onPlayState(false);
  });
  video.addEventListener('loadedmetadata', updateTimeLabel);
  video.addEventListener('seeking', () => {
    if (rangeQueue && !internalSeek) cancelRanges();
    internalSeek = false;
  });

  playBtn.addEventListener('click', () => toggle());
  rateSel.addEventListener('change', () => {
    video.playbackRate = parseFloat(rateSel.value);
  });
  muteBtn.addEventListener('click', () => {
    video.muted = !video.muted;
    muteBtn.textContent = video.muted ? '🔇' : '🔊';
  });

  function play() {
    return video.play().catch(() => {});
  }
  function pause() {
    cancelRanges();
    video.pause();
  }
  function toggle() {
    if (video.paused) play();
    else pause();
  }
  function seek(t) {
    cancelRanges();
    video.currentTime = Math.max(0, t);
  }
  function time() {
    return video.currentTime;
  }
  function duration() {
    return video.duration || 0;
  }
  function setSrc(newSrc, keepTime = false) {
    const t = video.currentTime;
    const wasPaused = video.paused;
    cancelRanges();
    video.src = newSrc || '';
    video.load();
    if (keepTime) {
      const onLoaded = () => {
        internalSeek = true;
        video.currentTime = t;
        if (!wasPaused) play();
        video.removeEventListener('loadedmetadata', onLoaded);
      };
      video.addEventListener('loadedmetadata', onLoaded);
    }
  }
  function setRate(r) {
    video.playbackRate = r;
    rateSel.value = String(r);
  }
  function step(frames) {
    cancelRanges();
    video.pause();
    internalSeek = true;
    video.currentTime = Math.max(0, video.currentTime + frames * FRAME);
  }
  function playRanges(ranges) {
    if (!ranges || !ranges.length) return;
    cancelRanges();
    rangeQueue = ranges.slice();
    let idx = 0;
    internalSeek = true;
    video.currentTime = rangeQueue[0][0];
    play();
    function tick() {
      if (rangeQueue == null) return;
      const [, b] = rangeQueue[idx];
      if (video.currentTime >= b - 0.02) {
        idx += 1;
        if (idx >= rangeQueue.length) {
          cancelRanges();
          video.pause();
          return;
        }
        internalSeek = true;
        video.currentTime = rangeQueue[idx][0];
      }
      rangeRaf = requestAnimationFrame(tick);
    }
    rangeRaf = requestAnimationFrame(tick);
  }
  function destroy() {
    cancelRanges();
    video.pause();
    video.removeAttribute('src');
    video.load();
    el.remove();
  }

  return { video, el, play, pause, toggle, seek, time, duration, setSrc, setRate, step, playRanges, destroy };
}
