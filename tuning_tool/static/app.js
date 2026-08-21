const STATUS_BITS = [
  "fail", "communication", "current", "voltage", "temperature", "torque_limit",
  "locked_shaft", "regulator", "moving", "reverse", "target", "input_a", "input_b",
  "user1", "user2",
];

async function api(method, path, body) {
  const res = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail || res.statusText);
  }
  const contentType = res.headers.get("content-type") || "";
  return contentType.includes("application/json") ? res.json() : res.text();
}

function setConnectionStatus(connected, info) {
  const el = document.getElementById("connection-status");
  if (connected) {
    el.textContent = `Connected: ${info.model_name} (${info.serial_number}) @ addr ${info.address}`;
    el.className = "status-pill connected";
  } else {
    el.textContent = "Disconnected";
    el.className = "status-pill disconnected";
  }
}

async function refreshConnectionStatus() {
  const status = await api("GET", "/api/connect");
  setConnectionStatus(status.connected, status);
  return status.connected;
}

// -- Connect panel ----------------------------------------------------------

document.getElementById("scan-btn").addEventListener("click", async () => {
  const resultsEl = document.getElementById("scan-results");
  resultsEl.textContent = "Scanning...";
  try {
    const port = document.getElementById("port").value;
    const baudrate = parseInt(document.getElementById("baudrate").value, 10);
    const parity = document.getElementById("parity").value;
    const found = await api("POST", "/api/scan", { port, baudrate, parity });
    const select = document.getElementById("motor-select");
    select.innerHTML = "";
    if (found.length === 0) {
      resultsEl.textContent = "No motors found.";
    } else {
      resultsEl.textContent = `Found ${found.length} motor(s).`;
      for (const m of found) {
        const opt = document.createElement("option");
        opt.value = m.address;
        opt.textContent = `#${m.address} - ${m.model_name} (${m.serial_number})`;
        select.appendChild(opt);
      }
    }
  } catch (e) {
    resultsEl.textContent = `Scan failed: ${e.message}`;
  }
});

document.getElementById("connect-btn").addEventListener("click", async () => {
  const port = document.getElementById("port").value;
  const baudrate = parseInt(document.getElementById("baudrate").value, 10);
  const parity = document.getElementById("parity").value;
  const address = parseInt(document.getElementById("motor-select").value, 10);
  try {
    const info = await api("POST", "/api/connect", { port, baudrate, parity, address });
    setConnectionStatus(true, info);
    await refreshParams();
    await refreshProfiles();
    await refreshRecorderChannels();
  } catch (e) {
    alert(`Connect failed: ${e.message}`);
  }
});

document.getElementById("disconnect-btn").addEventListener("click", async () => {
  await api("POST", "/api/disconnect");
  setConnectionStatus(false);
});

// -- Live panel ---------------------------------------------------------------

const LIVE_FIELDS = [
  ["supply_voltage", "Supply (V)"],
  ["temp_electronics", "Temp electronics (C)"],
  ["temp_motor", "Temp motor (C)"],
  ["motor_speed_rpm", "Motor speed (rpm)"],
  ["motor_torque", "Motor torque (mNm)"],
  ["reg_error", "Reg error"],
  ["reg_output", "Reg output"],
  ["ramp_speed_rpm", "Ramp speed (rpm)"],
];

const liveChart = new Chart(document.getElementById("live-chart"), {
  type: "line",
  data: {
    labels: [],
    datasets: [
      { label: "MotorSpeed (rpm)", data: [], borderColor: "#2b6cb0", pointRadius: 0 },
      { label: "MotorTorque (mNm)", data: [], borderColor: "#c05621", pointRadius: 0 },
      { label: "RegError", data: [], borderColor: "#9b2c2c", pointRadius: 0 },
      { label: "RampSpeed (rpm)", data: [], borderColor: "#2f855a", pointRadius: 0 },
    ],
  },
  options: {
    animation: false,
    scales: { x: { display: false } },
  },
});

const LIVE_WINDOW = 150;

function renderLiveGrid(snapshot) {
  const grid = document.getElementById("live-grid");
  grid.innerHTML = "";
  for (const [key, label] of LIVE_FIELDS) {
    const div = document.createElement("div");
    div.className = "readout";
    const value = typeof snapshot[key] === "number" ? snapshot[key].toFixed(2) : snapshot[key];
    div.innerHTML = `<span class="label">${label}</span><span class="value">${value}</span>`;
    grid.appendChild(div);
  }
  const activeBits = STATUS_BITS.filter((b) => snapshot.status[b]);
  const statusDiv = document.createElement("div");
  statusDiv.className = "readout";
  statusDiv.innerHTML = `<span class="label">Status</span><span class="value">${activeBits.join(", ") || "-"}</span>`;
  grid.appendChild(statusDiv);
}

