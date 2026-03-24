// ── State ────────────────────────────────────────────────────────────
let canvasMode = "view";       // view | pick | region | capture
let pickedCoords = [];
let selectionStart = null;
let selectionRect = null;
let isDragging = false;
let autoRefreshEnabled = true;
let refreshTimer = null;
let lastFrameTime = 0;
let frameCount = 0;
let currentImage = null;       // Image object for canvas
let imageScale = 1;            // Scale factor for coordinate mapping
let imageOffsetX = 0;
let imageOffsetY = 0;
let highlightRegions = [];

const canvas = document.getElementById("game-canvas");
const ctx = canvas.getContext("2d");

// ── Canvas ──────────────────────────────────────────────────────────

function getCanvasCoords(e) {
    const rect = canvas.getBoundingClientRect();
    const canvasX = e.clientX - rect.left;
    const canvasY = e.clientY - rect.top;
    // Map canvas coords to actual image coords
    const imgX = Math.round((canvasX - imageOffsetX) / imageScale);
    const imgY = Math.round((canvasY - imageOffsetY) / imageScale);
    return { x: imgX, y: imgY };
}

canvas.addEventListener("mousemove", (e) => {
    const pos = getCanvasCoords(e);
    document.getElementById("mouse-pos").textContent = `X: ${pos.x}, Y: ${pos.y}`;

    if (isDragging && (canvasMode === "region" || canvasMode === "capture")) {
        selectionRect = {
            x: Math.min(selectionStart.x, pos.x),
            y: Math.min(selectionStart.y, pos.y),
            w: Math.abs(pos.x - selectionStart.x),
            h: Math.abs(pos.y - selectionStart.y),
        };
        drawCanvas();
    }
});

canvas.addEventListener("mousedown", (e) => {
    const pos = getCanvasCoords(e);

    if (canvasMode === "pick") {
        pickedCoords.push({ x: pos.x, y: pos.y });
        updatePickedCoords();
        drawCanvas();
    } else if (canvasMode === "region" || canvasMode === "capture") {
        isDragging = true;
        selectionStart = pos;
        selectionRect = null;
    }
});

canvas.addEventListener("mouseup", (e) => {
    if (isDragging && selectionRect && selectionRect.w > 5 && selectionRect.h > 5) {
        document.getElementById("sel-x").value = selectionRect.x;
        document.getElementById("sel-y").value = selectionRect.y;
        document.getElementById("sel-w").value = selectionRect.w;
        document.getElementById("sel-h").value = selectionRect.h;
        document.getElementById("selection-result").classList.remove("hidden");

        if (canvasMode === "capture") {
            document.getElementById("capture-form").classList.remove("hidden");
        } else {
            document.getElementById("capture-form").classList.add("hidden");
        }
    }
    isDragging = false;
});

function drawCanvas() {
    if (!currentImage) return;

    // Calculate scale to fit canvas container
    const container = canvas.parentElement;
    const maxW = container.clientWidth;
    const maxH = container.clientHeight;
    imageScale = Math.min(maxW / currentImage.width, maxH / currentImage.height, 1);

    canvas.width = currentImage.width * imageScale;
    canvas.height = currentImage.height * imageScale;
    imageOffsetX = 0;
    imageOffsetY = 0;

    ctx.drawImage(currentImage, 0, 0, canvas.width, canvas.height);

    // Draw picked coordinates
    if (canvasMode === "pick") {
        ctx.fillStyle = "#e94560";
        pickedCoords.forEach((p) => {
            const sx = p.x * imageScale;
            const sy = p.y * imageScale;
            ctx.beginPath();
            ctx.arc(sx, sy, 5, 0, Math.PI * 2);
            ctx.fill();
            ctx.fillStyle = "#fff";
            ctx.font = "11px monospace";
            ctx.fillText(`(${p.x},${p.y})`, sx + 8, sy - 4);
            ctx.fillStyle = "#e94560";
        });
    }

    // Draw selection rectangle
    if (selectionRect) {
        ctx.strokeStyle = "#00ff88";
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 3]);
        ctx.strokeRect(
            selectionRect.x * imageScale,
            selectionRect.y * imageScale,
            selectionRect.w * imageScale,
            selectionRect.h * imageScale,
        );
        ctx.setLineDash([]);

        // Dimension label
        ctx.fillStyle = "#00ff88";
        ctx.font = "12px monospace";
        ctx.fillText(
            `${selectionRect.w}x${selectionRect.h}`,
            selectionRect.x * imageScale,
            (selectionRect.y - 4) * imageScale,
        );
    }

    // Draw highlight regions
    if (document.getElementById("show-regions").checked) {
        ctx.strokeStyle = "#ffd600";
        ctx.lineWidth = 2;
        highlightRegions.forEach((r) => {
            ctx.strokeRect(r.x * imageScale, r.y * imageScale, r.w * imageScale, r.h * imageScale);
            ctx.fillStyle = "#ffd600";
            ctx.font = "11px monospace";
            ctx.fillText(r.name || "", r.x * imageScale, (r.y - 3) * imageScale);
        });
    }
}

