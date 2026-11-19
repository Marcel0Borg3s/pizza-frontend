# pizza_frontend

![Python](https://img.shields.io/badge/python-3.13-blue)
![Django](https://img.shields.io/badge/django-6.1-092E20)
![Tailwind](https://img.shields.io/badge/Tailwind-4-38BDF8)
![Feito com IA](https://img.shields.io/badge/feito%20com-IA%20%2B%20Hermes-8b5cf6)

Front de estudo para a API [pizza-drf](https://github.com/Marcel0Borg3s/pizza-drf): um
site de pedidos de pizza (cardápio, carrinho, pedidos, avaliações e painel do dono) que
consome as APIs reais do backend, sempre pelo servidor.

> **Projeto 100% gerado com IA.** Todo o código foi escrito pelo
> [Hermes Agent](https://hermes-agent.nousresearch.com/docs) rodando o modelo
> **DeepSeek V4.1 Flash**, a partir de prompts e de decisões de orientação humana.
> O propósito é estudar consumo de API, simular o uso real de uma aplicação e servir de
> base de teste para o backend, não é um sistema pronto para produção
> (veja [limitações](#limitações-conhecidas-projeto-de-estudo)).

- Front (este projeto): `http://127.0.0.1:8001`
- API: https://github.com/Marcel0Borg3s/pizza-drf (`http://127.0.0.1:8000`)

## Arquitetura (BFF)

```
navegador  ──HTTP──▶  pizza_frontend (Django 6 + templates + Tailwind)
                            │
                            └──HTTP (servidor para servidor)──▶  pizza_drf (DRF)
                                                                  /clients/
                                                                  /pizzas/
                                                                  /reviews/
```

O navegador nunca chama a API diretamente:

- não existe CORS;
- nenhum token ou credencial vai para o HTML;
- toda chamada passa por `core/api/client.py` (timeout, erros tipados, telemetria).

## Como este projeto foi feito

- **Código:** 100% gerado por IA, com o Hermes Agent e o modelo **DeepSeek V4.1 Flash**,
  em sessões conduzidas por prompt (modelagem, rotas, templates, testes, documentação).
- **Direção humana:** as decisões de produto, o recorte do escopo e a revisão de cada
  entrega foram manuais, incluindo abrir o app no navegador e validar cada chamada
  contra a API real.
- **Propósito:** estudar na prática o consumo de uma API REST por um front server-side,
  simular o uso real (cadastro, pedido, avaliação, painel) e ter um ambiente de teste
  para experimentar mudanças no backend sem perder o histórico.
- **Relação com a API:** o backend [pizza-drf](https://github.com/Marcel0Borg3s/pizza-drf)
  foi escrito separadamente e é a fonte de verdade de pizzas, clientes e avaliações.

## Módulos

| App         | Responsabilidade                                                              |
| ----------- | ----------------------------------------------------------------------------- |
| `core`      | Cliente HTTP da API, mixin de acesso do dono, contexto global, filtros de UI   |
| `accounts`  | Cadastro (API + conta local), login, logout, perfil com dados vindos da API    |
| `catalog`   | Cardápio espelhado de `/pizzas/`: busca, categorias e formulário do dono       |
| `orders`    | Carrinho na sessão, checkout, histórico e cancelamento                        |
| `reviews`   | Avaliações lidas de `/reviews/`, 1 por item comprado (autoria local)           |
| `dashboard` | Painel do dono: pizzas gravadas na API, pedidos e clientes                    |

Regra de ouro: views e templates nunca falam com `httpx` ou com o banco de produtos
diretamente. Elas chamam `services.py` do próprio app.

## Como rodar

Pré-requisitos: Python 3.13 (`uv`), Node 20+ (só para recompilar o Tailwind) e a API
[pizza-drf](https://github.com/Marcel0Borg3s/pizza-drf) rodando na porta 8000.

```bash
# 0. clone os dois repositórios lado a lado
git clone https://github.com/Marcel0Borg3s/pizza-frontend.git
git clone https://github.com/Marcel0Borg3s/pizza-drf.git
cd pizza-frontend

# 1. dependências Python
uv sync

# 2. variáveis de ambiente
cp .env.example .env
# edite .env: DJANGO_SECRET_KEY (obrigatória) e DEMO_OWNER_PASSWORD

# 3. CSS: o build já está em static/dist/, rode só se mexer no Tailwind
npm install
npm run build:css        # ou: npm run watch:css durante o desenvolvimento

# 4. banco local e usuário do painel
uv run python manage.py migrate
uv run python manage.py create_owner     # usa DEMO_OWNER_USERNAME / DEMO_OWNER_PASSWORD

# 5. subir o front na 8001
uv run python manage.py runserver 127.0.0.1:8001
```

Em outro terminal, suba a API:

```bash
cd pizza-drf
uv run python manage.py migrate
uv run python manage.py runserver 127.0.0.1:8000
```

Com a API no ar, o cardápio de demonstração pode ser publicado por este front (opcional,
o comando é idempotente):

```bash
uv run python manage.py seed_catalog
```

## APIs consumidas hoje

| Método | Endpoint             | Onde é usada                          |
| ------ | -------------------- | ------------------------------------- |
| POST   | `/clients/`          | `/conta/cadastro/`                    |
| GET    | `/clients/`          | `/painel/clientes/` e health check    |
| GET    | `/clients/<uuid>/`   | `/conta/perfil/` e `/painel/clientes/<uuid>/` |
| GET    | `/pizzas/`           | cardápio, painel e espelho local      |
| POST   | `/pizzas/`           | `/painel/produtos/novo/`              |
| PATCH  | `/pizzas/<uuid>/`    | `/painel/produtos/<uuid>/editar/`     |
| DELETE | `/pizzas/<uuid>/`    | `/painel/produtos/<uuid>/excluir/`    |
| GET    | `/reviews/`          | `/avaliacoes/` e página da pizza (`?pizza=<uuid>`) |
| POST   | `/reviews/`          | avaliar item comprado                 |

O painel do dono mostra a latência do health check e as últimas chamadas (método, rota,
status e tempo, sem corpos de requisição).

## Acessos

| Papel              | O que pode fazer                                                      |
| ------------------ | --------------------------------------------------------------------- |
| Visitante          | Ver cardápio, avaliações e montar carrinho                            |
| Cliente logado     | Finalizar pedido, ver só os próprios pedidos, cancelar pendentes, avaliar itens comprados |
| Dono (`is_staff`)  | Tudo acima + `/painel/`: criar/editar/excluir produtos, mudar status de pedidos, ler clientes da API |

Pedidos usam `customer=request.user` em todas as consultas, então um cliente nunca acessa
o pedido de outro (404). O painel usa `StaffRequiredMixin`: visitante é redirecionado ao
login, cliente recebe 403.

## Cardápio (pizzas), pedidos e avaliações

O cardápio e as avaliações são da API; o front mantém um espelho local apenas onde
precisa de chave estável para o histórico:

- `catalog/services.py` faz `GET /pizzas/` (`refresh_catalog`) e espelha cada pizza na
  tabela `Product` (campo `api_id`). O carrinho, os pedidos e as avaliações continuam
  apontando para `Product.id`, então mudar preço na API nunca quebra pedido antigo.
  Pizza removida da API (ou produto legado sem vínculo) fica `is_available=False`
  em vez de ser apagada, porque pedidos antigos ainda apontam para ela.
- Dono cria, altera sabor/preço e exclui via `POST`/`PATCH`/`DELETE /pizzas/<uuid>/`
  (`/painel/produtos/`). A API devolve **409** ao excluir pizza que já tem avaliações.
- `reviews/services.py` lê `GET /reviews/` (com `?pizza=<uuid>` na página da pizza) e
  enriquece cada avaliação com o autor e a data locais (`Review.api_id`), porque a API
  ainda não guarda quem escreveu. Avaliar um item comprado faz `POST /reviews/` e só
  então grava o registro local que garante "uma avaliação por item".
- **Média de notas: pendente.** `rating_summary` devolve `average=None` de propósito;
  a tela mostra apenas a contagem até a regra de média ser definida (marcado com
  `TODO(reviews-media)`).
- `orders/services.py` concentra carrinho e criação do pedido (preço sempre relido do
  espelho no checkout).
- `accounts/services.py` concentra o vínculo com `/clients/`.

## Segurança

- Segredos em `.env` (fora do git) e `SECRET_KEY` obrigatória no start.
- Cookies de sessão `HttpOnly` + `SameSite=Lax`; `Secure` quando `DJANGO_DEBUG=False`.
- CSRF em todos os formulários, inclusive logout (POST) e ações do painel.
- Nenhuma credencial da API no navegador; token opcional (`PIZZA_API_TOKEN`) só no servidor.
- `SECURE_*`, HSTS e redirecionamento HTTPS ativos fora de desenvolvimento.
- Carrinho guarda apenas ids e quantidades: preços são recalculados no checkout.
- Consultas de pedido sempre filtradas pelo usuário autenticado.
- Senhas passam pelos validadores do Django; senha nunca é exibida em log.
- `next` de redirecionamento validado contra open redirect.

Verificação:

```bash
DJANGO_DEBUG=False DJANGO_SECRET_KEY=... uv run python manage.py check --deploy
```

## Testes e qualidade

```bash
uv run python manage.py test
uv run ruff check .
uv run ruff format --check .
```

## Limitações conhecidas (projeto de estudo)

- Sem pagamento, frete calculado ou integração com WhatsApp.
- Sem rate limiting / captcha no cadastro.
- A API está aberta (sem autenticação): quem alcançar `:8000` pode escrever em
  `/pizzas/` e `/reviews/`. O painel do front é restrito, mas a API em si não é.
- `Pizza` na API só tem sabor, descrição e preço: categoria, emoji e imagem continuam
  campos locais (as pizzas vindas da API caem em "Tradicionais", emoji 🍕).
- Média de notas ainda não é calculada nem na API nem no front.
- Avaliações locais antigas de itens que não existem em `/pizzas/` (ex.: as do
  refrigerante da demo) deixam de aparecer na lista pública; continuam no banco e no
  `/admin/`.
- Se a API aceitar o cadastro e a criação da conta local falhar, o cliente remoto fica
  órfão (documentado em `accounts/services.py`). O mesmo vale para avaliação: o `POST`
  acontece antes do registro local.
- Com `DEBUG=True` o Django mostra a página técnica de 404/500; os templates
  `templates/404.html` e `templates/500.html` entram em ação com `DEBUG=False`.

## Como montar uma demo

1. Suba a API e rode `uv run python manage.py seed_catalog` neste projeto: o comando
   publica 9 pizzas em `/pizzas/` e atualiza o espelho local.
2. Crie o dono com `uv run python manage.py create_owner` (usa `DEMO_OWNER_PASSWORD` do
   `.env`), entre em `/conta/entrar/` e abra `/painel/`.
3. Crie uma conta de cliente em `/conta/cadastro/`, monte um carrinho, finalize um pedido
   e avalie o item em "Meus pedidos" para ver a avaliação em `/avaliacoes/`.
4. No painel, edite o preço de uma pizza: a alteração vai para a API e o cardápio público
   reflete no próximo acesso.

Para zerar o front: `rm db.sqlite3 && uv run python manage.py migrate`.
