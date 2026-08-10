# PCPanel frontend POC

Interface estática de monitoramento desenhada prioritariamente para smartphones Android em landscape. A POC usa HTML, CSS e JavaScript com ES Modules, sem build system ou framework.

## Como executar

Na raiz do repositório, com as dependências Python instaladas:

```powershell
python -m app.main
```

Abra o endereço exibido pelo servidor. Os módulos ES precisam ser servidos por HTTP; abrir `index.html` diretamente como arquivo não é suportado.

## Estrutura

```text
web/
├── index.html
├── css/
│   ├── app.css
│   ├── variables.css
│   ├── layout.css
│   └── components.css
└── js/
    ├── app.js
    ├── state/telemetry.js
    ├── services/websocket-telemetry.js
    └── components/
        ├── cat-gauge.js
        └── thermal-state.js
```

## Arquitetura

O fluxo é unidirecional:

```text
websocket-telemetry.js → telemetry state → app/components → DOM
```

O serviço recebe snapshots canônicos e estados de conexão. O state mantém o último snapshot e notifica assinantes. Componentes recebem dados do state e não conhecem sensores raw.

## Contrato canônico

Cada snapshot contém `sequence`, `captured_at` e um objeto `metrics` indexado pelas chaves `cpu.temperature`, `cpu.load`, `gpu.temperature`, `gpu.load` e `memory.load`. Cada leitura contém `value`, `unit` e `source_sensor_identifier`. A interface usa somente chave, valor e unidade; o identificador de origem permanece disponível apenas para diagnóstico.

## Política térmica e humor

Os thresholds provisórios da POC são CPU 65/85/95 °C e GPU 65/83/90 °C. `thermalStress()` converte essas faixas em stress de 0 a 100. A cor do gato migra da cor-base do card para amarelo, laranja e vermelho conforme a temperatura.

O humor combina o maior valor entre stress térmico e 45% da carga. `MoodTracker` aplica smoothing assimétrico: piora mais rápido e melhora mais devagar, com margem de histerese. Os thresholds são parâmetros de UX, não limites universais de segurança.

## WebSocket

`services/websocket-telemetry.js` conecta em `/ws/v1/metrics`, escolhendo `ws://` ou `wss://` conforme a página. Em desconexão, o state conserva o último snapshot, a interface identifica os dados como antigos e tenta reconectar depois de três segundos.
