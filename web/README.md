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

Os fluxos são centralizados por domínio:

```text
websocket-telemetry.js → telemetry state → app/components → DOM
localStorage → auth-bootstrap/authenticated-fetch → auth state → app → DOM
```

O serviço recebe snapshots canônicos e estados de conexão. O state mantém o último snapshot e notifica assinantes. Componentes recebem dados do state e não conhecem sensores raw.

O dashboard usa CPU, GPU e RAM em três colunas no landscape e uma coluna no portrait. Se o WebSocket cair, o último snapshot permanece visível como dado anterior; a reconexão usa backoff de 1, 2, 4 e até 8 segundos, passa a Offline após 15 segundos e tenta imediatamente ao voltar do background quando o socket já encerrou.

No início, a aplicação valida `pcpanel.deviceToken` em `/api/v1/auth/status` antes de exibir o dashboard. Respostas 401 removem a credencial e retornam ao estado não pareado; falhas de rede preservam a credencial e exibem o estado offline. O dispositivo autorizado retornado pelo backend permanece somente em memória.

Dispositivos não pareados usam um fluxo em duas etapas: informam o nome, recebem apenas os metadados temporários de `/pairing/start` e digitam o código exibido localmente no PC. Após `/pairing/complete`, a credencial é armazenada e validada novamente em `/auth/status` antes de o dashboard ser liberado. Identificador, código e expiração do pairing não são persistidos pelo navegador.

A aba Apps carrega `/api/v1/actions` uma vez na primeira entrada e oferece atualização manual. O catálogo é projetado no frontend exclusivamente como `id` e `label`; lista vazia, API desabilitada, indisponibilidade de rede e falha do servidor possuem estados visuais distintos.

Cada card executa somente seu `action_id` por `POST /api/v1/actions/{action_id}/execute`. Os estados `idle`, `executing`, `success` e `error` são independentes por card; um segundo toque é bloqueado durante a requisição e o feedback retorna ao estado normal automaticamente.

A aba Sistema é somente leitura: combina o nome do dispositivo autorizado em memória, a conexão do WebSocket para servidor e telemetria e o estado compartilhado do catálogo de Actions. Nenhum comando ou segredo é apresentado por essa tela.

## Contrato canônico

Cada snapshot contém `sequence`, `captured_at` e um objeto `metrics` indexado pelas chaves `cpu.temperature`, `cpu.load`, `gpu.temperature`, `gpu.load` e `memory.load`. Cada leitura contém `value`, `unit` e `source_sensor_identifier`. A interface usa somente chave, valor e unidade; o identificador de origem permanece disponível apenas para diagnóstico.

## Política térmica e humor

Os thresholds provisórios da POC são CPU 65/85/95 °C e GPU 65/83/90 °C. `thermalStress()` converte essas faixas em stress de 0 a 100. A cor do gato migra da cor-base do card para amarelo, laranja e vermelho conforme a temperatura.

O humor combina o maior valor entre stress térmico e 45% da carga. `MoodTracker` aplica smoothing assimétrico: piora mais rápido e melhora mais devagar, com margem de histerese. Os thresholds são parâmetros de UX, não limites universais de segurança.

## WebSocket

`services/websocket-telemetry.js` conecta em `/ws/v1/metrics`, escolhendo `ws://` ou `wss://` conforme a página. Em desconexão, o state conserva o último snapshot, a interface identifica os dados como antigos e tenta reconectar depois de três segundos.
