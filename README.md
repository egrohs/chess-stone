# Chess Stone

Prototipo 2D de card game de xadrez para um jogador contra IA, em Python 3.10+
e **pygame-ce**. Sem imagens externas ou animacoes: regras e efeitos independem
da interface.

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

O deck automatico usa copias ciclicas das cartas do catalogo, embaralhadas. O tamanho
padrao e 30; nao ha limite de copias neste prototipo. Cada jogador recebe tres
cartas iniciais (ou o tamanho do deck, se menor). O primeiro jogador tambem
compra no inicio do seu primeiro turno. Nao ha mulligan, moeda, armas ou poder
heroico.

## Deck builder

No menu, use **Montar / editar decks**. Clique no campo de nome para digitar e
use **+** / **-** para ajustar as copias de cada carta. As paginas permitem
percorrer todo o catalogo. Nao ha limite de copias nem tamanho fixo: o deck deve
conter pelo menos uma carta. O painel mostra total, tipos de carta e custo medio.

**Salvar / substituir e selecionar** grava o deck e o seleciona para a proxima
partida. Salvar com um nome existente substitui sua composicao; mudar o nome
cria outro deck. Clique em um deck salvo para carrega-lo e edita-lo.
**Novo**, **Voltar** e Esc descartam alteracoes nao salvas.

No menu, clique no seletor **Deck** para alternar entre os salvos e o automatico.
A selecao vale durante a sessao; os decks permanecem salvos ao fechar o jogo.
O deck escolhido e usado pelo jogador, inclusive ao jogar novamente. A IA
continua usando o deck automatico de `--deck-size` cartas; essa opcao nao altera
o tamanho do deck personalizado. Ambos sao embaralhados antes da partida.

Os decks ficam em `data\decks.json`, criado no primeiro salvamento e ignorado
pelo Git por ser um arquivo local do jogador. Formato:

```json
{
  "Peoes e Torres": ["peao", "peao", "torre"],
  "Teste rapido": ["cavalo", "bispo", "dama"]
}
```

Nomes aceitam ate 40 caracteres. IDs desconhecidos, decks vazios e JSON
malformado geram uma mensagem visivel; um arquivo invalido nao e sobrescrito
pelo editor. Corrija-o e reabra o editor para recarregar. Os salvamentos usam
substituicao atomica para preservar o arquivo anterior se houver falha.

## Controles

- Clique em uma carta: borda dourada indica selecao; verde indica alvos validos.
- Lacaio: clique em um espaco verde vazio para adicionar ao fim da fila. As
  barras verdes entre unidades permitem escolher a posicao de insercao.
- Feitico com alvo: clique em um alvo verde. Sem alvo: use **Jogar carta**.
- Clique em uma unidade aliada pronta e depois em um inimigo verde para atacar.
  Azul indica prontidao; vermelho destaca Provocar. Clique direito ou Esc cancela.
- **Passar Turno**, **Ativar Rei (Endgame)** e **Voltar ao Menu** ficam a direita.
  O painel mostra a descricao completa da carta selecionada e as ultimas jogadas.

## Regras adotadas

Cada jogador comeca com 30 de vida. A mana maxima aumenta em um no inicio de
cada turno proprio, ate 10, e e totalmente restaurada. A mao comporta 10 cartas;
compras excedentes sao descartadas, mas consomem a carta do deck. Cada lado
comporta **oito unidades, incluindo o Rei**. Combate causa dano simultaneo e
mantem dano entre turnos. Morte dos dois Reis na mesma acao resulta em empate.

| Palavra-chave | Comportamento |
|---|---|
| Provocar | Ataques devem escolher uma unidade inimiga com Provocar. Nao restringe feiticos. |
| Investida | Permite atacar imediatamente, inclusive o heroi/Rei. |
| Rapidez | No turno de invocacao permite atacar unidades, mas nao o heroi nem o Rei ativado. |
| Escudo Divino | Absorve a primeira instancia de dano positivo; nao impede destruir. |
| Furia dos Ventos | Permite dois ataques por turno, sem remover a espera de invocacao. |
| Elusivo | Impede selecao manual por feiticos de ambos os lados. Nao bloqueia ataques, efeitos de area/aleatorios nem efeitos de entrada de lacaios. |

