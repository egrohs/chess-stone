# Manual do Chess Stone

[Voltar ao README](README.md) para instalacao, execucao e documentacao tecnica.

## Sumario

- [Inicio da partida](#inicio-da-partida)
- [Controles](#controles)
- [Turnos, tabuleiro e combate](#turnos-tabuleiro-e-combate)
- [Palavras-chave e efeitos](#palavras-chave-e-efeitos)
- [Ativacao do Rei e Final de jogo](#ativacao-do-rei-e-final-de-jogo)
- [Vitorias alternativas: seis padroes de mate](#vitorias-alternativas-seis-padroes-de-mate)
- [Colecao de cartas](#colecao-de-cartas)
- [Crafting por puzzles Lichess](#crafting-por-puzzles-lichess)
- [Montagem e selecao de decks](#montagem-e-selecao-de-decks)
- [Arquivos locais e recuperacao](#arquivos-locais-e-recuperacao)

## Inicio da partida

Chess Stone e um card game para um jogador contra IA. Venca reduzindo a vida do
Rei inimigo a zero ou executando uma das seis cartas de mate.

As versoes basicas de **Peao, Cavalo, Bispo, Torre e Dama** sao liberadas desde o
inicio, com copias livres, para permitir jogar sem internet. As cartas taticas,
os mates e as variantes aprimoradas precisam ser adquiridos por crafting.
Peao Passado nao faz parte das cinco pecas iniciais liberadas.

No menu, selecione um deck e clique em **Iniciar partida**. O deck automatico
do jogador usa copias ciclicas das cinco pecas basicas, embaralhadas. A IA usa
o catalogo base completo, sem variantes de crafting nem cartas lendarias.
O tamanho padrao e 30 cartas; a opcao de execucao `--deck-size` permite decks
de teste menores e nao altera o tamanho de decks personalizados.

Cada jogador comeca com **30 de vida** e recebe tres cartas iniciais (ou o
tamanho do deck, se menor). O primeiro jogador tambem compra no inicio do seu
primeiro turno. Nao ha mulligan, moeda, armas ou poder heroico.

## Controles

| Acao | Como executar |
|---|---|
| Inspecionar carta | Passe o mouse na mao para elevar e ampliar suavemente a carta; retirar o mouse restaura sua posicao |
| Selecionar carta | Clique na carta da mao, inclusive na parte ampliada; a borda fica dourada e ela permanece levemente elevada |
| Jogar como Peca | Selecione a carta e clique numa das suas seis casas vazias; pecas existentes nao sao deslocadas |
| Jogar como Manobra | Selecione a carta e clique fora das suas casas ou em **Jogar como Manobra** |
| Manobra com alvo | Clique direto no inimigo valido, ou escolha Manobra fora das casas e depois clique no alvo verde (inclusive aliado) |
| Atacar | Clique em uma peça aliada pronta e depois em um inimigo verde |
| Reposicionar | Arraste uma peça sua (exceto o Rei) para uma casa vazia (borda azul); custa 1 tempo |
| Cancelar selecao | Clique direito ou Esc |
| Encerrar turno | Clique em **Passar Turno** |
| Ativar o Rei manualmente | Use **Ativar Rei (Final de jogo)** quando estiver disponivel |
| Sair da partida | Use **Voltar ao Menu** |

Verde indica alvos/espacos validos; azul indica peça pronta para atacar.
O painel lateral mostra a descricao da carta
selecionada e as ultimas jogadas. Pecas envolvidas em ameacas de mate
anunciadas recebem uma borda interna dourada.

Uma peça com efeito de entrada que exige alvo primeiro pede posicionamento
e depois selecao de alvo.

**Todas as cartas sao modais:** a mesma carta pode virar Peca ou Manobra, nunca
as duas na mesma jogada. Os dois modos custam o mesmo Tempo. Como Peca, usa
ataque, vida, palavras-chave e efeitos de Peca, permanecendo no tabuleiro.
Como Manobra, executa somente o efeito imediato e vai ao descarte, sem ocupar
casa, mesmo com tabuleiro cheio. O descarte tambem recebe pecas mortas e compras
com mao cheia e tem seu tamanho exibido; nao retorna automaticamente ao deck.

Clicar numa casa sua ocupada nao joga a carta nem dispara Manobra por acidente.
Botoes de turno, Rei e menu, e cliques na mao continuam sendo controles:
nao contam como cliques de Manobra. Esc permite cancelar sem pagar Tempo.

### Modos das cartas

ATQ/VIDA e o arquetipo referem-se ao modo Peca. Efeitos antigos continuam no
modo original; os novos modos complementam cada carta:

| Carta | Tempo | Peca | Manobra |
|---|---|---|---|
| Peao | 1 | Peao 1/2, compra 1 ao morrer | Compra 1 |
| Cavalo | 3 | Cavalo 3/2, Desenvolvimento; ao entrar, +1 de ataque aos aliados adjacentes | Causa 2 de dano a uma peca inimiga |
| Bispo | 3 | Bispo 2/4, Elusivo; cura 1 no seu Rei no fim do turno | Cura 4 no seu Rei |
| Torre | 4 | Torre 3/5, Proteção | Concede Proteção a uma peca aliada |
| Dama | 7 | Dama 5/5, Iniciativa e Ataque duplo | Causa 4 de dano a todos os inimigos |
| Peao Passado | 2 | Peao 2/3 | Concede +1/+1 a uma peca aliada |
| Cravada Absoluta | 2 | Bispo 2/3 | Congela uma peca inimiga |
| Garfo | 3 | Cavalo 3/2 | Causa 2 de dano a ate duas pecas de menor Vida; compra 1 por abate |
| Par de Bispos | 3 | Bispo 2/4 | Com dois Bispos aliados, concede +1/+1 a todas as pecas aliadas |
| Coluna Aberta | 2 | Torre 2/3 | Concede +2 de ataque neste turno e Desenvolvimento a uma peca aliada |
| Zugzwang | 5 | Cavalo 4/4 | Congela todas as pecas inimigas |
| Roque | 4 | Torre 3/5 | Cura 4 no seu Rei e desenvolve uma Torre se houver espaco |
| Sacrificio da Dama | 6 | Dama 5/4 | Destroi uma Dama aliada, causa 5 a todos os inimigos e compra 2 |
| Mate de Anastasia | 9 | Torre 6/7 | Executa o mate se preparado |
| Mate de Boden | 5 | Bispo 4/5 | Executa o mate se preparado |
| Mate Abafado | 6 | Cavalo 4/5 | Executa o mate se preparado |
| Mate de Gaveta | 8 | Torre 5/7 | Executa o mate se preparado |
| Mate da Opera | 7 | Bispo 5/6 | Executa o mate se preparado |
| Final de jogo Puro | 10 | Peao 7/8 | Executa a vitoria de oposicao se preparada |

O arquetipo aparece na peca em jogo e define alcance, formacoes e efeitos por
tipo: Cravada Absoluta como Peca conta como Bispo, por exemplo.

## Turnos, tabuleiro e combate

O tempo maximo aumenta em um no inicio de cada turno proprio, ate **10**, e e
totalmente restaurado. Cada jogador compra uma carta por turno.

A mao comporta **10 cartas**. Compras excedentes sao descartadas, mas consomem
a carta do deck. Cada lado comporta **seis peças, incluindo o Rei ativado**.

O tabuleiro tem **seis casas fixas**. Mortes deixam lacunas e nao deslocam as demais
pecas. Adjacencia significa casas imediatamente vizinhas; uma lacuna interrompe
o apoio. Desenvolvimentos por efeitos e o Rei ocupam a primeira casa livre, da esquerda
para a direita. O jogador escolhe a casa ao jogar peças da mao.

**Apoio:** uma peça com aliado vivo imediatamente ao lado recebe **-1 de dano
de combate**, ate o minimo de zero. Sem esse aliado, fica **Pendurada** e recebe
**+1 de dano de combate**. Isso vale para atacante, defensor e Reis no tabuleiro;
o apoio e calculado antes dos dois danos simultaneos. Nao modifica dano de
manobras, efeitos ou fadiga. Dano reduzido a zero nao consome Proteção.
Remover o defensor pode, portanto, aumentar o dano dos ataques seguintes.

**Pressao territorial:** casas **1 e 6** sao os Cantos; **2 e 5** sao as Bordas;
**3 e 4** sao o Centro.
Ao terminar seu proprio turno, depois dos efeitos de fim de turno, controlar
mais casas centrais que o adversario concede **+1 de tempo temporario no proximo
turno proprio**. Empates nao concedem bonus. Reis no tabuleiro tambem contam.
O bonus nao acumula nem aumenta o limite permanente: pode haver 11 de tempo
disponivel com limite de 10, e o tempo nao usado nao passa ao turno seguinte.
Uma vez conquistado, o bonus permanece mesmo se o adversario remover pecas.
Ataques diretos ao Rei respeitam o alcance da peça e Desenvolvimento.

Uma peça normalmente precisa esperar ate seu proximo turno para atacar,
e pode atacar uma vez por turno. O combate causa dano simultaneo entre
atacante e defensor; o Rei fora do tabuleiro nao contra-ataca.

As peças respeitam o alcance do padrao da peca: torre em linha direta,
bispo em diagonais, cavalo em L e dama em alcance curto. Quando nao ha
alvo na fileira/padrao, a peça pode atacar o Rei diretamente.

O dano permanece entre turnos. Morte dos dois Reis na mesma acao resulta em
empate.

A Armadura dos Reis comeca em zero. Se houver Armadura, ela absorve dano
antes da vida, inclusive depois da Ativacao do Rei, e e exibida no tabuleiro.
O catalogo atual ainda nao tem cartas que concedem Armadura; a condicao de
Mate de Gaveta ja a verifica explicitamente.

## Palavras-chave e efeitos

Provocar foi removido: nao restringe ataques nem bloqueia mates.
Mate de Gaveta agora exige tres Peoes (incluindo Peao Passado).

| Palavra-chave | Comportamento |
|---|---|
| Iniciativa | Permite atacar imediatamente, inclusive o Rei. |
| Desenvolvimento | No turno de desenvolvimento permite atacar peças, mas nao o Rei nem o Rei ativado. |
| Proteção | Absorve a primeira instancia de dano positivo; nao impede destruir. |
| Ataque duplo | Permite dois ataques por turno, sem remover a espera de desenvolvimento. |
| Elusivo | Impede selecao manual por manobras de ambos os lados. Nao bloqueia ataques, efeitos de area/menor Vida nem efeitos de entrada de peças. |

Congelamento impede ataques ate o fim do proximo turno do dono da peça,
incluindo o restante do turno atual se aplicado durante ele. Bonus temporario
de ataque termina no fim do turno em que foi aplicado.

Desenvolvimentos por efeitos nao executam efeitos de entrada (`on_play`);
palavras-chave impressas continuam funcionando. Efeitos de morte acontecem
depois de remover as baixas simultaneas. A morte de um Rei encerra a partida
antes de novos efeitos de morte ou compras por abate.

Efeitos de uma carta sao executados na ordem. Dano em area e aplicado aos alvos
antes de resolver as mortes. Os efeitos manuais de uma mesma jogada compartilham
um unico alvo, valido para todos eles.

Os efeitos nao usam RNG; embaralhamento dos decks e escolhas da IA continuam
aleatorios. Garfo atinge ate duas peças inimigas distintas com **menor
Vida**, desempata pelo **menor numero de casa** e compra uma carta por peça
abatida. Os dois alvos sao definidos antes de aplicar dano; Proteção nao
conta como abate. O Rei ativado e uma peça elegivel, mas o Rei fora do tabuleiro
nao e alvo de Garfo.
Par de Bispos exige pelo menos dois Bispos aliados; se a condicao nao estiver
atendida, o efeito nao acontece, mas o custo da jogada continua sendo pago.
Sacrificio da Dama exige uma Dama aliada selecionavel, a destroi e executa
dano em area seguido de compras.

## Ativacao do Rei e Final de jogo

O Rei entra no tabuleiro com **2 de ataque e a vida atual do Rei**, nao com 8 de
vida fixa. A vida e compartilhada: causar dano ou curar o Rei afeta diretamente
a condicao de vitoria. O retrato deixa de ser um alvo separado. O Rei entra
na primeira casa livre e precisa esperar para atacar, como uma peça sem Iniciativa.

- Ao comprar a ultima carta, o Rei e ativado automaticamente. Tabuleiro cheio adia
  sua entrada ate surgir uma vaga; o Rei continua vulneravel enquanto espera.
- Comprar de um deck vazio causa fadiga crescente: 1, 2, 3... de dano.
- Ao terminar a oitava rodada completa (16 turnos individuais), ou qualquer turno
  posterior, **ate tres peças somadas entre os dois lados** liberam a ativacao
  manual para ambos. A elegibilidade, uma vez obtida, nao e perdida.
- Um efeito de ativacao tambem libera e tenta ativar o Rei imediatamente.
- Ativacao manual e gratuita, apenas no turno do dono. Nunca cria um segundo Rei
  nem excede seis peças. O Rei conta como peça para alvos e efeitos de area.

## Vitorias alternativas: seis padroes de mate

As seis cartas de mate sao **lendarias** modais, adquiridas por crafting.
Seus requisitos de preparacao e vitoria valem somente para o modo Manobra:
desenvolve-las como Peca nao exige preparacao nem executa o mate.
Cada deck aceita no maximo uma copia de cada mate, somando todas as qualidades.
Os decks automaticos nao incluem lendarias.

O Rei ocupa uma casa fixa, mas nao conta na quantidade de peças exigida pelos mates abaixo.

| Carta | Tempo | Formacao a anunciar | Condicoes adicionais para executar |
|---|---|---|---|
| Mate de Anastasia | 9 | Torre na casa 1 ou 6, com Cavalo na casa 2 ou 5 respectivamente; pelo menos tres peças aliadas | Inimigo com ate 15 de vida e ao menos duas peças |
| Mate de Boden | 5 | Bispos nas casas 1 e 6; pelo menos duas peças nas casas intermediarias | Jogar duas outras manobras no mesmo turno antes do mate |
| Mate Abafado | 6 | Um Cavalo | Inimigo com seis peças; Rei nao conta para as seis |
| Mate de Gaveta | 8 | Uma Torre | Essa mesma Torre deve ter atacado e sobrevivido no turno atual; inimigo com zero de Armadura e pelo menos tres Peoes |
| Mate da Opera | 7 | Exatamente uma Torre e um Bispo aliados, adjacentes; outras pecas sao permitidas | Ambos devem ter atacado nesta partida; inimigo com ate 15 de vida e exatamente uma peça |
| Final de jogo Puro (Rei e Peao) | 10 | Ambos os Reis ativados, sem nenhuma outra peça em qualquer lado | Peao Passado na mao e seu Rei com estritamente mais vida que o Rei inimigo |

### Preparacao e resposta adversaria

Ao terminar seu turno com uma dessas formacoes, ela e **anunciada
automaticamente**, mesmo sem a carta na mao. O log identifica o dono, o padrao
e os IDs das pecas envolvidas; uma faixa por lado resume seus padroes anunciados,
e as pecas participantes recebem uma borda interna dourada.
O adversario recebe um turno completo para responder antes de voce poder
executar o mate.

As mesmas pecas precisam permanecer vivas, com ataque positivo,
descongeladas e na geometria exigida. Se a formacao for rompida por morte,
congelamento ou mudanca de posicao/quantidade, a preparacao e cancelada.
Reconstruir a mesma formacao naquele turno nao restaura a ameaca: e preciso
anuncia-la novamente no fim de um turno proprio. Novas pecas do mesmo tipo
nao substituem os IDs anunciados. Mortes intermediarias que deixem a formacao
valida nao cancelam a preparacao.

### Execucao e excecoes

No turno da execucao, as pecas nao podem ter atacado, **exceto em Gaveta**,
que exige um ataque real da Torre nesse turno. A carta revalida todos os
requisitos antes de gastar tempo ou sair da mao; uma tentativa invalida exibe o
motivo e nao consome recursos. O mate bem-sucedido compromete os ataques
restantes das pecas e encerra a partida **sem reduzir a vida inimiga a zero**.

Somente Final de jogo Puro exige os Reis ativados.
Em Gaveta, Peao Passado tambem conta como Peao.
O Rei nao conta como bloqueador.

O historico de ataque da Opera pertence a cada peça individual: desenvolver
outra Torre/Bispo nao herda ataques da anterior. Os ataques precisam ter ocorrido
antes do turno da execucao, pois a dupla nao pode atacar nesse turno.
Os requisitos inimigos de vida/quantidade/Armadura sao revalidados
na execucao; a formacao aliada e que precisa permanecer intacta durante a
preparacao. No Final de jogo Puro, qualquer outra peça em qualquer tabuleiro cancela
a preparacao, mesmo se for removida logo depois.

O **Peao Passado** e uma carta de apoio 2/3 de custo 2, criada por puzzles
de peao avancado. Para Final de jogo Puro, ele precisa permanecer **na mao**,
pois o tabuleiro deve conter somente os Reis. Variantes aprimoradas/perfeitas
tambem atendem ao requisito e a carta nao e consumida.

### Observacoes de balanceamento

Anastasia exige pressao sobre o inimigo e uma terceira peça aliada para nao
virar apenas uma dupla facil na ponta. Em Boden, dois Bispos sozinhos nao bastam:
as duas peças intermediarias criam compromisso de tabuleiro.
O proprio Boden e a terceira manobra, permitindo uma sequencia real com o tempo
atual (por exemplo, duas Colunas Abertas de custo 2 e Boden de custo 5 = 9).
O contador de manobras e reiniciado no inicio do turno do dono e exibido no
painel de comandos.

Qualidades aprimoradas/perfeitas **nao reduzem custo nem requisitos de mate**.
Os bonus auxiliares de crafting seguem a ordem dos efeitos e nao executam
depois de uma vitoria, pois a partida ja terminou.

## Colecao de cartas

No menu, **Colecao de cartas** mostra todo o catalogo base e as variantes
adquiridas, sem alterar decks ou a partida durante a consulta. As cartas aparecem
em grade com custo comum, arquetipo, atributos e um resumo; clique em uma para
consultar os dois modos, ID, palavras-chave e gatilhos no painel lateral.
O painel tambem indica copias disponiveis, qualidade e tema do puzzle.

A busca aceita nome, ID, arquetipo, descricao e palavras-chave, ignorando
acentos e maiusculas. O filtro alterna entre todos os arquetipos,
Peao, Cavalo, Bispo, Torre e Dama; todas as cartas tambem possuem Manobra.
O botao de ordem alterna entre custo e nome.
Use os botoes de pagina para percorrer a colecao. Descricoes longas podem ser
roladas com o mouse sobre o painel de detalhes. **Voltar ao Menu** ou Esc sai.

## Crafting por puzzles Lichess

Selecione uma carta na colecao e clique em **Criar carta: resolver puzzle**.
O crafting exige internet; nao ha cache offline de puzzles. Um puzzle do tema
associado e baixado por solicitacao, sem token e sem download massivo.
Nao ha envio de desempenho ou credenciais ao Lichess.
Os puzzles sao de [dominio publico](https://database.lichess.org/#puzzles).

O tabuleiro padrao 8x8 fica dentro do Pygame, orientado com o lado do jogador
embaixo. Clique na peca e no destino; destinos legais ficam marcados.
O treinador valida movimentos, xeque, roque, en passant e promocao.
Promocoes pedem escolha explicita entre Dama, Torre, Bispo e Cavalo.
O adversario responde automaticamente conforme a solucao do puzzle. Nao e
necessario instalar o aplicativo PyChess, outro motor ou Stockfish.

Cada tentativa incorreta soma um erro e mantem a posicao. O treinador exige
a sequencia publicada pelo Lichess: nao analisa alternativas equivalentes com
um motor de xadrez. O tempo comeca depois do download e para na conclusao.
Nao ha prazo para terminar.

### Qualidades e recompensas

| Qualidade | Desempenho | Bonus em relacao a carta base |
|---|---|---|
| Perfeita | 0 erros, ate 60 segundos por lance do jogador na solucao | Peça: +2/+2 e compra 1 ao jogar. Manobra: cura extra de 2 no Rei e compra extra de 1. |
| Aprimorada | Ate 1 erro, ate 120 segundos por lance do jogador na solucao | Peça: +1/+1. Manobra: cura extra de 1 no Rei. |
| Basica | Demais resultados, desde que conclua | Atributos e efeitos originais. |

Cada variante recebe os bonus dos dois modos, mas so aplica os do modo escolhido
ao jogar. O custo de tempo nao muda; efeitos originais sao preservados. Os limites de tempo
sao para o puzzle inteiro, multiplicados pela quantidade total de lances do
jogador na solucao (nao incluem as respostas adversarias). Por exemplo, uma
solucao com tres lances seus permite ate 180 segundos para qualidade Perfeita.

Depois de concluir, clique em **Receber carta** para salvar uma copia da qualidade
obtida. Falhas ao gravar mostram erro e permitem tentar receber novamente sem
resolver outra vez. Voltar ou Esc abandona o puzzle e nao concede recompensa nao
resgatada. Cada ID de puzzle so concede uma recompensa no perfil inteiro, mesmo
se for sorteado para outra carta. Puzzles repetidos nao concedem novas copias;
volte e solicite outro. Nao ha repeticao automatica de requisicoes.

As pecas aprimoradas continuam contando como sua peca de origem para
Par de Bispos, Sacrificio da Dama e formacoes de mate.

### Temas dos puzzles

| Carta | Tema Lichess |
|---|---|
| Peao / Cavalo / Bispo / Torre / Dama | `pawnEndgame` / `knightEndgame` / `bishopEndgame` / `rookEndgame` / `queenEndgame` |
| Cravada Absoluta | `pin` (inclui cravadas relativas) |
| Garfo | `fork` |
| Par de Bispos | `doubleBishopMate` |
| Coluna Aberta | `clearance` (aproximacao: desobstrucao, nao necessariamente de coluna) |
| Zugzwang | `zugzwang` |
| Roque | `castling` |
| Sacrificio da Dama | `sacrifice` (nao garante sacrificio especificamente da dama) |
| Mate de Anastasia | `anastasiaMate` |
| Mate de Boden | `bodenMate` |
| Mate Abafado | `smotheredMate` |
| Mate de Gaveta | `backRankMate` |
| Mate da Opera | `operaMate` |
| Final de jogo Puro | `pawnEndgame` (aproximacao de oposicao) |
| Peao Passado | `advancedPawn` (aproximacao: peao avancado) |

Os temas oficiais estao em [lichess.org/training/themes](https://lichess.org/training/themes).
As aproximacoes tambem aparecem na tela. Cartas sem associacao exibem erro
ao solicitar crafting.

### Falhas de conexao

Os downloads nao bloqueiam a interface, tem timeout de 15 segundos e intervalo
minimo de tres segundos. HTTP 429 bloqueia novas tentativas por pelo menos 60
segundos. Falhas de rede ou dados invalidos sao exibidos na tela, sem conceder
cartas nem substituir o puzzle por um de outro tema.

## Montagem e selecao de decks

No menu, use **Montar / editar decks**. Clique no campo de nome para digitar e
use **+** / **-** para ajustar as copias de cada carta. As paginas permitem
percorrer todo o catalogo e variantes adquiridas. Nao ha tamanho fixo: o deck deve
conter pelo menos uma carta.

Pecas basicas tem copias livres; cartas taticas e variantes respeitam as
quantidades criadas na colecao. Uma copia pode ser usada em varios decks, mas
nao repetida no mesmo deck alem do inventario. Cada lendaria aceita somente uma
copia por deck, somando qualidades. Salvar/jogar nao consome cartas.
O painel mostra total de cartas modais e custo medio.

**Salvar / substituir e selecionar** grava o deck e o seleciona para a proxima
partida. Salvar com um nome existente substitui sua composicao; mudar o nome
cria outro deck. Clique em um deck salvo para carrega-lo e edita-lo.
**Novo**, **Voltar** e Esc descartam alteracoes nao salvas.

No menu, clique no seletor **Deck** para alternar entre os salvos e o automatico.
A selecao vale durante a sessao; os decks permanecem salvos ao fechar o jogo.
O deck escolhido e usado pelo jogador, inclusive ao jogar novamente. Ambos
os decks sao embaralhados antes da partida.

Decks antigos com cartas ainda nao adquiridas permanecem no arquivo, mas nao
podem ser usados ate ajustar as copias ou criar as cartas necessarias; o erro
informa a quantidade solicitada e disponivel. Nao ha remocao silenciosa de cartas.

## Arquivos locais e recuperacao

| Arquivo | Conteudo |
|---|---|
| `data\decks.json` | Decks nomeados; criado no primeiro salvamento |
| `data\collection.json` | Inventario e historico de recompensas; criado no primeiro resgate |

Ambos sao locais ao jogador e ignorados pelo Git. Nenhum progresso e salvo
apenas por abrir a colecao. Os salvamentos usam substituicao atomica para
preservar o arquivo anterior se houver falha.

Nomes de decks aceitam ate 40 caracteres. IDs desconhecidos, decks vazios e
JSON malformado geram uma mensagem visivel; um arquivo invalido nao e
sobrescrito pelo editor. Corrija o arquivo de decks e reabra o editor para
recarregar.

Inventario corrompido bloqueia novos resgates para evitar perda de progresso:
corrija `data\collection.json` e reinicie o jogo.

Para os formatos dos arquivos e detalhes de desenvolvimento, consulte o
[README](README.md).
