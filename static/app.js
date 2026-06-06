const state = {
  bootstrap: null,
  records: [],
  selectedRecord: null,
  adminToken: localStorage.getItem("adminToken") || "",
  selectedPhotoFiles: [],
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const roastPositions = {
  "ライトロースト": "8%",
  "シナモンロースト": "20%",
  "ミディアムロースト": "33%",
  "ハイロースト": "46%",
  "シティロースト": "59%",
  "フルシティロースト": "72%",
  "フレンチロースト": "85%",
  "イタリアンロースト": "98%",
};

async function api(path, options = {}) {
  const headers = options.headers || {};
  if (!(options.body instanceof FormData)) headers["Content-Type"] = "application/json";
  if (state.adminToken) headers["X-Admin-Token"] = state.adminToken;
  const res = await fetch(path, { ...options, headers });
  if (!res.ok) {
    const data = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(data.error || res.statusText);
  }
  return res.json();
}

function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2200);
}

function optionList(group, activeOnly = true) {
  return (state.bootstrap?.options?.[group] || []).filter((item) => !activeOnly || item.is_active);
}

function switchView(view) {
  $$(".view").forEach((el) => el.classList.toggle("active", el.id === view));
  $$(".nav-button").forEach((el) => el.classList.toggle("active", el.dataset.view === view));
  $("#page-title").textContent = {
    dashboard: "Dashboard",
    records: "Records",
    editor: "Roast Entry",
    settings: "Settings",
    backup: "Backup",
  }[view];
  $("#page-kicker").textContent = view === "settings" ? "Admin password required" : "";
}

async function loadBootstrap() {
  state.bootstrap = await api("/api/bootstrap");
  hydrateSelects();
  renderDashboard();
  renderSettings();
  renderFlavorInputs();
}

async function loadRecords() {
  const params = new URLSearchParams();
  const filterMap = {
    q: $("#search").value,
    roaster_id: $("#filter-roaster").value,
    roast_level: $("#filter-roast-level").value,
    processing: $("#filter-processing").value,
    taste_rating: $("#filter-rating").value,
    temperature_band: $("#filter-temp-band").value,
    sort: $("#sort-records").value,
  };
  Object.entries(filterMap).forEach(([key, value]) => value && params.set(key, value));
  const data = await api(`/api/records?${params.toString()}`);
  state.records = data.records;
  renderRecords();
}

function hydrateSelects() {
  fillSelect($("[name=roaster_id]"), state.bootstrap.roasters.filter((r) => r.is_active), "id", "name", true);
  fillSelect($("#filter-roaster"), state.bootstrap.roasters.filter((r) => r.is_active), "id", "name", true, "Roaster");
  fillSelect($("[name=processing]"), optionList("processing"), "value", "label", true);
  fillSelect($("#filter-processing"), optionList("processing"), "value", "label", true, "Process");
  fillSelect($("[name=temperature_band]"), optionList("temperature_band"), "value", "label", true);
  fillSelect($("#filter-temp-band"), optionList("temperature_band"), "value", "label", true, "Temp band");
  fillSelect($("[name=taste_rating]"), optionList("taste_rating"), "value", "label", true);
  fillSelect($("#filter-rating"), optionList("taste_rating"), "value", "label", true, "Rating");
  fillSelect($("#filter-roast-level"), optionList("roast_level"), "value", "label", true, "Roast");
  $("#bean-name-list").innerHTML = optionList("bean_name").map((item) => `<option value="${escapeHtml(item.label)}"></option>`).join("");
  renderRoastLevelPicker();
}

function fillSelect(select, items, valueKey, labelKey, includeBlank = false, blankLabel = "") {
  select.innerHTML = includeBlank ? `<option value="">${blankLabel}</option>` : "";
  select.insertAdjacentHTML(
    "beforeend",
    items.map((item) => `<option value="${escapeHtml(item[valueKey])}">${escapeHtml(item[labelKey])}</option>`).join("")
  );
}

