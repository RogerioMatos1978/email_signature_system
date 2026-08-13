# Changelog

Este projeto segue [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [2.6.0] — 2026-08-13

### Adicionado

- **Login por CPF para Usuário padrão.** Nova tela **Admin → Usuários → Importar CPFs** (só Administrador): sobe uma planilha (Nome; CPF) e cria uma conta de Usuário padrão para cada linha — login e senha inicial de cada conta são o próprio CPF (somente números; aceita CPF digitado com ou sem pontuação na planilha, mas grava só os dígitos). CPFs duplicados (na própria planilha ou já cadastrados no sistema) são rejeitados e listados no resultado, sem interromper as demais linhas.
- **Admin → Usuários → Novo usuário** também passa a aceitar CPF quando o perfil escolhido é "Usuário padrão": o campo "Usuário" exige um CPF de 11 dígitos e a senha inicial da conta passa a ser o próprio CPF — a tela deixa de mostrar a senha temporária aleatória ("chave de acesso") nesse caso, já que a senha já é conhecida (o CPF). Para os perfis Supervisor e Administrador, nada muda: continuam com usuário livre e senha temporária aleatória gerada pelo sistema, como sempre foi.
- **Busca pública por CPF**: na página "Como inserir sua assinatura no Outlook" (`/ajuda/outlook`), o campo de busca (sem login) passa a aceitar também o CPF do colaborador (somente números), além do nome — encontra a assinatura gerada pela própria conta CPF do usuário. Continua funcionando exatamente como antes para busca por nome.

Sem mudança de banco de dados (usa as colunas já existentes de `users`).

## [2.5.1] — 2026-08-13

### Corrigido

- **Layout do painel: cards distribuídos de forma mais equilibrada na tela**, em vez de ficarem presos a uma faixa central estreita (max-width 1100px) com uma sobra enorme de espaço vazio nas laterais em monitores largos, e cards "órfãos" (ex.: 5 cartões de estatística viravam 4 numa linha + 1 sozinho embaixo). Os grids de cards agora se ajustam automaticamente à largura disponível (CSS `auto-fit`/`minmax`, sem precisar de várias media queries por breakpoint), o container passou a usar até 1400px de largura (antes 1100px), e o padding interno das páginas e dos cards foi reduzido um pouco.

## [2.5.0] — 2026-08-13

### Alterado

- **Unidade / Gerência volta a ser um campo de texto livre**, na geração individual e na importação em lote — deixou de ser a lista fixa de opções (só "UI Rio Verde - Sesi Senai") introduzida na v2.0.0. Na importação por planilha, a coluna "Unidade"/"Gerência" volta a ser obrigatória e o valor de cada linha é usado normalmente (deixou de ser ignorado/sobrescrito).

## [2.4.0] — 2026-08-12

### Segurança

- **Crítico**: o arquivo `.env` (com `SECRET_KEY` e senha do administrador reais) estava versionado no Git e havia sido enviado ao repositório remoto. Adicionado `.gitignore` (não existia antes) e removido `.env`, `__pycache__/`, `.idea/` e afins do controle de versão. **Ação obrigatória para quem for expor o sistema na internet:** gerar uma `SECRET_KEY` nova e trocar a senha de admin — ver seção 0 do `GUIA_DEPLOY.md`.
- Suporte opcional a proxy reverso confiável: `TRUST_PROXY_HEADERS` (padrão `false`) ativa `ProxyFix` (Werkzeug), fazendo o Flask enxergar o IP e o `https` reais do visitante quando o sistema roda atrás de um proxy como Caddy/nginx — necessário para o rate limiting por IP e a auditoria funcionarem corretamente em produção. Só deve ser ativado quando existir de fato um proxy confiável na frente (senão qualquer visitante poderia forjar os cabeçalhos).
- Cabeçalho `Strict-Transport-Security` (HSTS) passa a ser enviado automaticamente quando a requisição chega via HTTPS.

### Adicionado

- `GUIA_DEPLOY.md`: guia passo a passo para colocar o sistema online (VPS, domínio, DNS, Docker, HTTPS automático via Caddy, backup, checklist de segurança).
- `docker-compose.prod.yml`: variante do Compose para produção — o serviço `web` não fica exposto diretamente à internet (só o Caddy, nas portas 80/443).
- `Caddyfile.example` e `scripts/backup.sh` (backup do volume de dados, pronto para agendar via cron).
- `.env.example`: novas variáveis documentadas (`TRUST_PROXY_HEADERS`, `GUNICORN_WORKERS`).

## [2.3.0] — 2026-08-11

### Adicionado
- **Favicon novo**, gerado com as cores oficiais da marca (degradê azul-marinho `#0B4390` → azul FIEG `#008BD2`, envelope branco) — aparece na aba do navegador, nos favoritos e como ícone de atalho em celulares (`apple-touch-icon`). Gerado localmente com Pillow, sem depender de nenhum serviço externo.

### Alterado
- **Ícones de e-mail, telefone e WhatsApp redesenhados**, na mesma linguagem visual do novo favicon — tanto os ícones do menu/interface (app/templates/_icons.html) quanto os desenhados dentro da própria imagem da assinatura quando "Incluir ícones" está marcado (app/utils/image_utils.py). Destaque: o ícone de telefone deixou de ser uma linha diagonal abstrata e virou uma silhueta de aparelho (retângulo arredondado com alto-falante e botão), bem mais reconhecível.

## [2.2.0] — 2026-08-10

### Alterado (mudança de banco e de comportamento)
- **Portal público: assinaturas geradas por importação de planilha não têm mais a trava de "peça ao Supervisor/Administrador" após 1 download.** Como esses colaboradores tipicamente não têm conta de usuário cadastrada no sistema, a trava de download único (pensada para o autoatendimento do usuário padrão) não fazia sentido para eles. Agora: uma assinatura gerada em lote pode ser baixada pelo portal público **até 4 vezes**; ao atingir o limite, o registro é **apagado automaticamente** — não é mais preciso pedir para ninguém reenviar, basta reimportar a planilha (ou gerar de novo individualmente) quando precisar. Assinaturas geradas individualmente (autoatendimento do usuário padrão, ou Admin/Supervisor gerando para alguém específico) continuam com a trava de download único de sempre.
- A busca pública agora mostra "Restam N download(s)" ao lado do botão de baixar, para as assinaturas de lote.
- `signature_records` ganhou as colunas `source` ("individual"/"batch") e `public_download_count`. Requer reset do volume em instalações existentes: `docker compose down -v && docker compose up -d --build`.

## [2.1.0] — 2026-08-10

### Adicionado
- **Barra de progresso na importação em lote**: ao clicar em "Importar e gerar assinaturas", a geração roda em segundo plano no servidor e a tela mostra uma barra de progresso em tempo real ("Gerando X de Y assinatura(s)..."), em vez de ficar sem nenhum retorno visual até o lote inteiro terminar. Sem JavaScript, o comportamento cai automaticamente para o mesmo fluxo de sempre (espera o lote todo e mostra o resultado direto).
- **Terceiro tema do site: "Cor da assinatura"**, além de Branco e Preto — usa a mesma paleta azul da assinatura oficial FIEG (#008BD2) como cor de destaque, com a barra lateral em um degradê azul-marinho → azul, no mesmo espírito visual da própria assinatura gerada. O botão único de alternância virou um seletor de 3 opções (ícones sol / lua / gota).

### Alterado (mudança de banco)
- Nova tabela `import_jobs`, usada para acompanhar o progresso de cada importação em lote. Requer reset do volume em instalações existentes: `docker compose down -v && docker compose up -d --build`.

## [2.0.1] — 2026-08-07

### Corrigido
- **Número de WhatsApp da planilha não estava sendo reconhecido** em cabeçalhos fora da lista exata prevista (ex.: "Nº WhatsApp", "WhatsApp Comercial", "Telefone WhatsApp"). A detecção da coluna agora também aceita correspondência por "contém a palavra" (whatsapp/zap), com prioridade sobre "telefone"/"celular" — cabeçalhos que citam as duas coisas juntas (ex.: "Telefone WhatsApp") agora vão para o campo WhatsApp, não para Telefone.

### Alterado (comportamento)
- **Na importação em lote, o número de WhatsApp da planilha só é usado quando o checkbox "Incluir ícones e número de WhatsApp" está marcado.** Desmarcado, o número é ignorado mesmo que a coluna exista na planilha — antes ele sempre entrava na assinatura se a coluna existisse, independente do checkbox.

## [2.0.0] — 2026-08-07

### Alterado (mudança de banco e de comportamento)
- **Campo "Unidade / Gerência" deixou de ser texto livre e virou uma lista suspensa** com uma única opção hoje: "UI Rio Verde - Sesi Senai". Vale tanto para a geração individual ("Gerar assinatura") quanto para a importação em lote — **se a planilha tiver uma coluna "Unidade"/"Gerência", o valor dela é ignorado e substituído** pela opção fixa. A coluna "Unidade" também deixou de ser obrigatória na planilha (planilhas antigas continuam funcionando normalmente, só que o valor da coluna não é mais usado).
- `signature_records` ganhou as colunas `whatsapp` e `with_icons`. Requer reset do volume em instalações existentes: `docker compose down -v && docker compose up -d --build`.

### Adicionado
- **Ícones opcionais antes do e-mail, telefone e WhatsApp**: novo checkbox "Incluir ícones" na geração individual e na importação em lote (aplica a todo o lote de uma vez). Os ícones (envelope, telefone, balão de mensagem) são desenhados diretamente na imagem — não dependem de nenhuma fonte ter esses símbolos, então funcionam com qualquer texto/acentuação.
- **Segundo telefone (WhatsApp) opcional**: novo campo na geração individual (e coluna opcional "WhatsApp"/"Zap"/"Segundo telefone" reconhecida na importação em lote), exibido logo abaixo do Telefone só quando preenchido. Aparece na confirmação e na Auditoria.
- Editor de modelo (Admin → Modelos) e pré-visualização da importação em lote ganharam o marcador/painel "WhatsApp", para reposicionar esse campo como qualquer outro.

## [1.9.1] — 2026-08-06

### Adicionado
- **Supervisor agora também pode liberar usuários padrão bloqueados** para gerar uma nova assinatura (antes só o Administrador podia). Nova tela enxuta **"Liberar assinaturas"** (no menu do Supervisor) lista só os usuários padrão bloqueados no momento, com um botão "Liberar assinatura" cada — sem dar ao Supervisor acesso ao cadastro completo de usuários (criar, editar, resetar senha e excluir continuam exclusivos do Administrador, em Admin → Usuários).
- O Administrador continua liberando pela tela de Usuários, como antes — nada muda no fluxo dele.

## [1.9.0] — 2026-08-05

### Adicionado
- Na página pública "Como usar no Outlook" (`/ajuda/outlook`): botão **"Entrar no sistema"** (visível só para quem não está logado, leva à tela de login) e botão **"Atualizar página"** (recarrega a página preservando a busca em andamento, se houver).
- **Assinaturas já baixadas pela busca pública agora ficam recolhidas**: quando a busca por nome encontra mais de uma assinatura já baixada, só a mais recente fica visível por padrão — as demais ficam dentro de um "Ver mais N assinatura(s) já baixada(s)" que expande/recolhe ao clicar (usando `<details>`/`<summary>` nativo do HTML, sem depender de JavaScript). Assinaturas ainda disponíveis para baixar continuam sempre todas visíveis.

## [1.8.1] — 2026-08-05

### Corrigido
- **Alinhamento (posição x/y) das duas variantes revisado direto do arquivo PowerPoint original**, com uma extração mais precisa: o arquivo define margem interna zero (`lIns="0" tIns="0"`) em cada caixa de texto, então a posição do texto é exatamente a posição da caixa — sem somar a margem padrão do PowerPoint (0,1"/0,05"), que uma extração anterior havia somado por engano. Isso corrige a posição de **todos os 5 campos nas duas variantes** (não só o Nome da variante "com foto", ajustado na v1.8.0 com base em uma estimativa visual, agora substituída pelo valor exato do arquivo). Tamanhos de fonte, negrito e cores **não foram alterados** — só a posição.
- O exemplo de pré-visualização usado por Administrador e Supervisor (tela de reposicionamento e editor de modelo) usa exatamente os mesmos valores — a leitura do arquivo virou a fonte única da verdade, sem divergência entre o que aparece no editor e o que o servidor realmente gera.
  - **Atenção:** assim como na v1.8.0, isso é uma mudança de *padrão* — modelos já salvos no seu sistema só recebem os novos valores depois de **Admin → Modelos → (modelo) → Restaurar layout padrão**, em cada uma das duas variantes.

## [1.8.0] — 2026-08-05

### Corrigido
- **Borda ao redor da foto (variante "com foto") removida** — o padrão agora não desenha nenhuma moldura (continua configurável no editor visual, para quem quiser reativá-la em um modelo específico).
- **Espaçamento entre Nome e Função na variante "com foto"**: o Nome estava posicionado bem acima do topo da caixa da foto (criando um vão grande e visualmente desalinhado até a Função). Alinhado ao topo da foto — o espaço ficou mais compacto e o Nome acompanha visualmente a foto.
  - **Atenção:** essas duas correções valem para o *padrão* da variante "com foto". Se o modelo já ativo no seu sistema tiver sido salvo/ajustado antes desta versão, ele mantém a configuração antiga até você clicar em **Admin → Modelos → (modelo "Com foto") → Restaurar layout padrão**.
- Corrigido também um desvio entre o editor visual do admin (JavaScript) e os padrões reais do servidor: a largura de texto ("Largura máx. do texto") da variante "com foto" no editor mostrava 42% (valor da variante "sem foto") em vez dos 28% corretos.

### Adicionado
- **Botão "Voltar"** no topo das páginas internas (nova assinatura, confirmar, resultado, histórico, modelos, usuários, auditoria, importar planilha, minha conta), com destino apropriado ao contexto e ao papel de quem está usando.
- **Menu lateral (sidebar)**: a navegação saiu da barra horizontal e passou para uma barra lateral fixa à esquerda, com o nome do sistema no topo dela. Em telas pequenas, vira um menu retrátil (ícone de hambúrguer), como antes.
- **Nome do sistema na barra superior**: a faixa fina no topo do conteúdo agora mostra "Sistema de Assinaturas de E-mail" de forma permanente, além do nome já exibido na sidebar e no rodapé.

## [1.7.0] — 2026-08-05

### Adicionado
- **Administrador e Supervisor podem gerar assinatura individual (com ou sem foto)**, além da importação em lote — antes o Supervisor só tinha acesso à importação de planilha. A trava de "uma geração por vez" (que existe para o Usuário padrão gerar a própria assinatura) não se aplica a Admin/Supervisor, que geram para colaboradores diferentes o tempo todo. Novo link "Gerar assinatura" no menu de ambos.
- **Portal público de autoatendimento** (sem login): a página "Como usar no Outlook" agora é pública e ganhou uma busca por nome — o colaborador procura a própria assinatura (já gerada individualmente ou em lote) e baixa direto, sem precisar de usuário/senha. Depois de baixada, ela some da busca; para baixar de novo é preciso pedir ao Supervisor ou Administrador (que sempre podem, via Auditoria, e reenviar por WhatsApp sem perda de qualidade). Toda busca e todo download ficam registrados em um novo log (Admin → Auditoria → "Ver acessos ao portal público"), com IP de origem. Link de acesso adicionado na tela de login.
- **"Minha conta" agora mostra o nome e o tipo da conta logada** (Administrador / Supervisor / Usuário padrão), além da troca de senha.
- **Tema escuro**: botão de alternância (ícone sol/lua) em todas as telas, com a preferência salva no navegador e detecção automática do tema do sistema operacional no primeiro acesso. Paleta baseada no GitHub Dark (Primer) — um dos temas escuros mais usados atualmente —, com o roxo da marca ajustado para manter bom contraste sobre fundo escuro.

### Alterado (mudança de banco)
- `signature_records` ganhou a coluna `public_downloaded_at` e uma nova tabela `public_access_logs` foi criada. Requer reset do volume em instalações existentes: `docker compose down -v && docker compose up -d --build`.

## [1.6.0] — 2026-08-05

### Adicionado
- **Grade de alinhamento** nas telas de posicionamento (editor de modelo do admin e pré-visualização da importação em lote): linhas guia a cada 10% da imagem, com destaque no centro (50%), sempre visíveis independente da cor de fundo (usa `mix-blend-mode`, funciona sobre áreas claras ou escuras). Ajuda a alinhar Nome/Função/Unidade/E-mail/Telefone entre si sem depender de "olhômetro".
- **Etiqueta do marcador movida para cima do ponto de arraste** (em vez de centralizada sobre ele) — antes cobria o próprio texto de amostra, dificultando ver o alinhamento real; agora um pontinho marca a ancoragem exata e a etiqueta fica logo acima, sem tampar o texto.

### Alterado (mudança de comportamento)
- **O posicionamento escolhido no reposicionamento passa a ser o padrão de todos**: antes, ajustar os campos na pré-visualização da importação em lote valia só para aquele lote específico (o modelo salvo não era tocado). Agora, tanto o Administrador quanto o Supervisor podem salvar o ajuste como o **novo padrão do modelo ativo** (variante "sem foto") — e esse padrão passa a valer também para a **geração individual de assinatura pelos usuários padrão**, já que ambos os fluxos leem a mesma configuração salva no modelo.
- Novo botão **"Salvar só o posicionamento (sem importar planilha)"** em Admin/Supervisor → Importar planilha: permite ajustar e salvar o layout padrão sem precisar ter uma planilha pronta para subir. O botão **"Importar e gerar assinaturas"** também salva a posição ajustada como padrão, além de gerar o lote.
- Escrita no banco só acontece quando a posição realmente muda (comparação antes de salvar), evitando gravações e avisos redundantes quando ninguém arrastou nada.

## [1.5.0] — 2026-08-05

### Adicionado
- **Fonte oficial Neo Sans**: extraída diretamente do PowerPoint "Assinatura de e-mail 2026.pptx" (fontes embutidas em `ppt/fonts/*.fntdata`, formato EOT sem compressão — extração legítima da fonte já licenciada e embutida pela própria organização no seu modelo oficial). Substitui a fonte genérica usada anteriormente; cobertura completa de acentos do português testada. Tamanhos agora batem exatamente com o PowerPoint: Nome 37,8pt negrito, Função/E-mail/Telefone 29,4pt, Unidade 29,4pt negrito.
- **Novo papel Supervisor**: acesso restrito a **Admin → Importar planilha** — não acessa Modelos, Usuários nem Auditoria. Administrador continua com acesso total; Usuário padrão continua restrito à própria assinatura (sem acesso à auditoria, como já era).
- **Pré-visualização e reposicionamento antes da importação em lote**: a tela de importar planilha agora mostra um exemplo de assinatura sobre o modelo ativo, com os campos arrastáveis (mesmo mecanismo do editor de modelo do admin). A posição ajustada vale para **todas as assinaturas geradas naquela importação** — o modelo salvo em Admin → Modelos não é alterado.

### Corrigido
- **Bug real no editor de modelo (drag-and-drop nunca era salvo corretamente): campo `fields_json` estava sendo renderizado duas vezes no HTML** — uma vez por `form.hidden_tag()` e outra manualmente para o JavaScript controlar. O navegador enviava o valor do PRIMEIRO campo com esse nome (desatualizado), descartando silenciosamente a posição arrastada pelo administrador. Corrigido em `admin/template_form.html` e no novo `admin/batch_import.html` — só o CSRF token é renderizado por `hidden_tag()` agora. Isso provavelmente explica reports anteriores de "a fonte não muda mesmo editando".

### Observação sobre licenciamento da fonte
A fonte Neo Sans foi extraída do arquivo PowerPoint oficial da própria organização, que já a tinha embutida com permissão de incorporação. O uso aqui é para gerar as assinaturas oficiais da mesma organização (uso interno), não para redistribuição do arquivo de fonte. Recomendamos confirmar com quem administra a licença da fonte (normalmente a área de marketing/comunicação) se esse uso está de acordo com os termos contratados.

## [1.4.0] — 2026-08-04

### Adicionado
- **Novo padrão oficial FIEG 2026** (a partir do PowerPoint "Assinatura de e-mail 2026.pptx"), em duas variantes, extraídas com precisão do XML do slide (posição, fonte e cor exatas — nome 37px azul `#008BD2` negrito, função/e-mail/telefone 29px branco, unidade 29px branco negrito):
  - **Sem foto**: texto começando em 5,68% da largura.
  - **Com foto**: foto do colaborador com moldura azul de 3px, recortada automaticamente ("cover", sem distorcer o rosto) para caber na caixa 15,6%×51,1%; texto deslocado para 23,4%.
  - Os dois modelos são criados e ativados **automaticamente no primeiro start** (a partir de `modelos_prontos/fieg_2026/`) — o administrador não precisa configurar nada.
- **Novo campo "Unidade / Gerência"** no formulário de assinatura (presente nos dois padrões 2026).
- **Opção "Gerar assinatura com foto"**: cada usuário escolhe, ao gerar a própria assinatura, se quer a variante com ou sem foto — nem todo colaborador usa foto. A pré-visualização em tempo real troca de fundo e layout automaticamente ao marcar/desmarcar.
- **Importação de planilha (Admin → Importar planilha)**: gera assinaturas **sem foto** em lote a partir de um `.xlsx` ou `.csv` (colunas: Nome, Função, Unidade, E-mail, Telefone — até 500 linhas), com download em um único ZIP. Linhas com dados inválidos (e-mail malformado, campo vazio, etc.) são listadas na tela de resultado e não interrompem as demais.
- Admin → Modelos agora suporta **duas variantes de modelo ativas ao mesmo tempo** (uma "sem foto" e uma "com foto"); o editor visual de posições recalcula os padrões ao trocar a variante selecionada.

### Alterado (breaking change)
- Tabela `signature_templates` ganhou a coluna `variant`; `signature_records` trocou `qr_filename` por `photo_filename` e ganhou a coluna `unit`. Requer reset do banco em instalações existentes: `docker compose down -v && docker compose up -d --build`.
- O antigo campo "QR Code do WhatsApp" foi substituído por "Foto do colaborador" (variante com foto) — o padrão SESI/SENAI anterior (`modelos_prontos/sesi_senai/`) continua no projeto para referência, mas o padrão ativo por padrão agora é o FIEG 2026.

## [1.3.1] — 2026-08-04

### Corrigido
- **Telefone visualmente grande demais na assinatura:** o telefone usava a mesma fonte do e-mail (21), mas dígitos têm altura de letra maiúscula — na mesma fonte, um telefone parece ~40% maior que um e-mail todo minúsculo. Fonte padrão do telefone reduzida para **17** (equilíbrio visual com o e-mail), nos três lugares sincronizados: `template_fields.py`, `template_editor.js` e `modelos_prontos/sesi_senai/campos.json`.
- **Alterações de fonte que "não pegavam":** o modelo salvo no banco guarda a configuração da época em que foi salvo — mudar padrões no código não afeta modelos existentes, e a edição visual depende de o JavaScript rodar no navegador. Novo botão **"Restaurar layout padrão"** em **Admin → Modelos**: reaplica o layout padrão completo ao modelo salvo, 100% no servidor (funciona mesmo com JS bloqueado), sem precisar excluir e recriar o modelo.

## [1.3.0] — 2026-08-04

### Adicionado
- **Uma assinatura por liberação:** quando o usuário padrão baixa a assinatura gerada, a geração de novas assinaturas é automaticamente bloqueada para ele. Somente o administrador pode liberá-lo novamente, pelo botão **"Liberar assinatura"** em **Admin → Usuários** (nova coluna "Assinatura" mostra Liberada/Bloqueada). O histórico e o download da assinatura já gerada continuam disponíveis ao usuário; administradores nunca são bloqueados.

### Alterado (breaking change)
- Nova coluna `can_generate_signature` na tabela de usuários — requer reset do banco em instalações existentes (`docker compose down -v && docker compose up -d --build`).

## [1.2.1] — 2026-08-04

### Corrigido
- **Rate limit compartilhado pela rede inteira (crítico para uso em rede local):** em Docker, todos os computadores da rede chegam à aplicação com o mesmo IP interno do proxy do Docker (visível nos logs como `172.19.0.1`). Como os limites eram por IP, o limite de login (8/min — que ainda contava até o simples carregamento da página) e o de geração de assinaturas (20/hora) valiam para TODOS os usuários somados: uma pessoa esgotava o limite da organização inteira. Agora o limite de login é por IP+conta e conta apenas tentativas de envio (POST), e o de geração é por usuário autenticado.
- **Fixação de sessão no login:** a sessão agora é limpa (regenerada) no momento da autenticação, conforme recomendação OWASP — nenhum dado de sessão pré-login sobrevive ao login.
- **Arquivos órfãos ao excluir usuário:** excluir um usuário apagava os registros de auditoria em cascata, mas deixava para sempre no disco as imagens geradas e QR Codes dele. Agora os arquivos são removidos junto (helper centralizado em `app/utils/files.py`, usado também no cancelamento e na limpeza de pendentes).

### Melhorado
- Porta configurável em um único lugar: o `docker-compose.yml` agora interpola `PORT` do `.env` no mapeamento de portas e no healthcheck (e o `HEALTHCHECK` do Dockerfile também usa `${PORT}`) — mudar a porta no `.env` não dessincroniza mais nada.
- Gunicorn com `--worker-tmp-dir /dev/shm` e `--graceful-timeout 30` (boas práticas para Gunicorn em Docker; evita travas espúrias de heartbeat em overlayfs).
- Código: `__import__("json")` substituído por import normal; documentada a limitação do `RATELIMIT_STORAGE_URI=memory://` com múltiplos workers no `.env.example`.

## [1.2.0] — 2026-07-29

### Adicionado
- **Login único por usuário**: cada login gera um token de sessão novo, gravado no banco. Se a mesma conta fizer login em outro dispositivo/navegador, a sessão anterior é encerrada automaticamente na próxima ação, com o aviso "Sua sessão foi encerrada porque este usuário fez login em outro dispositivo ou navegador." Resetar a senha ou desativar um usuário (pelo admin) também encerra imediatamente qualquer sessão aberta dessa conta.
- Acesso pela rede local: aplicação agora sobe na **porta 5002** (antes 5001) e o README traz instruções de acesso por IP de rede local, além de reforçar que `SESSION_COOKIE_SECURE` deve ficar `false` quando o acesso não é por HTTPS (navegadores só isentam "localhost" dessa exigência, não IPs de rede local).

### Alterado (breaking change)
- Nova coluna `current_session_token` na tabela de usuários — requer reset do banco em instalações existentes (`docker compose down -v && docker compose up -d --build`), como em atualizações de schema anteriores.

## [1.1.2] — 2026-07-29

### Corrigido
- O layout padrão usado quando nenhum JSON é colado agora é o padrão oficial da organização (SESI/SENAI): texto em azul marinho (#0B4390), negrito, nas posições exatas do modelo em PowerPoint — e não mais um layout genérico cinza. Isso corrige assinaturas geradas com cor/posição erradas ao criar o modelo sem colar a configuração JSON.
- QR Code agora usa por padrão o tamanho e a posição corretos (canto esquerdo, ~11,5% da largura), evitando que fique grande demais e sobreponha os logos.

> **Se você já tinha criado o modelo sem colar o JSON**, ele ficou salvo com as posições antigas. Vá em **Admin → Modelos**, exclua o modelo atual e crie um novo com a mesma imagem de fundo (`modelos_prontos/sesi_senai/fundo.png`), sem precisar colar nada — o padrão correto agora é aplicado automaticamente.

## [1.1.1] — 2026-07-28

### Corrigido
- Erro "Configuração dos campos: This field is required" ao salvar um modelo quando o JavaScript do editor visual não roda no navegador (bloqueado por antivírus/extensão/JS desabilitado). Agora o campo de posições é opcional no servidor: se vier vazio, aplica-se automaticamente um layout padrão com os 4 campos escalonados verticalmente (sem sobrepor), que pode ser ajustado depois em "Editar modelo". JSON genuinamente malformado continua sendo rejeitado com mensagem clara.

## [1.1.0] — 2026-07-28

### Alterado (breaking change)
- Login trocado de e-mail para **usuário** em todo o sistema (`User.email` → `User.username`). Requer reset do banco em instalações existentes — veja o aviso no README.
- Administrador inicial provisionado por padrão como `EmAssinaturas` / `Admin@123` (via `ADMIN_SEED_USERNAME`/`ADMIN_SEED_PASSWORD` no `.env`); a senha é trocada obrigatoriamente no primeiro login.

## [1.0.2] — 2026-07-28

### Adicionado
- Modelo pronto SESI/SENAI (`modelos_prontos/sesi_senai/`): imagem de fundo extraída do PowerPoint oficial (sem QR/textos de exemplo) + `campos.json` com a posição exata de cada campo, prontos para importar.
- Editor de modelo (admin): seção "Avançado" para colar uma configuração JSON de posições e aplicá-la de uma vez, sem precisar arrastar cada marcador manualmente.

## [1.0.1] — 2026-07-24

### Corrigido
- Falha de validação no formulário de criação/edição de modelo (e no de assinatura) agora sempre exibe uma mensagem de erro visível — antes, uma falha no campo oculto de posições recarregava a página sem nenhum aviso.
- Política de segurança (CSP) ajustada para permitir estilos inline necessários ao editor visual de posicionamento (arrastar marcadores), evitando comportamento visual inconsistente.

## [1.0.0] — 2026-07-24

### Adicionado
- Autenticação com papéis Administrador (100% de acesso) e Usuário padrão.
- Administrador: cadastro do modelo/imagem de fundo padrão da assinatura com editor visual de posicionamento (arrastar e soltar) dos campos.
- Administrador: gestão completa de usuários (criar, editar, ativar/desativar, resetar senha, excluir).
- Administrador: página de auditoria com todas as assinaturas geradas, filtro por usuário e download individual.
- Usuário padrão: formulário para gerar a própria assinatura (nome completo, função, e-mail, telefone, QR Code do WhatsApp opcional).
- Pré-visualização em tempo real (client-side, via canvas) enquanto o usuário digita.
- Fluxo de confirmação obrigatório ("está tudo correto?") antes de gravar a assinatura definitiva na auditoria.
- Geração da imagem final em PNG ou JPG, em resolução adequada para uso como assinatura no Outlook.
- Página de ajuda com o passo a passo oficial da Microsoft para inserir a imagem no Outlook (novo, clássico e web).
- Empacotamento em Docker/Docker Compose, expondo a aplicação na porta **5001**.
- Medidas de segurança: hashing de senha, CSRF, rate limiting, cabeçalhos HTTP de segurança, validação real de imagens (Pillow), remoção de metadados EXIF, proteção contra path traversal, usuário não-root no container.

### O que ele faz: lista todos os usuários que existem no banco e reseta a senha do rogeriomatos para Admin@123.

docker compose exec web python -c "
from app import create_app
from app.extensions import db
from app.models import User

app = create_app()
with app.app_context():
    try:
        users = User.query.all()
        print('Usuarios no banco:')
        for u in users:
            print(f' - {u.username} | papel={u.role} | ativo={u.is_active_flag} | trocar_senha={u.must_change_password}')
        admin = User.query.filter_by(username='EmAssinaturas').first()
        if admin:
            admin.set_password('Admin@123')
            admin.must_change_password = True
            admin.current_session_token = None
            db.session.commit()
            print()
            print('>>> Senha do EmAssinaturas RESETADA para: Admin@123')
        else:
            print()
            print('>>> Usuario EmAssinaturas NAO existe no banco.')
    except Exception as e:
        print('ERRO DE BANCO:', e)
"

docker compose down -v
docker compose up -d --build