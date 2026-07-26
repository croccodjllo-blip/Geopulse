# Deploy GeoPulse (geopulse.it) su server

Sì: il passo naturale ora è mettere **GeoPulse** su un VPS (consigliato: server dedicato o path separato da VentureOTC), con dominio `geopulse.it`.

## Cosa va in produzione

| Componente | Come |
|------------|------|
| App Flask | Gunicorn in Docker |
| DB | SQLite su volume Docker `/data` (poi Postgres in Fase 5) |
| Proxy | Nginx (compose profile `proxy` oppure host) |
| Secrets | file `.env` sul server |

## 1) Preparazione server

Requisiti: Ubuntu 22.04+, Docker + Docker Compose plugin, porta 80/443 aperte.

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"
```

## 2) Configura `.env` sul server

```bash
cp .env.example .env
```

Obbligatori:

```env
FLASK_SECRET_KEY=<stringa lunga random>
FLASK_DEBUG=0
DATABASE_URL=sqlite:////data/database.db
HOST_PORT=8000
```

Consigliati:

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
SESSION_COOKIE_SECURE=1
PREFERRED_URL_SCHEME=https
```

## 3) Avvio

### Locale / singolo comando

```bash
./scripts/deploy.sh
```

### Su VPS remoto

```bash
REMOTE=root@TUO_IP ./scripts/deploy.sh
```

App in ascolto su `http://SERVER:8000`.

### Con Nginx nel compose

```bash
docker compose --profile proxy up -d
```

## 4) HTTPS (host Nginx + Certbot)

1. Copia `deploy/nginx.host.conf` in `/etc/nginx/sites-available/aio-bot`
2. Sostituisci `aio-bot.example.com` con il tuo dominio
3. `ln -s .../aio-bot /etc/nginx/sites-enabled/`
4. `certbot --nginx -d tuo-dominio.com`

## 5) Stesso VPS di VentureOTC?

Possibile, ma meglio **isolare**:

- directory `/opt/aio-bot`
- container/porte dedicate (`8000`)
- dominio diverso (es. `app.aio-bot.com`)
- **non** mescolare DB/secret con VentureOTC

## Checklist go-live

- [ ] `FLASK_SECRET_KEY` forte
- [ ] `FLASK_DEBUG=0`
- [ ] HTTPS attivo
- [ ] Backup volume `aio_bot_data`
- [ ] `OPENAI_API_KEY` impostata (opzionale ma consigliata)
- [ ] Dominio punta al server

## Comandi utili

```bash
docker compose logs -f aio-bot
docker compose restart aio-bot
docker compose down
docker volume ls | grep aio
```


## Produzione attuale

- Host: `82.165.79.212`
- Path: `/opt/aio-bot`
- Service: `systemctl status aio-bot`
- URL: http://82.165.79.212/login
- Stack: Gunicorn + Nginx (porta 80)

