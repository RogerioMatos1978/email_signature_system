/**
 * Barra de progresso da importação em lote (Admin/Supervisor → Importar
 * planilha).
 *
 * A geração das assinaturas roda em segundo plano no servidor (ver
 * admin/routes.py, _run_batch_import_job) — este script intercepta o envio
 * do formulário, manda os dados via fetch() com o cabeçalho
 * "X-Requested-With: fetch" (o servidor responde com JSON só quando vê esse
 * cabeçalho) e fica perguntando o progresso a cada instante, atualizando a
 * barra, até o lote terminar.
 *
 * Sem JavaScript (ou se o fetch falhar de alguma forma antes de começar), o
 * botão "Salvar só o posicionamento" e o próprio envio normal do formulário
 * continuam funcionando exatamente como antes — o servidor, sem o cabeçalho
 * especial, processa o lote inteiro na mesma requisição e devolve a página
 * de resultado direto, sem barra de progresso.
 */
(function () {
  "use strict";

  var form = document.getElementById("batchImportForm");
  var submitBtn = document.getElementById("batchImportSubmitBtn");
  var urlsEl = document.getElementById("batchImportUrls");
  var progressWrap = document.getElementById("importProgress");
  var progressBar = document.getElementById("importProgressBar");
  var progressLabel = document.getElementById("importProgressLabel");
  var progressError = document.getElementById("importProgressError");

  if (!form || !submitBtn || !urlsEl || !progressWrap || !progressBar || !progressLabel || !progressError) return;

  var urls;
  try {
    urls = JSON.parse(urlsEl.textContent);
  } catch (e) {
    return;
  }

  function urlFor(template, jobId) {
    return template.replace("__ID__", encodeURIComponent(jobId));
  }

  function setProgress(processed, total) {
    var safeTotal = total > 0 ? total : 1;
    var pct = Math.min(100, Math.round((processed / safeTotal) * 100));
    progressBar.style.width = pct + "%";
    progressLabel.textContent = "Gerando " + processed + " de " + total + " assinatura(s)... (" + pct + "%)";
  }

  function showError(message) {
    progressError.textContent = message;
    progressError.classList.remove("is-hidden");
    submitBtn.disabled = false;
  }

  function poll(jobId) {
    fetch(urlFor(urls.progress, jobId), { headers: { "X-Requested-With": "fetch" } })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        setProgress(data.processed, data.total);
        if (data.status === "running") {
          setTimeout(function () { poll(jobId); }, 700);
        } else if (data.status === "done") {
          progressLabel.textContent = "Concluído! Abrindo o resultado...";
          window.location.href = urlFor(urls.result, jobId);
        } else {
          showError(data.error_message || "Falha ao gerar o lote.");
        }
      })
      .catch(function () {
        showError("Não foi possível consultar o progresso da importação. Recarregue a página para tentar de novo.");
      });
  }

  form.addEventListener("submit", function (evt) {
    // Só intercepta o botão principal "Importar e gerar assinaturas" — o
    // botão "Salvar só o posicionamento" (formaction diferente) continua
    // enviando o formulário do jeito normal, sem barra de progresso.
    var submitter = evt.submitter;
    if (submitter && submitter.id && submitter.id !== "batchImportSubmitBtn") return;

    evt.preventDefault();
    progressError.classList.add("is-hidden");
    progressWrap.classList.remove("is-hidden");
    submitBtn.disabled = true;
    progressBar.style.width = "0%";
    progressLabel.textContent = "Enviando planilha...";

    var formData = new FormData(form);
    fetch(urls.start, {
      method: "POST",
      body: formData,
      headers: { "X-Requested-With": "fetch" },
    })
      .then(function (r) {
        return r.json().then(function (data) { return { ok: r.ok, data: data }; });
      })
      .then(function (result) {
        if (!result.ok || !result.data.job_id) {
          progressLabel.textContent = "";
          showError((result.data && result.data.error) || "Não foi possível iniciar a importação.");
          return;
        }
        setProgress(0, result.data.total);
        poll(result.data.job_id);
      })
      .catch(function () {
        progressLabel.textContent = "";
        showError("Falha de conexão ao iniciar a importação. Tente novamente.");
      });
  });
})();