Congelamento impede ataques ate o fim do proximo turno do dono da unidade,
incluindo o restante do turno atual se aplicado durante ele. Bonus temporario
de ataque termina no fim do turno em que foi aplicado. Invocacoes por efeitos
nao executam `on_play`; palavras-chave impressas continuam funcionando. Efeitos
de morte acontecem depois de remover as baixas simultaneas. A morte de um heroi
encerra a partida antes de novos efeitos de morte ou compras por abate.

### Ativacao do Rei

Foi escolhida a variante **2 de ataque / vida atual do heroi**, nao a variante
2/8. A vida e compartilhada: causar dano ou curar o Rei afeta diretamente a
condicao de vitoria. O retrato deixa de ser um alvo separado. O Rei entra no fim
da fila e precisa esperar para atacar, como uma unidade sem Investida.

- Ao comprar a ultima carta, o Rei e ativado automaticamente. Mesa cheia adia
  sua entrada ate surgir uma vaga; o heroi continua vulneravel enquanto espera.
- Comprar de um deck vazio causa fadiga crescente: 1, 2, 3... de dano.
- Ao terminar a oitava rodada completa (16 turnos individuais), ou qualquer turno
  posterior, **ate tres unidades somadas entre os dois lados** liberam a ativacao
  manual para ambos. A elegibilidade, uma vez obtida, nao e perdida.
- Um efeito `activate_king` tambem libera e tenta ativar o Rei imediatamente.
- Ativacao manual e gratuita, apenas no turno do dono. Nunca cria um segundo Rei
  nem excede oito unidades. O Rei conta como unidade para alvos e efeitos de area.

## Estrutura

| Arquivo | Responsabilidade |
|---|---|
| `main.py` | Estados Menu/Deck builder/Partida/Fim, desenho, cliques, agenda da IA sem bloquear eventos |
| `deck_store.py` | Validacao de decks e persistencia local em JSON |
| `game_engine.py` | Estado, jogadas legais, combate, turnos, compras, Endgame e IA |
| `effect_parser.py` | Resolucao de alvos, condicoes e execucao ordenada dos efeitos |
| `csv_to_json.py` | Conversao e validacao do catalogo; utilizavel sem pygame |
| `data\cards.csv` | Fonte editavel em planilha, UTF-8 e delimitador virgula |
| `data\cards.json` | Catalogo validado carregado pelo jogo |
| `tests\` | Testes de dados, regras, cliques da interface e partidas completas reproduziveis |

## Editar as cartas

Exporte uma planilha como CSV UTF-8 com o cabecalho exato:

```text
id,name,category,card_type,cost,attack,health,keywords,trigger,effect_code,description
```

`card_type` aceita `minion` ou `spell`; ataque e vida sao obrigatorios para
lacaios. `keywords` aceita identificadores ingleses ou os nomes portugueses
separados por `|`. Os IDs devem ser unicos e estaveis.

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

O formato curto aceita `DAMAGE`, `HEAL`, `DRAW` e `FREEZE`, separados por `|`:

```text
DAMAGE:2:TARGET_2_ENEMIES|DRAW:1:IF_KILLED
```

Isso gera dano a ate duas unidades inimigas aleatorias **distintas**, com compra
de uma carta **por unidade abatida**. Escudo Divino nao conta como abate.
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
`all_allies`, `all_allied_minions`, `adjacent_allies`, `random_enemy`,
`random_enemy_minion`. `self` e o lacaio de origem ou o heroi para feiticos.
`adjacent_allies` usa a ordem atual da fila. Aleatorios aceitam `count` e usam
a semente da partida. O filtro opcional `card_id` restringe os alvos a uma carta.

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
