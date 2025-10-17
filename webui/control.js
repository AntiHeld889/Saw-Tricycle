(() => {
  'use strict';

  const state = {
    audioDevice: null,
    audioVolume: null,
    soundboardPort: null,
    cameraTarget: null
  };

  const audioSelect = document.getElementById('audioDevice');
  const batteryIndicator = document.getElementById('batteryIndicator');
  const batteryFill = document.getElementById('batteryFill');
  const batteryLabel = document.getElementById('batteryLabel');
  const soundboardButton = document.getElementById('soundboardButton');
  const cameraButton = document.getElementById('cameraButton');

  const BATTERY_CLASSES = ['charging', 'low', 'medium', 'error', 'unavailable'];
  const BATTERY_MAX_WIDTH = 32;

  let audioOptionsSignature = '';
  let pollTimer = null;

  if (audioSelect) {
    audioSelect.disabled = true;
  }

  const parseSoundboardPort = (value) => {
    if (typeof value === 'number') {
      return Number.isInteger(value) && value >= 1 && value <= 65535 ? value : null;
    }
    if (typeof value === 'string') {
      const trimmed = value.trim();
      if (!trimmed) {
        return null;
      }
      const parsed = Number.parseInt(trimmed, 10);
      if (Number.isInteger(parsed) && parsed >= 1 && parsed <= 65535) {
        return parsed;
      }
    }
    return null;
  };

  const normalizeHostname = (value) => {
    if (typeof value !== 'string') {
      return null;
    }
    const trimmed = value.trim();
    if (!trimmed) {
      return null;
    }
    try {
      const url = new URL(trimmed.startsWith('http') ? trimmed : `http://${trimmed}`);
      return url.hostname;
    } catch (err) {
      return null;
    }
  };

  const parseCameraTarget = (value) => {
    if (!value || typeof value !== 'object') {
      return null;
    }
    const { host, port, path } = value;
    const hostname = normalizeHostname(host);
    const portNumber = typeof port === 'number' ? port : Number.parseInt(String(port ?? ''), 10);
    const safePort = Number.isInteger(portNumber) && portNumber >= 1 && portNumber <= 65535 ? portNumber : null;
    const rawPath = typeof path === 'string' ? path.trim() : '';
    const safePath = rawPath ? (rawPath.startsWith('/') ? rawPath : `/${rawPath}`) : '';
    if (!hostname || !safePort) {
      return null;
    }
    const raw = `${hostname}:${safePort}${safePath}`;
    return { host: hostname, port: safePort, path: safePath, raw };
  };

  const buildSoundboardUrl = (port) => `http://localhost:${port}`;

  const buildCameraUrl = (target) => {
    if (!target) {
      return '#';
    }
    const protocol = window.location.protocol === 'https:' ? 'https' : 'http';
    const host = target.host || window.location.hostname;
    const base = `${protocol}://${host}:${target.port}`;
    return target.path ? `${base}${target.path}` : base;
  };

  const updateSoundboardButton = (port) => {
    if (!soundboardButton) {
      return;
    }
    if (!port) {
      soundboardButton.hidden = true;
      soundboardButton.dataset.url = '';
      soundboardButton.removeAttribute('data-port');
      return;
    }
    const url = buildSoundboardUrl(port);
    soundboardButton.hidden = false;
    soundboardButton.dataset.url = url;
    soundboardButton.dataset.port = String(port);
    soundboardButton.href = url;
    soundboardButton.setAttribute('aria-label', `Soundboard öffnen (Port ${port})`);
  };

  const updateCameraButton = (target) => {
    if (!cameraButton) {
      return;
    }
    if (!target) {
      cameraButton.hidden = true;
      cameraButton.dataset.url = '';
      cameraButton.removeAttribute('data-port');
      cameraButton.removeAttribute('data-path');
      cameraButton.removeAttribute('data-raw');
      cameraButton.href = '#';
      cameraButton.setAttribute('aria-label', 'Kamera nicht verfügbar');
      return;
    }
    const url = buildCameraUrl(target);
    cameraButton.hidden = false;
    cameraButton.dataset.url = url;
    cameraButton.dataset.port = String(target.port);
    if (target.path) {
      cameraButton.dataset.path = target.path;
    } else {
      cameraButton.removeAttribute('data-path');
    }
    cameraButton.dataset.raw = target.raw;
    cameraButton.href = url;
    cameraButton.setAttribute('aria-label', `Kamera öffnen (${target.raw})`);
  };

  if (soundboardButton) {
    updateSoundboardButton(null);
    soundboardButton.addEventListener('click', (event) => {
      const url = soundboardButton.dataset.url;
      if (!url) {
        event.preventDefault();
        return;
      }
      event.preventDefault();
      window.open(url, '_blank', 'noopener');
    });
  }

  if (cameraButton) {
    updateCameraButton(null);
    cameraButton.addEventListener('click', (event) => {
      const url = cameraButton.dataset.url;
      if (!url) {
        event.preventDefault();
        return;
      }
      event.preventDefault();
      window.open(url, '_blank', 'noopener');
    });
  }

  const updateBattery = (info) => {
    if (!batteryIndicator || !batteryFill || !batteryLabel) {
      return;
    }
    batteryIndicator.classList.remove(...BATTERY_CLASSES);
    if (!info || typeof info !== 'object') {
      batteryLabel.textContent = '--%';
      batteryFill.setAttribute('width', '0');
      batteryIndicator.classList.add('unavailable');
      batteryIndicator.title = 'Akkustand nicht verfügbar';
      return;
    }
    const percentRaw = Number(info.percent);
    const percent = Number.isFinite(percentRaw) ? Math.max(0, Math.min(100, percentRaw)) : null;
    const voltageRaw = Number(info.voltage);
    const voltage = Number.isFinite(voltageRaw) ? voltageRaw : null;
    const currentRaw = Number(info.current);
    const current = Number.isFinite(currentRaw) ? currentRaw : null;
    const powerRaw = Number(info.power);
    const power = Number.isFinite(powerRaw) ? powerRaw : null;
    const status = typeof info.status === 'string' ? info.status : 'unknown';

    if (percent === null) {
      batteryLabel.textContent = '--%';
      batteryFill.setAttribute('width', '0');
    } else {
      batteryLabel.textContent = `${Math.round(percent)}%`;
      const width = (BATTERY_MAX_WIDTH * percent) / 100;
      batteryFill.setAttribute('width', width > 0 ? width.toFixed(1) : '0');
    }

    let indicatorClass = null;
    if (status === 'error') {
      indicatorClass = 'error';
    } else if (status === 'charging') {
      indicatorClass = 'charging';
    } else if (status === 'initializing') {
      indicatorClass = 'unavailable';
    } else if (percent === null) {
      indicatorClass = 'unavailable';
    } else if (percent <= 20) {
      indicatorClass = 'low';
    } else if (percent <= 50) {
      indicatorClass = 'medium';
    }
    if (indicatorClass) {
      batteryIndicator.classList.add(indicatorClass);
    }

    const parts = [];
    if (percent === null) {
      parts.push('Akkustand unbekannt');
    } else {
      parts.push(`Akkustand: ${Math.round(percent)}%`);
    }
    if (Number.isFinite(voltage)) {
      parts.push(`Spannung: ${voltage.toFixed(2)} V`);
    }
    if (Number.isFinite(current)) {
      parts.push(`Strom: ${current.toFixed(1)} A`);
    }
    if (Number.isFinite(power)) {
      parts.push(`Leistung: ${power.toFixed(0)} W`);
    }
    batteryIndicator.title = parts.join(' · ') || 'Akkustand unbekannt';
  };

  const syncAudioSelection = (options, selectedId) => {
    if (!audioSelect) {
      return;
    }
    const normalized = options
      .map((option) => {
        if (!option || typeof option !== 'object') {
          return null;
        }
        const id = typeof option.id === 'string' ? option.id : String(option.id ?? '');
        const label = typeof option.label === 'string' ? option.label.trim() : '';
        if (!id) {
          return null;
        }
        return { id, label: label || id };
      })
      .filter(Boolean);

    const signature = JSON.stringify(normalized);
    if (signature !== audioOptionsSignature) {
      audioOptionsSignature = signature;
      audioSelect.innerHTML = '';
      normalized.forEach((option) => {
        const opt = document.createElement('option');
        opt.value = option.id;
        opt.textContent = option.label;
        audioSelect.append(opt);
      });
    }

    const targetValue = typeof selectedId === 'string' ? selectedId : selectedId == null ? '' : String(selectedId);
    if (audioSelect.value !== targetValue) {
      audioSelect.value = targetValue;
    }
    audioSelect.disabled = normalized.length === 0;
    state.audioDevice = targetValue || null;
  };

  async function sendState(overrides = {}) {
    const payload = {};
    const audioDevice = overrides.audioDevice ?? state.audioDevice;
    if (typeof audioDevice === 'string' && audioDevice.length > 0) {
      payload.audio_device = audioDevice;
      state.audioDevice = audioDevice;
    }
    const audioVolume = overrides.audioVolume ?? state.audioVolume;
    if (Number.isFinite(audioVolume)) {
      const normalized = Math.max(0, Math.min(100, audioVolume));
      payload.audio_volume = Math.round(normalized);
      state.audioVolume = normalized;
    }
    try {
      await fetch('/api/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    } catch (err) {
      console.error('Senden fehlgeschlagen', err);
    }
  }

  if (audioSelect) {
    audioSelect.addEventListener('change', () => {
      const value = audioSelect.value;
      state.audioDevice = value || null;
      if (state.audioDevice) {
        sendState({ audioDevice: state.audioDevice });
      }
    });
  }

  async function pollState() {
    try {
      const resp = await fetch('/api/state');
      if (!resp.ok) {
        return;
      }
      const data = await resp.json();
      const remoteAudioDevice = typeof data.audio_device === 'string' ? data.audio_device : null;
      const remoteAudioOutputs = Array.isArray(data.audio_outputs) ? data.audio_outputs : [];
      syncAudioSelection(remoteAudioOutputs, remoteAudioDevice);
      if (data.audio_volume && Number.isFinite(data.audio_volume.value)) {
        state.audioVolume = data.audio_volume.value;
      } else {
        state.audioVolume = null;
      }
      updateBattery(data.battery ?? null);
      const soundInfo = data.sound && typeof data.sound === 'object' ? data.sound : null;
      const portValue = soundInfo ? parseSoundboardPort(soundInfo.soundboard_port) : null;
      const cameraValue = soundInfo ? parseCameraTarget(soundInfo.camera_port) : null;
      state.soundboardPort = portValue;
      state.cameraTarget = cameraValue;
      updateSoundboardButton(portValue);
      updateCameraButton(cameraValue);
    } catch (err) {
      console.error('Poll fehlgeschlagen', err);
    }
  }

  const startPolling = (immediate = false) => {
    if (immediate) {
      pollState();
    }
    if (pollTimer != null) {
      return;
    }
    pollTimer = window.setInterval(pollState, 1500);
  };

  const stopPolling = () => {
    if (pollTimer == null) {
      return;
    }
    window.clearInterval(pollTimer);
    pollTimer = null;
  };

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      stopPolling();
    } else {
      startPolling(true);
    }
  });

  updateBattery(null);
  updateSoundboardButton(null);
  updateCameraButton(null);
  startPolling(true);
})();
