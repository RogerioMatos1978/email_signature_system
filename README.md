# Sistema de Assinaturas de E-mail para Outlook — v1.5.0

Sistema web para geração de assinaturas de e-mail em **PNG/JPG** prontas para uso no Outlook, com um administrador que define o modelo visual (imagem de fundo) e usuários padrão que preenchem apenas seus dados. Empacotado em **Docker**, exposto na **porta 5002**, acessível pela rede local. Cada usuário só pode ter uma sessão ativa por vez (novo login em outro dispositivo encerra a sessão anterior automaticamente).

## Sumário

- [Arquitetura e stack](#arquitetura-e-stack)
- [Como rodar (Docker)](#como-rodar-docker)
- [Primeiro acesso](#primeiro-acesso)
- [Fluxo de uso](#fluxo-de-uso)
- [Como inserir a assinatura no Outlook](#como-inserir-a-assinatura-no-outlook)
- [Segurança implementada](#segurança-implementada)
- [Performance e tratamento de erros](#performance-e-tratamento-de-erros)
- [Estrutura de pastas](#estrutura-de-pastas)
- [Backup e persistência](#backup-e-persistência)
- [Roadmap / próximas versões](#roadmap--próximas-versões)

## Arquitetura e stack

- **Backend:** Python 3.11 + Flask 3, SQLAlchemy (SQLite por padrão, pronto para migrar para PostgreSQL).
- **Autenticação:** Flask-Login + senhas com hash (Werkzeug/PBKDF2).
- **Formulários/CSRF:** Flask-WTF + WTForms.
- **Rate limiting:** Flask-Limiter.
- **Imagens:** Pillow (validação, redimensionamento com filtro LANCZOS, composição da assinatura, remoção de EXIF).
- **Servidor de produção:** Gunicorn.
- **Frontend:** HTML/CSS/JS "vanilla", sem dependências externas (sem CDN) — funciona 100% offline dentro do container. Ícones em SVG inline no padrão de e-mail (envelope, telefone, cargo, WhatsApp).
- **Container:** imagem baseada em `python:3.11-slim`, usuário não-root, healthcheck configurado.

## Como rodar (Docker)

1. Copie o arquivo de exemplo de variáveis de ambiente e ajuste os valores:

   ```bash
   cp .env.example .env
   ```

   No mínimo, defina:
   - `SECRET_KEY` — gere uma chave única: `python3 -c "import secrets; print(secrets.token_hex(32))"`
   - `ADMIN_SEED_USERNAME` e `ADMIN_SEED_PASSWORD` — conta de administrador criada automaticamente no primeiro start (já vem preenchido com `EmAssinaturas` / `Admin@123` no `.env.example`; troque a senha se for usar em produção).

2. Suba o container:

   ```bash
   docker compose up -d --build
   ```

3. Acesse:
   - No próprio servidor: **http://localhost:5002**
   - De qualquer outro computador na rede local: **http://IP:5002** (ajuste para o IP atual do servidor, se mudar — veja como descobrir abaixo)

   > O sistema roda na porta **5002** (não usa a porta 5000), tanto internamente quanto no mapeamento do `docker-compose.yml`. O Gunicorn já escuta em `0.0.0.0`, então qualquer máquina na mesma rede local consegue acessar pelo IP do servidor, sem configuração adicional — só verifique se o firewall do Windows libera a porta 5002 para conexões de entrada.

   **Descobrir/confirmar o IP local do servidor** (Windows, PowerShell): `ipconfig` → use o "Endereço IPv4" do adaptador de rede em uso. Se o IP mudar (ex.: renovação de DHCP), acesse pelo novo IP — não é preciso reconfigurar o sistema, pois ele não depende de um IP fixo internamente.

4. Acompanhe os logs, se necessário:

   ```bash
   docker compose logs -f web
   ```

Os dados (banco SQLite + imagens enviadas/geradas) ficam no volume nomeado `signature_instance`, persistente entre reinicializações e atualizações do container.

> **Quer colocar o sistema online, acessível pela internet (não só na rede
> local)?** Veja o [`GUIA_DEPLOY.md`](GUIA_DEPLOY.md) — passo a passo com VPS,
> domínio, HTTPS automático (Caddy) e backup. **Leia a seção 0 do guia antes
> de tudo:** um `.env` com segredos reais chegou a ser versionado no Git neste
> projeto; a `SECRET_KEY` e a senha de admin daquele período devem ser
> tratadas como comprometidas e trocadas.

> **Atualizando de uma instalação anterior à v2.8.0?** Sem mudança de banco —
> basta `docker compose up -d --build` (sem `-v`). Novidades: ícone de
> WhatsApp no Telefone quando marcado como tal, validação de CPF por dígito
> verificador, máscara de CPF no cadastro de usuário, informativo
> Usuário/CPF na tela de login, e a troca de senha deixou de ser obrigatória
> (agora é opcional, em "Minha conta").
>
> **Atualizando de uma instalação anterior à v2.7.2?** Muda o banco (coluna
> `qrcode_filename` removida de `signature_records`) — é preciso resetar o
> volume uma vez:
> ```bash
> docker compose down -v
> docker compose up -d --build
> ```
> O QR Code do WhatsApp em "Gerar assinatura" foi removido por completo, e
> marcar "Este telefone também é o WhatsApp" deixou de deslocar o texto do
> Telefone na imagem — ele agora fica sempre na mesma posição.
>
> **Atualizando de uma instalação anterior à v2.7.1?** Sem mudança de banco —
> basta `docker compose up -d --build` (sem `-v`). Correções em "Gerar
> assinatura": QR Code do WhatsApp aumentado para 36px com posicionamento
> vertical corrigido, e fim da duplicação do número quando "Este telefone
> também é o WhatsApp" está marcado. O campo separado "WhatsApp (opcional)" e
> o ícone automático de WhatsApp foram removidos dessa tela (a importação de
> planilha não foi afetada).
>
> **Atualizando de uma instalação anterior à v2.7.0?** Muda o banco (nova
> coluna `qrcode_filename` em `signature_records`) — é preciso resetar o
> volume uma vez:
> ```bash
> docker compose down -v
> docker compose up -d --build
> ```
> Novidades (só em "Gerar assinatura", não na importação de planilha): upload
> opcional de QR Code do WhatsApp (32x32px, inserido antes do número) e opção
> "Este telefone também é o WhatsApp" no campo Telefone.
>
> **Atualizando de uma instalação anterior à v2.6.0?** Sem mudança de banco —
> basta `docker compose up -d --build` (sem `-v`). Novidade: login por CPF para
> Usuário padrão — nova tela **Admin → Usuários → Importar CPFs** cria contas em
> lote a partir de uma planilha (Nome; CPF), com login e senha inicial iguais
> ao CPF; "Novo usuário" também aceita CPF quando o perfil é "Usuário padrão"
> (Supervisor/Administrador continuam com usuário livre e senha temporária, sem
> mudança). A busca pública em "Como inserir sua assinatura no Outlook" passa a
> aceitar CPF além do nome.
>
> **Atualizando de uma instalação anterior à v2.5.1?** Sem mudança de banco —
> basta `docker compose up -d --build` (sem `-v`). Ajuste de layout: os cards
> do painel se distribuem melhor no espaço disponível em telas largas (não
> ficam mais presos a uma faixa central estreita com espaço vazio nas
> laterais), e o padding geral das páginas ficou um pouco mais enxuto.
>
> **Atualizando de uma instalação anterior à v2.5.0?** Sem mudança de banco —
> basta `docker compose up -d --build` (sem `-v`). O campo "Unidade / Gerência"
> volta a ser texto livre (geração individual e importação em lote) — a lista
> fixa de opções da v2.0.0 foi removida. Na planilha de importação, a coluna
> "Unidade"/"Gerência" volta a ser obrigatória.
>
> **Atualizando de uma instalação anterior à v2.4.0?** Sem mudança de banco —
> basta `docker compose up -d --build` (sem `-v`). Este é um reforço de
> segurança para quem for expor o sistema na internet (não muda nada no uso
> em rede local): `.env` deixou de ser versionado no Git (era um risco de
> vazamento de credenciais), suporte opcional a proxy reverso confiável
> (`TRUST_PROXY_HEADERS`, para IP/HTTPS reais chegarem corretos atrás do
> Caddy/nginx), cabeçalho HSTS quando o acesso é HTTPS, e novos arquivos de
> apoio para deploy em produção (`docker-compose.prod.yml`, `Caddyfile.example`,
> `scripts/backup.sh`, `GUIA_DEPLOY.md`).
>
> **Atualizando de uma instalação anterior à v2.3.0?** Sem mudança de banco —
> basta `docker compose up -d --build` (sem `-v`). Novidades: favicon novo com
> as cores da marca, e ícones de e-mail/telefone/WhatsApp redesenhados (no
> menu e dentro da própria imagem da assinatura, quando "Incluir ícones" está
> marcado) — o ícone de telefone agora é uma silhueta de aparelho, bem mais
> reconhecível.
>
> **Atualizando de uma instalação anterior à v2.2.0?** Muda o banco (novas
> colunas `source` e `public_download_count` em `signature_records`) — é
> preciso resetar o volume uma vez:
> ```bash
> docker compose down -v
> docker compose up -d --build
> ```
> Novidade: assinaturas geradas por importação de planilha deixam de ter a
> trava de "peça ao Supervisor/Administrador" no portal público — agora podem
> ser baixadas até 4 vezes, e o registro é apagado automaticamente ao atingir
> o limite (basta reimportar quando precisar de novo). Assinaturas geradas
> individualmente continuam com a trava de download único de sempre.
>
> **Atualizando de uma instalação anterior à v2.1.0?** Muda o banco (nova
> tabela `import_jobs`) — é preciso resetar o volume uma vez:
> ```bash
> docker compose down -v
> docker compose up -d --build
> ```
> Novidades: barra de progresso ao importar planilha em lote (a geração roda em
> segundo plano e a tela mostra "Gerando X de Y assinatura(s)..." em tempo
> real); terceiro tema do site "Cor da assinatura" (paleta azul FIEG), além de
> Branco e Preto — o botão de tema virou um seletor de 3 opções.
>
> **Atualizando de uma instalação anterior à v2.0.1?** Sem mudança de banco —
> basta `docker compose up -d --build` (sem `-v`). Correções: número de WhatsApp
> da planilha agora é reconhecido mesmo com cabeçalhos fora do padrão exato (ex.:
> "Nº WhatsApp"); e passou a só entrar na assinatura do lote quando o checkbox
> "Incluir ícones e número de WhatsApp" está marcado (antes entrava sempre que a
> coluna existia na planilha, ignorando o checkbox).
>
> **Atualizando de uma instalação anterior à v2.0.0?** Muda o banco (novas colunas
> `whatsapp` e `with_icons` em `signature_records`) — é preciso resetar o volume uma vez:
> ```bash
> docker compose down -v
> docker compose up -d --build
> ```
> Novidades: campo "Unidade / Gerência" virou lista suspensa fixa ("UI Rio Verde -
> Sesi Senai") — na importação em lote, o valor da coluna "Unidade" da planilha passa
> a ser **ignorado** e substituído automaticamente; checkbox opcional para incluir
> ícones antes de e-mail/telefone/WhatsApp; novo campo opcional de segundo telefone
> (WhatsApp).
>
> **Atualizando de uma instalação anterior à v1.9.1?** Sem mudança de banco —
> basta `docker compose up -d --build` (sem `-v`). Novidade: o Supervisor agora
> também pode liberar usuários padrão bloqueados (tela nova "Liberar
> assinaturas" no menu dele) — antes só o Administrador conseguia.

> **Atualizando de uma instalação anterior à v1.9.0?** Sem mudança de banco —
> basta `docker compose up -d --build` (sem `-v`). A página pública "Como usar
> no Outlook" ganhou botões de "Entrar no sistema" e "Atualizar página", e a
> busca de assinatura passou a recolher as já baixadas (só a mais recente fica
> visível, com um "Ver mais" para as demais).

> **Atualizando de uma instalação anterior à v1.8.1?** Sem mudança de banco —
> basta `docker compose up -d --build` (sem `-v`). O alinhamento (posição x/y)
> das duas variantes foi revisado direto do PowerPoint original — mais preciso
> que antes, mas só afeta modelos NOVOS ou restaurados. **Importante:** para
> aplicar aos modelos já ativos, vá em **Admin → Modelos** e clique em
> **Restaurar layout padrão** em cada uma das duas variantes (sem foto e com
> foto).

> **Atualizando de uma instalação anterior à v1.8.0?** Sem mudança de banco —
> basta `docker compose up -d --build` (sem `-v`). Novidades: menu virou lateral
> (com o nome do sistema fixo no topo), botão "Voltar" nas páginas internas, e a
> foto da variante "com foto" perdeu a moldura e ficou melhor alinhada com o
> Nome. **Importante:** se o modelo "Com foto" já ativo no seu sistema foi salvo
> antes desta versão, ele só pega o novo visual depois que um administrador for
> em **Modelos → (modelo "Com foto") → Restaurar layout padrão**.

> **Atualizando de uma instalação anterior à v1.7.0?** Muda o banco (nova coluna
> em `signature_records` + nova tabela `public_access_logs`) — é preciso resetar o
> volume uma vez:
> ```bash
> docker compose down -v
> docker compose up -d --build
> ```
> Novidades: Admin/Supervisor podem gerar assinatura individual (com ou sem foto)
> além da importação em lote; portal público sem login para o colaborador buscar
> e baixar a própria assinatura (na página "Como usar no Outlook"); "Minha conta"
> mostra nome e tipo de conta; e tema escuro com botão de alternância.

> **Atualizando de uma instalação anterior à v1.6.0?** Sem mudança de banco —
> basta `docker compose up -d --build` (sem `-v`). Novidade: o reposicionamento feito em
> Admin/Supervisor → Importar planilha agora **grava o novo padrão no modelo ativo**
> (grade de alinhamento nova ajuda a acertar a posição), passando a valer também para a
> geração individual de assinatura pelos usuários padrão — antes valia só para aquele lote.

> **Atualizando de uma instalação anterior à v1.5.0?** Sem mudança de banco —
> basta `docker compose up -d --build` (sem `-v`). Novidades: fonte Neo Sans oficial nas
> assinaturas FIEG 2026, papel **Supervisor** (acesso só a Admin → Importar planilha) e
> pré-visualização/reposicionamento antes de importar planilhas em lote.

> **Atualizando de uma instalação anterior à v1.1.0?** O login passou a ser feito por
> **usuário**, não mais por e-mail — isso muda a estrutura da tabela de usuários. Como o
> banco (SQLite) não é migrado automaticamente, é preciso resetar o volume uma única vez:
> ```bash
> docker compose down -v
> docker compose up -d --build
> ```
> Isso recria o banco do zero e provisiona o novo administrador (`ADMIN_SEED_USERNAME`/
> `ADMIN_SEED_PASSWORD` do seu `.env`). Se você já tinha configurado um modelo de
> assinatura, reaplique-o normalmente após o reset (os arquivos de modelo prontos, se
> usados, continuam disponíveis em `modelos_prontos/`).

> **Atualizando de uma instalação anterior à v1.4.0?** O padrão visual mudou para o
> **FIEG 2026** (duas variantes: sem foto e com foto), com campo novo de Unidade/Gerência
> e a foto do colaborador substituindo o antigo QR Code do WhatsApp. Isso muda a estrutura
> das tabelas de modelos e registros — é preciso resetar o volume uma vez:
> ```bash
> docker compose down -v
> docker compose up -d --build
> ```
> Os dois modelos FIEG 2026 são criados e ativados automaticamente no primeiro start,
> a partir de `modelos_prontos/fieg_2026/` — nenhuma configuração manual é necessária.

> **Atualizando de uma instalação anterior à v1.2.0?** Duas mudanças:
> 1. A porta padrão mudou de **5001** para **5002** (acompanhe o `.env` e o
>    `docker-compose.yml`, que já vêm atualizados). Se você tinha um `.env` próprio
>    com `PORT=5001`, troque para `PORT=5002` antes de subir o container.
> 2. Login duplo (mesmo usuário logado em dois lugares ao mesmo tempo) agora é
>    bloqueado — isso adiciona uma coluna nova na tabela de usuários, então é
>    necessário resetar o volume uma vez, como no passo anterior (`docker compose down -v`).

## Primeiro acesso

1. Faça login com o usuário/senha definidos em `ADMIN_SEED_USERNAME`/`ADMIN_SEED_PASSWORD` (por padrão: `EmAssinaturas` / `Admin@123`).
2. O sistema exigirá a troca de senha no primeiro login (por segurança).
3. Como administrador, acesse **Modelos** e cadastre a imagem de fundo padrão da assinatura, posicionando os campos (nome, função, unidade, e-mail, telefone e foto) com o editor de arrastar e soltar. Os dois modelos oficiais FIEG 2026 (sem foto / com foto) já vêm prontos e ativados automaticamente.
4. Cadastre os usuários padrão e supervisores em **Usuários** — uma senha temporária é exibida uma única vez na tela; repasse-a com segurança à pessoa (o sistema não envia e-mails).

## Fluxo de uso

O sistema tem três papéis:

**Administrador (100% de acesso):**
- Define/atualiza a imagem de fundo padrão e o layout dos campos, para as duas variantes (sem foto / com foto).
- Cria, edita, ativa/desativa, reseta senha e exclui usuários (padrão, supervisor ou outro administrador).
- Consulta a auditoria completa de todas as assinaturas geradas por todos os usuários (e os acessos ao portal público), com filtro por usuário e download individual.
- Também gera assinaturas — individualmente (com ou sem foto, para qualquer colaborador) ou em lote via planilha — sem nenhuma trava de "uma por vez".

**Supervisor:**
- Acesso a **Gerar assinatura** (individual, com ou sem foto, para qualquer colaborador) e **Importar planilha** (em lote) — não vê Modelos, Usuários nem Auditoria completa.
- Antes de importar em lote, pode visualizar um **exemplo de assinatura** sobre o modelo ativo e **arrastar os campos** para reposicioná-los, com uma grade de alinhamento como guia. **O ajuste salvo vira o novo padrão do modelo** — vale para todas as assinaturas seguintes, geradas em lote ou individualmente pelos usuários padrão. É possível salvar só o posicionamento (botão dedicado), sem precisar importar uma planilha no mesmo momento.
- Também pode **liberar usuários padrão bloqueados** para gerar uma nova assinatura (tela "Liberar assinaturas") — sem acesso ao restante do cadastro de usuários (criar, editar, resetar senha, excluir continuam só do Admin).

**Usuário padrão:**
1. Acessa **Nova assinatura** e preenche: nome completo, função, unidade/gerência, e-mail e telefone.
2. Marca **"Gerar assinatura com foto"** se quiser a variante com foto (nem todo colaborador usa) e envia a foto — ela é recortada automaticamente para caber na moldura, sem distorcer.
3. Acompanha a pré-visualização em tempo real, logo abaixo do formulário, atualizada a cada campo digitado (o fundo troca automaticamente ao marcar/desmarcar "com foto").
4. Ao enviar, o sistema **pede confirmação** ("está tudo correto?") mostrando a imagem final antes de gravar definitivamente.
5. Ao confirmar, a assinatura é registrada na página de auditoria e liberada para download em PNG ou JPG.
6. **Ao baixar a assinatura, a geração de novas assinaturas é bloqueada para o usuário** — o Administrador (em Admin → Usuários) ou o Supervisor (em Liberar assinaturas) podem liberá-lo de novo. O histórico e o download da assinatura já gerada continuam disponíveis.

**Importação em lote (Admin ou Supervisor → Importar planilha):** para gerar várias assinaturas **sem foto** de uma vez (ex.: onboarding de um grupo de colaboradores), envie uma planilha `.xlsx` ou `.csv` com as colunas Nome, Função, Unidade, E-mail e Telefone. Os arquivos gerados usam o **nome do colaborador** (não um código aleatório). O sistema gera todas, registra na auditoria e devolve um ZIP para download; linhas com erro (e-mail inválido, campo vazio) são listadas e não travam as demais.

## Como inserir a assinatura no Outlook

Depois de baixar a imagem gerada, veja o passo a passo em **"Como usar no Outlook"** — **página pública, sem precisar de login** (disponível também no menu, para quem já está autenticado) —, com instruções para:
- Outlook novo (New Outlook para Windows)
- Outlook clássico (desktop)
- Outlook na Web / Outlook.com

Resumo rápido (Outlook clássico): nova mensagem → guia **Mensagem** → **Assinatura → Assinaturas...** → posicionar o cursor na caixa de edição → botão **Imagem** → selecionar o arquivo PNG/JPG gerado → **Inserir** → **OK**.

Fonte oficial: [Microsoft Support — How to add and change an email signature in Outlook](https://support.microsoft.com/en-us/outlook/mail/how-to-add-and-change-an-email-signature-in-outlook).

### Portal público: buscar e baixar a própria assinatura sem login

A mesma página "Como usar no Outlook" tem um campo de busca por nome — pensado para colaboradores que não têm conta no sistema (por exemplo, quem recebeu a assinatura via importação em lote do Supervisor). Basta digitar o nome completo (mínimo 3 caracteres); o sistema mostra as assinaturas com nome parecido (nome, função e unidade, sem expor e-mail/telefone na lista) e o colaborador baixa a que for dele.

Cada assinatura só pode ser baixada **uma vez** por esse caminho — depois disso ela some da lista de "disponíveis" e vira uma entrada "já baixada". Quando a busca encontra mais de uma assinatura já baixada (ex.: a mesma pessoa gerou em datas diferentes), só a mais recente fica visível; as demais ficam atrás de um "Ver mais" para não poluir a lista. Toda busca e todo download feitos ali ficam registrados (com IP de origem) em **Admin → Auditoria → "Ver acessos ao portal público"**. A busca é limitada por IP (`30/min` para buscar, `20/min` para baixar) para dificultar varredura automatizada de nomes.

A página também tem um botão **"Entrar no sistema"** (para quem ainda não tem sessão ativa) e um botão **"Atualizar página"** para recarregar a busca.

## Tema escuro

Um botão de sol/lua (no menu, para quem está logado; no canto da tela, nas páginas públicas) alterna entre tema claro e escuro. A escolha fica salva no navegador; no primeiro acesso, o sistema detecta automaticamente a preferência do sistema operacional. A paleta escura segue o **GitHub Dark** (design system Primer) — fundo `#0d1117`, superfícies `#161b22`, texto `#e6edf3` —, um dos temas escuros mais usados atualmente, com o roxo da marca ajustado para manter boa legibilidade.

## Segurança implementada

- **Autenticação/sessão:** senhas com hash (nunca em texto puro), cookies `HttpOnly`/`SameSite=Lax`/`Secure` (em produção), expiração de sessão, bloqueio de conta desativada.
- **Sessão única por usuário:** cada login gera um novo token de sessão salvo no banco; se o mesmo usuário fizer login em outro dispositivo/navegador, a sessão anterior é automaticamente encerrada na próxima ação (evita duas pessoas usando a mesma conta ao mesmo tempo).
- **CSRF:** todos os formulários e chamadas de estado (POST) protegidos via Flask-WTF.
- **Rate limiting:** login (8/min) e geração de assinatura (20/hora por usuário) para mitigar força bruta e abuso.
- **RBAC:** três papéis (Admin, Supervisor, Usuário padrão) com decoradores `admin_required`/`roles_required` aplicados rota a rota (não um guard único de blueprint) — Supervisor só acessa a importação em lote, Usuário padrão só a própria assinatura. Verificação de propriedade (`user_id`) em toda rota de download/visualização — usuário nunca acessa dados de outro usuário.
- **Upload de imagens:** validação real de conteúdo com Pillow (`verify()` + reabertura), whitelist de extensão/formato (PNG/JPG), limite de tamanho (5MB por arquivo, 6MB por requisição), limite de dimensão (proteção contra "decompression bomb"), nomes de arquivo gerados via `uuid4` (nunca o nome enviado pelo usuário) — evita path traversal e sobrescrita de arquivos.
- **Privacidade:** metadados EXIF (incluindo geolocalização) são removidos ao reprocessar imagens; endereços IP não são armazenados na auditoria.
- **Cabeçalhos HTTP:** `Content-Security-Policy`, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`.
- **SQL Injection:** 100% das consultas via SQLAlchemy ORM (nenhuma query SQL concatenada manualmente).
- **XSS:** auto-escape do Jinja2 habilitado; validação server-side com bloqueio de caracteres de controle nos campos de texto.
- **Erros:** páginas de erro genéricas — nenhum stack trace ou detalhe interno é exposto ao usuário final; exceções são logadas no servidor.
- **Container:** processo roda como usuário não-root; imagem mínima (`slim`); segredos apenas via variáveis de ambiente (nunca hardcoded).

## Performance e tratamento de erros

- Índices de banco em `users.username`, `users.role`, `signature_templates.is_active`, `signature_records.user_id`, `signature_records.created_at` (e índice composto `user_id + created_at`) para consultas de auditoria/histórico rápidas mesmo com grande volume.
- Redimensionamento de imagens com filtro **LANCZOS** (alta qualidade, sem serrilhado) e resolução de saída limitada (padrão 1300px de largura) — nítido em telas comuns e retina, sem gerar arquivos pesados.
- Cache de fontes carregadas em memória (evita reabrir o arquivo `.ttf` a cada caractere renderizado).
- Pré-visualização 100% client-side (canvas) — nenhuma chamada ao servidor a cada tecla digitada.
- Paginação em listagens de usuários, histórico e auditoria (evita carregar toda a tabela de uma vez).
- Ajuste automático do tamanho da fonte (e truncamento com "…" como último recurso) para nomes/funções longos não vazarem da área da assinatura.
- Tratamento explícito de: modelo não configurado, upload vazio, arquivo corrompido/formato inválido, e-mail duplicado, exclusão do último administrador, sessão expirada, arquivo maior que o permitido, e falhas inesperadas (erro 500 genérico, sem detalhes internos).

## Estrutura de pastas

```
email_signature_system/
├── app/
│   ├── blueprints/        # auth, admin, user, main
│   ├── static/             # css, js, fontes (Neo Sans oficial FIEG 2026, com DejaVu Sans como reserva)
│   ├── templates/          # views Jinja2
│   ├── utils/               # validação de imagem, renderização, segurança
│   ├── config.py, extensions.py, models.py, forms.py, seed.py
│   └── __init__.py          # application factory
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh
├── requirements.txt
├── wsgi.py
└── .env.example
```

## Backup e persistência

Todos os dados (banco SQLite, imagens de modelo, QR Codes e assinaturas geradas) ficam no volume Docker `signature_instance`. Para backup:

```bash
docker run --rm -v email_signature_system_signature_instance:/data -v $(pwd):/backup alpine \
  tar czf /backup/backup-assinaturas.tar.gz -C /data .
```

## Roadmap / próximas versões

- Migração de esquema versionada com Flask-Migrate/Alembic (v1 usa `create_all()` idempotente; recomendado para v1.1+ em produção com evolução frequente de schema).
- Suporte a múltiplos modelos ativos por departamento/setor.
- Envio automático das credenciais por e-mail (hoje a senha temporária é exibida apenas em tela, por padrão de segurança sem SMTP configurado).
- Exportação da auditoria em CSV/Excel.
