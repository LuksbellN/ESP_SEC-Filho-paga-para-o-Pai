"""Gera gráficos e PDF autossuficiente a partir dos resultados do analisador."""
import argparse
import csv
import json
import textwrap
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle

ROOT = Path(__file__).resolve().parent
REPO = 'https://github.com/LuksbellN/ESP_SEC-Filho-paga-para-o-Pai'
W, H = A4
M, CW = 43, A4[0] - 86
INK, TEAL, GRAY = '#202b36', '#14685d', '#5f6b73'


def n(value, digits=0):
    if value is None:
        return 'não aplicável'
    return f'{value:,.{digits}f}'.replace(',', '_').replace('.', ',').replace('_', '.')


def pct(value):
    return 'não aplicável' if value is None else n(value * 100, 3) + '%'


def plots(results, summary):
    figures = results / 'figures'
    figures.mkdir(exist_ok=True)
    with (results/'blocks.csv').open(encoding='utf-8') as f:
        blocks = list(csv.DictReader(f))
    with (results/'pairs.csv').open(encoding='utf-8') as f:
        pairs = list(csv.DictReader(f))
    plt.rcParams.update({'font.size': 9, 'axes.spines.top': False,
                         'axes.spines.right': False, 'figure.dpi': 170})
    fig, ax = plt.subplots(figsize=(8, 2.7))
    ax.bar(range(len(blocks)), [int(b['candidates']) for b in blocks], color=TEAL)
    ticks = sorted(set([0, len(blocks)//3, 2*len(blocks)//3, len(blocks)-1]))
    ax.set_xticks(ticks, [blocks[i]['height'] for i in ticks])
    ax.set(xlabel='Blocos amostrados, ordenados por altura (intervalos omitidos)',
           ylabel='Pares candidatos')
    fig.tight_layout(); fig.savefig(figures/'frequency.png'); plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 3.2))
    for flag, label, color, size in [(False, 'Demais pares simples', '#aeb9bf', 9),
                                    (True, 'Candidatos (k = 2)', TEAL, 19)]:
        rows = [p for p in pairs if (p['candidate_2.0'] == 'True') == flag]
        ax.scatter([float(p['parent_rate']) for p in rows],
                   [float(p['child_rate']) for p in rows], s=size,
                   c=color, label=label, alpha=.65, edgecolors='none')
    # A escala simétrica logarítmica mantém os zeros e torna os extremos visíveis.
    ax.set_xscale('symlog', linthresh=1)
    ax.set_yscale('symlog', linthresh=1)
    ax.set(xlabel='Taxa do pai (sat/vB)', ylabel='Taxa do filho (sat/vB)')
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout(); fig.savefig(figures/'rates.png'); plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 2.5))
    vals = list(summary['sensitivity'].values())
    ax.bar(['1,5', '2,0 (principal)', '3,0'], vals, color=[GRAY, TEAL, GRAY])
    for i, v in enumerate(vals): ax.text(i, v, n(v), ha='center', va='bottom')
    ax.set(xlabel='Multiplicador mínimo: taxa por tamanho do filho / pai',
           ylabel='Pares candidatos', ylim=(0, max(vals + [1])*1.22))
    fig.tight_layout(); fig.savefig(figures/'sensitivity.png'); plt.close(fig)


