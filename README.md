# PCPanel

PCPanel é uma aplicação Windows para coletar telemetria de hardware e disponibilizá-la por HTTP e WebSocket a um painel acessível pelo navegador.

O projeto está atualmente em fase de prova de conceito. A cadeia de coleta, snapshots raw, métricas canônicas, API e frontend já funciona; launcher de aplicativos, autenticação, persistência, PWA e instalador ainda não fazem parte da aplicação.

## Estado atual

Já estão implementados:

- coleta por `LibreHardwareMonitorLib.dll` através do Python.NET;
- sensores raw com identificadores de hardware e sensor;
- coleta periódica em uma worker dedicada e thread-safe;
- último `TelemetrySnapshot` raw mantido em memória;
- resolução determinística das métricas canônicas principais;
- API FastAPI com REST e WebSockets raw e canônicos;
- frontend em HTML, CSS e JavaScript puro, servido pelo FastAPI;
- consumo das métricas canônicas pelo frontend através de WebSocket;
- configuração de host e porta para acesso local ou pela LAN.

Não há autenticação, persistência, execução de ações no Windows ou empacotamento da aplicação.

## Arquitetura

```text
LibreHardwareMonitor
        ↓
LibreHardwareMonitorProvider
        ↓
TelemetryManager
        ↓
TelemetrySnapshot (raw)
        ↓
MetricResolver
        ↓
MetricSnapshot (canônico)
        ↓
FastAPI
   ┌────┴─────┐
 REST     WebSocket
   └────┬─────┘
        ↓
     Browser
```

Responsabilidades:

- `LibreHardwareMonitorProvider` é o único componente que interage com Python.NET, classes .NET e LibreHardwareMonitor. Ele converte os dados externos em modelos Python.
- `TelemetryManager` controla o ciclo de vida do provider, executa `update()` e `get_sensors()` em uma worker dedicada, gera `sequence` e `captured_at` e mantém o último snapshot raw.
- `TelemetrySnapshot` representa uma coleta imutável dos sensores raw.
- `MetricResolver` é uma transformação pura e determinística de `TelemetrySnapshot` para `MetricSnapshot`.
- `MetricSnapshot` contém leituras com chaves e unidades pertencentes ao domínio PCPanel.
- FastAPI lê somente o snapshot já armazenado. Requests HTTP e conexões WebSocket não executam `provider.update()` nem forçam uma coleta.
- O frontend consome métricas canônicas e não resolve nomes ou tipos específicos de sensores raw.

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
│   └── api/
│       ├── __init__.py
│       ├── app.py
│       ├── metric_contract.py
│       ├── routes.py
│       ├── schemas.py
│       └── websocket.py
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
│       │   ├── cat-gauge.js
│       │   └── thermal-state.js
│       ├── services/
│       │   └── websocket-telemetry.js
│       └── state/
│           └── telemetry.js
├── scripts/
│   └── inspect_sensors.py
├── tests/
│   ├── api/
│   ├── telemetry/
│   ├── test_config.py
│   └── test_main.py
├── libs/
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

O entry point real é:

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

Retorna o catálogo de sensores raw do último snapshot. O catálogo contém os campos de identificação e tipo, sem valores:

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

Enquanto ainda não houver um snapshot raw, os endpoints que dependem dele retornam `503 Service Unavailable`.

## WebSockets

- `WS /ws/v1/telemetry`: envia snapshots raw quando uma nova `sequence` é observada. É destinado a diagnóstico e usuários avançados.
- `WS /ws/v1/metrics`: envia o mesmo contrato conceitual de métricas usado por `GET /api/v1/metrics`. É o canal principal do frontend.

Cada conexão mantém seu próprio cursor de sequência. O mesmo snapshot não é reenviado como novo, e desconectar um cliente não interrompe o `TelemetryManager` ou outros clientes.

## Métricas canônicas

O `MetricResolver` produz atualmente estas métricas:

| Chave | Unidade |
|---|---|
| `cpu.temperature` | `celsius` |
| `cpu.load` | `percent` |
| `gpu.temperature` | `celsius` |
| `gpu.load` | `percent` |
| `memory.load` | `percent` |

Essas chaves pertencem ao domínio PCPanel e abstraem nomes específicos do LibreHardwareMonitor. Toda métrica conhecida permanece presente; quando indisponível, `value` e `source_sensor_identifier` são `null`.

