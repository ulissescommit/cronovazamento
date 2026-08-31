# cronovazamento

Ferramenta para **estimar quando um vazamento de dados aconteceu** e **de onde
ele provavelmente saiu**, cruzando uma amostra vazada contra bases de
referência que mudam ao longo do tempo por motivos naturais e conhecidos.

## A ideia

Toda base de dados relacionada a pessoas, empresas ou veículos tem campos que
mudam de valor em datas conhecíveis:

- **Pessoas**: CPF é único e estável, mas o *nome* pode mudar (casamento),
  a pessoa pode *nascer* (passar a existir na base) ou *falecer*.
- **População**: a base cresce (nascimentos) e muda (óbitos, mudanças de
  estado civil/nome) constantemente.
- **Empresas**: o quadro societário muda — sócios entram, saem, participação
  percentual varia.
- **Veículos / DETRAN**: a propriedade de uma placa muda de mãos; carros
  entram e saem da frota de um estado.

Se uma amostra vazada reflete o estado **anterior** ou **posterior** a um
desses eventos, isso vira um limite temporal (`>=` ou `<=`) para a data do
vazamento. Cruzando várias evidências desse tipo, a interseção dos limites dá
uma **janela estimada** de quando os dados foram extraídos — mesmo sem
nenhuma data explícita na amostra.

Da mesma forma, comparar **quais campos** (colunas) aparecem na amostra
contra um catálogo de vazamentos/bases já conhecidas ajuda a estimar
**de onde** ela veio, por fingerprint de schema.

Nenhum dos dois casamentos (registro ou schema) exige igualdade exata de
string — um motor de **algoritmos de proximidade estatística**
(`cronovazamento/proximidade.py`) permite escolher entre Jaccard/Dice/Cosseno
(TF-IDF) para schema e Levenshtein/Jaro-Winkler/fonético para nomes, tolerando
acento, abreviação e erro de digitação comuns em bases vazadas.

## Estrutura

```
cronovazamento/            # motor puro, sem dependência de web/banco
  evidencias.py             # tipos Evidencia/Direcao/Forca e o algoritmo de interseção de janela
  proximidade.py             # registro de algoritmos de proximidade (schema + string)
  eventos.py                  # carrega eventos de referência e casa (fuzzy) contra as linhas da amostra
  schema.py                    # normalização de nomes de coluna, Jaccard, Dice
  catalogo.py                   # catálogo de vazamentos conhecidos e fingerprint de origem
  comparador.py                  # orquestra tudo: amostra -> evidências -> relatório
  cli.py                          # interface de linha de comando (uso offline sobre JSON/CSV)
webapp/                     # interface web (FastAPI + HTMX), banco Postgres
  main.py, db.py, models.py, repositorio.py, routers/, templates/, static/
data/
  referencias/    -> JSONs de eventos de exemplo — só os *.exemplo.* vão para o git
  catalogo/       -> catálogo de exemplo — idem
  amostras/       -> amostra de exemplo — idem
tests/
Dockerfile, docker-compose.yml, .env.example
```

Nenhum dado real (CPFs, nomes, vazamentos reais) fica no repositório — o
`.gitignore` bloqueia tudo em `data/` exceto os exemplos sintéticos, além de
`.env` e `*.db`. Você alimenta o projeto com suas próprias fontes de pesquisa,
seja pelo banco (via web) ou pelos JSONs (via CLI).

## Rodando a interface web (Docker)

```bash
cp .env.example .env   # ajuste a senha do Postgres
docker compose up --build -d
```

Isso sobe dois containers: `db` (Postgres 16) e `web` (FastAPI, porta
`8000`). Por padrão o compose publica a porta **só em `127.0.0.1`** — nunca
`0.0.0.0` — porque essa ferramenta guarda dado pessoal sensível (CPF, nome).

- Na sua máquina: abra `http://localhost:8000`.
- Num servidor remoto (VPS etc.): **não** exponha a porta publicamente. Acesse
  por túnel SSH:
  ```bash
  ssh -L 8000:localhost:8000 seu-host
  ```
  e abra `http://localhost:8000` no seu navegador local.

O schema do banco é criado automaticamente no startup do container `web`
(sem Alembic nesta versão — projeto solo, sem múltiplos ambientes). Para
testar rápido sem digitar tudo à mão, o painel (`/`) tem um botão **"Importar
dados de exemplo"** que carrega os JSONs sintéticos de `data/` no banco.

Fluxo na UI: `/amostras/nova` (subir CSV) → abrir a amostra e definir o
**mapeamento** de campos → `/eventos/*` e `/catalogo` para cadastrar as
referências → `/analises/nova?amostra_id=` escolhendo os algoritmos de
proximidade → resultado em `/analises/{id}`.

