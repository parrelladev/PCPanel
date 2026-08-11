# PCPanel

PCPanel é um aplicativo Windows que coleta telemetria de hardware e disponibiliza
um painel para o PC e para dispositivos na rede local. O produto possui pairing,
autorização por dispositivo, métricas em tempo real e execução de Actions
previamente configuradas.

O runtime instalável é dividido em dois processos:

```text
PCPanelTelemetryService                 PCPanelAgent.exe
Windows Service (LocalSystem)           usuário interativo, sem elevação
        │                                      │
        ├── LibreHardwareMonitor               ├── FastAPI / WebSocket
        ├── TelemetryManager                   ├── Auth / Pairing
        ├── snapshots raw                      ├── SQLite / MetricResolver
        └── named pipe local ──────────────────┤── Actions / shell=False
                                               └── tray
```

M10.1 a M10.9 estão implementados e foram validados no Windows físico usado no
desenvolvimento. A aceitação final M10.10 em uma máquina limpa, sem Python e sem
checkout do repositório, ainda está pendente. Portanto, o build atual é funcional,
mas ainda não deve ser anunciado como uma release final aceita.

## Instalação para usuário

O usuário precisa somente de:

```text
PCPanelSetup.exe
```

O instalador inclui Agent, Service, frontend, runtime Python embutido,
LibreHardwareMonitor e as demais dependências. Não é necessário instalar Python,
criar `.venv`, copiar o repositório ou abrir um terminal.

O artefato local gerado pelo build fica em:

```text
dist/installer/PCPanelSetup.exe
```

Execute o instalador e aceite o UAC. As opções abaixo exigem consentimento
explícito e começam desmarcadas:

- iniciar o Telemetry Service automaticamente com o Windows;
- iniciar o Agent quando o usuário entrar no Windows;
- iniciar Service e Agent ao concluir a instalação;
- permitir acesso ao Agent pela rede privada local.

Para uso imediato sem autostart, marque apenas “Iniciar Service e Agent ao
concluir”. Para acessar pelo celular, marque também a opção de rede privada.

Os binários são instalados em:

```text
%ProgramFiles%\PCPanel
```

Os dados do usuário ficam separados em:

```text
%LOCALAPPDATA%\PCPanel\pcpanel.db
```

O uninstall padrão preserva esse diretório. A remoção dos dados exige uma
confirmação separada cuja resposta segura/default é “Não”.

## Uso

O Agent apresenta um ícone na bandeja do Windows. O menu permite:

- abrir o painel local;
- copiar um endereço IPv4 válido para acesso pelo celular;
- consultar o estado do Telemetry Service;
- reiniciar o Service com UAC somente após o clique;
- sair do Agent sem parar o Service.

Para conectar um celular:

1. conecte PC e celular à mesma rede privada;
2. copie pelo tray o endereço `http://<IP-LAN>:8000/`;
3. abra o endereço no celular;
4. inicie o pairing pela interface;
5. consulte o código exibido localmente em uma janela do Windows;
6. informe o código no celular.

O código não é devolvido pela API remota. O bearer token é emitido uma vez ao
concluir o pairing; o banco armazena somente seu hash.

Um banco novo não recebe Actions automaticamente. O catálogo contém somente
Actions persistidas com `enabled=true`. O produto não descobre executáveis nem
aceita cadastro ou alteração de comandos pela rede.

## Arquitetura e fronteira de privilégios

### Telemetry Service

O `PCPanelTelemetry` contém exclusivamente a fronteira de hardware:

```text
hardware
  ↓
LibreHardwareMonitorProvider
  ↓
TelemetryManager
  ↓
TelemetrySnapshot raw
  ↓
named pipe local
```

O Service não:

- hospeda FastAPI ou escuta TCP/LAN;
- conhece pairing, bearer tokens ou Auth;
- abre `pcpanel.db`;
- conhece ou executa Actions;
- inicia programas do usuário;
- possui tray ou UI;
- oferece comandos genéricos pelo IPC.

`LocalService` foi testado fisicamente, mas retornou `null` para os sensores de
temperatura da CPU. O mesmo binário retornou a temperatura imediatamente como
`LocalSystem`. Por isso a identidade mais privilegiada é usada somente no
processo hardware-only. A evidência e a decisão estão documentadas em
`packaging/SERVICE_IDENTITY.md`.

