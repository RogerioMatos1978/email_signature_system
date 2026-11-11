# Guia de deploy — colocar o sistema online na internet

Este guia leva o Sistema de Assinaturas de E-mail do uso atual (rede local,
`http://192.168.x.x:5002`) para um endereço público na internet, com domínio
próprio e HTTPS automático, usando uma VPS (servidor próprio) e o Docker
Compose que o projeto já usa.

Caminho escolhido: **VPS genérica + domínio a registrar + Caddy** (proxy
reverso que obtém e renova o certificado HTTPS sozinho, sem precisar mexer
com Certbot/OpenSSL na mão).

---

## 0. Antes de tudo: segurança — leia isto primeiro

Na revisão do projeto encontrei um problema sério: **o arquivo `.env` real
(com a `SECRET_KEY` e a senha do administrador) estava versionado no Git e já
foi enviado para o repositório no GitHub**
(`github.com/RogerioMatos1978/email_signature_system`). Já corrigi isso no
código (criei um `.gitignore` e tirei o `.env` do controle de versão — veja o
commit `security: remove segredos...`), mas **isso sozinho não desfaz o
vazamento**: o arquivo continua no histórico do repositório.

Faça isto antes de colocar qualquer coisa online:

1. **Verifique se o repositório no GitHub é público ou privado**
   (github.com → o repositório → aba de configurações). Se estiver público,
   trate a `SECRET_KEY` e a senha que estavam no `.env` como definitivamente
   comprometidas — qualquer pessoa pode ter visto.
2. **Torne o repositório privado**, se ainda não for (Settings → General →
   Danger Zone → Change visibility).
3. **Gere uma `SECRET_KEY` nova** (o passo 7 abaixo já mostra como) — nunca
   reaproveite a antiga.
4. **Troque a senha do administrador** — como o banco de dados na VPS vai
   nascer do zero, isso já acontece naturalmente (você define uma senha
   temporária nova no `.env` da VPS, e o sistema já obriga trocá-la no
   primeiro login). Só não reaproveite `Admin@123`.
5. Envie o commit de segurança que já preparei:
   ```bash
   git push
   ```
   (Opcional, avançado: se quiser apagar o `.env` também do **histórico** do
   repositório, não só dos commits novos, é preciso reescrever o histórico
   com `git filter-repo` ou o BFG Repo-Cleaner. Isso é mais trabalhoso e só
   vale a pena se o repositório for público — trocar as credenciais já
   resolve o risco prático na maioria dos casos.)

---

## 1. Contratar a VPS

Um servidor com **1 vCPU, 1–2 GB de RAM e 20 GB de disco** já é suficiente
(o sistema é leve: Flask + SQLite + geração de imagem). Sistema operacional
recomendado: **Ubuntu 22.04 ou 24.04 LTS** (mais fácil de encontrar tutorial
e o Docker tem suporte oficial).

Opções com datacenter no Brasil (menor latência para os usuários da
organização):
- **DigitalOcean** (região São Paulo) — a partir de ~US$6/mês.
- **Vultr** (região São Paulo) — faixa parecida.
- **AWS Lightsail** (região São Paulo) — bom se a organização já usa AWS.

Opções mais baratas (fora do Brasil, funciona igual, só com latência um
pouco maior):
- **Hetzner Cloud** — geralmente a melhor relação custo/benefício (~€4-5/mês).
- **Contabo**, **Oracle Cloud** (tem camada gratuita permanente).

Ao criar a VPS:
- Escolha Ubuntu 22.04/24.04 LTS.
- Configure acesso por **chave SSH** (mais seguro que senha) — a maioria dos
  provedores deixa colar sua chave pública na criação da máquina. Se você
  ainda não tem uma chave SSH no Windows, gere com:
  ```powershell
  ssh-keygen -t ed25519 -C "seu-email@exemplo.com"
  ```
  (aceite o caminho padrão, pode deixar sem senha ou colocar uma — ambos
  funcionam). Cole o conteúdo de `~/.ssh/id_ed25519.pub` no painel do
  provedor.
- Anote o **IP público** da VPS assim que ela for criada.

---

## 2. Registrar o domínio

- Domínio `.com.br`: registre em **registro.br** (~R$40/ano, precisa de
  CPF/CNPJ).
- Domínio `.com` ou outro internacional: **Namecheap**, **Cloudflare
  Registrar** ou **Registro.br** também vende alguns internacionais.

Sugestão de nome: algo como `assinaturas.suaempresa.com.br` (subdomínio) ou
um domínio próprio, como preferir.

---

## 3. Apontar o domínio para a VPS (DNS)

No painel do domínio (registro.br ou onde registrou), crie um registro:

| Tipo | Nome | Valor |
|---|---|---|
| A | `assinaturas` (ou `@` se for o domínio raiz) | IP público da VPS |

A propagação do DNS pode levar de alguns minutos a algumas horas. Para
conferir se já propagou:
```bash
nslookup assinaturas.suaempresa.com.br
```
(deve devolver o IP da sua VPS).

**Importante:** o Caddy (passo 8) só consegue emitir o certificado HTTPS
depois que o DNS já estiver apontando corretamente — não adianta subir o
Caddy antes disso.

---

## 4. Acessar a VPS e instalar o Docker

Do seu computador (PowerShell):
```powershell
ssh root@IP_DA_VPS
```

Na VPS, instale o Docker (script oficial, já traz o Docker Compose junto):
```bash
curl -fsSL https://get.docker.com | sh
```

Confirme que funcionou:
```bash
docker --version
docker compose version
```

---

## 5. Configurar o firewall

Libere só o necessário — SSH, HTTP e HTTPS:
```bash
apt-get update && apt-get install -y ufw
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```
(confirme com "y" quando perguntar — a porta do SSH já está liberada, então
não corre o risco de ficar trancado para fora).