function setCanvasMode(mode) {
    canvasMode = mode;
    document.querySelectorAll(".tool-btn").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.mode === mode);
    });
    document.getElementById("canvas-mode-label").textContent = `Mode: ${mode.charAt(0).toUpperCase() + mode.slice(1)}`;

    // Show/hide panels
    document.getElementById("picked-coords").classList.toggle("hidden", mode !== "pick");
    if (mode !== "region" && mode !== "capture") {
        document.getElementById("selection-result").classList.add("hidden");
    }

    selectionRect = null;
    drawCanvas();
}

// ── Screenshot ──────────────────────────────────────────────────────

async function refreshScreenshot() {
    try {
        const params = new URLSearchParams();

        // Add match template if selected
        const tplSelect = document.getElementById("template-select");
        if (tplSelect.value) {
            params.set("match_template", tplSelect.value);
            params.set("threshold", document.getElementById("match-threshold").value);
        }

        const res = await fetch(`/api/screenshot?${params}`);
        if (!res.ok) throw new Error("Screenshot failed");

        const data = await res.json();
        const img = new Image();
        img.onload = () => {
            currentImage = img;
            drawCanvas();
            setConnected(true);

            // FPS counter
            frameCount++;
            const now = performance.now();
            if (now - lastFrameTime >= 1000) {
                document.getElementById("fps-counter").textContent = `${frameCount} FPS`;
                frameCount = 0;
                lastFrameTime = now;
            }
        };
        img.src = "data:image/jpeg;base64," + data.image;
    } catch (e) {
        setConnected(false);
    }
}

function startAutoRefresh() {
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = setInterval(() => {
        if (document.getElementById("auto-refresh").checked) {
            refreshScreenshot();
        }
    }, 1000);
}

document.getElementById("auto-refresh").addEventListener("change", (e) => {
    autoRefreshEnabled = e.target.checked;
});

// ── Connection Status ───────────────────────────────────────────────

function setConnected(ok) {
    const dot = document.getElementById("connection-status");
    const text = document.getElementById("status-text");
    dot.className = `status-dot ${ok ? "green" : "red"}`;
    text.textContent = ok ? "Connected" : "Disconnected";
}

// ── Picked Coordinates ─────────────────────────────────────────────

function updatePickedCoords() {
    const list = document.getElementById("coords-list");
    list.innerHTML = pickedCoords
        .map((p, i) => `<div class="match-item">#${i + 1}: (${p.x}, ${p.y})</div>`)
        .join("");
}

function clearCoords() {
    pickedCoords = [];
    updatePickedCoords();
    drawCanvas();
}

function copyCoords() {
    const text = pickedCoords.map((p) => `[${p.x}, ${p.y}]`).join(", ");
    navigator.clipboard.writeText(text);
}

// ── Template Matching ───────────────────────────────────────────────

async function loadTemplates() {
    const res = await fetch("/api/templates");
    const templates = await res.json();
    const select = document.getElementById("template-select");
    select.innerHTML = '<option value="">-- Select Template --</option>';
    templates.forEach((t) => {
        const opt = document.createElement("option");
        opt.value = t.path;
        opt.textContent = `[${t.category}] ${t.name} (${t.width}x${t.height})`;
        select.appendChild(opt);
    });
}

document.getElementById("match-threshold").addEventListener("input", (e) => {
    document.getElementById("threshold-value").textContent = parseFloat(e.target.value).toFixed(2);
});

async function testMatch() {
    const tplPath = document.getElementById("template-select").value;
    if (!tplPath) return alert("Please select a template first");

    const threshold = parseFloat(document.getElementById("match-threshold").value);
    const res = await fetch("/api/match_test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ template_path: tplPath, threshold }),
    });

    const data = await res.json();
    if (data.error) return alert(data.error);

    // Show annotated screenshot
    const img = new Image();
    img.onload = () => {
        currentImage = img;
        drawCanvas();
    };
    img.src = "data:image/jpeg;base64," + data.image;

    // Show results
    const resultsDiv = document.getElementById("match-results");
    if (data.matches.length === 0) {
        resultsDiv.innerHTML = "<div>No matches found</div>";
    } else {
        resultsDiv.innerHTML = data.matches
            .map(
                (m) =>
                    `<div class="match-item">Position: (${m.x}, ${m.y}) - Confidence: <span class="confidence">${m.confidence}</span></div>`,
            )
            .join("");
    }
}

// ── Capture Template ────────────────────────────────────────────────

async function captureTemplate() {
    const x = parseInt(document.getElementById("sel-x").value);
    const y = parseInt(document.getElementById("sel-y").value);
    const w = parseInt(document.getElementById("sel-w").value);
    const h = parseInt(document.getElementById("sel-h").value);
    const name = document.getElementById("tpl-name").value || `template_${Date.now()}`;
    const category = document.getElementById("tpl-category").value;

    const res = await fetch("/api/capture_template", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ x, y, w, h, name, category }),
    });

    const data = await res.json();
    if (data.error) return alert(data.error);

    alert(`Template saved: ${data.path} (${data.width}x${data.height})`);
    loadTemplates();
}