`source_sensor_identifier` preserva a rastreabilidade até o sensor raw escolhido pelo resolver, mas não é usado pelo frontend para decidir qual métrica mostrar.

## Frontend

O frontend atual é uma POC em HTML, CSS e JavaScript puro, sem framework ou build system. Ele é servido pelo FastAPI na rota `/` e conecta-se a `/ws/v1/metrics` usando `ws://` ou `wss://` conforme a página.

A interface exibe temperatura e uso de CPU e GPU, além do uso da RAM. Ela mantém o último snapshot visível durante desconexões, tenta reconectar automaticamente e mostra `--` para métricas indisponíveis. O browser não conhece nomes específicos de sensores raw.

Esta interface valida a cadeia backend → browser; não deve ser considerada a interface final do produto.

## Acesso pela LAN

O servidor já usa `0.0.0.0` como host padrão. Para acessá-lo de outro dispositivo:

1. execute `python -m app.main` no PC;
2. execute `ipconfig` e identifique o IPv4 da interface conectada;
3. no celular conectado à mesma rede, abra `http://<IP-DO-PC>:8000/`.

Se não funcionar, verifique:

- regra de entrada do Windows Firewall para a porta configurada;
- se PC e celular estão na mesma rede;
- guest Wi-Fi ou isolamento de clientes/AP;
- porta utilizada;
- se `PCPANEL_HOST` não foi configurado como `127.0.0.1`.

O suporte de bind para LAN existe no código, mas o acesso depende da configuração local de rede e firewall.

## Diagnóstico de sensores

Para inspecionar diretamente os sensores raw expostos pelo LibreHardwareMonitor:

```powershell
python scripts/inspect_sensors.py
```

Para informar uma DLL específica:

```powershell
python scripts/inspect_sensors.py --dll-path "C:\Caminho\LibreHardwareMonitorLib.dll"
```

O script abre o provider, executa uma atualização, imprime hardware, tipos, valores atuais, mínimos, máximos e identificadores e fecha o provider. Use-o para investigar sensores ausentes, nomes reportados e diferenças entre máquinas.

## Testes

Com as dependências de desenvolvimento instaladas:

```powershell
python -m pytest -q
```

Os testes de `TelemetryManager`, `MetricResolver`, API e WebSockets usam providers, managers e snapshots sintéticos; não dependem de hardware real, privilégios administrativos, Python.NET ou classes .NET.

A suíte cobre, entre outros pontos:

- lifecycle, sincronização, thread affinity e snapshots do manager;
- endpoints REST e WebSockets raw e canônicos;
- equivalência do contrato canônico entre REST e WebSocket;
- resolução para Intel/NVIDIA, AMD/AMD e Intel com iGPU;
- múltiplas GPUs, sensores ausentes e `value=None`;
- nomes duplicados e independência da ordem dos sensores;
- configuração, entry point e arquivos do frontend.

Se `.pytest_cache` não puder ser gravado no ambiente local, o cache pode ser desativado sem alterar os testes:

```powershell
python -m pytest -q -p no:cacheprovider
```

## Limitações atuais

- execução e coleta focadas em Windows e no runtime `netfx`;
- telemetria limitada ao que LibreHardwareMonitor e o sistema conseguem expor;
- determinados sensores podem depender de drivers, mecanismos de acesso ou privilégios adicionais;
- resolução canônica limitada às cinco métricas principais listadas acima;
- frontend ainda é uma POC;
- ausência de autenticação, pairing e persistência;
- nenhuma API de ações ou comandos Windows.

## Roadmap

O próximo passo planejado é o **Milestone 5 — Actions**, ainda não implementado. Conceitos em avaliação incluem `ActionRegistry`, `AppLauncher`, uma rota `POST /api/v1/actions/{id}` e uma whitelist explícita.

Também são possibilidades futuras, não funcionalidades atuais: pairing/autenticação, configuração persistente, Vue, PWA e distribuição/instalador para Windows.

## Segurança

A exposição pela LAN deve ser considerada ambiente de desenvolvimento enquanto não houver autenticação ou pairing, especialmente antes de qualquer futura implementação de comandos Windows.

A telemetria atual é somente leitura e possui um perfil de risco diferente de endpoints capazes de executar ações. O projeto não implementa mecanismos de autenticação ou autorização neste momento.
