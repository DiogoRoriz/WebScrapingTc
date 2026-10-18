# Coletor de preços de hardware (TCC)

Pipeline automático que coleta diariamente os preços de produtos de hardware
na **KaBuM!**, **Pichau**, **Terabyte** e **Amazon**, carrega os dados no
modelo estrela do projeto (`produto`, `loja`, `oferta`) e calcula média
histórica, outliers e situação de compra.

Como não há banco de dados nesta máquina, as tabelas ficam em planilhas Excel
que simulam o Data Warehouse.

## Arquivos gerados

| Arquivo | Conteúdo |
|---|---|
| `dados/banco_dados.xlsx` | Aba **dicionario** e abas **produto**, **loja** e **oferta**, com as colunas do DER |
| `dados/coletas/coleta_AAAA-MM-DD.csv` e `.xlsx` | Tabela única de cada dia (UC01), entrada da carga. Ver "Integração com a carga e o tratamento da equipe" |
| `dados/log_execucoes.xlsx` | Uma linha por loja e execução: OK, PARCIAL, BLOQUEADO, SEM_DADOS ou ERRO (RNF03) |
| `logs/coleta_AAAA-MM-DD.log` | Log detalhado de cada execução |
| `catalogo_produtos.xlsx` | Produtos monitorados (editável no Excel) |

### Estrutura do banco_dados.xlsx

- **dicionario**: um quadro por tabela (PRODUTO, LOJA, OFERTA) com Coluna,
  Tipo, Descrição e Chave (pk em laranja, fk em verde).
- **produto**, **loja**, **oferta**: na linha 1 fica a faixa com o nome da
  tabela, na linha 2 o tipo e a chave de cada coluna, e na linha 3 o
  cabeçalho. Os registros começam na linha 4. Cada aba é também uma Tabela do
  Excel (`tb_produto`, `tb_loja`, `tb_oferta`).

As colunas, tipos e descrições ficam em `esquema.py`, que é a fonte única
usada pela carga, pelo tratamento e pela formatação. O pipeline regrava o
arquivo nesse formato a cada execução.

| Tabela | Colunas |
|---|---|
| produto | `id_produto` (pk), `nome_produto`, `categoria_produto`, `marca` |
| loja | `id_loja` (pk), `nome_loja`, `url_base` |
| oferta | `id_oferta` (pk), `id_produto` (fk), `id_loja` (fk), `preco`, `preco_medio_historico`, `outlier`, `situacao_compra`, `url_oferta`, `data_coleta` |

## Fluxo

```
Agendador do Windows (03:00)
  └─ main.py
       1. extracao.py   ScriptExtracao: coleta as 4 lojas e grava a planilha bruta do dia
       2. carga.py      insere em produto / loja / oferta (colunas analíticas nulas)
       3. tratamento.py padroniza lojas e marcas, recalcula média histórica,
                        outlier (>30%) e situação de compra (±10%), regrava a oferta
```

O tratamento segue a *Documentação Tratamento e banco*:

- a média de cada oferta usa só preços do mesmo produto, em todas as lojas,
  coletados em **dias anteriores** (sem *look-ahead*). As lojas do mesmo dia
  não se influenciam, então a ordem em que foram visitadas não altera o
  resultado, e a primeira coleta de cada produto fica "Sem histórico";
- outliers (variação acima de 30%) não entram no histórico e nunca são
  apagados (RNF04);
- a situação de compra é "Boa compra" (mais de 10% abaixo da média),
  "Preço médio" (dentro de ±10%) ou "Evitar" (mais de 10% acima).

A carga é idempotente: rodar duas vezes no mesmo dia não duplica ofertas, pois
o registro (produto, loja, dia) já existente é ignorado.

## Integração com a carga e o tratamento da equipe

A extração funciona sozinha e entrega a **tabela única** do dia, que é a
entrada da carga (`ScriptExtracao.salvar_tabela_unica()` do diagrama de
classes):

