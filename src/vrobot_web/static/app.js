(() => {
  "use strict";

  const STATUS_META = {
    idle: { label: "空闲", color: "#8a94a6" },
    moving: { label: "行驶", color: "#3fa9f5" },
    e_stop: { label: "急停", color: "#ff5d5d" },
    arrived: { label: "到达", color: "#43c463" },
    waiting_right: { label: "等待路权", color: "#f5a623" },
    holding_zone: { label: "持有区", color: "#a66bff" },
  };

  const MODE_LABELS = {
    unconfigured: "未配置",
    configured: "已配置",
    running: "运行中",
    paused: "已暂停",
  };

  const ZONE_COLORS = ["#5b8cff", "#ff9f43", "#2fbf71", "#c85cff", "#38d0d8"];
  const RECONNECT_DELAY_MS = 1000;
  const MAX_ROBOTS = 10;
  const TRAIL_LENGTH = 80;
  const MOTION_KEY = "vrobot.motion";

  const FONT_SANS = "'Segoe UI', 'Microsoft YaHei', 'PingFang SC', sans-serif";
  const FONT_MONO = "'Cascadia Mono', 'Consolas', 'SFMono-Regular', monospace";

  const COLORS = {
    floor: "#0b0e13",
    gridMinor: "rgba(148, 163, 184, 0.05)",
    gridMajor: "rgba(148, 163, 184, 0.085)",
    aisleBorder: "#1b2330",
    aisle: "#121821",
    aisleDash: "rgba(148, 163, 184, 0.13)",
    arrow: "rgba(154, 172, 200, 0.62)",
    nodeFill: "#1a222d",
    nodeStroke: "#46536a",
    nodeDot: "#7f8ca3",
    nodeText: "#98a4b8",
    plate: "rgba(13, 17, 23, 0.92)",
    plateBorder: "#2b3545",
    text: "#e6ebf2",
    muted: "#8a94a6",
    path: "#ffd166",
    pathEnd: "#ff8f3f",
    pathStart: "#43c463",
  };

  const state = {
    map: null,
    nodeById: new Map(),
    edgeById: new Map(),
    zoneBoundaries: new Map(),
    mode: "unconfigured",
    snapshot: null,
    resolvedPaths: {},
    selectedRobotId: null,
    rows: [],
    ws: null,
    reconnectTimer: null,
    connected: false,
    motionEnabled: true,
    trails: new Map(),
    lastTickIndex: -1,
    lastReadoutAt: 0,
    robotMarks: [],
    viewport: { width: 1, height: 1, dpr: 1, scale: 1, minX: 0, minY: 0, originX: 0, originY: 0 },
  };

  const dom = {};

  document.addEventListener("DOMContentLoaded", init);

  function init() {
    cacheDom();
    bindControls();
    initMotionPreference();
    buildLegend();
    resizeCanvas();
    window.addEventListener("resize", resizeCanvas);
    updateControls();
    updateConnection();
    updateReadout();
    requestAnimationFrame(renderFrame);
    loadMap();
    connectStateStream();
  }

  function cacheDom() {
    dom.connection = document.getElementById("connection");
    dom.connectionText = document.getElementById("connection-text");
    dom.modeText = document.getElementById("mode-text");
    dom.mapId = document.getElementById("map-id");
    dom.readout = document.getElementById("run-readout");
    dom.robotRows = document.getElementById("robot-rows");
    dom.addRobot = document.getElementById("add-robot");
    dom.applyScene = document.getElementById("apply-scene");
    dom.start = document.getElementById("button-start");
    dom.pause = document.getElementById("button-pause");
    dom.resume = document.getElementById("button-resume");
    dom.reset = document.getElementById("button-reset");
    dom.motionToggle = document.getElementById("motion-toggle");
    dom.statusLegend = document.getElementById("status-legend");
    dom.errorList = document.getElementById("error-list");
    dom.stage = document.getElementById("stage");
    dom.canvas = document.getElementById("canvas");
  }

  function bindControls() {
    dom.addRobot.addEventListener("click", addRobot);
    dom.applyScene.addEventListener("click", applyScene);
    dom.start.addEventListener("click", () => sendControl("start"));
    dom.pause.addEventListener("click", () => sendControl("pause"));
    dom.resume.addEventListener("click", () => sendControl("resume"));
    dom.reset.addEventListener("click", () => sendControl("reset"));
    dom.motionToggle.addEventListener("change", () => {
      state.motionEnabled = dom.motionToggle.checked;
      try {
        localStorage.setItem(MOTION_KEY, state.motionEnabled ? "on" : "off");
      } catch (error) {
        // Storage unavailable: the toggle still works for this page session.
      }
    });
    dom.canvas.addEventListener("click", handleCanvasClick);
  }

  function initMotionPreference() {
    let stored = null;
    try {
      stored = localStorage.getItem(MOTION_KEY);
    } catch (error) {
      stored = null;
    }
    if (stored === "on" || stored === "off") {
      state.motionEnabled = stored === "on";
    } else if (window.matchMedia) {
      state.motionEnabled = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    }
    dom.motionToggle.checked = state.motionEnabled;
  }

  function buildLegend() {
    for (const meta of Object.values(STATUS_META)) {
      const item = document.createElement("li");
      const swatch = document.createElement("span");
      swatch.className = "swatch";
      swatch.style.setProperty("--swatch", meta.color);
      const label = document.createElement("span");
      label.textContent = meta.label;
      item.append(swatch, label);
      dom.statusLegend.appendChild(item);
    }
  }

  // -- map and scene editor ---------------------------------------------

  async function loadMap() {
    try {
      const response = await fetch("/api/map");
      const payload = await readJson(response);
      if (!response.ok) {
        showErrors(violationsOf(payload, response));
        return;
      }
      state.map = payload;
      state.nodeById = new Map(payload.nodes.map(node => [node.node_id, node]));
      state.edgeById = new Map(payload.edges.map(edge => [edge.edge_id, edge]));
      state.zoneBoundaries = buildZoneBoundaries();
      dom.mapId.textContent = payload.map_id;
      if (state.rows.length === 0) {
        state.rows.push(createRow(nextRobotId()));
      }
      renderRobotTable();
      resizeCanvas();
    } catch (error) {
      showErrors([`地图加载失败：${errorText(error)}`]);
    }
  }

  function buildZoneBoundaries() {
    const boundaries = new Map();
    for (const zone of state.map.zones) {
      const zoneEdges = new Set(zone.edge_ids);
      const entries = [];
      const seen = new Set();
      for (const edgeId of zone.edge_ids) {
        const edge = state.edgeById.get(edgeId);
        if (!edge) {
          continue;
        }
        for (const nodeId of [edge.from_node_id, edge.to_node_id]) {
          if (seen.has(nodeId)) {
            continue;
          }
          const hasOutside = state.map.edges.some(candidate => {
            if (candidate.edge_id === edge.edge_id || zoneEdges.has(candidate.edge_id)) {
              return false;
            }
            return candidate.from_node_id === nodeId || candidate.to_node_id === nodeId;
          });
          if (hasOutside) {
            seen.add(nodeId);
            entries.push({ nodeId, edgeId });
          }
        }
      }
      boundaries.set(zone.zone_id, entries);
    }
    return boundaries;
  }

  function nextRobotId() {
    const used = new Set(state.rows.map(row => row.id));
    let index = 1;
    while (used.has(`R${index}`)) {
      index += 1;
    }
    return `R${index}`;
  }

  function createRow(robotId) {
    const nodeIds = state.map ? state.map.nodes.map(node => node.node_id) : [];
    const usedStarts = new Set(state.rows.map(row => row.start));
    const start = nodeIds.find(nodeId => !usedStarts.has(nodeId)) || nodeIds[0] || "";
    const target = nodeIds.find(nodeId => nodeId !== start) || start;
    return { id: robotId, start, waypoints: [""], target };
  }

  function addRobot() {
    if (state.rows.length >= MAX_ROBOTS) {
      return;
    }
    state.rows.push(createRow(nextRobotId()));
    renderRobotTable();
  }

  function removeRobot(robotId) {
    if (state.rows.length <= 1) {
      return;
    }
    state.rows = state.rows.filter(row => row.id !== robotId);
    if (state.selectedRobotId === robotId) {
      state.selectedRobotId = null;
    }
    renderRobotTable();
  }

  function renderRobotTable() {
    dom.robotRows.innerHTML = "";
    for (const row of state.rows) {
      const tr = document.createElement("tr");
      tr.classList.toggle("selected", row.id === state.selectedRobotId);
      tr.tabIndex = 0;
      tr.addEventListener("click", event => {
        if (event.target.closest("select, button")) {
          return;
        }
        selectRobot(row.id);
      });
      tr.addEventListener("keydown", event => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          selectRobot(row.id);
        }
      });

      const idCell = document.createElement("td");
      idCell.textContent = row.id;
      tr.appendChild(idCell);
      tr.appendChild(selectCell(row, "start"));
      tr.appendChild(waypointCell(row));
      tr.appendChild(selectCell(row, "target"));

      const actionCell = document.createElement("td");
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "remove";
      remove.textContent = "删除";
      remove.title = `删除 ${row.id}`;
      remove.setAttribute("aria-label", `删除 ${row.id}`);
      remove.disabled = state.rows.length <= 1;
      remove.addEventListener("click", () => removeRobot(row.id));
      actionCell.appendChild(remove);
      tr.appendChild(actionCell);

      dom.robotRows.appendChild(tr);
    }
    dom.addRobot.disabled = state.rows.length >= MAX_ROBOTS;
    dom.applyScene.disabled = state.rows.length === 0 || !state.map;
  }

  function selectCell(row, field) {
    const labels = { start: "起点", target: "终点" };
    const cell = document.createElement("td");
    const select = document.createElement("select");
    select.setAttribute("aria-label", `${row.id} ${labels[field] || field}`);
    for (const node of nodeOptions()) {
      select.appendChild(node);
    }
    select.value = row[field];
    select.addEventListener("change", () => {
      row[field] = select.value;
    });
    cell.appendChild(select);
    return cell;
  }

  function waypointCell(row) {
    const cell = document.createElement("td");
    cell.className = "waypoints";
    const list = document.createElement("div");
    list.className = "waypoint-list";
    row.waypoints.forEach((value, index) => {
      const line = document.createElement("div");
      line.className = "waypoint-line";
      const select = document.createElement("select");
      select.setAttribute("aria-label", `${row.id} 途经点 ${index + 1}`);
      const none = document.createElement("option");
      none.value = "";
      none.textContent = "无";
      select.appendChild(none);
      for (const node of nodeOptions()) {
        select.appendChild(node);
      }
      select.value = value;
      select.addEventListener("change", () => {
        row.waypoints[index] = select.value;
      });
      line.appendChild(select);

      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "waypoint-action";
      remove.textContent = "−";
      remove.title = "移除途经点";
      remove.setAttribute("aria-label", `移除 ${row.id} 途经点 ${index + 1}`);
      remove.disabled = row.waypoints.length <= 1;
      remove.addEventListener("click", () => {
        row.waypoints.splice(index, 1);
        renderRobotTable();
      });
      line.appendChild(remove);
      list.appendChild(line);
    });

    const add = document.createElement("button");
    add.type = "button";
    add.className = "waypoint-action add";
    add.textContent = "+";
    add.title = "添加途经点";
    add.setAttribute("aria-label", `为 ${row.id} 添加途经点`);
    add.addEventListener("click", () => {
      row.waypoints.push("");
      renderRobotTable();
    });
    list.appendChild(add);
    cell.appendChild(list);
    return cell;
  }

  function nodeOptions() {
    return (state.map ? state.map.nodes : []).map(node => {
      const option = document.createElement("option");
      option.value = node.node_id;
      option.textContent = node.node_id;
      return option;
    });
  }

  function selectRobot(robotId) {
    state.selectedRobotId = robotId;
    renderRobotTable();
  }

  async function applyScene() {
    if (!state.map || state.rows.length === 0) {
      return;
    }
    clearErrors();
    const robots = state.rows.map(row => ({
      robot_id: row.id,
      start_node_id: row.start,
      waypoints: row.waypoints.filter(Boolean),
      target_node_id: row.target,
    }));
    dom.applyScene.disabled = true;
    try {
      const response = await fetch("/api/scene", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ robots }),
      });
      const payload = await readJson(response);
      if (!response.ok) {
        showErrors(violationsOf(payload, response));
        return;
      }
      state.mode = payload.mode;
      state.snapshot = payload.snapshot;
      state.resolvedPaths = payload.resolved_paths || {};
      state.selectedRobotId = robots[0].robot_id;
      clearTrails();
      state.lastTickIndex = payload.snapshot ? payload.snapshot.tick_index : -1;
      renderRobotTable();
      updateControls();
      updateReadout();
    } catch (error) {
      showErrors([`配置请求失败：${errorText(error)}`]);
    } finally {
      dom.applyScene.disabled = state.rows.length === 0 || !state.map;
    }
  }

  // -- controls and state stream ----------------------------------------

  async function sendControl(action) {
    clearErrors();
    try {
      const response = await fetch("/api/control", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      const payload = await readJson(response);
      if (!response.ok) {
        showErrors(violationsOf(payload, response));
        if (payload.mode) {
          state.mode = payload.mode;
          updateControls();
        }
        return;
      }
      state.mode = payload.mode;
      state.snapshot = payload.snapshot;
      if (action === "reset") {
        clearTrails();
        state.lastTickIndex = payload.snapshot ? payload.snapshot.tick_index : -1;
      }
      updateControls();
      updateReadout();
    } catch (error) {
      showErrors([`控制请求失败：${errorText(error)}`]);
    }
  }

  function connectStateStream() {
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    let socket;
    try {
      socket = new WebSocket(`${protocol}://${location.host}/ws/state`);
    } catch (error) {
      scheduleReconnect();
      return;
    }
    state.ws = socket;
    socket.addEventListener("open", () => {
      state.connected = true;
      updateConnection();
    });
    socket.addEventListener("message", event => handleFrame(event.data));
    socket.addEventListener("close", () => {
      state.connected = false;
      state.ws = null;
      updateConnection();
      scheduleReconnect();
    });
    socket.addEventListener("error", () => socket.close());
  }

  function scheduleReconnect() {
    if (state.reconnectTimer !== null) {
      return;
    }
    state.reconnectTimer = window.setTimeout(() => {
      state.reconnectTimer = null;
      connectStateStream();
    }, RECONNECT_DELAY_MS);
  }

  function handleFrame(raw) {
    let frame;
    try {
      frame = JSON.parse(raw);
    } catch (error) {
      return;
    }
    if (frame.kind === "tick") {
      state.mode = "running";
      state.snapshot = frame.snapshot;
      pushTrail(frame.snapshot);
    } else if (frame.kind === "status") {
      state.mode = frame.mode;
      state.snapshot = frame.snapshot || null;
      if (frame.snapshot) {
        if (frame.snapshot.tick_index !== state.lastTickIndex) {
          clearTrails();
          state.lastTickIndex = frame.snapshot.tick_index;
        }
      } else {
        clearTrails();
        state.lastTickIndex = -1;
      }
    } else {
      return;
    }
    updateControls();
  }

  function clearTrails() {
    state.trails.clear();
  }

  function pushTrail(snapshot) {
    if (snapshot.tick_index <= state.lastTickIndex) {
      clearTrails();
    }
    const seen = new Set();
    for (const robot of snapshot.robots) {
      seen.add(robot.robot_id);
      let trail = state.trails.get(robot.robot_id);
      if (!trail) {
        trail = [];
        state.trails.set(robot.robot_id, trail);
      }
      trail.push({ x: robot.x_m, y: robot.y_m, status: robot.status });
      if (trail.length > TRAIL_LENGTH) {
        trail.splice(0, trail.length - TRAIL_LENGTH);
      }
    }
    for (const robotId of Array.from(state.trails.keys())) {
      if (!seen.has(robotId)) {
        state.trails.delete(robotId);
      }
    }
    state.lastTickIndex = snapshot.tick_index;
  }

  function updateControls() {
    dom.modeText.textContent = MODE_LABELS[state.mode] || state.mode;
    dom.modeText.dataset.mode = state.mode;
    dom.start.disabled = state.mode !== "configured";
    dom.pause.disabled = state.mode !== "running";
    dom.resume.disabled = state.mode !== "paused";
    dom.reset.disabled = state.mode === "unconfigured";
  }

  function updateConnection() {
    dom.connection.classList.toggle("connected", state.connected);
    dom.connectionText.textContent = state.connected ? "已连接" : "已断开，正在重连";
  }

  function updateReadout() {
    const snapshot = state.snapshot;
    if (!snapshot) {
      dom.readout.textContent = "t 0.00 s · tick 0 · 0 台 · 占用区 0 · 等待区 0";
      return;
    }
    let held = 0;
    let waiting = 0;
    for (const zone of snapshot.zones) {
      if (zone.holder_robot_ids.length > 0) {
        held += 1;
      }
      if (zone.waiting_robot_ids.length > 0) {
        waiting += 1;
      }
    }
    dom.readout.textContent =
      `t ${snapshot.sim_time_s.toFixed(2)} s · tick ${snapshot.tick_index} · ` +
      `${snapshot.robots.length} 台 · 占用区 ${held} · 等待区 ${waiting}`;
  }

  function showErrors(messages) {
    dom.errorList.innerHTML = "";
    for (const message of messages) {
      const item = document.createElement("li");
      item.textContent = message;
      dom.errorList.appendChild(item);
    }
  }

  function clearErrors() {
    dom.errorList.innerHTML = "";
  }

  async function readJson(response) {
    try {
      return await response.json();
    } catch (error) {
      return {};
    }
  }

  function violationsOf(payload, response) {
    if (Array.isArray(payload.violations) && payload.violations.length > 0) {
      return payload.violations;
    }
    return [`请求失败（HTTP ${response.status}）`];
  }

  function errorText(error) {
    return error && error.message ? error.message : String(error);
  }

  // -- canvas geometry ---------------------------------------------------

  function resizeCanvas() {
    const rect = dom.stage.getBoundingClientRect();
    const width = Math.max(1, rect.width);
    const height = Math.max(1, rect.height);
    const dpr = window.devicePixelRatio || 1;
    dom.canvas.width = Math.round(width * dpr);
    dom.canvas.height = Math.round(height * dpr);
    dom.canvas.style.width = `${width}px`;
    dom.canvas.style.height = `${height}px`;
    state.viewport.width = width;
    state.viewport.height = height;
    state.viewport.dpr = dpr;
    computeTransform();
  }

  function computeTransform() {
    const viewport = state.viewport;
    if (!state.map || state.map.nodes.length === 0) {
      return;
    }
    const xs = state.map.nodes.map(node => node.x_m);
    const ys = state.map.nodes.map(node => node.y_m);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const padding = 88;
    const width = Math.max(1, viewport.width - padding * 2);
    const height = Math.max(1, viewport.height - padding * 2);
    const scale = Math.min(
      width / Math.max(maxX - minX, 1e-6),
      height / Math.max(maxY - minY, 1e-6),
    );
    viewport.scale = scale;
    viewport.minX = minX;
    viewport.minY = minY;
    viewport.originX = padding + (width - (maxX - minX) * scale) / 2;
    viewport.originY = padding + (height - (maxY - minY) * scale) / 2;
  }

  function toScreen(x, y) {
    const viewport = state.viewport;
    return {
      x: viewport.originX + (x - viewport.minX) * viewport.scale,
      y: viewport.height - viewport.originY - (y - viewport.minY) * viewport.scale,
    };
  }

  function toWorld(screenX, screenY) {
    const viewport = state.viewport;
    return {
      x: (screenX - viewport.originX) / viewport.scale + viewport.minX,
      y: (viewport.height - viewport.originY - screenY) / viewport.scale + viewport.minY,
    };
  }

  function robotRadius() {
    return clamp(0.35 * state.viewport.scale, 7, 20);
  }

  function nodePadSize() {
    return clamp(0.7 * state.viewport.scale, 12, 30);
  }

  function laneWidthPx(edge) {
    const width = Number(edge.lane_width_m);
    return Math.max(12, (Number.isFinite(width) ? width : 2) * state.viewport.scale);
  }

  function handleCanvasClick(event) {
    if (!state.snapshot) {
      return;
    }
    const rect = dom.canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const radius = robotRadius() + 8;
    let nearest = null;
    for (const robot of state.snapshot.robots) {
      const point = toScreen(robot.x_m, robot.y_m);
      const distance = Math.hypot(point.x - x, point.y - y);
      if (distance <= radius && (nearest === null || distance < nearest.distance)) {
        nearest = { robotId: robot.robot_id, distance };
      }
    }
    if (nearest !== null) {
      selectRobot(nearest.robotId);
    }
  }

  // -- rendering ---------------------------------------------------------

  function renderFrame(now) {
    draw(now);
    if (now - state.lastReadoutAt > 120) {
      state.lastReadoutAt = now;
      updateReadout();
    }
    requestAnimationFrame(renderFrame);
  }

  function draw(now) {
    const ctx = dom.canvas.getContext("2d");
    const viewport = state.viewport;
    ctx.setTransform(viewport.dpr, 0, 0, viewport.dpr, 0, 0);
    ctx.clearRect(0, 0, viewport.width, viewport.height);
    ctx.fillStyle = COLORS.floor;
    ctx.fillRect(0, 0, viewport.width, viewport.height);
    if (!state.map) {
      drawEmptyState(ctx);
      return;
    }
    const zoneStates = zoneStatesById();
    drawFloorGrid(ctx);
    drawAisles(ctx);
    drawZones(ctx, zoneStates);
    drawZoneGates(ctx, zoneStates);
    drawNodes(ctx);
    drawSelectedPath(ctx);
    drawTrails(ctx);
    drawRobots(ctx, now);
    drawLabels(ctx, zoneStates);
    drawScaleBar(ctx);
  }

  function drawEmptyState(ctx) {
    const viewport = state.viewport;
    ctx.save();
    ctx.fillStyle = COLORS.muted;
    ctx.font = `12px ${FONT_SANS}`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("正在加载地图…", viewport.width / 2, viewport.height / 2);
    ctx.restore();
  }

  function drawFloorGrid(ctx) {
    const viewport = state.viewport;
    const topLeft = toWorld(0, 0);
    const bottomRight = toWorld(viewport.width, viewport.height);
    const minX = Math.floor(topLeft.x);
    const maxX = Math.ceil(bottomRight.x);
    const minY = Math.floor(bottomRight.y);
    const maxY = Math.ceil(topLeft.y);
    const showMinor = viewport.scale >= 12;
    ctx.save();
    ctx.lineWidth = 1;
    for (let x = minX; x <= maxX; x += 1) {
      const major = x % 5 === 0;
      if (!major && !showMinor) {
        continue;
      }
      const screenX = toScreen(x, 0).x;
      ctx.strokeStyle = major ? COLORS.gridMajor : COLORS.gridMinor;
      ctx.beginPath();
      ctx.moveTo(screenX, 0);
      ctx.lineTo(screenX, viewport.height);
      ctx.stroke();
    }
    for (let y = minY; y <= maxY; y += 1) {
      const major = y % 5 === 0;
      if (!major && !showMinor) {
        continue;
      }
      const screenY = toScreen(0, y).y;
      ctx.strokeStyle = major ? COLORS.gridMajor : COLORS.gridMinor;
      ctx.beginPath();
      ctx.moveTo(0, screenY);
      ctx.lineTo(viewport.width, screenY);
      ctx.stroke();
    }
    ctx.restore();
  }

  function edgeGeometry(edge) {
    const from = state.nodeById.get(edge.from_node_id);
    const to = state.nodeById.get(edge.to_node_id);
    if (!from || !to) {
      return null;
    }
    const a = toScreen(from.x_m, from.y_m);
    const b = toScreen(to.x_m, to.y_m);
    return {
      a,
      b,
      angle: Math.atan2(b.y - a.y, b.x - a.x),
      length: Math.hypot(b.x - a.x, b.y - a.y),
    };
  }

  function drawAisles(ctx) {
    ctx.save();
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    for (const edge of state.map.edges) {
      const geometry = edgeGeometry(edge);
      if (!geometry) {
        continue;
      }
      const lane = laneWidthPx(edge);
      ctx.beginPath();
      ctx.moveTo(geometry.a.x, geometry.a.y);
      ctx.lineTo(geometry.b.x, geometry.b.y);
      ctx.strokeStyle = COLORS.aisleBorder;
      ctx.lineWidth = lane + 2;
      ctx.stroke();
      ctx.strokeStyle = COLORS.aisle;
      ctx.lineWidth = lane;
      ctx.stroke();
      ctx.strokeStyle = COLORS.aisleDash;
      ctx.lineWidth = 1;
      ctx.setLineDash([9, 11]);
      ctx.stroke();
      ctx.setLineDash([]);
      if (edge.direction === "fwd") {
        drawDirectionArrow(ctx, geometry, lane);
      }
    }
    ctx.restore();
  }

  function drawDirectionArrow(ctx, geometry, lane) {
    const t = 0.62;
    const x = geometry.a.x + (geometry.b.x - geometry.a.x) * t;
    const y = geometry.a.y + (geometry.b.y - geometry.a.y) * t;
    const size = clamp(lane * 0.16, 5, 11);
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(geometry.angle);
    ctx.strokeStyle = COLORS.arrow;
    ctx.lineWidth = 2;
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.moveTo(-size, -size * 0.85);
    ctx.lineTo(0, 0);
    ctx.lineTo(-size, size * 0.85);
    ctx.stroke();
    ctx.restore();
  }

  function zoneStatesById() {
    const map = new Map();
    if (state.snapshot) {
      for (const zone of state.snapshot.zones) {
        map.set(zone.zone_id, zone);
      }
    }
    return map;
  }

  function drawZones(ctx, zoneStates) {
    ctx.save();
    state.map.zones.forEach((zone, index) => {
      const color = ZONE_COLORS[index % ZONE_COLORS.length];
      const zoneState = zoneStates.get(zone.zone_id);
      const held = Boolean(zoneState && zoneState.holder_robot_ids.length > 0);
      const waiting = Boolean(zoneState && zoneState.waiting_robot_ids.length > 0);
      const bandAlpha = held ? 0.1 : waiting ? 0.075 : 0.045;
      for (const edgeId of zone.edge_ids) {
        const edge = state.edgeById.get(edgeId);
        if (!edge) {
          continue;
        }
        const geometry = edgeGeometry(edge);
        if (!geometry) {
          continue;
        }
        const band = laneWidthPx(edge) * 0.66;
        ctx.beginPath();
        ctx.moveTo(geometry.a.x, geometry.a.y);
        ctx.lineTo(geometry.b.x, geometry.b.y);
        ctx.strokeStyle = withAlpha(color, bandAlpha);
        ctx.lineWidth = band;
        ctx.lineCap = "butt";
        ctx.stroke();

        const nx = Math.cos(geometry.angle + Math.PI / 2);
        const ny = Math.sin(geometry.angle + Math.PI / 2);
        const offset = band / 2;
        ctx.setLineDash([7, 7]);
        ctx.lineWidth = 1.4;
        ctx.strokeStyle = withAlpha(color, held ? 0.65 : 0.38);
        for (const sign of [-1, 1]) {
          ctx.beginPath();
          ctx.moveTo(geometry.a.x + nx * offset * sign, geometry.a.y + ny * offset * sign);
          ctx.lineTo(geometry.b.x + nx * offset * sign, geometry.b.y + ny * offset * sign);
          ctx.stroke();
        }
        ctx.setLineDash([]);
      }
    });
    ctx.restore();
  }

  function drawZoneGates(ctx, zoneStates) {
    ctx.save();
    state.map.zones.forEach((zone, index) => {
      const color = ZONE_COLORS[index % ZONE_COLORS.length];
      const zoneState = zoneStates.get(zone.zone_id);
      const held = Boolean(zoneState && zoneState.holder_robot_ids.length > 0);
      const entries = state.zoneBoundaries.get(zone.zone_id) || [];
      for (const entry of entries) {
        const node = state.nodeById.get(entry.nodeId);
        const edge = state.edgeById.get(entry.edgeId);
        if (!node || !edge) {
          continue;
        }
        const geometry = edgeGeometry(edge);
        if (!geometry) {
          continue;
        }
        const point = toScreen(node.x_m, node.y_m);
        const length = laneWidthPx(edge) * 0.82;
        const nx = Math.cos(geometry.angle + Math.PI / 2);
        const ny = Math.sin(geometry.angle + Math.PI / 2);
        const halfX = nx * length / 2;
        const halfY = ny * length / 2;

        ctx.save();
        if (held) {
          ctx.shadowColor = withAlpha(color, 0.55);
          ctx.shadowBlur = 10;
        }
        ctx.strokeStyle = withAlpha(color, held ? 0.95 : 0.58);
        ctx.lineWidth = 2.2;
        ctx.lineCap = "round";
        ctx.beginPath();
        ctx.moveTo(point.x - halfX, point.y - halfY);
        ctx.lineTo(point.x + halfX, point.y + halfY);
        ctx.stroke();
        ctx.restore();

        ctx.fillStyle = withAlpha(color, held ? 1 : 0.8);
        for (const sign of [-1, 1]) {
          ctx.beginPath();
          ctx.arc(point.x + halfX * sign, point.y + halfY * sign, 2, 0, Math.PI * 2);
          ctx.fill();
        }
      }
    });
    ctx.restore();
  }

  function drawNodes(ctx) {
    const size = nodePadSize();
    ctx.save();
    for (const node of state.map.nodes) {
      const point = toScreen(node.x_m, node.y_m);
      roundRect(ctx, point.x - size / 2, point.y - size / 2, size, size, 4);
      ctx.fillStyle = COLORS.nodeFill;
      ctx.fill();
      ctx.strokeStyle = COLORS.nodeStroke;
      ctx.lineWidth = 1.4;
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(point.x, point.y, 2, 0, Math.PI * 2);
      ctx.fillStyle = COLORS.nodeDot;
      ctx.fill();
    }
    ctx.restore();
  }

  function drawSelectedPath(ctx) {
    if (!state.selectedRobotId) {
      return;
    }
    const path = state.resolvedPaths[state.selectedRobotId];
    if (!path || path.length < 2) {
      return;
    }
    const points = path
      .map(nodeId => state.nodeById.get(nodeId))
      .filter(Boolean)
      .map(node => toScreen(node.x_m, node.y_m));
    if (points.length < 2) {
      return;
    }

    ctx.save();
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    tracePolyline(ctx, points);
    ctx.strokeStyle = withAlpha(COLORS.path, 0.1);
    ctx.lineWidth = 9;
    ctx.stroke();

    ctx.setLineDash([9, 7]);
    ctx.strokeStyle = withAlpha(COLORS.path, 0.82);
    ctx.lineWidth = 2.2;
    ctx.stroke();
    ctx.setLineDash([]);

    for (let index = 1; index < points.length; index += 1) {
      const a = points[index - 1];
      const b = points[index];
      if (Math.hypot(b.x - a.x, b.y - a.y) < 46) {
        continue;
      }
      const angle = Math.atan2(b.y - a.y, b.x - a.x);
      drawPathChevron(ctx, (a.x + b.x) / 2, (a.y + b.y) / 2, angle);
    }

    for (const point of points) {
      ctx.beginPath();
      ctx.arc(point.x, point.y, 2.6, 0, Math.PI * 2);
      ctx.fillStyle = COLORS.path;
      ctx.fill();
    }

    const start = points[0];
    const end = points[points.length - 1];
    ctx.strokeStyle = COLORS.pathStart;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(start.x, start.y, 10, 0, Math.PI * 2);
    ctx.stroke();
    ctx.strokeStyle = COLORS.pathEnd;
    ctx.strokeRect(end.x - 9, end.y - 9, 18, 18);
    ctx.restore();
  }

  function tracePolyline(ctx, points) {
    ctx.beginPath();
    points.forEach((point, index) => {
      if (index === 0) {
        ctx.moveTo(point.x, point.y);
      } else {
        ctx.lineTo(point.x, point.y);
      }
    });
  }

  function drawPathChevron(ctx, x, y, angle) {
    const size = 5;
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(angle);
    ctx.strokeStyle = withAlpha(COLORS.path, 0.85);
    ctx.lineWidth = 1.8;
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.moveTo(-size, -size * 0.8);
    ctx.lineTo(0, 0);
    ctx.lineTo(-size, size * 0.8);
    ctx.stroke();
    ctx.restore();
  }

  function drawTrails(ctx) {
    if (!state.motionEnabled || state.trails.size === 0) {
      return;
    }
    ctx.save();
    ctx.lineCap = "round";
    for (const trail of state.trails.values()) {
      if (trail.length < 2) {
        continue;
      }
      for (let index = 1; index < trail.length; index += 1) {
        const previous = trail[index - 1];
        const current = trail[index];
        const a = toScreen(previous.x, previous.y);
        const b = toScreen(current.x, current.y);
        const meta = STATUS_META[current.status] || STATUS_META.idle;
        const ratio = index / trail.length;
        const alpha = 0.16 + ratio * 0.5;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.strokeStyle = withAlpha(meta.color, alpha * 0.28);
        ctx.lineWidth = 4.4 + ratio * 2.2;
        ctx.stroke();
        ctx.strokeStyle = withAlpha(meta.color, alpha);
        ctx.lineWidth = 1.3 + ratio * 1.6;
        ctx.stroke();
      }
    }
    ctx.restore();
  }

  function drawRobots(ctx, now) {
    state.robotMarks = [];
    if (!state.snapshot) {
      return;
    }
    const radius = robotRadius();
    for (const robot of state.snapshot.robots) {
      const meta = STATUS_META[robot.status] || { label: robot.status, color: COLORS.muted };
      const point = toScreen(robot.x_m, robot.y_m);
      const selected = robot.robot_id === state.selectedRobotId;
      state.robotMarks.push({ robot, meta, point, radius, selected });
      drawRobotBody(ctx, robot, meta, point, radius, selected, now);
    }
  }

  function drawRobotBody(ctx, robot, meta, point, radius, selected, now) {
    ctx.save();
    ctx.strokeStyle = "rgba(150, 170, 200, 0.16)";
    ctx.lineWidth = 1;
    ctx.setLineDash([2, 4]);
    ctx.beginPath();
    ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.restore();

    ctx.save();
    ctx.translate(point.x, point.y);
    ctx.rotate(-robot.theta_rad);

    const bodyWidth = radius * 1.8;
    const bodyHeight = radius * 1.4;
    const wheelWidth = radius * 1.02;
    const wheelHeight = Math.max(2.6, radius * 0.28);

    ctx.save();
    ctx.shadowColor = "rgba(0, 0, 0, 0.55)";
    ctx.shadowBlur = radius * 1.3;
    ctx.shadowOffsetY = radius * 0.5;
    roundRect(ctx, -bodyWidth / 2, -bodyHeight / 2, bodyWidth, bodyHeight, radius * 0.34);
    ctx.fillStyle = "#151b24";
    ctx.fill();
    ctx.restore();

    ctx.strokeStyle = "#39465a";
    ctx.lineWidth = 0.8;
    ctx.fillStyle = "#05070a";
    roundRect(ctx, -wheelWidth / 2, -radius * 0.82 - wheelHeight / 2, wheelWidth, wheelHeight, wheelHeight / 2);
    ctx.fill();
    ctx.stroke();
    roundRect(ctx, -wheelWidth / 2, radius * 0.82 - wheelHeight / 2, wheelWidth, wheelHeight, wheelHeight / 2);
    ctx.fill();
    ctx.stroke();

    roundRect(ctx, -bodyWidth / 2, -bodyHeight / 2, bodyWidth, bodyHeight, radius * 0.34);
    ctx.fillStyle = "#2a3442";
    ctx.fill();
    ctx.strokeStyle = withAlpha(meta.color, 0.95);
    ctx.lineWidth = Math.max(1.8, radius * 0.16);
    ctx.stroke();

    roundRect(ctx, -radius * 0.5, -radius * 0.4, radius, radius * 0.8, radius * 0.16);
    ctx.fillStyle = "#303b4b";
    ctx.fill();
    ctx.fillStyle = withAlpha(meta.color, 0.14);
    ctx.fill();

    ctx.beginPath();
    ctx.moveTo(radius * 0.9, 0);
    ctx.lineTo(radius * 0.62, -radius * 0.18);
    ctx.lineTo(radius * 0.62, radius * 0.18);
    ctx.closePath();
    ctx.fillStyle = meta.color;
    ctx.fill();

    ctx.beginPath();
    ctx.arc(radius * 0.3, 0, radius * 0.22, 0, Math.PI * 2);
    ctx.fillStyle = meta.color;
    ctx.fill();

    ctx.restore();

    ctx.save();
    ctx.strokeStyle = withAlpha(meta.color, 0.42);
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(point.x, point.y, radius * 1.08, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();

    if (state.motionEnabled && (robot.status === "waiting_right" || robot.status === "e_stop")) {
      const period = robot.status === "e_stop" ? 360 : 900;
      const phase = (Math.sin(now / period * Math.PI * 2) + 1) / 2;
      ctx.save();
      ctx.strokeStyle = withAlpha(meta.color, 0.1 + phase * 0.3);
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(point.x, point.y, radius + 3 + phase * 5, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();
    }

    if (robot.status === "holding_zone" || robot.status === "arrived") {
      ctx.save();
      ctx.strokeStyle = withAlpha(meta.color, 0.5);
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(point.x, point.y, radius + 4, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();
    }

    if (selected) {
      ctx.save();
      ctx.strokeStyle = "rgba(255, 255, 255, 0.9)";
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.arc(point.x, point.y, radius + 6, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();
    }
  }

  function drawLabels(ctx, zoneStates) {
    const placed = [];
    drawNodeLabels(ctx, placed);
    const marks = [...state.robotMarks].sort((a, b) => Number(b.selected) - Number(a.selected));
    for (const mark of marks) {
      drawRobotLabel(ctx, placed, mark);
    }
    drawZoneLabels(ctx, placed, zoneStates);
  }

  function drawNodeLabels(ctx, placed) {
    const size = nodePadSize();
    ctx.save();
    ctx.font = `10px ${FONT_MONO}`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    for (const node of state.map.nodes) {
      const point = toScreen(node.x_m, node.y_m);
      const text = node.node_id;
      const width = ctx.measureText(text).width + 6;
      const height = 13;
      const gap = size / 2 + 4;
      const rect = placeLabel(placed, point, width, height, [
        [0, -(gap + height / 2)],
        [0, gap + height / 2],
        [gap + width / 2, 0],
        [-(gap + width / 2), 0],
      ]);
      const centerX = rect.x + rect.w / 2;
      const centerY = rect.y + rect.h / 2;
      ctx.lineWidth = 3;
      ctx.strokeStyle = COLORS.floor;
      ctx.strokeText(text, centerX, centerY);
      ctx.fillStyle = COLORS.nodeText;
      ctx.fillText(text, centerX, centerY);
    }
    ctx.restore();
  }

  function drawRobotLabel(ctx, placed, mark) {
    const title = `${mark.robot.robot_id} ${mark.meta.label}`;
    const subtitle = `${mark.robot.v_mps.toFixed(2)} m/s`;
    ctx.save();
    ctx.font = `600 11px ${FONT_SANS}`;
    const titleWidth = ctx.measureText(title).width;
    ctx.font = `10px ${FONT_MONO}`;
    const subtitleWidth = ctx.measureText(subtitle).width;
    const width = Math.max(titleWidth, subtitleWidth, 52) + 26;
    const height = 32;
    const gap = mark.radius + 10;
    const rect = placeLabel(placed, mark.point, width, height, [
      [0, -(gap + height / 2)],
      [0, gap + height / 2],
      [gap + width / 2, 0],
      [-(gap + width / 2), 0],
    ]);
    drawPlate(ctx, rect, mark.meta.color, title, subtitle, mark.selected);
    ctx.restore();
  }

  function drawZoneLabels(ctx, placed, zoneStates) {
    ctx.save();
    state.map.zones.forEach((zone, index) => {
      const anchor = zoneLabelAnchor(zone);
      if (!anchor) {
        return;
      }
      const zoneState = zoneStates.get(zone.zone_id);
      ctx.font = `600 11px ${FONT_SANS}`;
      const title = fitText(ctx, `${zone.zone_id} · ${zone.name}`, 240);
      const titleWidth = ctx.measureText(title).width;
      const subtitle = zoneStatusText(zone, zoneState);
      ctx.font = `10px ${FONT_MONO}`;
      const subtitleWidth = ctx.measureText(subtitle).width;
      const width = Math.max(titleWidth, subtitleWidth, 96) + 26;
      const height = 32;
      const gap = 20;
      const rect = placeLabel(placed, anchor, width, height, [
        [0, -(gap + height / 2)],
        [0, gap + height / 2],
        [gap + width / 2, 0],
        [-(gap + width / 2), 0],
      ]);
      drawPlate(ctx, rect, ZONE_COLORS[index % ZONE_COLORS.length], title, subtitle, false);
    });
    ctx.restore();
  }

  function zoneLabelAnchor(zone) {
    const points = zone.edge_ids
      .map(edgeId => state.edgeById.get(edgeId))
      .filter(Boolean)
      .map(edge => {
        const from = state.nodeById.get(edge.from_node_id);
        const to = state.nodeById.get(edge.to_node_id);
        if (!from || !to) {
          return null;
        }
        return toScreen((from.x_m + to.x_m) / 2, (from.y_m + to.y_m) / 2);
      })
      .filter(Boolean);
    if (points.length === 0) {
      return null;
    }
    return {
      x: points.reduce((sum, point) => sum + point.x, 0) / points.length,
      y: points.reduce((sum, point) => sum + point.y, 0) / points.length,
    };
  }

  function zoneStatusText(zone, zoneState) {
    const parts = [`容量 ${zone.capacity}`];
    const holders = zoneState ? zoneState.holder_robot_ids : [];
    const waiting = zoneState ? zoneState.waiting_robot_ids : [];
    if (holders.length > 0) {
      parts.push(`持有 ${holders.join("、")}`);
    }
    if (waiting.length > 0) {
      parts.push(`等待 ${waiting.join("、")}`);
    }
    if (holders.length === 0 && waiting.length === 0) {
      parts.push("空闲");
    }
    return parts.join(" · ");
  }

  function drawScaleBar(ctx) {
    const viewport = state.viewport;
    const candidates = [1, 2, 5, 10, 20];
    let length = candidates[0];
    let bestDifference = Infinity;
    for (const candidate of candidates) {
      const pixels = candidate * viewport.scale;
      if (pixels >= 56 && pixels <= 150) {
        length = candidate;
        bestDifference = 0;
        break;
      }
      const difference = Math.abs(pixels - 100);
      if (difference < bestDifference) {
        bestDifference = difference;
        length = candidate;
      }
    }
    const pixels = length * viewport.scale;
    const x = 18;
    const y = viewport.height - 20;
    ctx.save();
    ctx.strokeStyle = "rgba(138, 148, 166, 0.65)";
    ctx.lineWidth = 1.5;
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x + pixels, y);
    ctx.moveTo(x, y - 4);
    ctx.lineTo(x, y + 4);
    ctx.moveTo(x + pixels, y - 4);
    ctx.lineTo(x + pixels, y + 4);
    ctx.stroke();
    ctx.font = `10px ${FONT_MONO}`;
    ctx.fillStyle = COLORS.muted;
    ctx.textAlign = "left";
    ctx.textBaseline = "bottom";
    ctx.fillText(`${length} m`, x, y - 7);
    ctx.restore();
  }

  // -- label layout and plates -------------------------------------------

  function placeLabel(placed, anchor, width, height, offsets) {
    const viewport = state.viewport;
    const margin = 8;
    for (const [dx, dy] of offsets) {
      const rect = {
        x: clamp(anchor.x + dx - width / 2, margin, viewport.width - width - margin),
        y: clamp(anchor.y + dy - height / 2, margin, viewport.height - height - margin),
        w: width,
        h: height,
      };
      if (!placed.some(other => overlaps(rect, other))) {
        placed.push(rect);
        return rect;
      }
    }
    const fallback = {
      x: clamp(anchor.x - width / 2, margin, viewport.width - width - margin),
      y: clamp(anchor.y - height - 12, margin, viewport.height - height - margin),
      w: width,
      h: height,
    };
    placed.push(fallback);
    return fallback;
  }

  function overlaps(a, b) {
    const padding = 3;
    return (
      a.x < b.x + b.w + padding &&
      a.x + a.w + padding > b.x &&
      a.y < b.y + b.h + padding &&
      a.y + a.h + padding > b.y
    );
  }

  function drawPlate(ctx, rect, dotColor, title, subtitle, selected) {
    ctx.save();
    ctx.shadowColor = "rgba(0, 0, 0, 0.45)";
    ctx.shadowBlur = 8;
    ctx.shadowOffsetY = 2;
    roundRect(ctx, rect.x, rect.y, rect.w, rect.h, 4);
    ctx.fillStyle = COLORS.plate;
    ctx.fill();
    ctx.shadowColor = "transparent";
    ctx.shadowBlur = 0;
    ctx.shadowOffsetY = 0;
    ctx.strokeStyle = selected ? "rgba(255, 255, 255, 0.55)" : COLORS.plateBorder;
    ctx.lineWidth = 1;
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(rect.x + 10, rect.y + 11, 3, 0, Math.PI * 2);
    ctx.fillStyle = dotColor;
    ctx.fill();

    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.font = `600 11px ${FONT_SANS}`;
    ctx.fillStyle = COLORS.text;
    ctx.fillText(fitText(ctx, title, rect.w - 26), rect.x + 18, rect.y + 11);
    ctx.font = `10px ${FONT_MONO}`;
    ctx.fillStyle = COLORS.muted;
    ctx.fillText(fitText(ctx, subtitle, rect.w - 26), rect.x + 18, rect.y + 23);
    ctx.restore();
  }

  // -- small helpers -----------------------------------------------------

  function roundRect(ctx, x, y, width, height, radius) {
    const r = Math.min(radius, width / 2, height / 2);
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + width, y, x + width, y + height, r);
    ctx.arcTo(x + width, y + height, x, y + height, r);
    ctx.arcTo(x, y + height, x, y, r);
    ctx.arcTo(x, y, x + width, y, r);
    ctx.closePath();
  }

  function withAlpha(hex, alpha) {
    const value = hex.replace("#", "");
    const red = parseInt(value.slice(0, 2), 16);
    const green = parseInt(value.slice(2, 4), 16);
    const blue = parseInt(value.slice(4, 6), 16);
    return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
  }

  function clamp(value, low, high) {
    return Math.min(high, Math.max(low, value));
  }

  function fitText(ctx, text, maxWidth) {
    if (ctx.measureText(text).width <= maxWidth) {
      return text;
    }
    let low = 0;
    let high = text.length;
    while (low < high) {
      const mid = Math.ceil((low + high) / 2);
      if (ctx.measureText(`${text.slice(0, mid)}…`).width <= maxWidth) {
        low = mid;
      } else {
        high = mid - 1;
      }
    }
    return `${text.slice(0, low)}…`;
  }
})();