function renderDashboard() {
  const stats = state.bootstrap.stats;
  $("#stat-count").textContent = stats.count;
  $("#stat-loss").textContent = stats.avg_loss_rate == null ? "-" : `${stats.avg_loss_rate}%`;
  const topRating = Object.entries(stats.ratings).sort((a, b) => b[1] - a[1])[0];
  $("#stat-rating").textContent = topRating ? topRating[0] : "-";
  $("#stat-recent").textContent = stats.recent[0]?.date || "-";
  $("#recent-list").innerHTML = stats.recent.length
    ? stats.recent.map((record) => `<div class="compact-item"><strong>${escapeHtml(displayName(record))}</strong><span>${record.date}</span></div>`).join("")
    : `<div class="compact-item">No records</div>`;
  drawRadar($("#dashboard-radar"), stats.flavor_average);
}

function renderRecords() {
  $("#record-list").innerHTML = state.records.length
    ? state.records.map(recordRow).join("")
    : `<div class="panel">No records</div>`;
  $$(".record-row").forEach((row) =>
    row.addEventListener("click", (event) => {
      const editButton = event.target.closest("[data-edit]");
      if (editButton) {
        event.stopPropagation();
        openRecordForEdit(Number(editButton.dataset.edit));
        return;
      }
      openRecord(Number(row.dataset.id));
    })
  );
}

function recordRow(record) {
  const roastThumb = roastThumbHtml(record.roast_level);
  const photo = record.photos?.[0] || record.roaster_thumbnail_url;
  const thumb = photo ? `<img class="thumb" src="${photo}" alt="">` : roastThumb;
  return `
    <article class="record-row" data-id="${record.id}">
      ${thumb}
      <div>
        <div class="row-title">${escapeHtml(displayName(record))} <span class="chip">${record.date}</span></div>
        <div class="row-meta">
          <span>${escapeHtml(record.roaster_name || "-")}</span>
          <span>${escapeHtml(record.roast_level || "-")}</span>
          <span>${record.loss_rate == null ? "-" : record.loss_rate + "%"}</span>
          <span>${record.drop_temp_c == null ? "-" : record.drop_temp_c + "°C"}</span>
        </div>
      </div>
      <div class="row-actions"><button data-edit="${record.id}">Edit</button></div>
    </article>`;
}

async function openRecord(id) {
  const data = await api(`/api/records/${id}`);
  state.selectedRecord = data.record;
  renderDetail(data.record);
  switchView("records");
}

function renderDetail(record) {
  $("#record-detail").innerHTML = `
    <div class="detail-title">
      ${roastThumbHtml(record.roast_level)}
      <div><h2>${escapeHtml(displayName(record))}</h2><div class="row-meta">${record.date} / ${escapeHtml(record.roaster_name || "-")}</div></div>
    </div>
    <div class="chips">
      <span class="chip">${escapeHtml(record.roast_level || "-")}</span>
      <span class="chip">${escapeHtml(record.temperature_band || "-")}</span>
      <span class="chip">${record.loss_rate == null ? "-" : record.loss_rate + "% loss"}</span>
      <span class="chip">${record.taste_rating || "-"} rating</span>
    </div>
    <div class="detail-grid">
      ${detailItem("焙煎前", grams(record.green_weight_g))}
      ${detailItem("焙煎後", grams(record.roasted_weight_g))}
      ${detailItem("焙煎時間", record.roast_time || "-")}
      ${detailItem("総時間", record.total_time || "-")}
      ${detailItem("投入温度", temp(record.charge_temp_c))}
      ${detailItem("排出温度", temp(record.drop_temp_c))}
      ${detailItem("1ハゼ開始", temp(record.first_crack_start_temp_c))}
      ${detailItem("2ハゼ開始", temp(record.second_crack_start_temp_c))}
    </div>
    <canvas id="detail-radar" width="320" height="240"></canvas>
    <div class="photo-strip">${(record.photos || []).map((p) => `<img src="${p.url}" alt="">`).join("")}</div>
    <p>${escapeHtml(record.comment || "")}</p>
    <div class="form-actions">
      <button id="show-roast-ref">Roast ref</button>
      <button id="duplicate-record">Duplicate</button>
      <button id="edit-record">Edit</button>
      <button class="danger" id="delete-record">Delete</button>
    </div>`;
  drawRadar(
    $("#detail-radar"),
    state.bootstrap.flavor_axes.filter((a) => a.is_active).map((axis) => ({ label: axis.label, score: record.flavor_scores?.[axis.id] || null }))
  );
  $("#show-roast-ref").onclick = () => $("#image-modal").classList.remove("hidden");
  $("#duplicate-record").onclick = () => duplicateRecord(record.id);
  $("#edit-record").onclick = () => editRecord(record);
  $("#delete-record").onclick = () => deleteRecord(record.id);
}