```bash
py main.py --somente-extracao
```

Esse modo só coleta e grava a tabela única, sem carga e sem tratamento
locais. Para agendá-lo assim:
`powershell -ExecutionPolicy Bypass -File ./agendar_tarefa.ps1 -SomenteExtracao`.

**Arquivos:** `dados/coletas/coleta_AAAA-MM-DD.csv` e
`dados/coletas/coleta_AAAA-MM-DD.xlsx` (aba `coleta`), com o mesmo conteúdo.
O CSV usa UTF-8, separador vírgula, ponto decimal e data no padrão
`AAAA-MM-DD HH:MM:SS`.

| Coluna | Tipo | Destino no modelo estrela | Conteúdo |
|---|---|---|---|
| `data_coleta` | TIMESTAMP | oferta.data_coleta | Momento em que o preço foi lido |
| `nome_loja` | STRING | loja.nome_loja | KaBuM!, Pichau, Terabyte ou Amazon |
| `url_base` | STRING | loja.url_base | Endereço principal da loja |
| `nome_produto` | STRING | produto.nome_produto | Nome padronizado do catálogo, igual em todas as lojas |
| `categoria_produto` | STRING | produto.categoria_produto | Processador, Placa de Vídeo, Memória RAM, SSD, Placa-mãe ou Fonte |
| `preco` | FLOAT64 | oferta.preco | Preço à vista (PIX/boleto), em reais |
| `url_oferta` | STRING | oferta.url_oferta | Link direto do anúncio |
| `titulo_anuncio` | STRING | (complementar) | Título original do anúncio na loja |
| `preco_prazo` | FLOAT64 | (complementar) | Preço parcelado, quando a loja informa |

Garantias da tabela:

- uma linha por produto, loja e execução, com o anúncio mais barato
  disponível;
- produto sem estoque ou não encontrado não gera linha (fica registrado em
  `log_execucoes.xlsx`);
- `marca` não vem na tabela, porque é identificada pelo tratamento a partir
  de `nome_produto`. Os ids e as colunas analíticas também ficam com a carga
  e o tratamento;
- se a coleta rodar mais de uma vez no dia, as linhas novas são acrescentadas
  ao mesmo arquivo. Para manter uma oferta por produto, loja e dia, a carga
  deve ignorar o que já existe (como faz `carga.py`).

`carga.py` e `tratamento.py` deste projeto são a implementação local de
referência, sobre Excel, das regras da *Documentação Tratamento e banco*.
Eles servem para testar o fluxo completo nesta máquina e podem ser
substituídos pela ingestão da equipe.

## Como cada loja é coletada

| Loja | Método | Volume por execução |
|---|---|---|
| KaBuM! | API pública de catálogo (JSON), sem navegador | 1 busca por produto do catálogo |
| Amazon | Página de busca (permitida no `robots.txt`) aberta no Chrome | 1 busca por produto do catálogo |
| Pichau | 1 página de categoria no Chrome, com os dados embutidos na página | 36 produtos (os primeiros da categoria) |
| Terabyte | 1 página de categoria no Chrome, mais o botão "ver mais produtos" da própria página | a categoria inteira |

Categorias em rodízio: Pichau tem processadores, placas de vídeo, memórias e
SSD. A Terabyte tem esses e também placas-mãe e fontes. Para incluir outra
categoria, adicione o endereço em `CATEGORIAS_PICHAU` ou
`CATEGORIAS_TERABYTE` no `config.py`.

**Limitação da Pichau e da Terabyte.** As duas lojas usam proteção anti-bot
(Cloudflare). Elas aceitam a primeira página aberta pelo Chrome automatizado,
mas bloqueiam as páginas seguintes da mesma visita, mesmo com minutos de
intervalo. O coletor **não tenta burlar** essa proteção (nada de disfarçar o
navegador, resolver CAPTCHA ou abrir sessões novas para fugir do bloqueio).
Ele lê uma página por loja a cada execução e faz rodízio de categoria a cada
dia: é escolhida a categoria visitada há mais tempo. Se a loja bloquear, o
bloqueio é registrado em `log_execucoes.xlsx` e o pipeline segue com as
outras lojas.