function pushLivePoint(snapshot) {
  const t = new Date().toLocaleTimeString();
  liveChart.data.labels.push(t);
  liveChart.data.datasets[0].data.push(snapshot.motor_speed_rpm);
  liveChart.data.datasets[1].data.push(snapshot.motor_torque);
  liveChart.data.datasets[2].data.push(snapshot.reg_error);
  liveChart.data.datasets[3].data.push(snapshot.ramp_speed_rpm);
  if (liveChart.data.labels.length > LIVE_WINDOW) {
    liveChart.data.labels.shift();
    for (const ds of liveChart.data.datasets) ds.data.shift();
  }
  liveChart.update("none");
}

function connectLiveSocket() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws/live`);
  ws.onmessage = (event) => {
    const snapshot = JSON.parse(event.data);
    renderLiveGrid(snapshot);
    pushLivePoint(snapshot);
  };
  ws.onclose = () => setTimeout(connectLiveSocket, 2000);
}
connectLiveSocket();

// -- Params panel ---------------------------------------------------------------

async function refreshParams() {
  const grid = document.getElementById("params-grid");
  grid.innerHTML = "";
  let params;
  try {
    params = await api("GET", "/api/params");
  } catch (e) {
    grid.textContent = e.message;
    return;
  }

  for (const [name, def] of Object.entries(params)) {
    const field = document.createElement("div");
    field.className = "field";
    field.dataset.name = name;

    if (name === "mode") {
      field.innerHTML = `<span class="label">mode</span>` +
        `<select>${def.options.map((o) => `<option value="${o}" ${o === def.value ? "selected" : ""}>${o}</option>`).join("")}</select>`;
    } else if (def.bits) {
      const checkboxes = STATUS_BITS
        .map((bit) => `<label style="flex-direction:row;gap:0.3rem;font-size:0.7rem"><input type="checkbox" data-bit="${bit}" ${def.bits[bit] ? "checked" : ""}> ${bit}</label>`)
        .join("");
      field.innerHTML = `<span class="label">${name}</span><span class="note">raw=${def.value}</span>${checkboxes}`;
    } else {
      const unit = def.unit ? ` ${def.unit}` : "";
      const range = def.min !== undefined ? ` (${def.min}-${def.max})` : "";
      field.innerHTML = `<span class="label">${name}${unit}</span>` +
        `<input type="number" step="any" value="${def.value}">` +
        `<span class="note">${def.note || ""}${range}</span>`;
    }
    grid.appendChild(field);
  }
}

function collectParamValues() {
  const values = {};
  for (const field of document.querySelectorAll("#params-grid .field")) {
    const name = field.dataset.name;
    const checkboxes = field.querySelectorAll("input[data-bit]");
    if (checkboxes.length) {
      let raw = 0;
      checkboxes.forEach((cb, i) => {
        if (cb.checked) raw |= (1 << STATUS_BITS.indexOf(cb.dataset.bit));
      });
      values[name] = raw;
    } else if (field.querySelector("select")) {
      values[name] = field.querySelector("select").value;
    } else {
      values[name] = parseFloat(field.querySelector("input").value);
    }
  }
  return values;
}

document.getElementById("refresh-params-btn").addEventListener("click", refreshParams);
document.getElementById("apply-params-btn").addEventListener("click", async () => {
  try {
    await api("POST", "/api/params", { values: collectParamValues() });
    await refreshParams();
  } catch (e) {
    alert(`Apply failed: ${e.message}`);
  }
});
document.getElementById("store-btn").addEventListener("click", () => api("POST", "/api/store"));
document.getElementById("reload-btn").addEventListener("click", async () => {
  await api("POST", "/api/reload");
  await refreshParams();
});

// -- Recorder panel ---------------------------------------------------------------

let lastRecording = null;
const recChart = new Chart(document.getElementById("rec-chart"), {
  type: "line",
  data: { labels: [], datasets: [] },
  options: { animation: false, parsing: false },
});
const fftChart = new Chart(document.getElementById("fft-chart"), {
  type: "line",
  data: { labels: [], datasets: [{ label: "Magnitude", data: [], borderColor: "#2b6cb0", pointRadius: 0 }] },
  options: { animation: false, scales: { x: { title: { display: true, text: "Hz" } } } },
});

async function refreshRecorderChannels() {
  const channels = await api("GET", "/api/recorder/channels");
  const container = document.getElementById("channel-selects");
  container.innerHTML = "";
  const defaults = [202, 203, 0, 0];
  for (let i = 0; i < 4; i++) {
    const label = document.createElement("label");
    label.innerHTML = `Ch${i + 1} <select data-ch="${i}">` +
      `<option value="">-- none --</option>` +
      channels.map((c) => `<option value="${c.register}" ${c.register === defaults[i] ? "selected" : ""}>${c.name}</option>`).join("") +
      `</select>`;
    container.appendChild(label);
  }
}

document.getElementById("rec-start-btn").addEventListener("click", async () => {
  const channels = Array.from(document.querySelectorAll("#channel-selects select"))
    .map((s) => parseInt(s.value, 10))
    .filter((v) => !Number.isNaN(v) && v !== 0);
  if (channels.length === 0) {
    alert("Select at least one channel");
    return;
  }
  const period = parseInt(document.getElementById("rec-period").value, 10);
  const preceding = parseInt(document.getElementById("rec-preceding").value, 10);
  const mode = document.getElementById("rec-mode").value;
  const statusEl = document.getElementById("rec-status");

  try {
    await api("POST", "/api/recorder/start", { channels, period, preceding, mode });
    statusEl.textContent = "Recording...";
    await waitUntilIdle();
    statusEl.textContent = "Done, reading...";
    await loadRecordingResults();
    statusEl.textContent = "Done.";
  } catch (e) {
    statusEl.textContent = `Failed: ${e.message}`;
  }
});

async function waitUntilIdle() {
  for (let i = 0; i < 100; i++) {
    const s = await api("GET", "/api/recorder/status");
    if (s.idle) return;
    await new Promise((r) => setTimeout(r, 150));
  }
  throw new Error("timed out waiting for recorder");
}

async function loadRecordingResults() {
  lastRecording = await api("GET", "/api/recorder/data");

  recChart.data.labels = lastRecording.time.map((t) => t.toFixed(3));
  recChart.data.datasets = lastRecording.channel_names.map((name, i) => ({
    label: name,
    data: lastRecording.samples[i],
    pointRadius: 0,
    borderColor: ["#2b6cb0", "#c05621", "#9b2c2c", "#2f855a"][i % 4],
  }));
  recChart.update();

  const fftSelect = document.getElementById("fft-channel");
  fftSelect.innerHTML = lastRecording.channel_names
    .map((name, i) => `<option value="${i}">${name}</option>`)
    .join("");
  await loadFft();

  const stats = await api("GET", "/api/recorder/stats");
  const tbody = document.querySelector("#stats-table tbody");
  tbody.innerHTML = stats
    .map(
      (s) =>
        `<tr><td>${s.channel}</td><td>${s.mean.toFixed(2)}</td><td>${s.min}</td><td>${s.max}</td>` +
        `<td>${s.stdev.toFixed(2)}</td><td>${s.ripple_percent.toFixed(1)}</td></tr>`
    )
    .join("");

  document.getElementById("csv-link").href = "/api/recorder/csv";
}

document.getElementById("fft-channel").addEventListener("change", loadFft);

async function loadFft() {
  if (!lastRecording) return;
  const channel = parseInt(document.getElementById("fft-channel").value || "0", 10);
  const fft = await api("GET", `/api/recorder/fft?channel=${channel}`);

  fftChart.data.labels = fft.frequencies_hz.map((f) => f.toFixed(1));
  fftChart.data.datasets[0].data = fft.magnitudes;
  fftChart.update();

  const peaksEl = document.getElementById("fft-peaks");
  const peakList = fft.top_peaks.map((p) => `${p.frequency_hz.toFixed(1)} Hz (mag ${p.magnitude.toFixed(2)})`).join(", ");
  peaksEl.innerHTML =
    `<strong>6x rotation frequency:</strong> ${fft.six_x_frequency_hz.toFixed(1)} Hz ` +
    `(rotation ${fft.rotation_frequency_hz.toFixed(2)} Hz)<br>` +
    `<strong>Top peaks:</strong> ${peakList || "-"}`;
}

// -- Profiles panel ---------------------------------------------------------------

async function refreshProfiles() {
  const names = await api("GET", "/api/profiles");
  const select = document.getElementById("profile-select");
  select.innerHTML = names.map((n) => `<option value="${n}">${n}</option>`).join("");
}

document.getElementById("profile-save-btn").addEventListener("click", async () => {
  const name = document.getElementById("profile-name").value.trim();
  if (!name) return;
  await api("POST", `/api/profiles/${encodeURIComponent(name)}`);
  await refreshProfiles();
});

document.getElementById("profile-load-btn").addEventListener("click", async () => {
  const name = document.getElementById("profile-select").value;
  if (!name) return;
  await api("GET", `/api/profiles/${encodeURIComponent(name)}`);
  await refreshParams();
});

document.getElementById("profile-delete-btn").addEventListener("click", async () => {
  const name = document.getElementById("profile-select").value;
  if (!name) return;
  await api("DELETE", `/api/profiles/${encodeURIComponent(name)}`);
  await refreshProfiles();
});

// -- Init ---------------------------------------------------------------

(async () => {
  const connected = await refreshConnectionStatus();
  if (connected) {
    await refreshParams();
    await refreshProfiles();
    await refreshRecorderChannels();
  }
})();