function detailItem(label, value) {
  return `<div><span>${label}</span><strong>${escapeHtml(value)}</strong></div>`;
}

function renderRoastLevelPicker(selected = null) {
  const current = selected ?? $("[name=roast_level]:checked")?.value ?? "";
  $("#roast-level-picker").innerHTML = optionList("roast_level")
    .map(
      (item) => `
      <label class="roast-option ${current === item.value ? "active" : ""}">
        <input type="radio" name="roast_level" value="${escapeHtml(item.value)}" ${current === item.value ? "checked" : ""}>
        ${roastThumbHtml(item.value)}
        <span>${escapeHtml(item.label)}<small>${escapeHtml(item.category || "")}</small></span>
      </label>`
    )
    .join("");
  $$(".roast-option input").forEach((input) => {
    input.addEventListener("change", () => {
      $$(".roast-option").forEach((el) => el.classList.remove("active"));
      input.closest(".roast-option").classList.add("active");
    });
  });
}

function roastThumbHtml(level) {
  const pos = roastPositions[level] || "50%";
  return `<span class="roast-thumb" style="background-position-y:${pos}"></span>`;
}

function renderFlavorInputs(scores = {}) {
  $("#flavor-inputs").innerHTML = state.bootstrap.flavor_axes
    .filter((axis) => axis.is_active)
    .map(
      (axis) => `
      <label>${escapeHtml(axis.label)}
        <input data-axis="${axis.id}" type="range" min="1" max="5" value="${scores[axis.id] || 3}">
      </label>`
    )
    .join("");
  $$("#flavor-inputs input").forEach((input) => input.addEventListener("input", drawEditorRadar));
  drawEditorRadar();
}

function drawEditorRadar() {
  const data = $$("#flavor-inputs input").map((input) => ({
    label: state.bootstrap.flavor_axes.find((axis) => axis.id == input.dataset.axis)?.label || "",
    score: Number(input.value),
  }));
  drawRadar($("#editor-radar"), data);
}

async function saveRecord(event) {
  event.preventDefault();
  const form = $("#record-form");
  const data = Object.fromEntries(new FormData(form).entries());
  const id = data.id;
  delete data.id;
  data.add_name_option = Boolean(data.add_name_option);
  data.flavor_scores = {};
  $$("#flavor-inputs input").forEach((input) => (data.flavor_scores[input.dataset.axis] = Number(input.value)));
  const saved = await api(id ? `/api/records/${id}` : "/api/records", {
    method: id ? "PUT" : "POST",
    body: JSON.stringify(data),
  });
  const files = state.selectedPhotoFiles;
  if (files.length) {
    const fd = new FormData();
    files.forEach((file) => fd.append("photos", file));
    await api(`/api/records/${saved.record.id}/photos`, { method: "POST", body: fd, headers: {} });
  }
  toast("Saved");
  clearForm();
  await refreshAll();
  await openRecord(saved.record.id);
}

function editRecord(record) {
  switchView("editor");
  const form = $("#record-form");
  form.reset();
  Object.entries(record).forEach(([key, value]) => {
    const input = form.elements[key];
    if (input && value != null && typeof value !== "object") input.value = value;
  });
  renderRoastLevelPicker(record.roast_level || "");
  renderFlavorInputs(record.flavor_scores || {});
}

async function duplicateRecord(id) {
  const data = await api(`/api/records/${id}/duplicate`, { method: "POST", body: "{}" });
  toast("Duplicated");
  await refreshAll();
  editRecord(data.record);
}