Recomendado também: atualizações de segurança automáticas.
```bash
apt-get install -y unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades
```

---

## 6. Levar o projeto para a VPS

**Opção A — Git (recomendado, facilita atualizar depois):**
```bash
apt-get install -y git
git clone https://github.com/RogerioMatos1978/email_signature_system.git
cd email_signature_system
```
Se o repositório estiver privado, o Git vai pedir usuário/senha — use um
**Personal Access Token** do GitHub no lugar da senha (GitHub → Settings →
Developer settings → Personal access tokens).

**Opção B — Copiar direto do seu PC (mais simples, sem mexer com GitHub na VPS):**
```powershell
scp -r C:\Users\rogeriosm.senai\PycharmProjects\email_signature_system root@IP_DA_VPS:/root/
```
(ou use o WinSCP, interface gráfica, se preferir arrastar e soltar).

---

## 7. Configurar o `.env` de produção

Na VPS, dentro da pasta do projeto:
```bash
cp .env.example .env
nano .env
```

Gere uma `SECRET_KEY` nova:
```bash
openssl rand -hex 32
```
Cole o resultado em `SECRET_KEY=` no `.env`.

Ajuste também no `.env`:
```ini
APP_ENV=production
SECRET_KEY=<cole-o-valor-gerado-acima>
SESSION_COOKIE_SECURE=true
TRUST_PROXY_HEADERS=true
ADMIN_SEED_NAME=Administrador
ADMIN_SEED_USERNAME=admin
ADMIN_SEED_PASSWORD=<defina-uma-senha-forte-temporária>
```
`SESSION_COOKIE_SECURE=true` e `TRUST_PROXY_HEADERS=true` só devem ficar
"true" neste cenário (VPS com Caddy fazendo HTTPS na frente) — é exatamente
o que estamos montando aqui.

Salve e feche (no `nano`: `Ctrl+O`, Enter, `Ctrl+X`).

---

## 8. Configurar o Caddyfile

```bash
cp Caddyfile.example Caddyfile
nano Caddyfile
```
Troque `assinaturas.suaempresa.com.br` pelo seu domínio de verdade (o mesmo
que você apontou no passo 3). Salve e feche.

---

## 9. Subir o sistema

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Acompanhe os logs na primeira subida (o Caddy precisa emitir o certificado —
leva só alguns segundos, mas é bom conferir se não deu erro):
```bash
docker compose -f docker-compose.prod.yml logs -f caddy
```
(`Ctrl+C` para sair do modo "seguindo" os logs — o serviço continua rodando
em segundo plano).

Acesse `https://assinaturas.suaempresa.com.br` no navegador. O cadeado de
HTTPS deve aparecer automaticamente.

---

## 10. Primeiro acesso

Faça login com o usuário/senha definidos em `ADMIN_SEED_USERNAME` /
`ADMIN_SEED_PASSWORD` no `.env`. O sistema já obriga trocar a senha nesse
primeiro login — defina uma senha forte e definitiva.

Depois disso, configure os modelos de assinatura normalmente (Admin →
Modelos), como você já faz no uso local.

---

## Manutenção

**Atualizar o sistema** (depois de puxar mudanças novas do código):
```bash
cd ~/email_signature_system
git pull   # ou reenvie os arquivos alterados, se usou a Opção B do passo 6
docker compose -f docker-compose.prod.yml up -d --build
```
Isso não apaga o banco de dados (fica no volume Docker, fora dos
containers) — só reconstrói a aplicação.

**Ver logs:**
```bash
docker compose -f docker-compose.prod.yml logs -f web
docker compose -f docker-compose.prod.yml logs -f caddy
```

**Backup do banco de dados e arquivos gerados:**
```bash
chmod +x scripts/backup.sh   # só na primeira vez
./scripts/backup.sh
```
Confira antes o nome real do volume com `docker volume ls` — o script
assume `email_signature_system_signature_instance` (nome padrão quando a
pasta do projeto se chama `email_signature_system`); ajuste a variável
`VOLUME_NAME` no início do script se o seu volume tiver outro nome.

Para rodar automaticamente todo dia às 3h da manhã:
```bash
crontab -e
```
e adicione a linha:
```
0 3 * * * cd /root/email_signature_system && ./scripts/backup.sh >> /var/log/backup-assinaturas.log 2>&1
```

**Resetar o banco de dados** (só se precisar mesmo, ex.: mudança de versão
que exige — o CHANGELOG.md avisa quando isso é necessário):
```bash
docker compose -f docker-compose.prod.yml down -v
docker compose -f docker-compose.prod.yml up -d --build
```
`-v` apaga o volume — **faça backup antes** (`./scripts/backup.sh`).

---

## Checklist final de segurança

- [ ] Repositório no GitHub está privado (ou o `.env` antigo foi tratado como
      comprometido e as credenciais foram trocadas).
- [ ] `.env` da VPS tem uma `SECRET_KEY` **nova** (gerada com `openssl rand -hex 32`).
- [ ] `SESSION_COOKIE_SECURE=true` e `TRUST_PROXY_HEADERS=true` no `.env` da VPS.
- [ ] Senha do administrador trocada no primeiro login (o sistema já obriga).
- [ ] `ufw` ativo, só com 22/80/443 liberados.
- [ ] Acesso SSH por chave (não por senha) — opcional, mas recomendado.
- [ ] HTTPS funcionando (cadeado no navegador, sem avisos).
- [ ] Backup configurado (`scripts/backup.sh` + cron).
- [ ] Testado: login, gerar uma assinatura, importar planilha, portal
      público (`/ajuda/outlook`) — tudo funcionando pelo domínio novo.
