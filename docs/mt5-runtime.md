# Runtime MT5 no servidor

## Objetivo

Preparar um runtime reproduzivel para executar MetaTrader 5 neste servidor Linux sem depender de instalacao global no host.

## Decisao

Usar Docker para encapsular:

- Ubuntu 24.04
- Wine 9
- Xvfb
- utilitarios de automacao basicos

## Motivo

- o host nao tem `wine`
- o host nao tem `sudo` sem senha
- o projeto precisa de setup repetivel
- a execucao do MT5 em Linux e suportada oficialmente via Wine

## O que o runtime resolve

- instala o runtime Wine de forma isolada
- deixa a imagem reproduzivel
- permite persistir `WINEPREFIX` em volume
- evita acoplar o projeto ao estado atual do host

## O que ainda nao resolve sozinho

- login em corretora
- conta demo/real
- automacao completa do wizard do MT5
- estrategia
- execucao de ordens do bot

## Artefatos do projeto

- `infra/mt5-runtime/Dockerfile`
- `infra/mt5-runtime/verify-runtime.sh`
- `infra/mt5-runtime/bootstrap-mt5.sh`
- `infra/mt5-runtime/start-remote-desktop.sh`
- `scripts/build-mt5-runtime.sh`
- `scripts/run-mt5-desktop.sh`

## Validacao minima do passo 1

O passo 1 e considerado concluido quando:

1. a imagem Docker builda
2. o smoke test do runtime retorna versao do Wine
3. o bootstrap do MT5 fica pronto para a proxima rodada

## Estado validado em 2026-07-17

- imagem `2lotus-mt5-runtime` buildando localmente
- `verify-runtime` retornando `wine-9.0` e `xvfb_ok=yes`
- prefixo Wine persistido em `.runtime/mt5-prefix`
- `system32/kernel32.dll` e `syswow64/kernel32.dll` presentes no prefixo limpo
- logs persistidos em `.runtime/logs`

## Estado de instalação

O runtime Wine está definido no Dockerfile, mas a imagem e o terminal ainda precisam ser construídos
e instalados neste host. A primeira instalação permanece assistida por noVNC.

Sinais observados:

- o erro antigo de `syswow64/ntdll.dll` foi resolvido ao instalar `wine32`
- o prefixo passou a ser criado corretamente ao usar `/usr/lib/wine/wine`
- a etapa do WebView2 ainda consome o tempo do bootstrap e o arquivo `mt5setup.log` nao chega a ser gerado nesta rodada

## Proximo passo tecnico

Habilitar uma etapa de primeira instalacao assistida do desktop Windows dentro do container, com um destes caminhos:

1. expor VNC/noVNC para concluir o wizard manualmente uma vez
2. automatizar a primeira instalacao com `xdotool` apos validar a arvore de janelas

A partir disso, o terminal instalado pode ser congelado no volume persistido e reutilizado pelo servico do bot.

## Desktop remoto local

O runtime agora possui uma sessao grafica local com `x11vnc` e `noVNC` para concluir a primeira instalacao do terminal dentro do container.

Uso:

1. buildar a imagem com `./scripts/build-mt5-runtime.sh`
2. iniciar o desktop com `./scripts/run-mt5-desktop.sh`
3. abrir `http://127.0.0.1:6080/vnc.html?host=127.0.0.1&port=6080`
4. concluir manualmente o WebView2 e o instalador do MT5 se aparecerem janelas interativas

Observacoes:

- as portas `5900` e `6080` ficam publicadas apenas em `127.0.0.1`
- o estado do terminal continua persistido em `.runtime/mt5-prefix`
- os logs continuam em `.runtime/logs`

## Rede atual

O serviço API usa `network_mode: service:mt5`; portanto, MT5 e API compartilham o mesmo namespace de
rede e o EA deve acessar `http://127.0.0.1:1112`.

O checklist completo está em:

- `docs/live-core-go-live.md`

## Referencias oficiais

- instalacao do MT5 no Linux via Wine:
  `https://www.metatrader5.com/en/terminal/help/start_advanced/install_linux`
- integracao Python do MT5:
  `https://www.mql5.com/en/docs/python_metatrader5`
