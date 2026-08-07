/**
 * Editor visual de posicionamento dos campos do modelo de assinatura (admin).
 * Suporta as duas variantes do padrão FIEG 2026 ("sem_foto" e "com_foto") —
 * ao trocar a variante no formulário, os padrões de posição/cor mudam junto.
 */
(function () {
  "use strict";

  var stage = document.getElementById("editorStage");
  var bgImg = document.getElementById("editorBgImg");
  var noImageMsg = document.getElementById("editorNoImage");
  var fileInput = document.querySelector('input[name="background_image"]');
  var variantSelect = document.querySelector('select[name="variant"]');
  var hiddenInput = document.getElementById("fieldsJsonInput");
  var form = document.getElementById("templateForm");
  var initialEl = document.getElementById("initialFields");

  if (!stage || !hiddenInput || !form) return;

  // Padrões FIEG 2026 — mesmos valores de app/utils/template_fields.py.
  var TEXT_KEYS = ["full_name", "role_title", "unit", "signature_email", "phone", "whatsapp"];
  var AZUL = "#008BD2";
  var BRANCO = "#FFFFFF";

  // Posições extraídas do slide 1 (sem_foto) do PPTX: box left/top de cada
  // caixa de texto ÷ largura/altura do slide — sem somar recuo interno
  // (lIns/tIns), porque o arquivo zera esses recuos explicitamente
  // (<a:bodyPr lIns="0" tIns="0" anchor="t">). Mesmos valores de
  // app/utils/template_fields.py (fonte da verdade no servidor).
  function textDefaults(x, nameY, boxWidth) {
    return {
      full_name: { x_pct: x, y_pct: nameY, font_size: 37.8, bold: true, align: "left", color: AZUL, max_chars: 40, box_width_pct: boxWidth },
      role_title: { x_pct: x, y_pct: 0.3208, font_size: 29.4, bold: false, align: "left", color: BRANCO, max_chars: 45, box_width_pct: boxWidth },
      unit: { x_pct: x, y_pct: 0.5004, font_size: 29.4, bold: true, align: "left", color: BRANCO, max_chars: 45, box_width_pct: boxWidth },
      signature_email: { x_pct: x, y_pct: 0.5815, font_size: 29.4, bold: false, align: "left", color: BRANCO, max_chars: 50, box_width_pct: boxWidth },
      phone: { x_pct: x, y_pct: 0.6609, font_size: 29.4, bold: false, align: "left", color: BRANCO, max_chars: 30, box_width_pct: boxWidth },
      whatsapp: { x_pct: x, y_pct: 0.7403, font_size: 29.4, bold: false, align: "left", color: BRANCO, max_chars: 30, box_width_pct: boxWidth },
    };
  }

  // com_foto: full_name em y=0,2248 (valor exato do slide 2 do PPTX) — a
  // caixa do Nome nessa variante é mais alta e começa um pouco mais abaixo
  // que na variante sem_foto, ficando com o topo bem próximo do topo da
  // foto (0,2518). Ver mesma explicação em app/utils/template_fields.py.
  var DEFAULTS_BY_VARIANT = {
    sem_foto: Object.assign({}, textDefaults(0.0514, 0.2116, 0.42)),
    com_foto: Object.assign({}, textDefaults(0.2284, 0.2248, 0.28), {
      // Sem moldura por padrão (border_px=0) — mesma justificativa do lado servidor.
      photo: { x_pct: 0.0511, y_pct: 0.2518, width_pct: 0.1563, height_pct: 0.5106, border_color: AZUL, border_px: 0 },
    }),
  };

  function currentVariant() {
    var v = variantSelect ? variantSelect.value : "sem_foto";
    return DEFAULTS_BY_VARIANT[v] ? v : "sem_foto";
  }

  var initial = {};
  try {
    initial = initialEl ? JSON.parse(initialEl.textContent) : {};
  } catch (e) {
    initial = {};
  }

  var fields = {};

  function resetFields(useInitial) {
    var defaults = DEFAULTS_BY_VARIANT[currentVariant()];
    fields = {};
    Object.keys(defaults).forEach(function (key) {
      fields[key] = Object.assign({}, defaults[key], useInitial ? (initial[key] || {}) : {});
    });
    loadPanelValues();
    updateMarkerVisibility();
    Object.keys(fields).forEach(positionMarker);
    syncHiddenInput();
  }

  function syncHiddenInput() {
    hiddenInput.value = JSON.stringify(fields);
  }

  function positionMarker(key) {
    var marker = stage.querySelector('.editor-marker[data-field="' + key + '"]');
    if (!marker || !fields[key]) return;
    marker.style.left = (fields[key].x_pct * 100) + "%";
    marker.style.top = (fields[key].y_pct * 100) + "%";
  }

  function updateMarkerVisibility() {
    var photoMarker = stage.querySelector('.editor-marker[data-field="photo"]');
    var photoPanel = document.querySelector('[data-field-panel="photo"]');
    var hasPhoto = !!fields.photo;
    if (photoMarker) photoMarker.classList.toggle("is-hidden", !hasPhoto || bgImg.classList.contains("is-hidden"));
    if (photoPanel) photoPanel.classList.toggle("is-hidden", !hasPhoto);
  }

  function showEditor() {
    noImageMsg.classList.add("is-hidden");
    bgImg.classList.remove("is-hidden");
    stage.querySelectorAll(".editor-marker").forEach(function (m) {
      m.classList.remove("is-hidden");
    });
    updateMarkerVisibility();
    Object.keys(fields).forEach(positionMarker);
  }

  function loadPanelValues() {
    document.querySelectorAll(".editor-panel").forEach(function (panel) {
      var key = panel.getAttribute("data-field-panel");
      var cfg = fields[key];
      if (!cfg) return;
      panel.querySelectorAll("[data-prop]").forEach(function (input) {
        var prop = input.getAttribute("data-prop");
        if (prop === "box_width_pct_pct") {
          input.value = Math.round((cfg.box_width_pct || 0.4) * 100);
        } else if (prop === "width_pct_pct") {
          input.value = Math.round((cfg.width_pct || 0.16) * 100);
        } else if (prop === "height_pct_pct") {
          input.value = Math.round((cfg.height_pct || 0.51) * 100);
        } else if (input.type === "checkbox") {
          input.checked = !!cfg[prop];
        } else {
          input.value = cfg[prop] !== undefined ? cfg[prop] : "";
        }
      });
    });
  }

  document.querySelectorAll(".editor-panel").forEach(function (panel) {
    var key = panel.getAttribute("data-field-panel");
    panel.querySelectorAll("[data-prop]").forEach(function (input) {
      input.addEventListener("input", function () {
        var prop = input.getAttribute("data-prop");
        var cfg = fields[key];
        if (!cfg) return;

        if (prop === "box_width_pct_pct") {
          cfg.box_width_pct = Math.min(1, Math.max(0.05, Number(input.value) / 100));
        } else if (prop === "width_pct_pct") {
          cfg.width_pct = Math.min(0.6, Math.max(0.03, Number(input.value) / 100));
        } else if (prop === "height_pct_pct") {
          cfg.height_pct = Math.min(1, Math.max(0.03, Number(input.value) / 100));
        } else if (input.type === "checkbox") {
          cfg[prop] = input.checked;
        } else if (input.type === "number") {
          cfg[prop] = Number(input.value);
        } else {
          cfg[prop] = input.value;
        }
        syncHiddenInput();
      });
    });
  });

  // --------------------------------------------------------------- drag
  var dragging = null;

  function onPointerDown(evt) {
    dragging = evt.currentTarget.getAttribute("data-field");
    evt.currentTarget.setPointerCapture(evt.pointerId);
  }

  function onPointerMove(evt) {
    if (!dragging || !fields[dragging]) return;
    var rect = stage.getBoundingClientRect();
    var xPct = (evt.clientX - rect.left) / rect.width;
    var yPct = (evt.clientY - rect.top) / rect.height;
    fields[dragging].x_pct = Math.min(1, Math.max(0, xPct));
    fields[dragging].y_pct = Math.min(1, Math.max(0, yPct));
    positionMarker(dragging);
    syncHiddenInput();
  }

  function onPointerUp() {
    dragging = null;
  }

  stage.querySelectorAll(".editor-marker").forEach(function (marker) {
    marker.addEventListener("pointerdown", onPointerDown);
    marker.addEventListener("pointermove", onPointerMove);
    marker.addEventListener("pointerup", onPointerUp);
    marker.addEventListener("pointercancel", onPointerUp);
  });

  // --------------------------------------------------------------- variante
  if (variantSelect) {
    variantSelect.addEventListener("change", function () {
      // Trocar a variante reaplica os padrões daquela variante (as posições
      // salvas só valem para a variante original do modelo).
      resetFields(false);
    });
  }

  // --------------------------------------------------------------- upload preview
  if (fileInput) {
    fileInput.addEventListener("change", function () {
      var file = fileInput.files && fileInput.files[0];
      if (!file) return;
      if (!/^image\/(png|jpe?g)$/i.test(file.type)) {
        return; // validação real acontece no servidor
      }
      var reader = new FileReader();
      reader.onload = function (evt) {
        bgImg.src = evt.target.result;
        bgImg.onload = showEditor;
      };
      reader.readAsDataURL(file);
    });
  }

  if (bgImg && bgImg.getAttribute("src")) {
    if (bgImg.complete && bgImg.naturalWidth > 0) {
      showEditor();
    } else {
      bgImg.addEventListener("load", showEditor);
    }
  }

  resetFields(true);

  form.addEventListener("submit", function () {
    syncHiddenInput();
  });

  // --------------------------------------------------------------- importar JSON
  var applyBtn = document.getElementById("applyFieldsJsonBtn");
  var importTextarea = document.getElementById("fieldsJsonImport");
  var importError = document.getElementById("fieldsJsonImportError");

  function clamp01(value, fallback) {
    var n = Number(value);
    if (isNaN(n)) return fallback;
    return Math.min(1, Math.max(0, n));
  }

  if (applyBtn && importTextarea) {
    applyBtn.addEventListener("click", function () {
      importError.classList.add("is-hidden");
      var parsed;
      try {
        parsed = JSON.parse(importTextarea.value);
      } catch (e) {
        importError.textContent = "JSON inválido: " + e.message;
        importError.classList.remove("is-hidden");
        return;
      }

      Object.keys(fields).forEach(function (key) {
        var incoming = parsed[key];
        if (!incoming || typeof incoming !== "object") return;
        var cfg = fields[key];
        if ("x_pct" in incoming) cfg.x_pct = clamp01(incoming.x_pct, cfg.x_pct);
        if ("y_pct" in incoming) cfg.y_pct = clamp01(incoming.y_pct, cfg.y_pct);
        if (key === "photo") {
          if ("width_pct" in incoming) cfg.width_pct = clamp01(incoming.width_pct, cfg.width_pct);
          if ("height_pct" in incoming) cfg.height_pct = clamp01(incoming.height_pct, cfg.height_pct);
          if ("border_color" in incoming && /^#[0-9a-fA-F]{6}$/.test(incoming.border_color)) cfg.border_color = incoming.border_color;
          if ("border_px" in incoming) cfg.border_px = Number(incoming.border_px) || cfg.border_px;
        } else {
          if ("font_size" in incoming) cfg.font_size = Number(incoming.font_size) || cfg.font_size;
          if ("bold" in incoming) cfg.bold = !!incoming.bold;
          if ("align" in incoming && ["left", "center", "right"].indexOf(incoming.align) !== -1) cfg.align = incoming.align;
          if ("color" in incoming && /^#[0-9a-fA-F]{6}$/.test(incoming.color)) cfg.color = incoming.color;
          if ("max_chars" in incoming) cfg.max_chars = Number(incoming.max_chars) || cfg.max_chars;
          if ("box_width_pct" in incoming) cfg.box_width_pct = clamp01(incoming.box_width_pct, cfg.box_width_pct);
        }
      });

      loadPanelValues();
      Object.keys(fields).forEach(positionMarker);
      syncHiddenInput();
    });
  }
})();
