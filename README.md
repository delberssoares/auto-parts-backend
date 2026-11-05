# Auto Parts (API)

API REST da loja de autopeças [Auto Parts](https://github.com/delberssoares/auto-parts-frontend): autenticação, catálogo, pedidos com controle de estoque, fluxo de envio e recuperação de senha.

![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-336791?logo=postgresql&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?logo=sqlalchemy&logoColor=white)

**Frontend (demonstração):** https://auto-parts-frontend-ten.vercel.app
**Documentação interativa (Swagger):** https://auto-parts-backend-bzag.onrender.com/docs

> A API roda no plano gratuito do Render e "dorme" após 15 minutos sem acesso. A primeira requisição depois disso pode levar até 1 minuto.

## Sumário

- [Funcionalidades](#funcionalidades)
- [Stack](#stack)
- [Arquitetura](#arquitetura)
- [Modelo de dados](#modelo-de-dados)
- [Fluxo de status do pedido](#fluxo-de-status-do-pedido)
- [Decisões técnicas e segurança](#decisões-técnicas-e-segurança)
- [Endpoints](#endpoints)
- [Como rodar localmente](#como-rodar-localmente)
- [Variáveis de ambiente](#variáveis-de-ambiente)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Deploy](#deploy)
- [Modo demonstração e limitações](#modo-demonstração-e-limitações)
- [Roadmap](#roadmap)
- [Autor](#autor)

## Funcionalidades

- **Autenticação:** cadastro, login, dados do usuário logado, troca de senha e recuperação de senha por link. Papéis `customer` e `admin`.
- **Catálogo:** categorias e produtos com busca por nome ou marca, filtro por categoria e ordenação. Criar, editar e excluir produtos é restrito a administradores.
- **Pedidos:** criação com validação de estoque, listagem e detalhe do próprio cliente, pagamento (simulado) e cancelamento com devolução de estoque.
- **Operação (admin):** fila de pedidos com filtro por status, busca e paginação, contadores por status, início da separação, informação de envio com código de rastreio, confirmação de entrega e cancelamento.
- **Histórico:** cada mudança de status do pedido é registrada com autor e data.

## Stack

| Área | Tecnologias |
|---|---|
| Linguagem e framework | Python, FastAPI, Pydantic v2 |
| Banco de dados | PostgreSQL (Neon), SQLAlchemy 2.0, driver psycopg 3 |
| Migrações | Alembic |
| Segurança | bcrypt (senhas), PyJWT (tokens) |
| Configuração | pydantic-settings (variáveis de ambiente) |
| Hospedagem | Render (API) e Neon (banco) |

## Arquitetura

```mermaid
flowchart LR
    F["Frontend<br/>React (Vercel)"] -->|"REST + JWT (Bearer)"| API["FastAPI<br/>(Render)"]
    API -->|SQLAlchemy| DB[("PostgreSQL<br/>(Neon)")]
    API -.->|"e-mail (opcional)"| M["Provedor de e-mail"]
```

A API segue camadas simples, cada uma com um papel:

```
routers  ->  services  ->  models (SQLAlchemy)  ->  PostgreSQL
   |            |
schemas      regras de negócio e transações
(Pydantic)
```

- **routers**: recebem a requisição, validam a entrada com os schemas e chamam o serviço. Quase não têm lógica.
- **services**: concentram as regras de negócio (estoque, transições de status, recuperação de senha) e controlam a transação.
- **models** e **schemas**: o modelo do banco e o contrato da API ficam separados, então mudar um não vaza para o outro.
- **core**: configuração, segurança, dependências de autenticação, erros e as regras de status.

## Modelo de dados

```mermaid
erDiagram
    USERS ||--o{ ORDERS : faz
    USERS ||--o{ PASSWORD_RESET_TOKENS : possui
    CATEGORIES ||--o{ PRODUCTS : agrupa
    ORDERS ||--|{ ORDER_ITEMS : contem
    ORDERS ||--|{ ORDER_STATUS_EVENTS : registra
    PRODUCTS ||--o{ ORDER_ITEMS : "origem do item"

    USERS {
        int id PK
        string email UK
        string password_hash
        string role
        bool is_demo
    }
    CATEGORIES {
        int id PK
        string name UK
    }
    PRODUCTS {
        int id PK
        string name
        string brand
        numeric price
        int stock
        int category_id FK
    }
    ORDERS {
        string id PK
        int user_id FK
        string status
        numeric total
        bool refunded
        string tracking_code
    }
    ORDER_ITEMS {
        int id PK
        string order_id FK
        int product_id FK
        string name
        numeric price
        int quantity
    }
    ORDER_STATUS_EVENTS {
        int id PK
        string order_id FK
        string status
        string actor
        datetime created_at
    }
    PASSWORD_RESET_TOKENS {
        int id PK
        int user_id FK
        string token_hash UK
        datetime expires_at
    }
```

Há ainda a tabela `password_reset_requests`, que controla o intervalo mínimo entre pedidos de recuperação por e-mail.

Detalhes que importam:

- `ORDER_ITEMS` guarda **cópia do nome e do preço** no momento da compra. Se o produto for excluído, o item continua no histórico (`product_id` vira nulo).
- O endereço de entrega também é copiado para o pedido, então alterar a conta depois não muda pedidos antigos.
- O código do pedido (`ORDERS.id`) é um texto curto e aleatório de 8 caracteres, sem caracteres ambíguos como `0`, `O`, `1` e `I`.
- Restrições no banco (`price > 0`, `stock >= 0`, `quantity > 0`) garantem consistência mesmo se uma validação falhar.

## Fluxo de status do pedido

```mermaid
stateDiagram-v2
    direction LR
    pending: Aguardando pagamento
    paid: Pago
    processing: Em separação
    shipped: Enviado
    delivered: Entregue
    cancelled: Cancelado

    [*] --> pending
    pending --> paid
    pending --> cancelled
    paid --> processing
    paid --> cancelled
    processing --> shipped
    processing --> cancelled
    shipped --> delivered
    delivered --> [*]
    cancelled --> [*]
```

- Toda transição passa por uma única função que valida o mapa de transições permitidas (`app/core/order_status.py`). Uma transição inválida devolve `409`.
- O cliente só cancela sozinho enquanto o pedido está `pending` ou `paid`. Depois que entra em separação, só o administrador cancela. Depois de enviado, o pedido não pode mais ser cancelado.
- Cancelar um pedido pago marca `refunded` e registra "Estorno solicitado" no histórico. O pagamento é simulado, então nenhum estorno real acontece.

## Decisões técnicas e segurança

**Pedidos e estoque**

- **O servidor calcula tudo.** O cliente envia apenas `product_id` e `quantity`. Preço e total vêm do banco, então não dá para adulterar o valor pela requisição.
- **Baixa de estoque atômica.** Cada item usa `UPDATE products SET stock = stock - :qty WHERE id = :id AND stock >= :qty`. Se não houver saldo, nada é alterado e o pedido inteiro é desfeito com rollback. Dois clientes comprando a última unidade nunca vendem o mesmo item duas vezes.
- **Trava de linha nas transições.** As ações sobre um pedido usam `SELECT ... FOR UPDATE`. Dois cliques, duas abas ou uma ação do cliente junto com a do admin entram em fila, e o estoque não é devolvido duas vezes.
- **Ordem fixa de produtos** ao reservar estoque, para evitar deadlock entre pedidos simultâneos.
- **Pedido de outra pessoa responde `404`**, e não `403`, para não revelar que aquele código existe.

**Contas e senhas**

- Senhas com **bcrypt**. A regra (8 a 72 bytes, com letra e número) vale no cadastro, na troca e na redefinição.
- **Login sem vazar informação:** a mensagem é a mesma para e-mail inexistente e senha errada, e um hash falso é conferido quando a conta não existe, para o tempo de resposta não revelar se o e-mail está cadastrado.
- **Autorização no servidor.** Rotas de admin exigem o papel `admin` em toda requisição. O que o front esconde é só conveniência.

**Recuperação de senha**

- Token aleatório de 256 bits. **Só o hash (SHA-256) vai para o banco**, então um vazamento do banco não entrega links válidos.
- Expira em 30 minutos, **só pode ser usado uma vez** e cada conta tem **um único link ativo** (um pedido novo invalida o anterior).
- **Intervalo mínimo entre pedidos** por e-mail, também para contas inexistentes, devolvendo `429` com o cabeçalho `Retry-After`.
- **A resposta é idêntica** exista a conta ou não, para ninguém descobrir quais e-mails estão cadastrados.
- Link inválido, expirado ou já usado mostram a mesma mensagem.

**Contrato da API**

- Todo erro volta como `{"detail": "mensagem"}`. Erros de validação (`422`) trazem também a lista `errors` com campo e mensagem, e o `429` traz `retry_after`.
- Mensagens em português, prontas para exibir ao usuário.

## Endpoints

A documentação completa, com exemplos e esquemas, fica em `/docs` (Swagger) e `/redoc`.

| Método | Rota | Acesso | Descrição |
|---|---|---|---|
| POST | `/auth/register` | Público | Cria conta e já devolve a sessão |
| POST | `/auth/login` | Público | Login |
| GET | `/auth/me` | Logado | Dados do usuário atual |
| POST | `/auth/change-password` | Logado | Troca de senha |
| POST | `/auth/forgot-password` | Público | Pede o link de redefinição |
| POST | `/auth/reset-password/validate` | Público | Confere o link e devolve o e-mail mascarado |
| POST | `/auth/reset-password` | Público | Define a nova senha |
| GET | `/categories` | Público | Lista categorias |
| GET | `/products` | Público | Lista produtos (`search`, `category_id`, `sort`) |
| GET | `/products/{id}` | Público | Detalhe do produto |
| POST | `/products` | Admin | Cria produto |
| PUT | `/products/{id}` | Admin | Atualiza produto |
| DELETE | `/products/{id}` | Admin | Exclui produto |
| POST | `/orders` | Logado | Cria pedido (baixa o estoque) |
| GET | `/orders` | Logado | Pedidos do usuário |
| GET | `/orders/{id}` | Dono ou admin | Detalhe do pedido |
| POST | `/orders/{id}/pay` | Dono | Pagamento simulado |
| POST | `/orders/{id}/cancel` | Dono | Cancela (devolve o estoque) |
| GET | `/admin/orders` | Admin | Fila de pedidos (`status`, `search`, `page`, `page_size`) |
| GET | `/admin/orders/summary` | Admin | Contagem por status |
| POST | `/admin/orders/{id}/start-processing` | Admin | Inicia a separação |
| POST | `/admin/orders/{id}/ship` | Admin | Informa envio (transportadora, rastreio, previsão) |
| POST | `/admin/orders/{id}/deliver` | Admin | Marca como entregue |
| POST | `/admin/orders/{id}/cancel` | Admin | Cancela (devolve o estoque) |
| GET | `/health` | Público | Verificação de saúde |
| GET | `/health/db` | Público | Verifica a conexão com o banco |

## Como rodar localmente

Pré-requisitos: **Python 3.12+** (desenvolvido na 3.14) e um PostgreSQL, local ou um projeto gratuito no [Neon](https://neon.tech).

```bash
git clone https://github.com/delberssoares/auto-parts-backend.git
cd auto-parts-backend

python -m venv .venv
source .venv/Scripts/activate        # Windows (Git Bash). Em Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env                 # preencha DATABASE_URL e SECRET_KEY
alembic upgrade head                 # cria as tabelas
python -m scripts.seed_catalog       # categorias e produtos de exemplo
python -m scripts.seed_admin         # cria o administrador (pergunta e-mail e senha)

uvicorn app.main:app --reload
```

A API sobe em `http://localhost:8000` e o Swagger em `http://localhost:8000/docs`.

Para gerar uma `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Em desenvolvimento, o link de recuperação de senha aparece no terminal do `uvicorn`, no log de e-mail.

## Variáveis de ambiente

| Variável | Obrigatória | Descrição |
|---|---|---|
| `DATABASE_URL` | Sim | Conexão PostgreSQL, no formato `postgresql+psycopg://usuario:senha@host/banco?sslmode=require` |
| `SECRET_KEY` | Sim | Chave de assinatura do JWT. Em produção exige 32 caracteres ou mais |
| `FRONTEND_URL` | Não | Origem do front. Usada no CORS e nos links de e-mail. Padrão: `http://localhost:5173` |
| `ENVIRONMENT` | Não | `development` (padrão) ou `production`. Em produção, só a origem do front é aceita no CORS |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Não | Validade do token. Padrão: 480 (8 horas) |
| `RESET_TOKEN_TTL_MINUTES` | Não | Validade do link de redefinição. Padrão: 30 |
| `RESET_COOLDOWN_SECONDS` | Não | Intervalo entre pedidos de recuperação por e-mail. Padrão: 60 |
| `RESEND_API_KEY` | Não | Chave do provedor de e-mail. Sem ela, nenhum e-mail é enviado |
| `MAIL_FROM` | Não | Remetente dos e-mails |
| `LOG_EMAILS` | Não | Com `true`, escreve o conteúdo dos e-mails (com os links) no log. Use só de forma temporária |
| `DEMO_RESET_ENABLED` | Não | Com `true`, contas criadas pelo cadastro viram contas de teste e redefinem a senha sem e-mail |

## Estrutura do projeto

```
app/
├── core/        config, segurança (bcrypt/JWT), dependências de autenticação, erros, regras de status
├── db/          engine, sessão e Base do SQLAlchemy
├── models/      users, catálogo, pedidos, tokens de redefinição
├── routers/     auth, products (e categories), orders (cliente e admin)
├── schemas/     contratos de entrada e saída (Pydantic)
├── services/    regras de negócio: auth, catálogo, pedidos, e-mail
└── main.py      aplicação, CORS e tratamento de erros
migrations/      versões do Alembic
scripts/         seed_catalog e seed_admin
```

## Deploy

A API roda como **Web Service no Render** e o banco no **Neon**.

| Campo | Valor |
|---|---|
| Build Command | `pip install -r requirements.txt` |
| Start Command | `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/health` |
| Variáveis | `DATABASE_URL`, `SECRET_KEY`, `FRONTEND_URL`, `ENVIRONMENT=production`, `PYTHON_VERSION` |

Observações:

- As migrações rodam a cada inicialização. Quando o banco já está atualizado, o `alembic upgrade head` não faz nada.
- Use a mesma região do projeto no Neon para reduzir a latência de cada consulta.
- Use a connection string direta do Neon (sem `-pooler`).
- O plano gratuito do Render suspende o serviço por inatividade. Um monitor externo chamando `/health` a cada poucos minutos evita isso.
- Os scripts de seed rodam fora do servidor, com o `DATABASE_URL` apontando para o banco desejado.

## Modo demonstração e limitações

- **Pagamento simulado.** O endpoint `/pay` apenas muda o status. Em um sistema real, quem confirma o pagamento é o webhook do provedor, e não o cliente.
- **E-mail.** O envio depende de um provedor com domínio verificado. Enquanto isso não existe, a recuperação de senha funciona por dois caminhos: o modo demonstração (contas de teste recebem o token na própria resposta, sem e-mail) e o log temporário de e-mails.
- **Modo demonstração.** Com `DEMO_RESET_ENABLED=true`, só contas criadas pelo cadastro público são marcadas como `is_demo`. Administradores e contas reais nunca recebem o token na resposta.
- **Valores monetários** usam `NUMERIC(10,2)` e saem como número na API. Para cálculos mais complexos (descontos, frete), o ideal é trabalhar em centavos inteiros.
- **Endereço** é guardado como texto (`address` e `city`). Uma modelagem estruturada (rua, número, bairro, UF) é um passo futuro.
- **Token JWT** de 8 horas, sem revogação. Trocar a senha não invalida tokens já emitidos.
- **Sem limite de tentativas no login.** Hoje só a recuperação de senha tem proteção por intervalo.

## Roadmap

- [ ] Testes automatizados com `pytest` (concorrência de estoque, permissões, transições de status) e workflow de CI
- [ ] Limite de tentativas no login e invalidação de tokens ao trocar a senha (`token_version`)
- [ ] Envio de e-mail com domínio verificado: recuperação de senha, confirmação de pedido e aviso de envio
- [ ] Compatibilidade de peças por veículo
- [ ] Cálculo de frete e prazo por CEP
- [ ] Pagamento em modo de teste (Mercado Pago ou Stripe) com webhook assinado e idempotente
- [ ] Upload de imagens dos produtos
- [ ] Logs estruturados com identificador de requisição e `docker-compose` para subir API e banco com um comando

## Autor

Feito por [@delberssoares](https://github.com/delberssoares). Sugestões e correções são bem-vindas por [issues](https://github.com/delberssoares/auto-parts-backend/issues).