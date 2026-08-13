/**
 * Pré-visualização em tempo real da assinatura (100% client-side).
 * Suporta os dois padrões FIEG 2026: "sem_foto" e "com_foto" — ao marcar
 * "Gerar assinatura com foto", o fundo e o layout trocam automaticamente e a
 * foto enviada é desenhada com recorte "cover" e moldura azul.
 */
(function () {
  "use strict";

  var configEl = document.getElementById("templateConfig");
  var canvas = document.getElementById("signaturePreview");
  if (!configEl || !canvas) return;

  var config;
  try {
    config = JSON.parse(configEl.textContent);
  } catch (e) {
    return;
  }

  var variants = config.variants || {};
  var ctx = canvas.getContext("2d");
  var backgrounds = {}; // variante -> {img, loaded}
  var photoImage = null;

  Object.keys(variants).forEach(function (key) {
    if (!variants[key]) return;
    var img = new Image();
    backgrounds[key] = { img: img, loaded: false };
    img.onload = function () {
      backgrounds[key].loaded = true;
      draw();
    };
    img.src = variants[key].backgroundUrl;
  });

  var form = document.getElementById("signatureForm");
  var fieldMap = {
    full_name: form.querySelector("#full_name"),
    role_title: form.querySelector("#role_title"),
    unit: form.querySelector("#unit"),
    signature_email: form.querySelector("#signature_email"),
    phone: form.querySelector("#phone"),
  };
  var photoInput = form.querySelector("#photo");
  var withPhotoCheckbox = form.querySelector("#with_photo");
  var photoFieldWrap = document.getElementById("photoField");
  // Não há mais um campo "WhatsApp" separado: o número aparece como WhatsApp
  // na assinatura só quando "Este telefone também é o WhatsApp" está
  // marcado — nesse caso a linha de Telefone some (mesmo número, uma vez só,
  // igual ao que o servidor gera) e o valor do Telefone é espelhado ali.
  var phoneIsWhatsappCheckbox = form.querySelector("#phone_is_whatsapp");

  function currentVariant() {
    var wantsPhoto = withPhotoCheckbox && withPhotoCheckbox.checked;
    if (wantsPhoto && variants.com_foto) return "com_foto";
    return variants.sem_foto ? "sem_foto" : "com_foto";
  }

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

    if (ctx.measureText(text).width > maxWidthPx) {
      var truncated = text;
      while (truncated.length > 1 && ctx.measureText(truncated + "…").width > maxWidthPx) {
        truncated = truncated.slice(0, -1);
      }
      text = truncated + "…";
    }
    return text;
  }

  function drawField(key, cfg, overrideValue) {
    var el = fieldMap[key];
    var value = overrideValue != null ? overrideValue : (el ? el.value.trim() : "");
    if (!value) return;

    value = value.slice(0, cfg.max_chars || 60);

    var x = (cfg.x_pct || 0) * canvas.width;
    var y = (cfg.y_pct || 0) * canvas.height;
    var maxWidth = Math.max(20, (cfg.box_width_pct || 0.6) * canvas.width);

    var fitted = fitText(value, cfg, maxWidth);

    ctx.fillStyle = cfg.color || "#FFFFFF";
    ctx.textBaseline = "top";

    var textWidth = ctx.measureText(fitted).width;
    var drawX = x;
    if (cfg.align === "center") drawX = x - textWidth / 2;
    if (cfg.align === "right") drawX = x - textWidth;

    ctx.fillText(fitted, drawX, y);
  }

  function drawPhoto(photoCfg) {
    if (!photoImage || !photoCfg) return;

    var boxW = Math.max(10, (photoCfg.width_pct || 0.15) * canvas.width);
    var boxH = Math.max(10, (photoCfg.height_pct || 0.5) * canvas.height);
    var x = (photoCfg.x_pct || 0.05) * canvas.width;
    var y = (photoCfg.y_pct || 0.25) * canvas.height;

    // Recorte "cover": preenche a caixa mantendo a proporção da foto.
    var scale = Math.max(boxW / photoImage.width, boxH / photoImage.height);
    var sw = boxW / scale;
    var sh = boxH / scale;
    var sx = (photoImage.width - sw) / 2;
    var sy = (photoImage.height - sh) / 2;

    ctx.drawImage(photoImage, sx, sy, sw, sh, x, y, boxW, boxH);

    var borderPx = photoCfg.border_px != null ? photoCfg.border_px : 3;
    if (borderPx > 0) {
      ctx.strokeStyle = photoCfg.border_color || "#008BD2";
      ctx.lineWidth = borderPx;
      ctx.strokeRect(x + borderPx / 2, y + borderPx / 2, boxW - borderPx, boxH - borderPx);
    }
  }

  function draw() {
    var variantKey = currentVariant();
    var variant = variants[variantKey];
    var bg = backgrounds[variantKey];
    if (!variant || !bg || !bg.loaded) return;

    canvas.width = variant.width;
    canvas.height = variant.height;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(bg.img, 0, 0, canvas.width, canvas.height);

    var fields = variant.fields || {};
    ["full_name", "role_title", "unit", "signature_email"].forEach(function (key) {
      drawField(key, fields[key] || {});
    });

    // Telefone/WhatsApp: mesmo número, nunca as duas linhas juntas (igual à
    // imagem final gerada no servidor) — com o checkbox marcado, o número
    // aparece só como WhatsApp; sem marcar, só como Telefone.
    var phoneVal = fieldMap.phone ? fieldMap.phone.value.trim() : "";
    var isWhatsapp = !!(phoneIsWhatsappCheckbox && phoneIsWhatsappCheckbox.checked);
    if (isWhatsapp) {
      drawField("whatsapp", fields.whatsapp || {}, phoneVal);
    } else {
      drawField("phone", fields.phone || {});
    }

    if (variantKey === "com_foto") {
      drawPhoto(fields.photo);
    }
  }

  var debounceTimer = null;
  function scheduleDraw() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(draw, 150);
  }

  Object.keys(fieldMap).forEach(function (key) {
    var el = fieldMap[key];
    if (el) el.addEventListener("input", scheduleDraw);
  });

  if (phoneIsWhatsappCheckbox) {
    phoneIsWhatsappCheckbox.addEventListener("change", scheduleDraw);
  }

  if (withPhotoCheckbox) {
    withPhotoCheckbox.addEventListener("change", function () {
      if (photoFieldWrap) {
        photoFieldWrap.classList.toggle("is-hidden", !withPhotoCheckbox.checked);
      }
      draw();
    });
    // Estado inicial (ex.: volta de validação com o checkbox já marcado)
    if (photoFieldWrap) {
      photoFieldWrap.classList.toggle("is-hidden", !withPhotoCheckbox.checked);
    }
  }

  if (photoInput) {
    photoInput.addEventListener("change", function () {
      var file = photoInput.files && photoInput.files[0];
      if (!file || !/^image\/(png|jpe?g)$/i.test(file.type)) {
        photoImage = null;
        draw();
        return;
      }
      var reader = new FileReader();
      reader.onload = function (evt) {
        var img = new Image();
        img.onload = function () {
          photoImage = img;
          draw();
        };
        img.onerror = function () {
          photoImage = null;
        };
        img.src = evt.target.result;
      };
      reader.onerror = function () {
        photoImage = null;
      };
      reader.readAsDataURL(file);
    });
  }
})();
