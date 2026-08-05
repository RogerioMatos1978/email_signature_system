/**
 * Pré-visualização e reposicionamento para a importação em lote
 * (Admin/Supervisor → Importar planilha).
 *
 * Mostra um exemplo de assinatura (dados fictícios) desenhado sobre o fundo
 * do modelo "sem foto" ativo, em um <canvas> — o mesmo mecanismo de
 * renderização usado na pré-visualização do usuário padrão (preview.js).
 * Marcadores arrastáveis sobrepostos ao canvas (mesmo padrão do editor de
 * modelo do admin, template_editor.js) permitem reposicionar cada campo.
 *
 * As posições ajustadas aqui são aplicadas a TODAS as assinaturas geradas
 * nesta importação (enviadas via campo oculto no submit do formulário) —
 * o modelo salvo em Admin → Modelos não é alterado.
 */
(function () {
  "use strict";

  var dataEl = document.getElementById("batchInitialData");
  var stage = document.getElementById("batchStage");
  var canvas = document.getElementById("batchPreviewCanvas");
  var hiddenInput = document.getElementById("batchFieldsJsonInput");
  var form = document.getElementById("batchImportForm");
  var resetBtn = document.getElementById("batchResetBtn");

  if (!dataEl || !stage || !canvas || !hiddenInput || !form) return;

  var initial;
  try {
    initial = JSON.parse(dataEl.textContent);
  } catch (e) {
    return;
  }

  var FIELD_KEYS = ["full_name", "role_title", "unit", "signature_email", "phone"];
  var SAMPLE_VALUES = {
    full_name: "Nome do Colaborador Exemplo",
    role_title: "Cargo de Exemplo",
    unit: "Unidade de Exemplo",
    signature_email: "exemplo.colaborador@fieg.com.br",
    phone: "(62) 00000-0000",
  };

  var savedFields = initial.fields || {};
  var fields = {};

  function resetFields() {
    FIELD_KEYS.forEach(function (key) {
      fields[key] = Object.assign({}, savedFields[key] || {});
    });
  }
  resetFields();

  var ctx = canvas.getContext("2d");
  var bgImage = new Image();
  var bgLoaded = false;

  canvas.width = initial.width;
  canvas.height = initial.height;

  bgImage.onload = function () {
    bgLoaded = true;
    draw();
  };
  bgImage.src = initial.backgroundUrl;

  function fitText(text, cfg, maxWidthPx) {
    var size = cfg.font_size || 18;
    var weight = cfg.bold ? "700" : "400";
    var minSize = 10;

    function setFont(s) {
      ctx.font = weight + " " + s + "px -apple-system, Segoe UI, Roboto, Arial, sans-serif";
    }

    setFont(size);
    while (size > minSize && ctx.measureText(text).width > maxWidthPx) {
      size -= 1;
      setFont(size);
    }
    return text;
  }

  function drawField(key) {
    var cfg = fields[key];
    if (!cfg) return;
    var value = SAMPLE_VALUES[key];

    var x = (cfg.x_pct || 0) * canvas.width;
    var y = (cfg.y_pct || 0) * canvas.height;
    var maxWidth = Math.max(20, (cfg.box_width_pct || 0.4) * canvas.width);

    var fitted = fitText(value, cfg, maxWidth);

    ctx.fillStyle = cfg.color || "#FFFFFF";
    ctx.textBaseline = "top";

    var textWidth = ctx.measureText(fitted).width;
    var drawX = x;
    if (cfg.align === "center") drawX = x - textWidth / 2;
    if (cfg.align === "right") drawX = x - textWidth;

    ctx.fillText(fitted, drawX, y);
  }

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!bgLoaded) return;
    ctx.drawImage(bgImage, 0, 0, canvas.width, canvas.height);
    FIELD_KEYS.forEach(drawField);
  }

  function syncHiddenInput() {
    hiddenInput.value = JSON.stringify(fields);
  }

  function positionMarker(key) {
    var marker = stage.querySelector('.editor-marker[data-field="' + key + '"]');
    var cfg = fields[key];
    if (!marker || !cfg) return;
    marker.style.left = (cfg.x_pct * 100) + "%";
    marker.style.top = (cfg.y_pct * 100) + "%";
  }

  function loadPanelValues() {
    document.querySelectorAll("#batchPanels .editor-panel").forEach(function (panel) {
      var key = panel.getAttribute("data-field-panel");
      var cfg = fields[key];
      if (!cfg) return;
      panel.querySelectorAll("[data-prop]").forEach(function (input) {
        var prop = input.getAttribute("data-prop");
        if (prop === "box_width_pct_pct") {
          input.value = Math.round((cfg.box_width_pct || 0.4) * 100);
        } else if (input.type === "checkbox") {
          input.checked = !!cfg[prop];
        } else {
          input.value = cfg[prop] !== undefined ? cfg[prop] : "";
        }
      });
    });
  }

  function refreshAll() {
    loadPanelValues();
    FIELD_KEYS.forEach(positionMarker);
    draw();
    syncHiddenInput();
  }

  document.querySelectorAll("#batchPanels .editor-panel").forEach(function (panel) {
    var key = panel.getAttribute("data-field-panel");
    panel.querySelectorAll("[data-prop]").forEach(function (input) {
      input.addEventListener("input", function () {
        var prop = input.getAttribute("data-prop");
        var cfg = fields[key];
        if (!cfg) return;

        if (prop === "box_width_pct_pct") {
          cfg.box_width_pct = Math.min(1, Math.max(0.05, Number(input.value) / 100));
        } else if (input.type === "checkbox") {
          cfg[prop] = input.checked;
        } else if (input.type === "number") {
          cfg[prop] = Number(input.value);
        } else {
          cfg[prop] = input.value;
        }
        draw();
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
    draw();
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

  if (resetBtn) {
    resetBtn.addEventListener("click", function () {
      resetFields();
      refreshAll();
    });
  }

  form.addEventListener("submit", syncHiddenInput);

  refreshAll();
})();
