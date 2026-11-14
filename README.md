# Chess Stone

![Arte de apresentacao do Chess Stone](assets/artwork.jpg)

Prototipo 2D de card game de xadrez para um jogador contra IA, em Python 3.10+,
**pygame-ce** e **python-chess** (pacote `chess`). Sem imagens externas ou
animacoes: regras e efeitos independem da interface.

## Executar

No PowerShell, na raiz do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Para um deck menor e resultados reproduziveis:

```powershell
.\.venv\Scripts\python.exe main.py --deck-size 12 --seed 42
```

## Manual do jogador

Consulte o **[MANUAL.md](MANUAL.md)** para controles, regras de combate,
palavras-chave, Endgame, condicoes dos seis mates, colecao, crafting e
montagem de decks. Este README concentra instalacao e documentacao tecnica.

## Persistencia e integracao

Os arquivos locais `data\decks.json` e `data\collection.json` sao criados no
primeiro salvamento/resgate e ignorados pelo Git. Decks sao um objeto JSON
que associa nomes a listas de IDs:

```json
{
  "Peoes e Torres": ["peao", "peao", "torre"],
  "Teste rapido": ["cavalo", "bispo", "dama"]
}
```

O inventario registra o historico de recompensas. Variantes tem IDs estaveis,
como `torre__improved` e `torre__perfect`; seus atributos sao derivados
deterministicamente do catalogo base em `crafting.py`.