### Agent

O `PCPanelAgent.exe` roda na sessão interativa do usuário e sem elevação. Ele
contém FastAPI, HTTP/WebSocket, Auth, pairing, SQLite, `MetricResolver`, Actions e
tray. Se o Service estiver indisponível, o Agent e a UI continuam vivos, mostram
telemetria indisponível e recuperam a conexão IPC quando o Service retornar.

O Agent é single-instance por sessão. Upgrade e uninstall solicitam seu
encerramento gracioso e aguardam a liberação real da instância.

### Named Pipe IPC

O transporte entre Service e Agent usa:

```text
\\.\pipe\PCPanelTelemetry
```

Características:

- framing JSON com prefixo de tamanho e versão de protocolo;
- comandos somente `GET_STATUS` e `GET_LATEST_SNAPSHOT`;
- DACL explícita para `SYSTEM`, Administrators e Interactive Users;
- `PIPE_REJECT_REMOTE_CLIENTS` habilitado;
- nenhuma primitive de command execution.

O framing e a DACL foram validados com um Agent Windows normal, interativo e não
elevado. Testes executados sob tokens restritos detectam esse ambiente e são
marcados como skipped, sem enfraquecer a ACL.

## Metrics

O Service entrega snapshots raw. A transformação em métricas de produto permanece
pura e ocorre no Agent:

```text
TelemetrySnapshot → MetricResolver → MetricSnapshot → REST/WebSocket/UI
```

As métricas principais incluem temperatura/carga de CPU e GPU e uso de memória.
Quando um sensor não é suportado, a chave permanece no contrato com `value=null`.

Endpoints principais:

- `GET /api/v1/health`;
- `GET /api/v1/telemetry`;
- `GET /api/v1/sensors`;
- `GET /api/v1/metrics`;
- `WS /ws/v1/telemetry`;
- `WS /ws/v1/metrics`.

## Auth e Actions

O fluxo de autorização é:

```text
pairing → Device → opaque bearer token → AuthorizedDevice
```

As rotas de Actions exigem um dispositivo autorizado:

- `GET /api/v1/actions`;
- `POST /api/v1/actions/{action_id}/execute`.

O fluxo de execução é restrito:

```text
action_id remoto
  ↓
ActionService
  ↓
ActionRegistry
  ↓
ActionDefinition persistida e preexistente
  ↓
WindowsProcessExecutor(shell=False)
```

O cliente remoto nunca controla `executable`, argumentos, working directory,
shell ou command line. Actions são executadas pelo Agent para que o processo
apareça no desktop do usuário, nunca na Session 0 do Service.

No runtime empacotado, as rotas protegidas de Actions são habilitadas por padrão.
No modo de desenvolvimento continuam opt-in por
`PCPANEL_ENABLE_ACTIONS_API=true`. Em ambos os casos, bearer válido continua
obrigatório.

## Persistência e migração

O PCPanel usa SQLite com `PRAGMA user_version`, migrations incrementais e falha
explícita para schemas futuros não suportados. O banco persiste:

- Devices e hashes de bearer tokens;
- status de revogação;
- Actions estruturadas e seu estado `enabled`.

Pairing codes, sessões pendentes e bearer tokens plaintext não são persistidos.

No runtime empacotado, o diretório `%LOCALAPPDATA%\PCPanel` recebe ACL restrita ao
usuário atual e `SYSTEM`. A variável `PCPANEL_DATA_DIR` permanece disponível como
override explícito. No modo de desenvolvimento, o default continua sendo
`./data`.

Para migrar um banco legado sem sobrescrever um destino existente:

```powershell
python scripts/migrate-data.py .\data `
  --destination "$env:LOCALAPPDATA\PCPanel"
