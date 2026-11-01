/* Resident Information System - map client */
(() => {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  const fmt = (n) => (n == null ? "–" : Number(n).toLocaleString("en-AU"));
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);

  // Data access: the Django REST API by default. The static GitHub Pages build
  // sets window.RIS_BACKEND (static/ris/static-backend.js) to run in-browser.
  const postJSON = (url, body) => fetch(url, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const backend = window.RIS_BACKEND || {
    async meta() { return (await fetch("/api/meta/")).json(); },
    async buildings(params) {
      const res = await fetch(`/api/buildings/?${new URLSearchParams(params)}`);
      if (!res.ok) throw new Error("Could not load buildings.");
      return res.json();
    },
    async areaStats(body) {
      const res = await postJSON("/api/area-stats/", body);
      const data = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(data));
      return data;
    },
    async exportCsv(body) { return (await postJSON("/api/export/", body)).blob(); },
  };

  let META = null;
  let COLORS = {};
  let LABELS = {};
  let currentArea = null;      // geometry sent to the API
  let selectedIds = new Set();
  const markersById = new Map();

  // ---- map ---------------------------------------------------------------
  const map = L.map("map", { preferCanvas: true, zoomControl: true }).setView([-37.8136, 144.9631], 14);
  const renderer = L.canvas({ padding: 0.5 });

  const basemaps = {
    "Light (CARTO)": L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
      maxZoom: 20, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
    }),
    OpenStreetMap: L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }),
    "Satellite (Esri)": L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
      maxZoom: 19, attribution: "Tiles &copy; Esri, Maxar, Earthstar Geographics",
    }),
  };
  basemaps["Light (CARTO)"].addTo(map);
  const buildingLayer = L.layerGroup().addTo(map);
  const drawnItems = new L.FeatureGroup().addTo(map);
  L.control.layers(basemaps, { Buildings: buildingLayer, "Affected area": drawnItems }, { collapsed: true }).addTo(map);
  L.control.scale({ imperial: false }).addTo(map);

  // ---- helpers -----------------------------------------------------------
  function filterParams() {
    const form = $("#filters");
    const fd = new FormData(form);
    const p = {};
    for (const key of ["q", "small_area", "year_min", "year_max", "floors_min"]) {
      const v = (fd.get(key) || "").trim();
      if (v) p[key] = v;
    }
    const risks = fd.getAll("risk");
    if (risks.length && risks.length < META.risk_classes.length) p.risk = risks.join(",");
    if (fd.get("residential")) p.residential = "1";
    return p;
  }

  function radiusFor(props) {
    return props.dwellings > 0 ? Math.min(3 + Math.sqrt(props.dwellings) * 0.6, 12) : 2.5;
  }

  function popupHtml(p) {
    const color = COLORS[p.risk_class];
    const rows = [
      ["Address", p.street_address],
      ["Small area", p.small_area],
      ["Built", p.construction_year || "unknown"],
      ["Refurbished", p.refurbished_year],
      ["Floors", p.floors_above_ground],
      ["Use", p.space_use],
      ["Dwellings", p.dwellings ? `${fmt(p.dwellings)} (${esc(p.dwelling_type)})` : "0"],
      ["Est. residents", p.dwellings ? `≈ ${fmt(Math.round(p.est_residents))}` : "–"],
      ["Accessibility", p.accessibility],
      ["Property ID", p.property_id],
    ].filter(([, v]) => v !== null && v !== undefined && v !== "");
    return `<div class="popup"><h4>${esc(p.building_name || p.street_address || "Building")}</h4>
      <span class="badge" style="background:${color}">${esc(LABELS[p.risk_class])} vulnerability</span>
      <table>${rows.map(([k, v]) => `<tr><th>${k}</th><td>${typeof v === "string" && !v.includes("(") ? esc(v) : v}</td></tr>`).join("")}</table></div>`;
  }

  function styleFor(id, props) {
    const sel = selectedIds.has(id);
    return {
      renderer, radius: radiusFor(props), color: sel ? "#111827" : "#ffffff",
      weight: sel ? 1.5 : 0.5, fillColor: COLORS[props.risk_class], fillOpacity: sel || !selectedIds.size ? 0.8 : 0.25,
    };
  }

  function restyleAll() {
    markersById.forEach((m, id) => m.setStyle(styleFor(id, m.feature.properties)));
  }

  // ---- data loading ------------------------------------------------------
  async function loadBuildings(fit = false) {
    $("#result-count").textContent = "Loading…";
    let fc;
    try { fc = await backend.buildings(filterParams()); }
    catch (err) { $("#result-count").textContent = err.message; return; }
    buildingLayer.clearLayers();
    markersById.clear();
    const bounds = [];
    let residents = 0;
    for (const f of fc.features) {
      const [lon, lat] = f.geometry.coordinates;
      const m = L.circleMarker([lat, lon], styleFor(f.id, f.properties));
      m.feature = f;
      m.bindPopup(() => popupHtml(f.properties), { maxWidth: 320 });
      m.addTo(buildingLayer);
      markersById.set(f.id, m);
      bounds.push([lat, lon]);
      residents += f.properties.est_residents || 0;
    }
    $("#result-count").textContent = `${fmt(fc.features.length)} buildings shown · ≈ ${fmt(Math.round(residents))} est. residents`;
    if (fit && bounds.length) map.fitBounds(bounds, { padding: [30, 30], maxZoom: 17 });
    if (currentArea) analyseArea();
  }

  async function analyseArea() {
    let data;
    try { data = await backend.areaStats({ geometry: currentArea, filters: filterParams() }); }
    catch (err) { alertBox(err.message); return; }
    $("#stats").hidden = false;
    $("#k-buildings").textContent = fmt(data.buildings);
    $("#k-res").textContent = fmt(data.residential_buildings);
    $("#k-dw").textContent = fmt(data.dwellings);
    $("#k-people").textContent = "≈ " + fmt(data.est_residents);
    const meta = [];
    if (data.area_km2) meta.push(`Area ${data.area_km2.toLocaleString("en-AU", { maximumFractionDigits: 3 })} km²`);
    if (data.floors_max) meta.push(`tallest ${data.floors_max} floors`);
    if (data.oldest_construction_year) meta.push(`oldest built ${data.oldest_construction_year}`);
    $("#stats-meta").textContent = meta.join(" · ");
    const maxB = Math.max(1, ...data.by_risk.map((r) => r.est_residents));
    $("#risk-bars").innerHTML = data.by_risk.map((r) => `
      <div class="bar" title="${esc(r.description)}">
        <span>${esc(r.label)}</span>
        <span class="track"><span class="fill" style="display:block;width:${(100 * r.est_residents) / maxB}%;background:${r.color}"></span></span>
        <span class="val">${fmt(r.buildings)} / ${fmt(r.est_residents)}</span>
      </div>`).join("") + '<p class="hint">buildings / est. residents</p>';
    $("#priority").innerHTML = data.priority_buildings.length
      ? data.priority_buildings.map((b) => `<li data-id="${b.id}">${esc(b.building_name || b.street_address)} – ${fmt(b.dwellings)} dw., ≈ ${fmt(Math.round(b.est_residents))} people, built ${b.construction_year ?? "?"}</li>`).join("")
      : '<li class="hint">No residential pre-1980 buildings in this area.</li>';
    selectedIds = new Set(data.ids);
    restyleAll();
  }

  function alertBox(msg) { $("#stats-meta").textContent = msg; }

  function geometryFromLayer(layer) {
    if (layer instanceof L.Circle) {
      const c = layer.getLatLng();
      return { type: "Circle", center: [c.lng, c.lat], radius: layer.getRadius() };
    }
    return layer.toGeoJSON().geometry;
  }

  // ---- drawing -----------------------------------------------------------
  const shapeOpts = { color: "#1d4ed8", weight: 2, fillOpacity: 0.08 };
  const drawers = {
    polygon: new L.Draw.Polygon(map, { shapeOptions: shapeOpts, allowIntersection: false, showArea: true }),
    rectangle: new L.Draw.Rectangle(map, { shapeOptions: shapeOpts }),
    circle: new L.Draw.Circle(map, { shapeOptions: shapeOpts }),
  };
  for (const [kind, drawer] of Object.entries(drawers)) {
    $(`#draw-${kind}`).addEventListener("click", () => {
      Object.values(drawers).forEach((d) => d.disable());
      drawer.enable();
      closePanelOnMobile();
    });
  }
  map.on(L.Draw.Event.CREATED, (e) => {
    drawnItems.clearLayers();
    drawnItems.addLayer(e.layer);
    currentArea = geometryFromLayer(e.layer);
    analyseArea();
    openPanelOnMobile();
  });
  $("#clear-area").addEventListener("click", () => {
    drawnItems.clearLayers();
    currentArea = null;
    selectedIds = new Set();
    $("#stats").hidden = true;
    restyleAll();
  });
  $("#priority").addEventListener("click", (e) => {
    const id = Number(e.target.closest("li")?.dataset.id);
    const m = markersById.get(id);
    if (m) { map.setView(m.getLatLng(), 18); m.openPopup(); closePanelOnMobile(); }
  });
  $("#export").addEventListener("click", async () => {
    const blob = await backend.exportCsv({ geometry: currentArea, filters: filterParams() });
    const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: "ris_selection.csv" });
    document.body.appendChild(a); a.click(); a.remove();
  });

  // ---- filters -----------------------------------------------------------
  $("#filters").addEventListener("submit", (e) => { e.preventDefault(); loadBuildings(true); });
  $("#small-area").addEventListener("change", () => loadBuildings(true));
  $("#reset").addEventListener("click", () => {
    $("#filters").reset();
    document.querySelectorAll('#risk-boxes input').forEach((i) => (i.checked = true));
    loadBuildings(true);
  });

  // ---- mobile panel ------------------------------------------------------
  const sidebar = $("#sidebar");
  $("#toggle").addEventListener("click", () => sidebar.classList.toggle("open"));
  function closePanelOnMobile() { if (window.innerWidth <= 760) sidebar.classList.remove("open"); }
  function openPanelOnMobile() { if (window.innerWidth <= 760) sidebar.classList.add("open"); }

  // ---- legend ------------------------------------------------------------
  function addLegend() {
    const legend = L.control({ position: "bottomright" });
    legend.onAdd = () => {
      const div = L.DomUtil.create("div", "legend");
      div.innerHTML = "<strong>Vulnerability (by construction year)</strong>" + META.risk_classes
        .map((r) => `<div><span class="swatch" style="background:${r.color}"></span>${esc(r.description)}</div>`).join("")
        + '<div class="hint">Marker size ∝ number of dwellings</div>';
      return div;
    };
    legend.addTo(map);
  }

  // ---- init --------------------------------------------------------------
  async function init() {
    META = await backend.meta();
    if (window.RIS_BACKEND) document.querySelectorAll(".server-only").forEach((el) => el.remove());
    META.risk_classes.forEach((r) => { COLORS[r.key] = r.color; LABELS[r.key] = r.label; });
    $("#hh").textContent = META.persons_per_dwelling;
    $("#dataset-summary").textContent = META.buildings
      ? `${fmt(META.buildings)} buildings · ${fmt(META.dwellings)} dwellings · ≈ ${fmt(META.est_residents)} residents (CLUE ${META.census_year})`
      : "No data loaded yet – run the import commands (see README).";
    const sel = $("#small-area");
    for (const a of META.small_areas) sel.add(new Option(`${a.name} (${a.buildings})`, a.name));
    $("#risk-boxes").innerHTML = META.risk_classes.map((r) => `
      <label><input type="checkbox" name="risk" value="${r.key}" checked>
      <span class="swatch" style="background:${r.color}"></span>${esc(r.label)}</label>`).join("");
    addLegend();
    await loadBuildings(true);
  }
  init();
})();