Os puzzles usam a [API oficial Lichess](https://lichess.org/api#tag/Puzzles/operation/apiPuzzleNext)
(`GET /api/puzzle/next?angle=...`). A associacao entre cartas e temas fica em
`crafting.py`; os temas e as regras de recompensa estao no
[manual](MANUAL.md#crafting-por-puzzles-lichess).

## Estrutura

| Arquivo | Responsabilidade |
|---|---|
| `MANUAL.md` | Regras e guia do jogador |
| `main.py` | Estados Menu/Colecao/Puzzle/Deck builder/Partida/Fim, desenho, cliques, agenda da IA sem bloquear eventos |
| `collection_view.py` | Catalogo com busca, filtros, detalhes, disponibilidade e entrada do crafting |
| `crafting.py` | Temas por carta, qualidades, variantes e inventario persistente |
| `chess_puzzles\` | Modulo independente de puzzles: download Lichess, validacao, sessao e resultado |
| `puzzles.py` | Imports de compatibilidade para o modulo `chess_puzzles` |
| `puzzle_view.py` | Tabuleiro de xadrez no Pygame, requisicoes em segundo plano e resgate |
| `ui_theme.py` | Paleta de cores compartilhada pelas telas |
| `audio.py` | Impactos genericos pre-carregados e reproducao imediata ao aplicar dano |
| `tools\generate_impacts.py` | Geracao reproduzivel dos sons originais de impacto |
| `deck_store.py` | Validacao de decks e persistencia local em JSON |
| `game_engine.py` | Estado, jogadas legais, combate, turnos, compras, Endgame e IA |
| `mate_rules.py` | Formacoes anunciadas, cancelamento e vitorias alternativas |
| `effect_parser.py` | Resolucao de alvos, condicoes e execucao ordenada dos efeitos |
| `csv_to_json.py` | Conversao e validacao do catalogo; utilizavel sem pygame |
| `data\cards.csv` | Fonte editavel em planilha, UTF-8 e delimitador virgula |
| `data\cards.json` | Catalogo validado carregado pelo jogo |
| `tests\` | Testes de dados, regras, cliques da interface e partidas completas reproduziveis |

## Reutilizar os puzzles em outro jogo

Copie a pasta `chess_puzzles\` para o outro projeto e instale `chess>=1.11.2,<2`.
O modulo nao depende de pygame, cartas, interface ou persistencia do Chess Stone.
`download_puzzle` e sincrono; execute-o em uma thread se a interface nao puder
esperar pela rede. O tema e um identificador da API Lichess, nao um ID de carta.

```python
import chess
from chess_puzzles import PuzzleError, PuzzleSession, download_puzzle

try:
    puzzle = download_puzzle("fork", user_agent="MeuJogo/1.0")
    session = PuzzleSession(puzzle)
    # Para cada tentativa do jogador:
    correct = session.play(chess.Move.from_uci("e2e4"))
    if session.result is not None:
        result = session.result
        print(result.quality, result.errors, result.elapsed, result.player_moves)
except PuzzleError as error:
    print(error)  # error.retry_after informa o tempo de espera, se aplicavel.
```

O lance do exemplo deve ser substituido pelo lance escolhido pelo jogador.
Um lance incorreto incrementa `errors` sem alterar o tabuleiro; um correto
aplica tambem a resposta do adversario, quando existir. `result` e `None`
antes da conclusao e depois retorna um `PuzzleResult` imutavel com ID, tema,
rating, erros, tempo em segundos, numero de lances do jogador e qualidade.
O tempo e a qualidade ficam congelados ao concluir; abandonar nao produz resultado.

A classificacao padrao e `perfect` (sem erros, ate 60 segundos por lance),
`improved` (ate um erro, ate 120 segundos por lance) ou `basic` (demais casos).
Outro jogo pode fornecer `PuzzleSession(puzzle, grader=funcao)`, onde a funcao
recebe `(errors, elapsed, player_moves)` e retorna uma string de classificacao.
A propriedade `quality` durante a sessao e uma previa, nao um resultado final.
Cada jogo decide suas recompensas e persistencia; o Chess Stone conserva as regras
padrao e o formato existente da colecao.

## Imagens e sons das cartas

A pasta `assets\cards\` possui uma subpasta para cada ID de carta do catalogo,
alem de `rei` para o heroi. Coloque a imagem e os sons juntos na pasta da carta:

```text
assets\
  cards\
    peao\
      art.png
      on_play.ogg
      on_attack.ogg
      on_death.ogg
      on_effect.ogg
    cavalo\
    bispo\
    torre\
    dama\
    cravada_absoluta\
    ataque_duplo\
    par_de_bispos\
    coluna_aberta\
    zugzwang\
    roque\
    sacrificio_da_dama\
    mate_anastasia\
    mate_boden\
    mate_abafado\
    mate_gaveta\
    mate_opera\
    endgame_puro\
    peao_passado\
    rei\
```

Os arquivos mostrados em `peao` sao exemplos de nomes; nenhuma imagem ou som
foi incluido. Use essa mesma convencao em cada pasta: `art.png` para a arte,
`on_play.ogg` ao jogar, `on_attack.ogg` ao atacar, `on_death.ogg` ao morrer e
`on_effect.ogg` para o efeito. Prefira PNG com transparencia e audio OGG ou WAV
(`on_play.wav`, por exemplo). Eventos que nao se aplicam a uma carta podem
ficar sem arquivo.

Para artes/sons exclusivos das qualidades, use subpastas opcionais `improved`
e `perfect` dentro da pasta base, por exemplo
`assets\cards\torre\perfect\art.png`. Para novas cartas, crie uma pasta com o
mesmo `id` do CSV, sem acentos ou espacos.

Os arquivos `.gitkeep` apenas preservam as pastas vazias no Git e podem ser
removidos depois de adicionar seus recursos. **Esta estrutura ainda nao carrega
nem reproduz os arquivos no jogo**; a interface continua minimalista.

### Sons genericos de impacto

O jogo ja reproduz os impactos originais incluidos em `assets\sounds\impacts\`:
`light.wav` para 1-2 de dano, `medium.wav` para 3-4 e `heavy.wav` para 5 ou mais.
Sao sons sintetizados, sem recursos de terceiros, com duracoes de 120, 180 e
260 ms, respectivamente. Podem ser recriados com:

```powershell
python tools\generate_impacts.py
```

Os WAVs sao carregados uma vez ao iniciar. O motor notifica o cliente
sincronamente logo apos descontar a vida; o som e iniciado nesse mesmo ponto,
sem esperar o proximo frame, percorrer o log ou usar temporizadores. Isso cobre
ataques do jogador/IA, contra-ataques, feiticos, efeitos em area, dano letal e
fadiga, inclusive contra o Rei. Cada alvo atingido dispara um impacto;
impactos simultaneos podem se sobrepor. Cura, destruir sem dano, dano zero e
dano absorvido por Escudo Divino nao disparam o som.

O mixer usa buffer de 256 amostras a 44,1 kHz (aproximadamente 5,8 ms por buffer),
volume de 45% e pelo menos 16 canais. A latencia audivel final tambem depende do
driver e do dispositivo; nao e possivel garantir latencia fisica zero. Nenhuma
reproducao bloqueia o loop. Se o dispositivo ou os WAVs estiverem indisponiveis,
o jogo continua com aviso visivel no menu/partida e detalhes no console.
Os sons especificos de `assets\cards\` continuam sem carregamento automatico.

## Editar as cartas

Exporte uma planilha como CSV UTF-8 com o cabecalho exato:

```text
id,name,category,card_type,cost,attack,health,keywords,trigger,effect_code,description
```

`card_type` aceita `minion` ou `spell`; ataque e vida sao obrigatorios para
lacaios. `keywords` aceita identificadores ingleses ou os nomes portugueses
separados por `|`. Os IDs devem ser unicos e estaveis.
`category` aceita somente `Peça`, `Tática` ou `Estratégia`.
Raridade e categoria sao independentes: efeitos `win_pattern` geram
`"rarity": "legendary"` no JSON, preservando a restricao dos mates no deck.

```powershell
python csv_to_json.py
python csv_to_json.py data\cards.csv data\cards.json
```

O conversor rejeita custos/atributos invalidos, IDs duplicados, palavras-chave,
acoes, alvos e gatilhos desconhecidos, alem de referencias a cartas inexistentes.
O jogo revalida o JSON ao carregar. Apenas `on_play` solicita alvo manual;
feiticos nao podem usar gatilhos futuros, pois nao permanecem na mesa.
Uma conversao invalida nao substitui o catalogo existente.

### Efeitos

Vitoria alternativa usa `{"trigger":"on_play","action":"win_pattern","pattern":"anastasia"}`.
Os padroes aceitos sao `anastasia`, `boden`, `smothered`, `back_rank`, `opera` e
`opposition`, apenas em feiticos lendarios. O parser encaminha a
acao para o modulo de regras de mate; padroes desconhecidos sao rejeitados.

O formato curto aceita `DAMAGE`, `HEAL`, `DRAW` e `FREEZE`, separados por `|`:

```text
DAMAGE:2:TARGET_2_ENEMIES|DRAW:1:IF_KILLED
```

Isso gera dano a ate duas unidades inimigas **distintas com menor Vida**,
desempatando pelo menor slot, com compra de uma carta **por unidade abatida**.
Escudo Divino nao conta como abate. Os efeitos nao usam RNG; decks continuam
embaralhados e a IA pode escolher alvos manuais aleatoriamente.
`DRAW:1:SELF` compra para o dono da carta. Para efeitos complexos, use um objeto
ou uma lista JSON na celula; planilhas normalmente escapam as aspas na exportacao.

```json
[
  {
    "trigger": "on_play",
    "action": "buff",
    "attack": 2,
    "duration": "until_end_of_turn",
    "target": "target_ally_minion"
  },
  {
    "trigger": "on_play",
    "action": "grant_keyword",
    "keyword": "rush",
    "target": "target_ally_minion"
  }
]
```

As acoes sao executadas na ordem. Cada acao de area aplica suas alteracoes antes
de resolver mortes. Todos os efeitos manuais de uma mesma jogada compartilham um
unico alvo, valido para todos eles. Um lacaio com alvo manual primeiro exige
posicionamento e depois selecao de alvo. `on_kill` e um objeto de acao adicional,
executado por abate e sem solicitar novos alvos.

Gatilhos: `on_play`, `on_death`, `on_turn_start`, `on_turn_end`. O gatilho da
coluna CSV e o padrao; cada objeto JSON pode sobrescreve-lo.

Acoes: `damage`, `heal`, `buff`, `draw`, `summon`, `freeze`, `grant_keyword`,
`destroy`, `activate_king`. Dano/cura/compra exigem `amount`; `summon` usa
`card_id` e `count` opcional. `buff` usa `attack`/`health` positivos ou zero;
apenas ataque aceita duracao `until_end_of_turn`. `grant_keyword` usa `keyword`.
Congelamento tem duracao fixa; `amount` no formato curto de FREEZE nao altera isso.

Alvos: `self`, `own_hero`, `enemy_hero`, `target_enemy`, `target_enemy_minion`,
`target_ally`, `target_ally_minion`, `all_enemies`, `all_enemy_minions`,
`all_allies`, `all_allied_minions`, `adjacent_allies`, `lowest_health_enemy`,
`lowest_health_enemy_minion`. `self` e o lacaio de origem ou o heroi para feiticos.
`adjacent_allies` usa slots fixos imediatamente vizinhos; lacunas interrompem
a adjacencia. Seletores `lowest_health_*` aceitam `count`, ordenam por Vida e
desempatam pelo slot (heroi fora da mesa vem depois dos slots em empates).
Os alvos sao definidos antes da resolucao da acao.
Seletores antigos `random_*` sao rejeitados pela validacao.
O filtro opcional `card_id` restringe os alvos a uma carta.

Cada `Unit.slot` identifica uma posicao fixa de 0 a 5; `Player.board` contem
apenas unidades ocupantes, ordenadas por slot. `unit_at` e `free_slots` consultam
ocupacao sem compactar a mesa. Apoio modifica somente dano de combate, antes de
Escudo Divino/Armadura; o bonus de Centro adiciona 1 mana por um unico turno,
sem elevar o limite de 10 cristais permanentes. Veja o manual para as regras.

A condicao suportada e `{"type":"friendly_count","card_id":"bispo","at_least":2}`,
utilizada em Par de Bispos. Se nao atendida, a acao e ignorada com registro no
log; o custo da jogada continua sendo pago. Sacrificio da Dama exige uma Dama
aliada selecionavel, a destroi e executa dano em area seguido de compras.

## Verificacoes

```powershell
python -m unittest discover -s tests -v
python main.py --smoke-test
```

Os testes de interface e o segundo comando usam o driver SDL dummy, sem janela.
Para executar somente as regras, sem depender de pygame, use
`python -m unittest discover -s tests -p test_game.py -v`.
Os testes de decks usam arquivos temporarios e nao alteram sua biblioteca.
Os testes de crafting tambem usam arquivos temporarios e respostas de rede
simuladas; nao dependem de internet nem modificam o inventario local.

### TODO

- Vamos adicionar classes de heroes que seriam os campeões de chess. Seriam 4 classes dos perfis de jogadores, ativista, pragmático, reflector, teorista.