Para ter cobertura diária completa dessas duas lojas, o caminho legítimo é um
feed oficial de produtos (programas de afiliados costumam fornecer um).

## Instalação

```bash
py -m pip install -r requirements.txt
```

É necessário ter o Google Chrome instalado. O Selenium baixa o driver
compatível automaticamente.

## Uso

```bash
py main.py                        # pipeline completo
py main.py --lojas kabum amazon   # só algumas lojas
py main.py --somente-tratamento   # só recalcula os indicadores
py main.py --somente-extracao     # só gera a tabela única do dia (CSV/Excel)
py testes.py                      # testes da correspondência e do tratamento
```

### Automação (sem intervenção humana)

```powershell
powershell -ExecutionPolicy Bypass -File .\agendar_tarefa.ps1                  # todo dia às 03:00
powershell -ExecutionPolicy Bypass -File .\agendar_tarefa.ps1 -Horario 04:30   # outro horário
powershell -ExecutionPolicy Bypass -File .\remover_tarefa.ps1                  # desfaz o agendamento
```

A tarefa roda sem janela. Se o computador estiver desligado ou suspenso no
horário, ela roda assim que ele estiver disponível. Ela precisa da sessão do
Windows aberta, pois o Chrome abre uma janela fora da área visível da tela.
Ao final, aparece um aviso na central de notificações com o resumo da coleta.

**Mantenha o `banco_dados.xlsx` fechado no Excel durante a coleta.** Se ele
estiver aberto, o programa tenta gravar novamente por 5 minutos e, se não
conseguir, deixa os dados em `dados/~tmp_banco_dados.xlsx` e registra o erro
no log.

## Catálogo de produtos

Cada linha de `catalogo_produtos.xlsx` define um produto monitorado:

- `ativo`: SIM/NÃO
- `categoria_produto`: Processador, Placa de Vídeo, Memória RAM, SSD,
  Placa-mãe ou Fonte
- `nome_produto`: nome padronizado gravado na tabela produto
- `termo_busca`: texto pesquisado na KaBuM! e na Amazon
- `palavras_obrigatorias`: termos que o título do anúncio precisa ter,
  separados por `;`. Use `|` para alternativas, por exemplo `3200mhz|3200`
- `palavras_proibidas`: termos que descartam o anúncio, por exemplo
  `5060 ti; fonte; kit`
- `preco_minimo`: ignora anúncios mais baratos que isso, como acessórios com
  nome parecido

Os termos casam com palavras inteiras, então `ryzen 5 5600` não casa com
`Ryzen 5 5600X`. Entre as lojas, a coleta registra o anúncio **mais barato e
disponível** que corresponda ao produto. Kits, PCs montados, notebooks e
usados são descartados (`PALAVRAS_PROIBIDAS_GLOBAIS` em `config.py`).

## Power BI

Em *Obter dados → Excel*, selecione `dados/banco_dados.xlsx` e marque as
**tabelas** `tb_produto`, `tb_loja` e `tb_oferta`, e não as abas: as tabelas
já começam no cabeçalho, sem as faixas de título. Depois relacione
`tb_oferta.id_produto` com `tb_produto.id_produto` e `tb_oferta.id_loja` com
`tb_loja.id_loja` (1:N). Para seguir o critério da HU01, filtre
`outlier = FALSE` nas visualizações.

## Observação sobre o numpy

Nesta máquina, o Controle Inteligente de Aplicativos do Windows 11 bloqueia
DLLs do numpy 2.5.x. Por isso o `requirements.txt` fixa `numpy<2.5`.