```

A migração copia para arquivo temporário, valida o schema e conclui com replace
atômico. Upgrade do instalador preserva o data directory e aplica migrations no
próximo startup do Agent.

## Firewall

Quando autorizada no instalador, a regra criada é:

- inbound;
- perfil Private;
- limitada ao executável do Agent;
- origem `LocalSubnet`;
- nome `PCPanel Agent (Private LAN)`.

O instalador não desabilita o Windows Firewall. A regra é removida no uninstall.
O produto ainda usa HTTP sem TLS; utilize apenas uma LAN confiável, pois um bearer
token pode ser observado por alguém com acesso ao caminho de rede.

## Desenvolvimento

Requisitos do ambiente de desenvolvimento:

- Windows x64;
- Python compatível com Python.NET;
- .NET Framework compatível;
- PowerShell.

Crie o ambiente e instale as dependências:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

Instale a distribuição fixada do LibreHardwareMonitor:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\install_lhm.ps1
```

O modo monolítico de desenvolvimento continua disponível:

```powershell
python -m app.main
```

Variáveis reconhecidas:

| Variável | Finalidade | Default de desenvolvimento |
|---|---|---|
| `PCPANEL_LHM_DLL` | DLL alternativa do LHM | distribuição em `libs/` |
| `PCPANEL_TELEMETRY_INTERVAL` | intervalo de coleta | `0.5` |
| `PCPANEL_HOST` | bind HTTP | `0.0.0.0` |
| `PCPANEL_PORT` | porta HTTP | `8000` |
| `PCPANEL_ENABLE_ACTIONS_API` | habilita Actions protegidas | `false` |
| `PCPANEL_DATA_DIR` | diretório de dados | `./data` |

## Build

Instale as dependências de build fixadas em `requirements-build.txt` e execute:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build.ps1
```

Isso gera:

```text
dist/PCPanelAgent/PCPanelAgent.exe
dist/PCPanelTelemetryService/PCPanelTelemetryService.exe
```

Para compilar o instalador com Inno Setup 6.7.3 disponível em
`.tools/InnoSetup/ISCC.exe`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\build_installer.ps1
```

Resultado:

```text
dist/installer/PCPanelSetup.exe
```

`build/`, `dist/`, `.tools/`, `venv/`, dados locais e bibliotecas de terceiros não
são versionados. O setup deve ser distribuído como artefato de release, não como
arquivo do commit.

## Testes

Execute:

```powershell
python -m pytest -q
git diff --check
```

A suíte cobre domínios, REST/WebSocket, Auth, Actions, persistência, IPC, Service,
Agent, tray, lifecycle, migração, packaging e política do instalador. Testes não
abrem programas reais; a validação de Notepad, SCM, tray, UAC e hardware é manual.

O último ciclo completo do M10.9 passou com 416 testes e dois skips esperados do
IPC quando pytest roda sob um token que restringe `INTERACTIVE`.

## Upgrade, downgrade e uninstall

O upgrade:

- encerra o Agent de forma controlada;
- aguarda o Service parar;
- substitui binários em `Program Files`;
- reconfigura a identidade hardware-only;
- preserva banco, Devices, tokens e Actions;
- respeita novamente as escolhas de autostart.

Downgrade automático não é suportado. Um binário antigo diante de schema futuro
falha claramente sem tentar rebaixar ou recriar o banco.

O uninstall remove Service, Agent, startup, firewall, atalhos e binários. Dados são
preservados por padrão e só são apagados após confirmação explícita.

## Estado dos milestones

- M5 — Actions Core: concluído;
- M6 — Pairing & Authorization: concluído;
- M7 — Authorized Actions API: concluído;
- M8 — Persistent Configuration: concluído;
- M9 — Product UI: concluído e aceito fisicamente;
- M10.1–M10.9 — packaging e experiência instalável: implementados e validados;
- M10.10 — clean machine acceptance: pendente.

O Milestone 10 somente poderá ser declarado concluído depois da instalação em
Windows limpo/equivalente, reboot com autostart consentido, pairing pelo celular,
persistência após reboot, upgrade e uninstall nesse ambiente.

## Limitações atuais

- aceitação final em máquina Windows limpa ainda pendente;
- HTTP sem TLS na LAN;
- ausência de auto-update;
- nenhuma descoberta automática de programas;
- nenhum CRUD remoto de Actions;
- sem cloud, mDNS, shell remota ou comandos de energia do Windows;
- disponibilidade de sensores depende do hardware, drivers e LHM.