## Uso via linha de comando (offline, sobre JSON/CSV)

### 1. Descreva os eventos de referência que você conhece

`data/referencias/eventos_pessoa.json`:

```json
[
  { "cpf": "12345678900", "tipo": "nascimento", "data": "1995-03-10" },
  { "cpf": "98765432100", "tipo": "mudanca_nome", "data": "2019-08-15",
    "nome_anterior": "Maria Souza", "nome_novo": "Maria Souza Lima" },
  { "cpf": "11122233344", "tipo": "obito", "data": "2021-02-01" }
]
```

Também existem `eventos_empresa.json` (tipo `alteracao_societaria`, com
`socio`, `situacao_nova`: `"presente"`/`"ausente"`, `participacao_nova`) e
`eventos_veiculo.json` (tipo `transferencia_propriedade`, com `placa`,
`proprietario_anterior`/`proprietario_novo`).

### 2. Rode a análise

```bash
python -m cronovazamento.cli analisar \
  --amostra data/amostras/amostra.csv \
  --mapa cpf=CPF --mapa nome=NOME_COMPLETO --mapa status_obito=STATUS_OBITO \
  --eventos-pessoa data/referencias/eventos_pessoa.json \
  --eventos-empresa data/referencias/eventos_empresa.json \
  --eventos-veiculo data/referencias/eventos_veiculo.json \
  --catalogo data/catalogo/catalogo.json \
  --algoritmo-registro exato --algoritmo-registro levenshtein \
  --algoritmo-origem jaccard --algoritmo-origem cosseno_tfidf \
  --limiar 0.85 \
  --saida relatorio.json
```

`--mapa campo=coluna` diz qual coluna da SUA amostra corresponde a cada
campo lógico que o motor entende (`cpf`, `nome`, `status_obito`, `cnpj`,
`socio`, `participacao`, `placa`, `proprietario`). `--algoritmo-registro` e
`--algoritmo-origem` são repetíveis; sem eles o comportamento é o mesmo de
antes (igualdade exata para registro, todos os algoritmos para origem).

### 3. Alimente o catálogo de origem

Toda vez que você identificar de forma confiável a origem de um vazamento
(ou quiser cadastrar o schema de uma base legítima para referência), some
ele ao catálogo:

```bash
python -m cronovazamento.cli catalogar \
  --amostra data/amostras/vazamento_x.csv \
  --catalogo data/catalogo/catalogo.json \
  --id vazamento-x-2022 --nome "Vazamento X (2022)" \
  --fonte "Loja Y — confirmado via nota da empresa"
```

Da próxima vez que uma amostra desconhecida tiver campos parecidos, o
comando `analisar` vai apontar essa entrada como candidata de origem.

## Como ler o resultado

- **Evidência forte**: aperta a janela temporal (vira limite `>=` ou `<=`
  definitivo). Ex.: nome novo já aparece na amostra → vazamento é depois da
  mudança.
- **Evidência fraca**: fica registrada como apoio, mas não aperta a janela,
  porque o fato pode não ter sido refletido na base por atraso cadastral
  (ex.: DETRAN demora a averbar transferência; nome antigo pode persistir
  em bases desatualizadas). Você pode reclassificar a força de qualquer
  evento no JSON com `"forca": "forte"` se souber que a base de referência
  atualiza rápido.
- **Conflito**: quando uma evidência forte exige `>= D1` e outra exige
  `<= D2` com `D1 > D2` — sinal de que a amostra pode ser um **mosaico**
  (dados de fontes/datas diferentes combinados), ou que uma evidência foi
  classificada com força errada.
- **Casamento fuzzy**: quando o nome na amostra bate por um algoritmo de
  proximidade (não igualdade exata), a evidência mostra o algoritmo e o
  score. Score >= 0.97 é tratado como equivalente a exato; abaixo disso, a
  evidência é sempre classificada como fraca, mesmo que o evento diga
  `"forca": "forte"` — é uma identificação aproximada, não deveria travar a
  janela sozinha.
- **Origem por algoritmo**: cada candidato do catálogo mostra um score por
  algoritmo escolhido (não um único score combinado) — mais transparente
  para você decidir qual bater o olho, já que Jaccard, Dice e Cosseno(TF-IDF)
  podem discordar sobre qual candidato é mais provável.

## Rodando os testes

```bash
python -m unittest discover -s tests -v
```

Sem dependências externas — só biblioteca padrão do Python 3.11+.

## Aviso

Este projeto é uma ferramenta de **análise forense/investigativa** para
pesquisa em segurança da informação (ex.: atribuir e datar vazamentos para
notificação responsável, due diligence, ou investigação). Trate todo dado
pessoal com o mesmo cuidado — e as mesmas obrigações legais (LGPD) — que
você trataria qualquer outra base de dados pessoais sensível.