async function openRecordForEdit(id) {
  const data = await api(`/api/records/${id}`);
  editRecord(data.record);
}

async function deleteRecord(id) {
  if (!confirm("Delete this record?")) return;
  await api(`/api/records/${id}`, { method: "DELETE" });
  toast("Deleted");
  $("#record-detail").innerHTML = "";
  await refreshAll();
}

function clearForm() {
  $("#record-form").reset();
  $("#record-form [name=id]").value = "";
  $("#record-form [name=date]").value = state.bootstrap.today;
  state.selectedPhotoFiles = [];
  $("#record-photos").value = "";
  renderPhotoPreview();
  renderRoastLevelPicker("");
  renderFlavorInputs();
}

function renderSettings() {
  $("#admin-content").classList.toggle("hidden", !state.adminToken);
  $("#admin-lock").classList.toggle("hidden", Boolean(state.adminToken));
  renderRoasterAdmin();
  renderOptionAdmin();
  renderAxisAdmin();
}

function renderRoasterAdmin() {
  $("#roaster-admin-list").innerHTML = state.bootstrap.roasters
    .map(
      (r) => `
      <div class="admin-item">
        <div>${r.thumbnail_url ? `<img class="thumb" src="${r.thumbnail_url}" alt="">` : `<span class="thumb"></span>`}<strong>${escapeHtml(r.name)}</strong><span class="chip">${r.is_active ? "active" : "off"}</span></div>
        <button data-roaster-edit="${r.id}">Edit</button>
      </div>`
    )
    .join("");
  $$("[data-roaster-edit]").forEach((button) => {
    button.onclick = () => {
      const r = state.bootstrap.roasters.find((item) => item.id == button.dataset.roasterEdit);
      const form = $("#roaster-form");
      form.elements.id.value = r.id;
      form.elements.name.value = r.name;
      form.elements.memo.value = r.memo || "";
      form.elements.sort_order.value = r.sort_order || 0;
      form.elements.is_active.checked = Boolean(r.is_active);
    };
  });
}

function renderOptionAdmin() {
  const labels = { bean_name: "名称", processing: "精選", roast_level: "焙煎度", taste_rating: "評価", temperature_band: "温度帯" };
  $("#option-admin-list").innerHTML = Object.entries(state.bootstrap.options)
    .flatMap(([group, items]) =>
      items.map(
        (item) => `
        <div class="admin-item">
          <div>${group === "roast_level" ? roastThumbHtml(item.value) : ""}<strong>${escapeHtml(item.label)}</strong><span class="chip">${labels[group] || group}</span><span class="chip">${item.is_active ? "active" : "off"}</span></div>
          <button data-option-edit="${item.id}">Edit</button>
        </div>`
      )
    )
    .join("");
  $$("[data-option-edit]").forEach((button) => {
    button.onclick = () => {
      const item = Object.values(state.bootstrap.options).flat().find((option) => option.id == button.dataset.optionEdit);
      const form = $("#option-form");
      form.elements.id.value = item.id;
      form.elements.group_key.value = item.group_key;
      form.elements.label.value = item.label;
      form.elements.description.value = item.description || "";
      form.elements.category.value = item.category || "";
      form.elements.sort_order.value = item.sort_order || 0;
      form.elements.is_active.checked = Boolean(item.is_active);
    };
  });
}

function renderAxisAdmin() {
  $("#axis-admin-list").innerHTML = state.bootstrap.flavor_axes
    .map(
      (axis) => `
      <div class="admin-item">
        <div><strong>${escapeHtml(axis.label)}</strong><span class="chip">${axis.is_active ? "active" : "off"}</span></div>
        <button data-axis-edit="${axis.id}">Edit</button>
      </div>`
    )
    .join("");
  $$("[data-axis-edit]").forEach((button) => {
    button.onclick = () => {
      const axis = state.bootstrap.flavor_axes.find((item) => item.id == button.dataset.axisEdit);
      const form = $("#axis-form");
      form.elements.id.value = axis.id;
      form.elements.label.value = axis.label;
      form.elements.sort_order.value = axis.sort_order || 0;
      form.elements.is_active.checked = Boolean(axis.is_active);
    };
  });
}

