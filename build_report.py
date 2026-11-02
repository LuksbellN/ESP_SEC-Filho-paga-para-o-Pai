"""Gera gráficos e PDF autossuficiente a partir dos resultados do analisador."""
import argparse
import csv
import json
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
INK, TEAL, GRAY = '#202020', '#333333', '#666666'


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
        c.setStrokeColor(colors.HexColor(GRAY)); c.setLineWidth(.5)
        c.line(M, H-35, W-M, H-35)
        c.setFont('Body', 8); c.setFillColor(colors.HexColor(GRAY))
        c.drawString(M, H-27, 'TÓPICOS ESPECIAIS DE SEGURANÇA | FILHO PAGA PARA O PAI')
        c.drawRightString(W-M, 25, f'{self.page} / 5')
        c.drawString(M, 25, 'Lucas Panonko Assis Belchior | 12311BCC068 | 02/11/2026')
        self.y = H-62
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
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eeeeee')),
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
    c = r.c
    # Capa simples, seguindo a apresentação da entrega ColdCard - ML.
    r.page = 1
    def center(y, text, size=11, font='Body'):
        c.setFont(font, size)
        c.setFillColor(colors.HexColor(INK))
        c.drawCentredString(W/2, y, text)
    center(H-115, 'Tópicos Especiais de Segurança', 12, 'Bold')
    center(H-185, 'Lucas Panonko Assis Belchior')
    center(H-205, 'Matrícula: 12311BCC068', 10)
    center(H/2+15, 'Filho paga para o Pai', 24, 'Bold')
    center(H/2-15, 'Detecção e análise de transações compatíveis com CPFP', 10)
    center(H/2-90, 'Repositório do projeto', 10, 'Bold')
    center(H/2-110, REPO, 8)
    c.linkURL(REPO, (M, H/2-115, W-M, H/2-95), relative=0)
    center(110, '2 de novembro de 2026', 10)

    r.new('Visão geral do trabalho')
    r.p('01 / OBJETIVO', 9, 'Bold')
    r.p('Desenvolver um algoritmo para detectar o padrão <b>Filho Paga para o Pai</b> '
        '(Child Pays for Parent, CPFP) e analisar sua frequência, valores, taxas e endereços '
        'nos blocos fornecidos pela disciplina.')
    r.table([['Blocos analisados', 'Transações normais', 'Pares candidatos'],
             [n(s['blocks']), n(s['normal_transactions']), n(s['candidates'])]], size=12)
    r.p('Como funciona o CPFP', 12, 'Bold')
    r.p('O <b>pai</b> cria uma saída não gasta (UTxO) e paga uma taxa baixa. '
        'O <b>filho</b> consome essa saída e paga uma taxa mais alta. Quando ambos '
        'entram no mesmo bloco, o minerador recebe as duas taxas. O filho pode, assim, '
        'tornar economicamente mais atraente incluir o pai [1].')
    r.table([['PAI', 'FILHO', 'MESMO BLOCO'],
             ['Cria o UTxO e paga pouco', 'Gasta o UTxO e paga mais',
              'Minerador recebe as duas taxas']], size=9.5)
    r.p('Dados utilizados', 12, 'Bold')
    r.p('Foi utilizado o <b>blocos.tgz</b> dos exercícios anteriores: 98 blocos não '
        'contínuos, com alturas entre 960179 e 960802, registrados entre 30/07 e '
        '03/08/2026 (UTC). Foram excluídas 98 transações coinbase, que criam moedas '
        'e não representam o tipo de gasto procurado. A amostra não representa toda a rede.')
    r.p('Resultado principal', 12, 'Bold')
    r.p(f"Foram encontrados <b>{n(s['candidates'])} candidatos</b> entre "
        f"{n(s['simple_pairs'])} pares simples ({pct(s['candidate_fraction_pairs'])}), "
        f"distribuídos em {n(s['blocks_with_candidates'])} blocos. Os filhos candidatos "
        f"representam {pct(s['candidate_fraction_transactions'])} das transações normais.")
    r.p('A dependência entre as transações e a confirmação conjunta são observáveis '
        'nos dados. A intenção de acelerar a confirmação não é comprovável apenas '
        'pela blockchain; por isso, os resultados são chamados de <b>candidatos a CPFP</b>.')

    r.new('Algoritmo e critérios de detecção')
    r.p('02 / METODOLOGIA', 9, 'Bold')
    r.p('Implementação em Python', 12, 'Bold')
    r.p('1. Ler um bloco por vez e indexar suas transações e saídas.<br/>'
        '2. Para cada entrada, procurar a transação que criou a saída consumida.<br/>'
        '3. Se o pai estiver no mesmo bloco, conferir a saída, o valor e sua posição '
        'anterior ao filho. Registrar uma ligação pai → filho.<br/>'
        '4. Agrupar as ligações em componentes. Aplicar a regra de taxas aos pares '
        'isolados de duas transações e agregar os resultados.')
    r.p('Se várias entradas do filho gastam saídas do mesmo pai, elas formam um único '
        'par, com os valores somados. Componentes com três ou mais transações '
        '(cadeias ou ramificações) são contados separadamente: a taxa de um par '
        'isolado não descreve todo esse pacote.')
    r.p('Cálculo das taxas', 12, 'Bold')
    r.p('Taxa = soma dos valores das entradas − soma dos valores das saídas.<br/>'
        'Tamanho virtual = teto(peso da transação / 4).<br/>'
        'Taxa por tamanho = taxa / tamanho virtual, em sat/vB.<br/>'
        'Taxa conjunta = (taxa do pai + taxa do filho) / '
        '(tamanho virtual do pai + tamanho virtual do filho).')
    r.p('A comparação usa sat/vB: pagar mais satoshis não garante uma taxa por '
        'tamanho maior. Define-se <b>M</b> como a mediana de sat/vB das transações '
        'normais do bloco. O par precisa satisfazer todas as condições:')
    r.table([['Critério', 'Condição'],
             ['Pai com taxa baixa', 'Taxa por tamanho do pai < M'],
             ['Filho com taxa alta', 'Taxa absoluta maior que a do pai e taxa por tamanho '
              'maior e pelo menos 2 vezes a do pai'],
             ['Compensação conjunta', 'Taxa conjunta ≥ M']], [CW*.34, CW*.66])
    r.p('Pai com taxa zero é permitido, desde que o filho pague taxa positiva e o '
        'conjunto alcance M. Não se divide pela taxa do pai. Se M for zero, nenhum '
        'par tem taxa estritamente abaixo dela. Esses limiares são escolhas '
        'didáticas, não regras do protocolo nem limites conhecidos do minerador.', 9)
    r.p('Verificação: nove testes sintéticos cobrem taxas, referências, coinbase, '
        'cadeias e saídas sem endereço. A análise completa não detectou inconsistências '
        'de taxas ou referências internas; os exemplos foram reconferidos na fonte.', 9)

    r.new('Frequência, valores e endereços')
    r.p('03 / RESULTADOS', 9, 'Bold')
    r.p(f"Foram observadas {n(s['direct_dependencies'])} dependências diretas no mesmo "
        f"bloco. Destas estruturas, {n(s['simple_pairs'])} são pares simples. Outros "
        f"{n(s['complex_components'])} componentes possuem três ou mais transações "
        'e ficaram fora da classificação econômica principal.', 9.2)
    r.image(results/'figures/frequency.png', 145)
    r.p('Candidatos por bloco amostrado, em ordem de altura. Intervalos sem blocos '
        'no arquivo foram omitidos; não representam blocos sem candidatos.', 8)
    ms = s['metrics']
    r.table([['Medida entre os 552 candidatos', 'Mínimo', 'Mediana', 'Máximo']]+[
        [label, n(ms[key]['minimum'], digits), n(ms[key]['median'], max(1, digits)),
         n(ms[key]['maximum'], digits)] for key, label, digits in [
            ('parent_fee', 'Taxa do pai (sat)', 0),
            ('child_fee', 'Taxa do filho (sat)', 0),
            ('package_rate', 'Taxa conjunta (sat/vB)', 3),
            ('consumed_sat', 'Valor consumido do pai (sat)', 0)]],
            [CW*.43, CW*.19, CW*.19, CW*.19], 8.3)
    r.p(f"Há {n(s['zero_fee_parents'])} pais candidatos com taxa zero. As taxas das "
        f"transações dos candidatos somam {n(s['unique_fee_total_sat'])} sat. "
        f"O valor consumido dos pais soma {n(ms['consumed_sat']['total']/100000000, 8)} BTC. "
        'São valores transferidos entre transações, não dinheiro novo ou prejuízo. '
        'O máximo consumido é muito superior à mediana; o total não descreve '
        'um par típico. 1 BTC = 100.000.000 sat.', 8.7)
    r.p('Endereços mais recorrentes nas saídas consumidas', 10.5, 'Bold')
    r.table([['Endereço da saída do pai', 'Pares', 'Valor (sat)']]+[
        [a['address'], n(a['pairs']), n(a['value_sat'])] for a in s['top_addresses'][:3]],
        [CW*.65, CW*.10, CW*.25], 7.7)
    r.p(f"Foram observados {n(s['unique_addresses'])} endereços distintos nas "
        f"{n(s['consumed_outputs'])} saídas consumidas, sem endereços ausentes. "
        'Cada endereço é contado uma vez por par. A recorrência não identifica '
        'pessoas ou carteiras.', 8.6)
    r.p('O endereço mais frequente movimenta menos valor que o terceiro da tabela. '
        'Assim, frequência de uso e valor transferido são medidas distintas.', 8.6)

    r.new('Exemplos e análise dos resultados')
    r.p('04 / DISCUSSÃO', 9, 'Bold')
    r.p('Dois exemplos reais', 12, 'Bold')
    examples = s['examples']
    r.table([['Medida', 'Bloco '+str(examples[0]['height']),
              'Bloco '+str(examples[1]['height'])]]+[
        [label]+[n(p[key], digits) for p in examples] for key, label, digits in [
            ('parent_fee', 'Taxa do pai (sat)', 0),
            ('child_fee', 'Taxa do filho (sat)', 0),
            ('parent_rate', 'Pai (sat/vB)', 4),
            ('child_rate', 'Filho (sat/vB)', 4),
            ('package_rate', 'Conjunto (sat/vB)', 4),
            ('median_rate', 'Mediana do bloco (sat/vB)', 4),
            ('consumed_sat', 'Valor consumido do pai (sat)', 0)]],
            [CW*.46, CW*.27, CW*.27], 8.5)
    r.p('O primeiro exemplo tem o maior aumento absoluto da taxa do conjunto em '
        'relação ao pai entre os candidatos. O segundo mostra um pai com taxa zero: '
        'o filho paga 503 sat e eleva a taxa conjunta acima da mediana do bloco. '
        'Em ambos, o filho consome a saída 0 do pai, e as duas transações estão no '
        'mesmo bloco. Os identificadores completos estão nos resultados do repositório.', 9)
    r.p('Sensibilidade da regra', 11, 'Bold')
    r.table([['Multiplicador mínimo da taxa do filho', '1,5 ×', '2 × (principal)', '3 ×'],
             ['Pares candidatos']+[n(v) for v in s['sensitivity'].values()]],
            [CW*.49, CW*.17, CW*.17, CW*.17], 8.5)
    r.p('Apenas o multiplicador varia; os outros critérios permanecem fixos. '
        'A contagem diminui com a exigência de uma diferença maior de taxas, '
        'mostrando que o resultado depende da definição adotada para taxa alta.', 9)
    r.p('Conclusão e limitações', 11, 'Bold')
    r.p('O algoritmo identifica um padrão compatível com CPFP combinando a dependência '
        'entre UTxOs e a taxa conjunta. Foram encontrados <b>552 candidatos</b>, '
        'mas gastos comuns também podem satisfazer a regra. Sem registros históricos '
        'da mempool ou confirmação dos autores, não é possível provar intenção, '
        'necessidade de aceleração ou o limite real de seleção do minerador. '
        'Pacotes complexos não foram classificados, e o recorte não permite '
        'estimar a frequência global da técnica.', 9)
    r.p('Referências e código', 10.5, 'Bold')
    r.p('[1] BITCOIN CORE. Bitcoin Core 0.13.0 Released!, seção “More intelligent '
        'transaction selection for mining”, 2016. '
        '<link href="https://bitcoincore.org/en/2016/08/23/release-0.13.0/">'
        'bitcoincore.org/en/2016/08/23/release-0.13.0/</link>. Acesso: 02/11/2026.<br/>'
        '[2] Enunciado da atividade “(P1) Filho paga para o Pai” e blocos.tgz '
        'fornecidos pela disciplina.<br/>'
        f'Código, testes, dados derivados e instruções: '
        f'<link href="{REPO}">{REPO}</link>.', 7.8)
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
