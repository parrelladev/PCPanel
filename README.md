# PCPanel Telemetry POC

Primeira prova de conceito para coletar telemetria de hardware no Windows com Python, usando `pythonnet` para acessar `LibreHardwareMonitorLib.dll`.

O objetivo atual é somente validar a cadeia:

```text
Python -> pythonnet -> .NET Framework -> LibreHardwareMonitorLib -> sensores
```

Esta POC ainda não possui servidor HTTP, interface web, banco de dados ou coleta contínua em background.

## Estrutura esperada

```text
.
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── main.py
│   └── telemetry/
│       ├── __init__.py
│       ├── models.py
│       └── providers/
│           ├── __init__.py
│           ├── base.py
│           └── librehardwaremonitor.py
├── libs/
│   └── LibreHardwareMonitorLib.dll
└── scripts/
    └── inspect_sensors.py
```

A pasta `libs/` é o local recomendado para a DLL nesta POC.

## Pré-requisitos

### Obrigatórios

- Windows.
- Python **x64**.
- Python **3.11 ou superior**, dentro da faixa suportada pela versão de `pythonnet` fixada em `requirements.txt`.
- .NET Framework **4.7.2 ou superior**.
- `LibreHardwareMonitorLib.dll` compatível com **.NET Framework 4.7.2 (`net472`)**.
- Dependências instaladas a partir de `requirements.txt`.

A implementação atual seleciona explicitamente o runtime `netfx` do Python.NET e foi preparada para a build `net472` do LibreHardwareMonitorLib.

Para esta POC, **Python 3.12 x64 é a opção recomendada**.

> A arquitetura deve ser consistente. Misturar Python x86 com assemblies ou componentes x64 pode causar erros de carregamento, como `BadImageFormatException`. x86 não é um alvo desta POC.

## Criar o ambiente virtual

Na raiz do projeto, usando PowerShell:

```powershell
py -3.12 -m venv .venv
```

Se o launcher `py` não estiver disponível:

```powershell
python -m venv .venv
```

## Ativar o ambiente virtual

No PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Depois da ativação, confirme o Python utilizado:

```powershell
python --version
python -c "import struct; print(struct.calcsize('P') * 8)"
```

O segundo comando deve imprimir:

```text
64
```

Se a política local do PowerShell bloquear a ativação de scripts, use um terminal compatível com a política da máquina ou siga as regras de execução definidas para o ambiente. Não é necessário alterar permanentemente a política do sistema para executar a POC.

## Instalar as dependências

Com o ambiente virtual ativo:

```powershell
python -m pip install -r requirements.txt
```

O `requirements.txt` atual contém somente a dependência necessária para a interoperabilidade com .NET:

```text
pythonnet==3.1.0
```

Não instale um pacote PyPI separado chamado `clr`. O módulo `clr` utilizado pelo projeto é fornecido pelo `pythonnet`.

## Obter o LibreHardwareMonitor

Use o projeto oficial:

- Repositório: https://github.com/LibreHardwareMonitor/LibreHardwareMonitor
- Releases oficiais: https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases

O próprio projeto oficial alerta que **não é afiliado ao site `librehardwaremonitor.com`**. Para esta POC, prefira os releases disponibilizados pelo repositório oficial no GitHub.

O LibreHardwareMonitorLib suporta, entre outros targets, **.NET Framework 4.7.2**. Como o provider atual carrega o runtime `netfx`, utilize a versão da biblioteca destinada a `net472`.

A DLL necessária é:

```text
LibreHardwareMonitorLib.dll
```

Ao obter os binários, mantenha também junto dela quaisquer DLLs dependentes distribuídas com a mesma build. O provider adiciona o diretório da biblioteca ao caminho de resolução de assemblies do Python.NET.

## Instalar a DLL no projeto

A opção recomendada é criar:

```text
libs/
```

na raiz e colocar a biblioteca em:

```text
libs/LibreHardwareMonitorLib.dll
```

Exemplo:

```text
pcpanel/
├── app/
├── libs/
│   ├── LibreHardwareMonitorLib.dll
│   └── ... possíveis dependências da mesma distribuição
├── scripts/
└── requirements.txt
```

A implementação atual do `LibreHardwareMonitorProvider` procura a DLL, nesta ordem:

1. caminho passado diretamente ao construtor `dll_path`;
2. variável de ambiente `PCPANEL_LHM_DLL`;
3. `libs/LibreHardwareMonitorLib.dll` relativo ao projeto;
4. `libs/LibreHardwareMonitorLib.dll` relativo ao diretório atual;
5. `backend/libs/LibreHardwareMonitorLib.dll`, mantido como caminho alternativo pela implementação atual.

### Usar uma DLL em outro local

Para o script de inspeção:

```powershell
python scripts/inspect_sensors.py --dll-path "C:\Caminho\LibreHardwareMonitorLib.dll"
```

Também é possível definir a variável de ambiente usada pelo provider:

```powershell
$env:PCPANEL_LHM_DLL = "C:\Caminho\LibreHardwareMonitorLib.dll"
```

Depois:

```powershell
python scripts/inspect_sensors.py
```

ou:

```powershell
python -m app.main
```

A variável definida dessa forma vale para a sessão atual do PowerShell.

## Inspecionar todos os sensores

Execute na raiz do projeto:

```powershell
python scripts/inspect_sensors.py
```

O script abre o provider, atualiza o hardware uma vez, obtém os sensores e encerra o provider corretamente.

