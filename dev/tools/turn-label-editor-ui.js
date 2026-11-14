/* Turn label editor — controls, import/export UI and boot. Loaded after
   `turn-label-editor.js`; plain classic scripts so the page works from `file://`. */
"use strict";
function syncControls() {
  const s = setting();
  ui.rotation.value = String(s.rotation);
  ui["rotation-number"].value = String(s.rotation);
  ui.zoom.value = String(s.zoom);
  ui["label-mode"].value = s.mode;
  ui["font-size"].value = String(s.fontSize);
  ui["rotation-value"].textContent = s.rotation + "°";
  ui["zoom-value"].textContent = s.zoom + "%";
  ui["font-size-value"].textContent = s.fontSize + " px";
}
function setRotation(degrees) {
  setting().rotation = Math.max(-180, Math.min(180, Math.round(Number(degrees) || 0)));
  syncControls();
  draw();
  saveStore();
}
ui.track.addEventListener("change", () => {
  state.slug = ui.track.value;
  state.selected = null;
  store.current = state.slug;
  syncControls();
  draw();
  saveStore();
});
ui.rotation.addEventListener("input", () => setRotation(ui.rotation.value));
ui["rotation-number"].addEventListener("change", () => setRotation(ui["rotation-number"].value));
ui.zoom.addEventListener("input", () => {
  setting().zoom = Number(ui.zoom.value);
  syncControls();
  draw();
  saveStore();
});
ui["label-mode"].addEventListener("change", () => {
  setting().mode = ui["label-mode"].value;
  draw();
  saveStore();
});
ui["font-size"].addEventListener("input", () => {
  setting().fontSize = Number(ui["font-size"].value);
  syncControls();
  draw();
  saveStore();
});
["leaders", "dots"].forEach((id) => ui[id].addEventListener("change", draw));
ui["reset-track"].addEventListener("click", () => {
  store.tracks[state.slug] = presetFor(state.slug) || blankTrack();
  state.selected = null;
  syncControls();
  draw();
  saveStore();
});
ui["reset-all"].addEventListener("click", () => {
  Object.keys(store.tracks).forEach((slug) => { delete store.tracks[slug]; });
  state.selected = null;
  syncControls();
  draw();
  saveStore();
});
ui.copy.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(JSON.stringify(exportPayload(), null, 2));
    ui.status.textContent = "Copied the placement JSON to the clipboard.";
  } catch (error) {
    ui.json.select();
    ui.status.textContent = "Clipboard blocked — the JSON is selected, press Ctrl+C.";
  }
});
/** Apply an exported placement: switch to its track and adopt rotation + offsets. */
function importPlacement(text) {
  let payload;
  try { payload = JSON.parse(text); } catch (error) { return describeImport("not valid JSON"); }
  if (!payload || typeof payload !== "object" || !payload.labels) return describeImport("no labels in the file");
  if (payload.tool && payload.tool !== "turn-label-editor") {
    return describeImport('not a turn-label-editor export ("' + payload.tool + '")');
  }
  if (!TRACKS.tracks[payload.track]) return describeImport('unknown track "' + payload.track + '"');
  const placement = placementFromPayload(payload);
  store.tracks[payload.track] = placement;
  state.slug = payload.track;
  state.selected = null;
  store.current = payload.track;
  ui.track.value = payload.track;
  syncControls();
  draw();
  saveStore();
  return describeImport(null, payload, Object.keys(placement.offsets).length);
}
function describeImport(problem, payload, count = 0) {
  ui.status.textContent = problem ? "import failed: " + problem
    : "imported " + count + " label(s) for " + TRACKS.tracks[payload.track].track_name +
      " at " + placementFromPayload(payload).rotation + "°";
  return problem || null;
}
const importFile = document.getElementById("import-file");
document.getElementById("import-button").addEventListener("click", () => importFile.click());
importFile.addEventListener("change", async () => {
  const file = importFile.files && importFile.files[0];
  if (file) importPlacement(await file.text());
  importFile.value = "";
});
["dragover", "drop"].forEach((type) => document.addEventListener(type, (event) => {
  event.preventDefault();
  if (type === "drop" && event.dataTransfer && event.dataTransfer.files.length) {
    event.dataTransfer.files[0].text().then(importPlacement);
  }
}));
ui.download.addEventListener("click", () => {
  const blob = new Blob([JSON.stringify(exportPayload(), null, 2)], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "turn-labels-" + state.slug + ".json";
  link.click();
  URL.revokeObjectURL(link.href);
});

new ResizeObserver(draw).observe(canvas.parentElement);

const slugs = Object.keys(TRACKS.tracks);
ui.track.innerHTML = slugs.map((slug) => {
  const track = TRACKS.tracks[slug];
  const label = track.track_name + (track.layout ? " — " + track.layout : "");
  return '<option value="' + slug + '">' + label.replace(/&/g, "&amp;").replace(/</g, "&lt;") + "</option>";
}).join("");
state.slug = store.current && TRACKS.tracks[store.current] ? store.current : slugs[0];
ui.track.value = state.slug;
store.current = state.slug;
syncControls();
draw();
saveStore();

// Debug/automation hook: the tests drive the editor through this instead of
// scraping the canvas.
window.__turnLabelEditor = { state, store, setting, outline, exportPayload, draw, toScreen,
  labelText, importPlacement, presetFor };
