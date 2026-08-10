# PCPanel

PCPanel é uma aplicação Windows para coletar telemetria de hardware, transformá-la em métricas estáveis do produto e disponibilizá-la por HTTP e WebSocket a um painel acessível pelo navegador.

O projeto está em fase de prova de conceito. A cadeia de telemetria, métricas canônicas, API read-only, WebSockets e frontend mínimo está implementada. O domínio interno de Actions também existe e pode iniciar ações locais explicitamente registradas, mas ainda não está conectado à API HTTP.

## Estado atual

Já estão implementados:

- coleta por `LibreHardwareMonitorLib.dll` através do Python.NET;
- sensores raw com identificadores estáveis de hardware e sensor;
- coleta periódica e thread-safe em uma worker dedicada do `TelemetryManager`;
- último `TelemetrySnapshot` raw mantido em memória;
- transformação pura e determinística por `MetricResolver`;
- conjunto inicial de métricas canônicas em `MetricSnapshot`;
- API FastAPI read-only com REST e WebSockets raw e canônicos;
- frontend mínimo em HTML, CSS e JavaScript puro, servido pelo FastAPI;
- consumo das métricas canônicas pelo frontend através de WebSocket;
- configuração de host e porta para acesso local ou pela LAN;
- Actions Core interno, com definições estruturadas, registry de ações permitidas, executor abstrato, adapter Windows e `ActionService`;
- testes unitários do domínio Actions sem abertura de programas reais;
- script manual local para validar a execução de uma ação registrada.

Actions é, neste momento, uma funcionalidade interna/local. O navegador não inicia aplicações e não existe endpoint HTTP para execução de ações.

## Arquitetura

As duas áreas principais são independentes:

```text
PCPanel
│
├── Telemetry
│   LibreHardwareMonitor
│           ↓
│   LibreHardwareMonitorProvider
│           ↓
│   TelemetryManager
│           ↓
│   TelemetrySnapshot (raw)
│           ↓
│   MetricResolver
│           ↓
│   MetricSnapshot (canônico)
│           ↓
│   REST / WebSocket
│           ↓
│        Browser
│
└── Actions (interno/local)
    ActionDefinition
            ↓
    ActionRegistry
            ↓
    ActionService
            ↓
    ActionExecutor
            ↓
    WindowsProcessExecutor
            ↓
    Processo Windows
```

### Regras de Telemetry

- `LibreHardwareMonitorProvider` é o único componente que interage com Python.NET, classes .NET e LibreHardwareMonitor. Ele converte dados externos em modelos Python.
- `TelemetryManager` controla o ciclo de vida do provider, executa `update()` e `get_sensors()` na worker dedicada, gera `sequence` e `captured_at` e mantém o último snapshot raw.
- `TelemetrySnapshot` representa uma coleta imutável dos sensores raw.
- `MetricResolver` é uma transformação pura e determinística de `TelemetrySnapshot` para `MetricSnapshot`.
- FastAPI lê somente o snapshot já armazenado. Requests e conexões WebSocket não executam coleta.
- O frontend consome métricas canônicas e não resolve nomes específicos de sensores raw.

### Regras de Actions

- `ActionService.execute()` recebe somente um `action_id`.
- Somente `ActionRegistry` resolve um ID em uma `ActionDefinition` previamente conhecida.
- Caminhos de executáveis e argumentos não vêm de requests.
- Executável e argumentos permanecem estruturados e separados.
- `WindowsProcessExecutor` é o único componente de Actions que conhece `subprocess`.
- A criação de processos usa `shell=False`.
- Não existe fallback de ID para path, command line ou shell command.
- Actions ainda não está conectado à camada HTTP.

## Estrutura do projeto