async function saveRoaster(event) {
  event.preventDefault();
  const form = event.target;
  const data = Object.fromEntries(new FormData(form).entries());
  const id = data.id;
  data.is_active = form.elements.is_active.checked;
  delete data.id;
  const saved = await api(id ? `/api/roasters/${id}` : "/api/roasters", {
    method: id ? "PUT" : "POST",
    body: JSON.stringify(data),
  });
  const file = $("#roaster-photo").files[0];
  if (file) {
    const fd = new FormData();
    fd.append("photo", file);
    await api(`/api/roasters/${saved.roaster.id}/photo`, { method: "POST", body: fd, headers: {} });
  }
  form.reset();
  form.elements.is_active.checked = true;
  toast("Roaster saved");
  await refreshAll();
}

async function saveOption(event) {
  event.preventDefault();
  const form = event.target;
  const data = Object.fromEntries(new FormData(form).entries());
  const id = data.id;
  data.is_active = form.elements.is_active.checked;
  delete data.id;
  await api(id ? `/api/options/${id}` : "/api/options", { method: id ? "PUT" : "POST", body: JSON.stringify(data) });
  form.reset();
  form.elements.is_active.checked = true;
  toast("Option saved");
  await refreshAll();
}

async function saveAxis(event) {
  event.preventDefault();
  const form = event.target;
  const data = Object.fromEntries(new FormData(form).entries());
  const id = data.id;
  data.is_active = form.elements.is_active.checked;
  delete data.id;
  await api(id ? `/api/flavor-axes/${id}` : "/api/flavor-axes", { method: id ? "PUT" : "POST", body: JSON.stringify(data) });
  form.reset();
  form.elements.is_active.checked = true;
  toast("Axis saved");
  await refreshAll();
}

async function loginAdmin() {
  const password = $("#admin-password").value;
  const data = await api("/api/admin/login", { method: "POST", body: JSON.stringify({ password }) });
  state.adminToken = data.token;
  localStorage.setItem("adminToken", data.token);
  toast("Unlocked");
  renderSettings();
}

async function changePassword(event) {
  event.preventDefault();
  const password = new FormData(event.target).get("password");
  await api("/api/admin/password", { method: "POST", body: JSON.stringify({ password }) });
  event.target.reset();
  toast("Password changed");
}

async function restoreBackup(event) {
  event.preventDefault();
  if (!state.adminToken) return toast("Unlock settings first");
  if (!confirm("Restore backup and replace current data?")) return;
  const file = $("#restore-file").files[0];
  const fd = new FormData();
  fd.append("backup", file);
  await api("/api/backup/import", { method: "POST", body: fd, headers: {} });
  toast("Restored");
  await refreshAll();
}

function setupPhotoDropzone() {
  const dropzone = $("#photo-dropzone");
  const input = $("#record-photos");
  if (!dropzone || !input) return;

  input.addEventListener("change", () => {
    setSelectedPhotos([...input.files]);
  });

  dropzone.addEventListener("click", (event) => {
    if (event.target !== input) input.click();
  });
  dropzone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      input.click();
    }
  });

  ["dragenter", "dragover"].forEach((name) => {
    dropzone.addEventListener(name, (event) => {
      event.preventDefault();
      dropzone.classList.add("dragging");
    });
  });
  ["dragleave", "drop"].forEach((name) => {
    dropzone.addEventListener(name, (event) => {
      event.preventDefault();
      if (name === "dragleave" && dropzone.contains(event.relatedTarget)) return;
      dropzone.classList.remove("dragging");
    });
  });
  dropzone.addEventListener("drop", (event) => {
    const files = [...event.dataTransfer.files].filter((file) => file.type.startsWith("image/"));
    if (!files.length) {
      toast("Image files only");
      return;
    }
    setSelectedPhotos(files);
  });
}

function setSelectedPhotos(files) {
  state.selectedPhotoFiles = files.filter((file) => file.type.startsWith("image/"));
  renderPhotoPreview();
}