A saída é agrupada por hardware e tipo de sensor, mostrando:

- nome e tipo do hardware;
- nome do sensor;
- tipo do sensor;
- valor atual;
- mínimo;
- máximo.

Exemplo ilustrativo:

```text
Detected 27 sensor(s).

================================================================================
AMD Ryzen ... [Cpu]
================================================================================

  Temperature
  Sensor                                      Current          Min          Max
  -------------------------------------- ------------ ------------ ------------
  Core (Tctl/Tdie)                              52.63        43.10        71.84

  Load
  Sensor                                      Current          Min          Max
  -------------------------------------- ------------ ------------ ------------
  CPU Total                                     14.21         2.18        89.32

================================================================================
NVIDIA GeForce ... [GpuNvidia]
================================================================================

  Temperature
  Sensor                                      Current          Min          Max
  -------------------------------------- ------------ ------------ ------------
  GPU Core                                      45.20        38.10        67.40
```

Os nomes e a quantidade de sensores variam conforme CPU, GPU, placa-mãe, drivers, firmware e suporte do LibreHardwareMonitor para aquele hardware.

## Executar o entry point da POC

Na raiz do projeto:

```powershell
python -m app.main
```

Esse entry point realiza uma única coleta e mostra somente um resumo, por exemplo:

```text
PCPanel telemetry POC
Sensors detected: 27
Hardware devices: 5
Sensor types: Clock, Fan, Load, Power, Temperature, Voltage
Representative readings:
  AMD Ryzen ... | CPU Total (Load): 14.21
  AMD Ryzen ... | Core (Tctl/Tdie) (Temperature): 52.63
```

Para investigar a árvore completa, use `scripts/inspect_sensors.py`.

## Problemas comuns

### `LibreHardwareMonitorLib.dll was not found`

Confirme se existe:

```text
libs/LibreHardwareMonitorLib.dll
```

ou informe explicitamente:

```powershell
python scripts/inspect_sensors.py --dll-path "C:\Caminho\LibreHardwareMonitorLib.dll"
```

Também é possível usar `PCPANEL_LHM_DLL`.

### Falha ao importar `clr` ou `pythonnet`

Confirme que o ambiente virtual está ativo:

```powershell
python -m pip show pythonnet
```

Reinstale as dependências, se necessário:

```powershell
python -m pip install -r requirements.txt
```

Não instale o pacote independente `clr`; ele pode conflitar com o módulo fornecido pelo `pythonnet`.

### Falha ao inicializar o runtime .NET

O provider atual chama explicitamente:

```python
load("netfx")
```

Portanto, esta POC espera o **.NET Framework no Windows**. O Python.NET documenta que `netfx` é suportado apenas no Windows e recomenda .NET Framework 4.7.2 ou posterior.

Confirme também que está usando a build `net472` do `LibreHardwareMonitorLib`.

### `BadImageFormatException` ou erro ao carregar assembly

Verifique primeiro:

- Python x64;
- build correta do LibreHardwareMonitorLib;
- .NET Framework disponível;
- DLLs dependentes presentes no mesmo diretório da biblioteca principal.

Confirme a arquitetura do Python:

```powershell
python -c "import struct; print(struct.calcsize('P') * 8)"
```

Para esta POC, o resultado esperado é `64`.

### Nenhum sensor aparece

Primeiro execute:

```powershell
python scripts/inspect_sensors.py
```

Se ainda não houver sensores:

1. execute o aplicativo oficial LibreHardwareMonitor na mesma máquina e verifique se ele detecta o hardware;
2. confirme que a DLL utilizada pertence à mesma linha oficial do projeto e ao target esperado;
3. teste o terminal como administrador;
4. confira se os drivers do hardware estão instalados e atualizados;
5. verifique se o hardware específico é suportado pelo LibreHardwareMonitor.

Se o aplicativo oficial também não expuser determinado sensor, a POC normalmente não conseguirá obtê-lo através da mesma biblioteca.

### Apenas parte dos sensores aparece

Isso pode ser normal. O suporte varia entre fabricantes, modelos de placa-mãe, controladores, GPUs e dispositivos de armazenamento.

Alguns sensores requerem privilégios administrativos para acesso. **Administrador não é um requisito universal**, mas pode liberar sensores que não ficam acessíveis em uma sessão comum.

Para testar:

1. feche o terminal atual;
2. abra PowerShell como administrador;
3. ative novamente `.venv`;
4. execute:

```powershell
python scripts/inspect_sensors.py
```

Compare a saída com a execução sem elevação.

Se um sensor continuar ausente, compare novamente com o aplicativo oficial do LibreHardwareMonitor. Isso ajuda a separar uma limitação do nosso provider de uma limitação de suporte/acesso do próprio LibreHardwareMonitor.

## Referências técnicas

- LibreHardwareMonitor oficial: https://github.com/LibreHardwareMonitor/LibreHardwareMonitor
- Releases: https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases
- Python.NET: https://pythonnet.github.io/
- Carregamento de runtimes no Python.NET: https://pythonnet.github.io/pythonnet/python.html
- Pacote `pythonnet` no PyPI: https://pypi.org/project/pythonnet/

## Próximos passos

Depois que esta POC estiver validando sensores de forma consistente em hardware real, a camada de telemetria poderá evoluir para manter snapshots periódicos e, posteriormente, ser exposta por um backend HTTP/WebSocket. Essas funcionalidades ainda não fazem parte da implementação atual.