```text
PCPanel/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── main.py
│   ├── telemetry/
│   │   ├── __init__.py
│   │   ├── manager.py
│   │   ├── metrics.py
│   │   ├── models.py
│   │   └── providers/
│   │       ├── __init__.py
│   │       ├── base.py
│   │       └── librehardwaremonitor.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── app.py
│   │   ├── metric_contract.py
│   │   ├── routes.py
│   │   ├── schemas.py
│   │   └── websocket.py
│   └── actions/
│       ├── __init__.py
│       ├── errors.py
│       ├── executor.py
│       ├── models.py
│       ├── registry.py
│       ├── service.py
│       └── windows.py
├── web/
│   ├── index.html
│   ├── README.md
│   ├── css/
│   │   ├── app.css
│   │   ├── components.css
│   │   ├── layout.css
│   │   └── variables.css
│   └── js/
│       ├── app.js
│       ├── components/
│       ├── services/
│       └── state/
├── scripts/
│   ├── inspect_sensors.py
│   └── test_action.py
├── tests/
│   ├── actions/
│   ├── api/
│   ├── telemetry/
│   ├── test_config.py
│   └── test_main.py
├── libs/
├── pytest.ini
├── requirements.txt
├── requirements-dev.txt
├── .gitignore
└── README.md
```

## Requisitos

- Windows e Python x64;
- Python 3.11 ou superior, dentro da faixa suportada pelo Python.NET 3.1.0;
- .NET Framework 4.7.2 ou superior;
- build `net472` de `LibreHardwareMonitorLib.dll` e suas dependências;
- dependências de `requirements.txt`.

O provider seleciona explicitamente o runtime `netfx`. Python, runtime .NET e assemblies precisam ter arquiteturas compatíveis.

Privilégios administrativos não são universalmente obrigatórios. Dependendo do hardware, drivers e mecanismos de acesso disponíveis no sistema, executar como administrador pode disponibilizar sensores adicionais. A aplicação depende dos sensores que o LibreHardwareMonitor consegue detectar naquela máquina.

## Instalação

Na raiz do repositório, em PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Para desenvolvimento e testes, instale também:

```powershell
python -m pip install -r requirements-dev.txt
```

Não instale um pacote separado chamado `clr`. O módulo `clr` utilizado pelo provider é fornecido por `pythonnet`.

## LibreHardwareMonitor DLL

Por padrão, coloque a biblioteca e as DLLs dependentes da mesma distribuição em:

```text
libs/LibreHardwareMonitorLib.dll
```

O provider procura a DLL nesta ordem:

1. caminho fornecido ao construtor;
2. variável de ambiente `PCPANEL_LHM_DLL`;
3. `libs/LibreHardwareMonitorLib.dll` na raiz do projeto.

Para usar outro local:

```powershell
$env:PCPANEL_LHM_DLL = "C:\Caminho\LibreHardwareMonitorLib.dll"
python -m app.main
```

Use os binários oficiais do projeto LibreHardwareMonitor e mantenha ao lado da DLL principal as dependências fornecidas na mesma distribuição.

## Configuração

`AppSettings.from_env()` reconhece:

| Variável | Finalidade | Default |
|---|---|---|
| `PCPANEL_LHM_DLL` | Caminho alternativo para `LibreHardwareMonitorLib.dll` | busca em `libs/LibreHardwareMonitorLib.dll` |
| `PCPANEL_TELEMETRY_INTERVAL` | Intervalo de coleta em segundos | `0.5` |
| `PCPANEL_HOST` | Endereço em que o servidor escuta | `0.0.0.0` |
| `PCPANEL_PORT` | Porta HTTP | `8000` |

Exemplo:

```powershell
$env:PCPANEL_TELEMETRY_INTERVAL = "0.5"
$env:PCPANEL_HOST = "0.0.0.0"
$env:PCPANEL_PORT = "8000"
python -m app.main
```

O intervalo deve ser finito e maior que zero, a porta deve estar entre 1 e 65535 e o host não pode ser vazio.

## Executando

O entry point é:

```powershell
python -m app.main
```

Para limitar o acesso à própria máquina:

```powershell
$env:PCPANEL_HOST = "127.0.0.1"
python -m app.main
```

Abra `http://127.0.0.1:8000/` no navegador.

O default `0.0.0.0` permite que o servidor aceite conexões locais e, quando a rede e o firewall permitirem, conexões pela LAN.

## Endpoints HTTP

Todos os endpoints HTTP atuais são read-only.

### `GET /api/v1/health`