// ── Tasks ───────────────────────────────────────────────────────────

async function loadTasks() {
    try {
        const res = await fetch("/api/tasks");
        if (!res.ok) return;
        const tasks = await res.json();
        if (tasks.error) return;

        const container = document.getElementById("task-list");
        container.innerHTML = tasks
            .map(
                (t) => `
            <div class="task-card">
                <div class="task-card-header">
                    <span class="task-name">${t.name}</span>
                    <label class="toggle">
                        <input type="checkbox" ${t.enabled ? "checked" : ""}
                               onchange="updateTask('${t.name}', {enabled: this.checked})">
                        <span class="slider"></span>
                    </label>
                </div>
                <div class="task-controls">
                    <label>Cooldown:
                        <input type="number" value="${t.cooldown}" min="1"
                               onchange="updateTask('${t.name}', {cooldown: parseFloat(this.value)})">s
                    </label>
                </div>
                <div class="task-stats">
                    Runs: ${t.run_count} | Fails: ${t.fail_count} |
                    Last: ${t.last_run >= 0 ? Math.round(t.last_run) + "s ago" : "never"}
                </div>
            </div>
        `,
            )
            .join("");
    } catch (e) {}
}

async function updateTask(name, data) {
    await fetch(`/api/tasks/${name}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });
}

// ── Game State ──────────────────────────────────────────────────────

async function loadGameState() {
    try {
        const res = await fetch("/api/state");
        if (!res.ok) return;
        const state = await res.json();
        if (state.error) return;

        const container = document.getElementById("game-state");
        const rows = [
            ["Resources Collected", state.resources_collected],
            ["Teams Joined", state.teams_joined],
            ["Timers Checked", state.timers_checked],
            ["Daily Completed", state.daily_tasks_completed ? "Yes" : "No"],
            ["Errors", state.errors],
        ];
        if (state.last_error) {
            rows.push(["Last Error", state.last_error]);
        }

        container.innerHTML = rows
            .map(
                ([k, v]) =>
                    `<div class="state-row"><span>${k}</span><span class="state-value">${v}</span></div>`,
            )
            .join("");
    } catch (e) {}
}

// ── Coordinates ─────────────────────────────────────────────────────

let coordsData = {};

async function loadCoordinates() {
    try {
        const res = await fetch("/api/coordinates");
        coordsData = await res.json();
        renderTimerRegions();
    } catch (e) {}
}

function renderTimerRegions() {
    const container = document.getElementById("timer-regions");
    const timers = coordsData.timers || {};
    highlightRegions = [];

    container.innerHTML = Object.entries(timers)
        .map(([name, cfg]) => {
            const r = cfg.region || [0, 0, 100, 30];
            highlightRegions.push({ name, x: r[0], y: r[1], w: r[2], h: r[3] });
            return `
            <div class="region-item">
                <div class="region-name">${name}</div>
                <div class="region-coords">
                    <label>X<input type="number" value="${r[0]}" data-timer="${name}" data-idx="0" onchange="updateRegion(this)"></label>
                    <label>Y<input type="number" value="${r[1]}" data-timer="${name}" data-idx="1" onchange="updateRegion(this)"></label>
                    <label>W<input type="number" value="${r[2]}" data-timer="${name}" data-idx="2" onchange="updateRegion(this)"></label>
                    <label>H<input type="number" value="${r[3]}" data-timer="${name}" data-idx="3" onchange="updateRegion(this)"></label>
                </div>
            </div>
        `;
        })
        .join("");
}

function updateRegion(input) {
    const name = input.dataset.timer;
    const idx = parseInt(input.dataset.idx);
    if (coordsData.timers && coordsData.timers[name]) {
        coordsData.timers[name].region[idx] = parseInt(input.value);

        // Update highlight
        const r = coordsData.timers[name].region;
        const region = highlightRegions.find((hr) => hr.name === name);
        if (region) {
            region.x = r[0]; region.y = r[1]; region.w = r[2]; region.h = r[3];
        }
        drawCanvas();
    }
}

async function saveCoordinates() {
    const res = await fetch("/api/coordinates", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(coordsData),
    });
    const data = await res.json();
    if (data.ok) alert("Coordinates saved!");
    else alert("Error: " + (data.error || "Unknown"));
}

function toggleRegionOverlay() {
    drawCanvas();
}

// ── Init ────────────────────────────────────────────────────────────

async function init() {
    await loadTemplates();
    await loadCoordinates();
    refreshScreenshot();
    startAutoRefresh();

    // Periodic data refresh
    setInterval(() => {
        loadTasks();
        loadGameState();
    }, 3000);
}

init();