function renderPhotoPreview() {
  const count = $("#photo-count");
  const preview = $("#photo-preview");
  if (!count || !preview) return;
  count.textContent = `${state.selectedPhotoFiles.length} file${state.selectedPhotoFiles.length === 1 ? "" : "s"}`;
  preview.innerHTML = "";
  state.selectedPhotoFiles.forEach((file) => {
    const url = URL.createObjectURL(file);
    const img = document.createElement("img");
    img.src = url;
    img.alt = file.name;
    img.onload = () => URL.revokeObjectURL(url);
    preview.appendChild(img);
  });
}

async function refreshAll() {
  await loadBootstrap();
  await loadRecords();
}

function drawRadar(canvas, data) {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  const values = data.filter((d) => d.score != null);
  if (!values.length) {
    ctx.fillStyle = "#66717f";
    ctx.fillText("No flavor data", 20, 30);
    return;
  }
  const cx = w / 2;
  const cy = h / 2 + 8;
  const radius = Math.min(w, h) * 0.34;
  const axes = data.length;
  ctx.strokeStyle = "#dce2e8";
  ctx.fillStyle = "#66717f";
  ctx.font = "12px Segoe UI";
  for (let ring = 1; ring <= 5; ring++) {
    ctx.beginPath();
    for (let i = 0; i < axes; i++) {
      const angle = -Math.PI / 2 + (Math.PI * 2 * i) / axes;
      const r = (radius * ring) / 5;
      const x = cx + Math.cos(angle) * r;
      const y = cy + Math.sin(angle) * r;
      i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
    }
    ctx.closePath();
    ctx.stroke();
  }
  data.forEach((axis, i) => {
    const angle = -Math.PI / 2 + (Math.PI * 2 * i) / axes;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + Math.cos(angle) * radius, cy + Math.sin(angle) * radius);
    ctx.stroke();
    ctx.fillText(axis.label, cx + Math.cos(angle) * (radius + 16) - 18, cy + Math.sin(angle) * (radius + 16) + 4);
  });
  ctx.beginPath();
  data.forEach((axis, i) => {
    const angle = -Math.PI / 2 + (Math.PI * 2 * i) / axes;
    const r = (radius * (Number(axis.score) || 0)) / 5;
    const x = cx + Math.cos(angle) * r;
    const y = cy + Math.sin(angle) * r;
    i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  });
  ctx.closePath();
  ctx.fillStyle = "rgba(47, 111, 99, 0.22)";
  ctx.strokeStyle = "#2f6f63";
  ctx.lineWidth = 2;
  ctx.fill();
  ctx.stroke();
  ctx.lineWidth = 1;
}

function grams(value) {
  return value == null ? "-" : `${value}g`;
}

function displayName(record) {
  return String(record?.name || "").trim() || "無題の焙煎";
}

function temp(value) {
  return value == null ? "-" : `${value}°C`;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function bindEvents() {
  $$(".nav-button").forEach((button) => button.addEventListener("click", () => switchView(button.dataset.view)));
  $("#new-record").onclick = () => {
    clearForm();
    switchView("editor");
  };
  $("#record-form").addEventListener("submit", saveRecord);
  $("#clear-form").onclick = clearForm;
  ["search", "filter-roaster", "filter-roast-level", "filter-processing", "filter-rating", "filter-temp-band", "sort-records"].forEach((id) => {
    $("#" + id).addEventListener("input", loadRecords);
  });
  $("#admin-login").onclick = loginAdmin;
  $("#roaster-form").addEventListener("submit", saveRoaster);
  $("#option-form").addEventListener("submit", saveOption);
  $("#axis-form").addEventListener("submit", saveAxis);
  $("#password-form").addEventListener("submit", changePassword);
  $("#restore-form").addEventListener("submit", restoreBackup);
  $("#close-modal").onclick = () => $("#image-modal").classList.add("hidden");
  setupPhotoDropzone();
}

async function init() {
  bindEvents();
  await refreshAll();
  clearForm();
}

init().catch((error) => toast(error.message));