Retorna o estado da API e do runtime de telemetria:

```json
{
  "status": "ok",
  "telemetry_status": "running"
}
```

### `GET /api/v1/telemetry`

Retorna o último snapshot raw para diagnóstico:

```json
{
  "sequence": 42,
  "captured_at": "2026-08-10T14:20:31Z",
  "sensors": [
    {
      "hardware_identifier": "/cpu/0",
      "hardware_name": "CPU",
      "hardware_type": "Cpu",
      "sensor_identifier": "/cpu/0/load/0",
      "sensor_name": "CPU Total",
      "sensor_type": "Load",
      "value": 25.5,
      "min_value": 0.0,
      "max_value": 80.0
    }
  ]
}
```

### `GET /api/v1/sensors`

Retorna o catálogo de sensores raw do último snapshot, com campos de identificação e tipo, sem valores:

```json
{
  "sensors": [
    {
      "hardware_identifier": "/cpu/0",
      "hardware_name": "CPU",
      "hardware_type": "Cpu",
      "sensor_identifier": "/cpu/0/load/0",
      "sensor_name": "CPU Total",
      "sensor_type": "Load"
    }
  ]
}
```

### `GET /api/v1/metrics`

Retorna o contrato canônico destinado ao produto e à UI:

```json
{
  "sequence": 42,
  "captured_at": "2026-08-10T14:20:31Z",
  "metrics": {
    "cpu.load": {
      "value": 25.5,
      "unit": "percent",
      "source_sensor_identifier": "/cpu/0/load/0"
    }
  }
}
```

Enquanto não houver snapshot raw, os endpoints que dependem dele retornam `503 Service Unavailable`.

> **Actions não possui API neste milestone.** Não existe `POST /api/v1/actions/{id}` nem rota equivalente capaz de iniciar processos. Essa separação é deliberada: o servidor pode estar acessível pela LAN e ainda não existe pairing ou autorização.

## WebSockets

- `WS /ws/v1/telemetry`: envia snapshots raw quando uma nova `sequence` é observada. É destinado a diagnóstico e usuários avançados.
- `WS /ws/v1/metrics`: envia o mesmo contrato conceitual usado por `GET /api/v1/metrics`. É o canal principal do frontend.

Cada conexão mantém seu próprio cursor de sequência. O mesmo snapshot não é reenviado como novo, e desconectar um cliente não interrompe o `TelemetryManager` ou outros clientes.

## Métricas canônicas

O `MetricResolver` garante atualmente estas métricas:

| Chave | Unidade |
|---|---|
| `cpu.temperature` | `celsius` |
| `cpu.load` | `percent` |
| `gpu.temperature` | `celsius` |
| `gpu.load` | `percent` |
| `memory.load` | `percent` |

Essas chaves pertencem ao domínio PCPanel e abstraem nomes específicos do LibreHardwareMonitor. Toda métrica garantida permanece presente; quando indisponível, `value` e `source_sensor_identifier` são `null`.

`source_sensor_identifier` preserva a rastreabilidade até o sensor raw escolhido, mas não é usado pelo frontend para decidir qual métrica mostrar.

## Frontend

O frontend atual é uma POC em HTML, CSS e JavaScript puro, sem framework ou build system. Ele é servido pelo FastAPI na rota `/` e conecta-se a `/ws/v1/metrics` usando `ws://` ou `wss://` conforme a página.

A interface exibe temperatura e uso de CPU e GPU, além do uso da RAM. Ela mantém o último snapshot visível durante desconexões, tenta reconectar automaticamente e mostra `--` para métricas indisponíveis. O browser não conhece nomes específicos de sensores raw e não possui controles para iniciar ações.

Essa interface valida a cadeia backend → browser; não é a interface final do produto.

## Actions Core

O Milestone 5 implementa o domínio interno de ações sem expor execução pela rede.

### ActionDefinition

`ActionDefinition` é uma dataclass imutável que representa uma ação permitida conhecida pelo PCPanel:

