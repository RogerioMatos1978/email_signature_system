# Modelo pronto — SESI/SENAI

Gerado a partir do arquivo `Assinatura de E-mail - SESI SENAI.pptx`. Contém:

- `fundo.png` — a arte de fundo (faixa azul, barras coloridas, logos SESI/SENAI, marca d'água), já sem o QR Code e sem os textos de exemplo ("Nome", "Função" etc.) — esses espaços ficam em branco para o sistema desenhar os dados de cada usuário por cima.
- `campos.json` — a posição exata de cada campo (nome, função, e-mail, telefone, QR Code do WhatsApp), calculada a partir das coordenadas originais do PowerPoint.

## Como aplicar

1. Entre como **Administrador** e acesse **Modelos → Novo modelo**.
2. Em "Nome do modelo", coloque algo como `SESI/SENAI`.
3. Em "Imagem de fundo", envie o arquivo `fundo.png` desta pasta.
4. Abra a seção **"Avançado: colar configuração de posições (JSON)"**, cole o conteúdo do arquivo `campos.json` e clique em **Aplicar JSON**.
5. Os marcadores vão se posicionar automaticamente nos lugares corretos (nome, função, e-mail, telefone e QR Code). Se quiser, ajuste manualmente arrastando algum marcador.
6. Clique em **Salvar modelo**.

Pronto — a partir daí, cada usuário padrão só precisa preencher nome, função, e-mail, telefone e (opcionalmente) o QR Code do WhatsApp; o sistema desenha tudo automaticamente sobre esta arte, exatamente nas posições do modelo original em PowerPoint.

## Observação sobre o QR Code

No PowerPoint original havia uma imagem de QR Code de exemplo — ela foi removida do fundo porque, no sistema, **cada usuário envia o próprio QR Code do WhatsApp** na hora de gerar a assinatura, e o sistema o posiciona automaticamente nesse mesmo local.
