# Filho paga para o Pai (CPFP)

Trabalho acadêmico da disciplina de **Tópicos Especiais de Segurança**, atividade **(P1) Filho paga para o Pai**.

**Lucas Panonko Assis Belchior — 12311BCC068**

## Entrega

[Relatório em PDF](report/Filho_Paga_Para_Pai_Lucas_Belchior.pdf): seis páginas de conteúdo, uma de reprodução e referências, seguidas do código integral em apêndice. Documento único para entrega na plataforma da disciplina.

O objetivo é identificar transações compatíveis com CPFP usando dependências de UTxOs e taxas. Não há rótulos verdadeiros ou dados históricos da mempool para comprovar a intenção dos autores.

## Resultados da base fornecida

| Medida | Resultado |
|---|---:|
| Blocos | 98 |
| Transações normais | 493.473 |
| Dependências diretas no mesmo bloco | 338.781 |
| Pares simples elegíveis | 8.375 |
| Componentes complexos (fora da classificação) | 18.227 |
| Candidatos, k = 2 | 552 |
| Blocos com candidatos | 60 |
| Pais candidatos com taxa zero | 26 |
| Candidatos entre pares simples | 6,591% |

Sensibilidade: 668 candidatos para k=1,5; 552 para k=2; 396 para k=3. Os valores e as regras foram definidos antes da análise.

## Método

1. Ler um bloco JSON por vez diretamente do TAR compactado.
2. Excluir coinbase; conferir taxas, pesos e referências internas.
3. Indexar transações por `tx_index` e saídas por `n`. O `tx_index` é um identificador do provedor dos dados, não um campo do protocolo Bitcoin. Conservar os hashes das transações para auditoria.
4. Construir arestas pai → filho quando a entrada do filho consome uma saída do pai no mesmo bloco. Conferir posição anterior do pai e valor da saída.
5. Separar componentes conexos de exatamente duas transações e uma aresta. Cadeias e ramificações maiores são contabilizadas, sem classificação econômica.
6. Para cada par simples, aplicar simultaneamente:
   - taxa do pai em sat/vB abaixo da mediana das transações normais do bloco;
   - taxa absoluta do filho maior que a do pai;
   - taxa em sat/vB do filho maior que a do pai e pelo menos k vezes a do pai;
   - taxa conjunta `(taxa_pai + taxa_filho)/(vsize_pai + vsize_filho)` igual ou acima da mediana do bloco.

O valor principal de k é 2; os valores de sensibilidade são 1,5 e 3. Taxa zero no pai é permitida. Se a mediana for zero, nenhum par atende à condição de pai estritamente abaixo da mediana.

Taxa = soma dos valores das entradas menos soma das saídas, em satoshis inteiros. Tamanho virtual = teto(peso/4). Endereços são aqueles informados nas saídas dos pais consumidas pelos filhos; sua recorrência não identifica pessoas.

## Como reproduzir

Requer **Python 3.12+** instalado e funcional. No Windows, use `py` no lugar de `python` se esse for o inicializador disponível. O alias da Microsoft Store pode não apontar para um interpretador instalado.

```powershell
python -m pip install -r requirements.txt
python -m unittest -v test_analyze
python analyze.py --archive ../blocos.tgz --output results
python build_report.py --results results
```

O arquivo original fica na pasta imediatamente acima do repositório. Também é possível passar qualquer caminho válido em `--archive`. O detector usa somente a biblioteca padrão; as dependências são necessárias para gráficos, relatório e conferência do PDF.

### Arquivo de entrada

Usar o `blocos.tgz` fornecido pela disciplina. Não é redistribuído no repositório (207.436.070 bytes).

SHA-256:

```text
679fe208f9a807fdd38e9d64948c73581af3e99ca52fb707ce06937e67bc536d
```

Os arquivos internos são JSONs com `height`, `hash`, `time`, `n_tx` e `tx`. As transações contêm `hash`, `tx_index`, `weight`, `fee`, `inputs[].prev_out` e `out[]`. Entradas incluem valor e referência da saída anterior. Não é necessário baixar transações de exploradores.

### Organização

```text
analyze.py        detector, censo e exportação de resultados
build_report.py   gráficos e PDF, incluindo código em apêndice
test_analyze.py   testes sintéticos de regras e integridade
results/          CSVs, resumo JSON, verificação e três gráficos
report/           PDF final
```

`pairs.csv` contém todos os pares simples, inclusive rejeitados; `reasons` lista as condições não atendidas. `consumed_outputs` é uma lista JSON com número, valor e endereço das saídas consumidas. `blocks.csv` contém o censo por bloco. `addresses.csv` agrega somente candidatos com k=2. `summary.json` registra parâmetros, totais, estatísticas e exemplos. `verification.json` registra a reconferência independente dos dois exemplos na fonte durante a preparação desta entrega.

## Limites

A mediana do bloco é uma referência didática, não o limite de seleção do minerador. A contagem é restrita aos pares simples da amostra; pacotes complexos podem conter outros CPFP. Dependência e inclusão conjunta são observáveis, mas intenção e necessidade da aceleração não são comprovadas. Não são apresentadas métricas de classificação supervisionada.

Referência conceitual: [Bitcoin Core 0.13.0 — More intelligent transaction selection for mining](https://bitcoincore.org/en/2016/08/23/release-0.13.0/).