| Campo | Tipo | Finalidade |
|---|---|---|
| `id` | `str` | Identidade da ação usada para lookup |
| `label` | `str` | Nome legível |
| `executable` | `Path` | Executável estruturado |
| `arguments` | `tuple[str, ...]` | Argumentos separados; default `()` |
| `working_directory` | `Path \| None` | Diretório de trabalho opcional |

O `id` é uma identidade, não um caminho. Ele deve corresponder integralmente a:

```text
^[a-z][a-z0-9_-]{0,63}$
```

Isso significa que começa com letra minúscula, possui no máximo 64 caracteres e depois aceita letras minúsculas, números, `_` e `-`.

Válidos: `notepad`, `steam`, `my_app`, `obs-2`.

Inválidos: `../cmd`, `C:\Windows\cmd.exe`, `Steam`, `app.exe`.

Os exemplos válidos ilustram apenas o formato. Eles não são ações registradas automaticamente pelo produto.

### ActionRegistry

`ActionRegistry` é a whitelist interna das ações conhecidas. Recebe somente instâncias estruturadas de `ActionDefinition`, rejeita IDs duplicados e preserva a ordem de registro na listagem.

```text
action_id
    ↓
ActionRegistry
    ↓
ActionDefinition
```

Quando um ID não existe, `get()` lança `ActionNotFoundError`. O texto desconhecido nunca é reinterpretado como caminho, comando ou shell command; não existe fallback para execução arbitrária.

### ActionService

`ActionService` é a interface de orquestração que uma futura camada externa deverá usar:

```text
ActionService.execute(action_id)
        ↓
ActionRegistry.get(action_id)
        ↓
ActionExecutor.execute(action)
```

Sua entrada de execução é somente `action_id`. O service não recebe executable, path, command line, shell command ou argumentos enviados pelo chamador.

### ActionExecutor e adapter Windows

`ActionExecutor` define o contrato abstrato de tentativa de inicialização. `WindowsProcessExecutor` é a implementação concreta:

```text
ActionService
      ↓
ActionExecutor
      ↓
WindowsProcessExecutor
```

Essa separação permite testar o service com `FakeActionExecutor`, sem abrir programas reais.

O adapter Windows valida o executável e o diretório de trabalho, constrói `argv` como sequência e chama `subprocess.Popen` com `shell=False`. Executável e argumentos permanecem separados, inclusive quando um argumento contém espaços:

```python
[
    r"C:\Program Files\App\app.exe",
    "--flag",
    "valor com espaços",
]
```

Não é construída uma command line única. O pacote Actions não usa `os.system`, `shell=True` ou `cmd.exe /c` para interpretar entrada.

### Erros de domínio

- `ActionNotFoundError`: o `action_id` não existe no registry.
- `ActionUnavailableError`: a ação existe, mas seu executável ou diretório de trabalho não está disponível neste computador.
- `ActionExecutionError`: houve falha ao iniciar a ação.

Esses erros pertencem ao domínio e não dependem de FastAPI ou status HTTP. Uma futura API poderá mapeá-los depois que houver autorização, mas esse mapeamento ainda não existe.

## Teste manual local de Actions

O script `scripts/test_action.py` valida manualmente esta cadeia local:

```text
Python
   ↓
ActionService
   ↓
ActionRegistry
   ↓
WindowsProcessExecutor
   ↓
Programa Windows
```

Atualmente o script registra somente `notepad`, associado internamente a `%SystemRoot%\System32\notepad.exe`:

```powershell
python scripts/test_action.py notepad
```

Para consultar a ajuda:

```powershell
python scripts/test_action.py --help
```

O usuário fornece apenas o `action_id`. Não existem opções `--command`, `--executable`, `--args` ou `--shell`. Esse é um teste manual e não integra a suíte pytest, portanto CI não abre o Notepad.

## Acesso pela LAN

O servidor usa `0.0.0.0` como host padrão. Para acessá-lo de outro dispositivo:

1. execute `python -m app.main` no PC;
2. execute `ipconfig` e identifique o IPv4 da interface conectada;
3. no celular conectado à mesma rede, abra `http://<IP-DO-PC>:8000/`.