class Report:
    def __init__(self, dest):
        fontdir = Path(matplotlib.get_data_path())/'fonts/ttf'
        for name, filename in [('Body', 'DejaVuSans.ttf'),
                               ('Bold', 'DejaVuSans-Bold.ttf'),
                               ('Mono', 'DejaVuSansMono.ttf')]:
            pdfmetrics.registerFont(TTFont(name, str(fontdir/filename)))
        self.c = canvas.Canvas(str(dest), pagesize=A4)
        self.c.setTitle('Filho paga para o Pai - análise de candidatos a CPFP')
        self.c.setAuthor('Lucas Panonko Assis Belchior')
        self.page, self.y = 0, 0

    def new(self, title):
        if self.page:
            self.c.showPage()
        self.page += 1
        c = self.c
        c.setFillColor(colors.HexColor(TEAL)); c.rect(M, H-35, CW, 3, fill=1, stroke=0)
        c.setFont('Body', 8); c.setFillColor(colors.HexColor(GRAY))
        c.drawString(M, H-51, 'TÓPICOS ESPECIAIS DE SEGURANÇA  |  P1  |  02/11/2026')
        c.drawRightString(W-M, 25, str(self.page))
        c.drawString(M, 25, 'Lucas Belchior  |  Filho paga para o Pai')
        self.y = H-78
        self.p(title, 19, 'Bold', 25)
        self.y -= 6

    def p(self, text, size=9.6, font='Body', leading=None):
        para = Paragraph(text, ParagraphStyle('body', fontName=font, fontSize=size,
                         leading=leading or size*1.42, textColor=colors.HexColor(INK)))
        _, height = para.wrap(CW, H)
        if self.y-height < 45:
            raise ValueError(f'Texto ultrapassa a página {self.page}: {text[:60]}')
        para.drawOn(self.c, M, self.y-height)
        self.y -= height+9

    def table(self, rows, widths=None, size=9):
        style = ParagraphStyle('cell', fontName='Body', fontSize=size,
                               leading=size*1.35, textColor=colors.HexColor(INK))
        cells = [[Paragraph(escape(str(x)), style) for x in row] for row in rows]
        t = Table(cells, colWidths=widths or [CW/len(rows[0])]*len(rows[0]))
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e7f0ed')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LINEBELOW', (0, 0), (-1, 0), .5, colors.HexColor(TEAL)),
            ('LINEBELOW', (0, 1), (-1, -1), .25, colors.HexColor('#dce1e3')),
            ('LEFTPADDING', (0, 0), (-1, -1), 7),
            ('RIGHTPADDING', (0, 0), (-1, -1), 7),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        _, height = t.wrap(CW, H)
        if self.y-height < 45: raise ValueError(f'Tabela ultrapassa página {self.page}')
        t.drawOn(self.c, M, self.y-height); self.y -= height+12

    def image(self, path, height):
        if self.y-height < 45: raise ValueError('Figura ultrapassa página')
        self.c.drawImage(str(path), M, self.y-height, CW, height,
                         preserveAspectRatio=True, anchor='c', mask='auto')
        self.y -= height+8


