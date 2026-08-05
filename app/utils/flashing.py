"""Garante feedback visível ao usuário sempre que um formulário falhar na
validação — inclusive para campos ocultos (ex.: fields_json do editor de
modelo) cujos erros não aparecem em nenhum lugar do HTML renderizado.

Sem isto, uma falha de validação nesses campos fazia a página simplesmente
recarregar em branco, sem qualquer indicação do que deu errado — o usuário
tinha a impressão de que "nada foi salvo" sem saber por quê.
"""
from flask import flash


def flash_form_errors(form, prefix="Não foi possível salvar.") -> None:
    messages = []
    for field_name, errors in form.errors.items():
        field = getattr(form, field_name, None)
        label_text = field.label.text if field is not None and getattr(field, "label", None) else field_name
        for err in errors:
            messages.append(f"{label_text}: {err}")

    if messages:
        flash(prefix + " " + " | ".join(messages), "error")
    else:
        flash(prefix + " Verifique os dados informados e tente novamente.", "error")