Se não funcionar, verifique firewall, rede, isolamento de clientes, porta utilizada e se `PCPANEL_HOST` não foi configurado como `127.0.0.1`.

O bind para LAN existe no código, mas o acesso depende da configuração local. A API disponível pela LAN continua limitada a telemetria read-only; Actions não está conectado a ela.

## Diagnóstico de sensores

Para inspecionar os sensores raw expostos pelo LibreHardwareMonitor:

```powershell
python scripts/inspect_sensors.py
```

Para informar uma DLL específica:

```powershell
python scripts/inspect_sensors.py --dll-path "C:\Caminho\LibreHardwareMonitorLib.dll"
```

O script abre o provider, executa uma atualização, imprime hardware, tipos, valores atuais, mínimos, máximos e identificadores e fecha o provider.

## Testes

Com as dependências de desenvolvimento instaladas:

```powershell
python -m pytest -q
```

Os testes de Telemetry, Metrics, API e WebSockets usam providers, managers e snapshots sintéticos; não dependem de hardware real, privilégios administrativos, Python.NET ou classes .NET.

Actions possui testes para:

- validação e imutabilidade de `ActionDefinition`;
- IDs válidos, inválidos e limite de tamanho;
- registry, listagem, lookup e rejeição de duplicados;
- `ActionNotFoundError`, `ActionUnavailableError` e `ActionExecutionError`;
- orquestração por `ActionService` com `FakeActionExecutor`;
- preservação de argumentos estruturados;
- construção de `argv`, `working_directory`/`cwd` e `shell=False`;
- executável indisponível e falhas de `Popen`;
- checks estáticos contra padrões de execução por shell e contra uma assinatura pública baseada em command line.

`subprocess.Popen` é substituído nos testes do adapter; a suíte não abre programas reais.

Se `.pytest_cache` não puder ser gravado no ambiente local, o cache pode ser desativado:

```powershell
python -m pytest -q -p no:cacheprovider
```

## Segurança

O projeto ainda não possui autenticação, pairing ou autorização e não deve ser descrito como seguro de forma absoluta.

Telemetry possui uma interface de rede read-only. A API e os WebSockets leem snapshots mantidos em memória e não iniciam coleta nem processos.

Actions possui capacidade local de iniciar processos, mas permanece desconectado da API. Sua fronteira atual combina:

- `ActionRegistry` como whitelist de definições conhecidas;
- execução solicitada por `action_id`, sem path ou command line externos;
- executable e argumentos estruturados;
- `shell=False` no adapter Windows.

Conectar Actions ao FastAPI antes de pairing e autorização criaria uma superfície inadequada enquanto o servidor pode estar acessível pela LAN. Por isso, a integração HTTP foi deliberadamente adiada.

## Limitações atuais

- suporte focado em Windows e no runtime `netfx`;
- telemetria limitada ao que LibreHardwareMonitor e o sistema conseguem expor;
- determinados sensores podem depender de drivers, mecanismos de acesso ou privilégios adicionais;
- conjunto canônico garantido limitado às cinco métricas principais listadas acima;
- frontend ainda é uma POC;
- ausência de autenticação, pairing e autorização;
- Actions não está exposto pela API;
- ações não possuem configuração persistente nem discovery automático de programas;
- apenas o script manual registra `notepad`; não existe catálogo de ações de produção;
- não existe launcher de produção, PWA ou instalador.

## Roadmap

- **Milestone 5 — Actions Core:** concluído como domínio interno/local, sem API.
- **Milestone 6 — Pairing & Authorization:** próximo passo planejado.
- **Milestone 7 — Actions API:** integração autorizada, conceitualmente `POST /api/v1/actions/{id}`, somente após o Milestone 6.
- **Milestone 8 — Persistent Configuration:** configuração persistente do produto e das ações.
- **Milestone 9 — Product UI:** evolução da interface além da POC atual.
- **Milestone 10 — Packaging / PWA:** distribuição e experiência instalável.

Pairing, tokens, login, Actions API, configuração persistente, discovery de programas, Steam discovery, shutdown/restart, volume, scripts customizados, Vue, PWA e installer não são funcionalidades implementadas atualmente.