def build_report(results: Path, output: Path) -> Path:
    s = json.loads((results/'summary.json').read_text(encoding='utf-8'))
    plots(results, s)
    output.parent.mkdir(parents=True, exist_ok=True)
    r = Report(output)
    r.new('Filho paga para o Pai')
    r.p('Lucas Panonko Assis Belchior - Matrícula 12311BCC068', 10, 'Bold')
    r.p('Detecção e análise de candidatos a Child Pays for Parent (CPFP)', 12)
    r.p('1. Objetivo e dados', 12, 'Bold')
    r.p('O objetivo é detectar uma transação pai de baixa taxa e uma transação filho '
        'que consome pelo menos uma saída do pai, paga uma taxa maior e aparece no '
        'mesmo bloco. As taxas das duas transações são destinadas ao minerador que '
        'produziu esse bloco. A classificação econômica é uma heurística: a inclusão '
        'conjunta comprova a dependência, mas não a intenção de acelerar a confirmação [1, 2].')
    r.table([['Característica da amostra', 'Resultado'],
             ['Fonte', 'blocos.tgz fornecido nos exercícios da disciplina'],
             ['Arquivo compactado', n(s['archive_bytes'])+' bytes'],
             ['Blocos analisados', n(s['blocks'])],
             ['Alturas mínima e máxima', f"{s['height_min']} a {s['height_max']}"],
             ['Período dos timestamps (UTC)', s['start_utc']+' até '+s['end_utc']],
             ['Transações normais / coinbase', n(s['normal_transactions'])+' / '+n(s['coinbase'])],
             ['Anomalias de integridade detectadas', n(s['anomalies'])]], [CW*.42, CW*.58])
    r.p('A amostra não é tratada como uma sequência contínua de blocos nem como '
        'representativa de toda a rede. Os JSONs são lidos diretamente do TAR '
        'compactado, um bloco por vez. O hash do arquivo e os comandos de reprodução '
        'estão na página de referências.')
    r.p(f"Resultado principal: {n(s['candidates'])} pares candidatos, em "
        f"{n(s['blocks_with_candidates'])} dos {n(s['blocks'])} blocos.", 12, 'Bold')

    r.new('Como o algoritmo detecta os pares')
    r.p('2. Dependência e unidade de análise', 12, 'Bold')
    r.p('Cada saída é identificada por (tx_index, n), no formato fornecido. O '
        'tx_index é um identificador do provedor; o hash da transação é conservado '
        'para auditoria. Uma entrada do filho deve referenciar uma saída existente '
        'do pai, com o mesmo valor, e o pai deve aparecer antes do filho no bloco. '
        'Várias saídas consumidas do mesmo pai formam uma única aresta.')
    r.p('Construímos um grafo por bloco. A análise econômica usa somente componentes '
        'conexos com duas transações e uma aresta: um par simples e isolado. '
        'Componentes com três ou mais transações são contados separadamente. Isso '
        'evita atribuir a um par a taxa de um pacote que contém outros ancestrais.')
    r.p('3. Taxas e regra principal', 12, 'Bold')
    r.p('f = soma das entradas - soma das saídas (satoshis)<br/>'
        'v = teto(peso / 4) (vbytes); r = f / v (sat/vB)<br/>'
        'r_conjunto = (f_pai + f_filho) / (v_pai + v_filho)', 10, 'Mono')
    r.p('M é a mediana de sat/vB das transações normais do próprio bloco. '
        'Um par simples é candidato quando atende simultaneamente:')
    r.table([['Condição', 'Interpretação'],
             ['r_pai < M', 'Pai relativamente barato no bloco'],
             ['f_filho > f_pai', 'Filho paga mais em taxa absoluta'],
             ['r_filho > r_pai e r_filho >= 2 × r_pai', 'Filho tem maior taxa por tamanho'],
             ['r_conjunto >= M', 'Conjunto alcança a referência adotada']], [CW*.52, CW*.48])
    r.p('Pai com taxa zero é permitido; o filho deve pagar taxa positiva. Não se '
        'calcula razão dividindo por zero. Se M = 0, nenhum par atende à primeira '
        'condição. M não é o limite de aceitação do minerador: é uma escolha didática.')
    r.p('Fluxo: ler e validar bloco → indexar transações/saídas → criar arestas → '
        'identificar componentes → aplicar regra → agregar resultados. O grafo '
        'custa O(T + I + O), em média, por bloco; a mediana e as ordenações acrescentam '
        'custo. T, I e O representam transações, entradas e saídas.')

    r.new('Frequência e comparação das taxas')
    r.table([['Indicador', 'Quantidade'],
             ['Dependências diretas no mesmo bloco', n(s['direct_dependencies'])],
             ['Pares simples elegíveis', n(s['simple_pairs'])],
             ['Componentes complexos / transações nesses componentes',
              n(s['complex_components'])+' / '+n(s['complex_transactions'])],
             ['Candidatos / pares simples', n(s['candidates'])+' / '+n(s['simple_pairs'])+' = '+pct(s['candidate_fraction_pairs'])],
             ['Filhos candidatos / transações normais', n(s['unique_children'])+' / '+n(s['normal_transactions'])+' = '+pct(s['candidate_fraction_transactions'])]], [CW*.69, CW*.31], 8.6)
    r.image(results/'figures/frequency.png', 170)
    r.p('Figura 1. Candidatos por bloco amostrado; os intervalos sem blocos no arquivo '
        'não são preenchidos com zeros.', 8.4)
    r.image(results/'figures/rates.png', 190)
    r.p('Figura 2. Todos os pares simples. Escala symlog nos dois eixos: linear '
        'até 1 sat/vB e logarítmica acima, preservando os casos de taxa zero. '
        'Os pontos destacados satisfazem todas as condições, não apenas a diferença de taxas.', 8.4)

    r.new('Taxas, valores e endereços')
    ms = s['metrics']
    r.table([['Medida entre candidatos', 'Mínimo', 'Mediana', 'Máximo']]+[
        [label, n(ms[key]['minimum'], digits), n(ms[key]['median'], max(digits, 1)),
         n(ms[key]['maximum'], digits)] for key, label, digits in [
            ('parent_fee', 'Taxa do pai (sat)', 0), ('child_fee', 'Taxa do filho (sat)', 0),
            ('parent_rate', 'Pai (sat/vB)', 3), ('child_rate', 'Filho (sat/vB)', 3),
            ('package_rate', 'Conjunto (sat/vB)', 3),
            ('consumed_sat', 'Valor consumido do pai (sat)', 0)]], [CW*.43, CW*.19, CW*.19, CW*.19], 8.3)
    r.p(f"Os candidatos têm {n(s['unique_parents'])} pais e {n(s['unique_children'])} filhos "
        f"distintos; {n(s['zero_fee_parents'])} pais pagam taxa zero. As taxas das "
        f"transações únicas somam {n(s['unique_fee_total_sat'])} sat. O valor das "
        f"saídas dos pais consumidas pelos filhos soma {n(ms['consumed_sat']['total'])} "
        f"sat ({n(ms['consumed_sat']['total']/100000000, 8)} BTC). "
        'Esse valor pode circular em outras transações: não representa dinheiro novo ou prejuízo.')
    r.p(f"Foram observados {n(s['unique_addresses'])} endereços distintos nas saídas "
        f"consumidas dos pais; {n(s['missing_address_outputs'])} de "
        f"{n(s['consumed_outputs'])} saídas não possuem endereço informado.")
    r.table([['Endereço da saída do pai', 'Pares', 'Valor (sat)']]+[
        [a['address'], n(a['pairs']), n(a['value_sat'])] for a in s['top_addresses']],
        [CW*.68, CW*.10, CW*.22], 7.8)
    r.p('Tabela de até cinco endereços mais recorrentes. Um endereço é contado uma '
        'vez por par, mesmo se houver várias saídas consumidas. Os valores agregam '
        'essas saídas. Endereço não equivale a pessoa; a análise não identifica '
        'proprietários nem deduz que pai e filho pertencem à mesma carteira.')

    r.new('Exemplos rastreáveis nos dados')
    for i, p in enumerate(s['examples'], 1):
        r.p(f"Exemplo {i} - bloco {p['height']}", 11, 'Bold')
        r.p('Pai: '+p['parent']+'<br/>Filho: '+p['child'], 7.2, 'Mono', 11)
        r.table([['Medida', 'Pai', 'Filho'],
                 ['Taxa (sat)', n(p['parent_fee']), n(p['child_fee'])],
                 ['Tamanho virtual (vB)', n(p['parent_vsize']), n(p['child_vsize'])],
                 ['Taxa por tamanho (sat/vB)', n(p['parent_rate'], 4), n(p['child_rate'], 4)]],
                [CW*.5, CW*.25, CW*.25], 8.5)
        r.p(f"Taxa conjunta: {n(p['package_rate'], 4)} sat/vB; mediana do bloco: "
            f"{n(p['median_rate'], 4)} sat/vB. Aumento absoluto em relação ao pai: "
            f"{n(p['uplift'], 4)} sat/vB. Valor consumido: {n(p['consumed_sat'])} sat. "
            f"Classificação: {'candidato' if p['candidate_2.0'] else 'rejeitado: '+p['reasons']}.", 9)
        consumed = '; '.join(f"saída {o['n']}: {n(o['value'])} sat, "
                             f"{o['address'] or 'endereço ausente'}" for o in p['consumed_outputs'])
        r.p(escape(consumed), 7.5)
    r.p('Seleção dos exemplos: maior aumento absoluto da taxa do conjunto em relação '
        'ao pai e, depois, menor taxa do pai entre os demais candidatos. Os vínculos '
        'e cálculos foram reconferidos diretamente nos blocos originais. '
        'A seleção ilustra o mecanismo e não representa o caso típico.', 8.7)

    r.new('Sensibilidade, limites e conclusão')
    r.image(results/'figures/sensitivity.png', 185)
    r.p('Figura 3. Variação apenas do multiplicador mínimo da taxa por tamanho do '
        'filho em relação ao pai. Todas as demais condições permanecem fixas. '
        'Os três valores foram definidos antes de examinar os resultados.', 8.6)
    r.p('Limitações', 12, 'Bold')
    r.p('A regra usa taxas relativas ao próprio bloco, sem estimar a política '
        'real do minerador. Não há dados históricos da mempool, tempo de espera, '
        'declaração de intenção ou rótulos verdadeiros. Por isso, não se calculam '
        'acurácia, precisão ou recall, e os pares classificados são candidatos '
        'compatíveis com CPFP, não ocorrências confirmadas por intenção.')
    r.p('Pacotes com três ou mais transações ficam fora da classificação principal, '
        'embora possam conter CPFP. A contagem é restrita aos pares simples da '
        'amostra e não mede a frequência global da técnica. Gastos comuns podem '
        'satisfazer os critérios. Endereços ausentes limitam a análise de recorrência.')
    r.p('Validação', 12, 'Bold')
    r.p('Os testes sintéticos verificam: taxa zero, mediana zero, arredondamento de '
        'peso, taxas inconsistentes, entradas repetidas do mesmo pai, pais externos, '
        'cadeias, ramificações, coinbase, referências internas inválidas e endereço '
        'ausente. Na base completa, foram conferidos duplicados, taxas, referências '
        'internas e a ordem pai-filho. Os dois exemplos foram recalculados na fonte.')
    r.p('Conclusão', 12, 'Bold')
    r.p(f"O algoritmo encontrou {n(s['candidates'])} candidatos entre "
        f"{n(s['simple_pairs'])} pares simples ({pct(s['candidate_fraction_pairs'])}). "
        'O trabalho mostra como o grafo de UTxOs e a taxa conjunta permitem '
        'detectar um padrão econômico explicável. A principal distinção aprendida '
        'é entre observar uma dependência na cadeia e comprovar a motivação de quem '
        'criou a transação.')

    r.new('Reprodução e referências')
    r.p('Código e resultados', 12, 'Bold')
    r.p(f'<link href="{REPO}" color="{TEAL}">{REPO}</link>', 8.5)
    r.p('O repositório contém os dois scripts, testes, tabelas resumidas e este PDF. '
        'O arquivo original não é redistribuído: usar o blocos.tgz fornecido pela '
        'disciplina. O apêndice traz o código integral, para que o documento seja '
        'autossuficiente. As tabelas completas são regeneradas pelos comandos abaixo.')
    r.p('Python 3.12 ou superior. Dentro da pasta do repositório, com um interpretador '
        'Python instalado e funcional:')
    r.p('Dependências usadas: matplotlib 3.10.7, reportlab 4.4.9 e pypdf 6.10.0 '
        '(conteúdo de requirements.txt). O detector usa somente a biblioteca padrão.', 8.7)
    r.p('python -m pip install -r requirements.txt<br/>'
        'python -m unittest -v test_analyze<br/>'
        'python analyze.py --archive ../blocos.tgz --output results<br/>'
        'python build_report.py --results results<br/>'
        'No último comando, o PDF é gravado em report/.', 8, 'Mono', 13)
    r.p('Identificação exata do arquivo de entrada (SHA-256):', 9)
    r.p(s['archive_sha256'], 7.7, 'Mono')
    r.p('Saídas: pairs.csv (pares simples e motivos de rejeição), blocks.csv (censo '
        'por bloco), addresses.csv (endereços dos candidatos) e summary.json '
        '(parâmetros, totais, métricas e exemplos). Valores monetários estão em '
        'satoshis; 1 BTC = 100.000.000 sat.')
    r.p('Referências', 12, 'Bold')
    r.p('[1] Enunciado da atividade “(P1) Filho paga para o Pai”, disciplina de '
        'Tópicos Especiais de Segurança. Material fornecido ao aluno, 2026.<br/><br/>'
        '[2] BITCOIN CORE. Bitcoin Core 0.13.0 Released!, seção “More intelligent '
        'transaction selection for mining”, 23 ago. 2016. Disponível em: '
        '<link href="https://bitcoincore.org/en/2016/08/23/release-0.13.0/">'
        'https://bitcoincore.org/en/2016/08/23/release-0.13.0/</link>. '
        'Acesso em: 2 nov. 2026.<br/><br/>'
        '[3] blocos.tgz. Conjunto de blocos JSON fornecido nos exercícios anteriores '
        'da disciplina. Arquivo identificado pelo SHA-256 acima.', 9)
    r.p('Apêndice - código-fonte integral', 12, 'Bold')
    r.p('As páginas seguintes reproduzem analyze.py e build_report.py com números '
        'de linha. Linhas longas são quebradas visualmente; para execução, usar '
        'os arquivos do repositório. A lógica de detecção não depende de rede, '
        'serviços pagos ou aprendizado de máquina.')
    for filename in ['analyze.py', 'build_report.py']:
        lines = []
        for num, line in enumerate((ROOT/filename).read_text(encoding='utf-8').splitlines(), 1):
            wrapped = textwrap.wrap(line.expandtabs(4), width=99, replace_whitespace=False,
                                    drop_whitespace=False) or ['']
            lines.extend([f'{num:03d}  '+wrapped[0]]+['     '+v for v in wrapped[1:]])
        for offset in range(0, len(lines), 65):
            r.new(f'Apêndice | {filename}')
            r.c.setFont('Mono', 7.5)
            r.c.setFillColor(colors.HexColor(INK))
            for line in lines[offset:offset+65]:
                r.c.drawString(M, r.y, line)
                r.y -= 10.1
    r.c.save()
    print(f'PDF: {output.resolve()} ({r.page} páginas)')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, default=Path('results'))
    parser.add_argument('--output', type=Path,
        default=Path('report/Filho_Paga_Para_Pai_Lucas_Belchior.pdf'))
    args = parser.parse_args()
    build_report(args.results, args.output)
