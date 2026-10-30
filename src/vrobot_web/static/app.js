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

  const ZONE_COLORS = ["#5b8cff", "#ff9f43", "#2fbf71", "#c85cff", "#e8c547"];
  const RECONNECT_DELAY_MS = 1000;
  const MAX_ROBOTS = 10;

  const state = {
    map: null,
    nodeById: new Map(),
    edgeById: new Map(),
    mode: "unconfigured",
    snapshot: null,
    resolvedPaths: {},
    selectedRobotId: null,
    rows: [],
    ws: null,
    reconnectTimer: null,
    connected: false,
    viewport: { width: 1, height: 1, dpr: 1, scale: 1, minX: 0, minY: 0, originX: 0, originY: 0 },
  };

  const dom = {};

  document.addEventListener("DOMContentLoaded", init);

  function init() {
    cacheDom();
    bindControls();
    resizeCanvas();
    window.addEventListener("resize", resizeCanvas);
    updateControls();
    updateConnection();
    requestAnimationFrame(renderFrame);
    loadMap();
    connectStateStream();
  }

  function cacheDom() {
    dom.connection = document.getElementById("connection");
    dom.connectionText = document.getElementById("connection-text");
    dom.modeText = document.getElementById("mode-text");
    dom.robotRows = document.getElementById("robot-rows");
    dom.addRobot = document.getElementById("add-robot");
    dom.applyScene = document.getElementById("apply-scene");
    dom.start = document.getElementById("button-start");
    dom.pause = document.getElementById("button-pause");
    dom.resume = document.getElementById("button-resume");
    dom.reset = document.getElementById("button-reset");
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
    dom.canvas.addEventListener("click", handleCanvasClick);
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
      if (state.rows.length === 0) {
        state.rows.push(createRow(nextRobotId()));
      }
      renderRobotTable();
      resizeCanvas();
    } catch (error) {
      showErrors([`地图加载失败：${errorText(error)}`]);
    }
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
      tr.addEventListener("click", event => {
        if (event.target.closest("select, button")) {
          return;
        }
        selectRobot(row.id);
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
    const cell = document.createElement("td");
    const select = document.createElement("select");
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
      renderRobotTable();
      updateControls();
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
      updateControls();
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
    if (frame.kind === "status" || frame.kind === "tick") {
      state.mode = frame.mode;
      state.snapshot = frame.snapshot;
      updateControls();
    }
  }

  function updateControls() {
    dom.modeText.textContent = MODE_LABELS[state.mode] || state.mode;
    dom.start.disabled = state.mode !== "configured";
    dom.pause.disabled = state.mode !== "running";
    dom.resume.disabled = state.mode !== "paused";
    dom.reset.disabled = state.mode === "unconfigured";
  }

  function updateConnection() {
    dom.connection.classList.toggle("connected", state.connected);
    dom.connectionText.textContent = state.connected ? "已连接" : "已断开，正在重连";
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
    const padding = 56;
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

  function handleCanvasClick(event) {
    if (!state.snapshot) {
      return;
    }
    const rect = dom.canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    let nearest = null;
    for (const robot of state.snapshot.robots) {
      const point = toScreen(robot.x_m, robot.y_m);
      const distance = Math.hypot(point.x - x, point.y - y);
      if (distance <= 18 && (nearest === null || distance < nearest.distance)) {
        nearest = { robotId: robot.robot_id, distance };
      }
    }
    if (nearest !== null) {
      selectRobot(nearest.robotId);
    }
  }

  // -- rendering ---------------------------------------------------------

  function renderFrame() {
    draw();
    requestAnimationFrame(renderFrame);
  }

  function draw() {
    const ctx = dom.canvas.getContext("2d");
    const viewport = state.viewport;
    ctx.setTransform(viewport.dpr, 0, 0, viewport.dpr, 0, 0);
    ctx.clearRect(0, 0, viewport.width, viewport.height);
    ctx.fillStyle = "#0f1115";
    ctx.fillRect(0, 0, viewport.width, viewport.height);
    if (!state.map) {
      return;
    }
    drawZones(ctx);
    drawEdges(ctx);
    drawNodes(ctx);
    drawSelectedPath(ctx);
    drawRobots(ctx);
    drawZoneOccupancy(ctx);
  }

  function drawZones(ctx) {
    state.map.zones.forEach((zone, index) => {
      const color = ZONE_COLORS[index % ZONE_COLORS.length];
      ctx.save();
      ctx.globalAlpha = 0.16;
      ctx.strokeStyle = color;
      ctx.lineWidth = 12;
      ctx.lineCap = "round";
      for (const edgeId of zone.edge_ids) {
        const edge = state.edgeById.get(edgeId);
        if (!edge) {
          continue;
        }
        const from = state.nodeById.get(edge.from_node_id);
        const to = state.nodeById.get(edge.to_node_id);
        if (!from || !to) {
          continue;
        }
        const a = toScreen(from.x_m, from.y_m);
        const b = toScreen(to.x_m, to.y_m);
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      }
      ctx.restore();

      const label = zoneLabelPoint(zone);
      ctx.fillStyle = color;
      ctx.font = "11px 'Segoe UI', 'Microsoft YaHei', sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(`${zone.zone_id} ${zone.name}`, label.x, label.y);
    });
  }

  function zoneLabelPoint(zone) {
    const points = zone.edge_ids
      .map(edgeId => state.edgeById.get(edgeId))
      .filter(Boolean)
      .map(edge => {
        const from = state.nodeById.get(edge.from_node_id);
        const to = state.nodeById.get(edge.to_node_id);
        return toScreen((from.x_m + to.x_m) / 2, (from.y_m + to.y_m) / 2);
      });
    if (points.length === 0) {
      return { x: 0, y: 0 };
    }
    const x = points.reduce((sum, point) => sum + point.x, 0) / points.length;
    const y = points.reduce((sum, point) => sum + point.y, 0) / points.length;
    return { x, y: y - 26 };
  }

  function drawEdges(ctx) {
    ctx.strokeStyle = "#2b3442";
    ctx.lineWidth = 3;
    ctx.lineCap = "round";
    for (const edge of state.map.edges) {
      const from = state.nodeById.get(edge.from_node_id);
      const to = state.nodeById.get(edge.to_node_id);
      if (!from || !to) {
        continue;
      }
      const a = toScreen(from.x_m, from.y_m);
      const b = toScreen(to.x_m, to.y_m);
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
      if (edge.direction === "fwd") {
        drawArrow(ctx, a, b);
      }
    }
  }

  function drawArrow(ctx, from, to) {
    const angle = Math.atan2(to.y - from.y, to.x - from.x);
    const midX = from.x + (to.x - from.x) * 0.62;
    const midY = from.y + (to.y - from.y) * 0.62;
    const size = 8;
    ctx.save();
    ctx.fillStyle = "#5b6b84";
    ctx.beginPath();
    ctx.moveTo(midX + Math.cos(angle) * size, midY + Math.sin(angle) * size);
    ctx.lineTo(midX + Math.cos(angle + 2.5) * size, midY + Math.sin(angle + 2.5) * size);
    ctx.lineTo(midX + Math.cos(angle - 2.5) * size, midY + Math.sin(angle - 2.5) * size);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
  }

  function drawNodes(ctx) {
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.font = "11px 'Segoe UI', 'Microsoft YaHei', sans-serif";
    for (const node of state.map.nodes) {
      const point = toScreen(node.x_m, node.y_m);
      ctx.beginPath();
      ctx.arc(point.x, point.y, 9, 0, Math.PI * 2);
      ctx.fillStyle = "#1c2330";
      ctx.fill();
      ctx.strokeStyle = "#5b6b84";
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.fillStyle = "#c7d1df";
      ctx.fillText(node.node_id, point.x, point.y - 18);
    }
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
    ctx.beginPath();
    points.forEach((point, index) => {
      if (index === 0) {
        ctx.moveTo(point.x, point.y);
      } else {
        ctx.lineTo(point.x, point.y);
      }
    });
    ctx.strokeStyle = "rgba(255, 209, 102, 0.30)";
    ctx.lineWidth = 12;
    ctx.stroke();
    ctx.strokeStyle = "#ffd166";
    ctx.lineWidth = 3;
    ctx.stroke();

    for (const point of points) {
      ctx.beginPath();
      ctx.arc(point.x, point.y, 5, 0, Math.PI * 2);
      ctx.fillStyle = "#ffd166";
      ctx.fill();
    }

    const start = points[0];
    const end = points[points.length - 1];
    ctx.lineWidth = 2;
    ctx.strokeStyle = "#43c463";
    ctx.beginPath();
    ctx.arc(start.x, start.y, 13, 0, Math.PI * 2);
    ctx.stroke();
    ctx.strokeStyle = "#ff8f3f";
    ctx.strokeRect(end.x - 11, end.y - 11, 22, 22);
    ctx.restore();
  }

  function drawRobots(ctx) {
    if (!state.snapshot) {
      return;
    }
    const radius = Math.max(8, Math.min(18, 0.35 * state.viewport.scale));
    ctx.font = "11px 'Segoe UI', 'Microsoft YaHei', sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    for (const robot of state.snapshot.robots) {
      const meta = STATUS_META[robot.status] || { label: robot.status, color: "#8a94a6" };
      const point = toScreen(robot.x_m, robot.y_m);
      const selected = robot.robot_id === state.selectedRobotId;

      ctx.beginPath();
      ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
      ctx.fillStyle = meta.color;
      ctx.fill();
      ctx.lineWidth = selected ? 3 : 1.5;
      ctx.strokeStyle = selected ? "#ffffff" : "rgba(15, 17, 21, 0.8)";
      ctx.stroke();

      ctx.beginPath();
      ctx.moveTo(point.x, point.y);
      ctx.lineTo(
        point.x + Math.cos(robot.theta_rad) * radius * 1.8,
        point.y - Math.sin(robot.theta_rad) * radius * 1.8,
      );
      ctx.strokeStyle = "#0f1115";
      ctx.lineWidth = 2;
      ctx.stroke();

      ctx.fillStyle = meta.color;
      ctx.fillText(`${robot.robot_id} ${meta.label}`, point.x, point.y - radius - 12);
      ctx.fillStyle = "#c7d1df";
      ctx.fillText(`${robot.v_mps.toFixed(2)} m/s`, point.x, point.y + radius + 12);
    }
  }

  function drawZoneOccupancy(ctx) {
    if (!state.snapshot) {
      return;
    }
    const zonesById = new Map(state.map.zones.map(zone => [zone.zone_id, zone]));
    ctx.font = "11px 'Segoe UI', 'Microsoft YaHei', sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    for (const zoneState of state.snapshot.zones) {
      const holders = zoneState.holder_robot_ids || [];
      const waiting = zoneState.waiting_robot_ids || [];
      if (holders.length === 0 && waiting.length === 0) {
        continue;
      }
      const zone = zonesById.get(zoneState.zone_id);
      if (!zone) {
        continue;
      }
      const label = zoneLabelPoint(zone);
      if (holders.length > 0) {
        ctx.fillStyle = "#ffd166";
        ctx.fillText(`持有: ${holders.join(", ")}`, label.x, label.y + 32);
      }
      if (waiting.length > 0) {
        ctx.fillStyle = "#f5a623";
        ctx.fillText(`等待: ${waiting.join(", ")}`, label.x, label.y + 47);
      }
    }
  }
})();
