"""
Gera PDF com visualizacoes do modelo de risco FPD - Hackathon PoD Academy.
Cada pagina: titulo + descricao + plot full-width em fundo branco.
"""
import os
from fpdf import FPDF
from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(BASE, "..", ".."))
PLOTS_DIR = os.path.join(PROJECT, "artifacts", "analysis", "plots")
OUTPUT = os.path.join(BASE, "visualizacoes-modelo-fpd.pdf")

# Azul Claro brand
BLUE = (0, 161, 224)
DARK = (51, 51, 51)
GRAY = (108, 117, 125)
WHITE = (255, 255, 255)


def t(text):
    """Sanitize unicode chars unsupported by Helvetica/latin-1."""
    for old, new in [
        ("\u2014", "-"), ("\u2013", "-"), ("\u2018", "'"), ("\u2019", "'"),
        ("\u201c", '"'), ("\u201d", '"'), ("\u2026", "..."),
    ]:
        text = text.replace(old, new)
    return text


SLIDES = [
    {
        "title": "Performance do Modelo - 8 Metricas",
        "subtitle": "LightGBM Baseline v6 | KS 33.97% | AUC 0.7303 | Gini 46.06 pp",
        "description": (
            "Painel com ROC Curve, Precision-Recall, KS Statistic, Score Distribution, "
            "Confusion Matrix, Calibration e metricas por safra. "
            "O modelo supera o Score Bureau em +0.87 pp de KS com degradacao controlada entre treino e teste."
        ),
        "image": "panel1_performance_8plots.png",
    },
    {
        "title": "Estabilidade e Ranking - 8 Metricas",
        "subtitle": "PSI 0.0011 | Decil 1 captura 52.7% de defaults | Lift 2.47x",
        "description": (
            "Painel com Decile Analysis, Lift Chart, PSI (Population Stability Index), "
            "Swap Analysis, Calibration Curve e estabilidade temporal. "
            "O ranking se mantem estavel entre safras com PSI bem abaixo de 0.10."
        ),
        "image": "panel2_stability_8plots.png",
    },
    {
        "title": "Impacto no Negocio - 8 Metricas",
        "subtitle": "Economia estimada de R$ 550K a R$ 1.25M/mes conforme estrategia de corte",
        "description": (
            "Painel com Model Comparison, LR Coefficients, Risk Bands, "
            "Feature Importance, Approval Rate Trade-offs e cenarios de impacto financeiro. "
            "Top 10% negados = 90% aprovacao com 24.7% dos defaults evitados."
        ),
        "image": "panel3_business_8plots.png",
    },
    {
        "title": "SHAP Beeswarm - Top 40 Features",
        "subtitle": "Importancia e direcao de impacto de cada variavel no modelo",
        "description": (
            "Grafico SHAP mostrando a distribuicao de impacto das 40 features mais importantes. "
            "TARGET_SCORE_02 domina com 29.2% de importancia. "
            "Dados internos de recarga (REC_*) representam 24% da importancia total, "
            "comprovando o valor dos dados proprietarios da Claro."
        ),
        "image": "shap_beeswarm_top40.png",
    },
    {
        "title": "SHAP Pareto - Importancia Acumulada",
        "subtitle": "Top 20 features = 60% | Top 40 = 81% da importancia total",
        "description": (
            "Curva de Pareto acumulada mostrando que poucas features concentram "
            "a maior parte do poder preditivo. Das 59 features selecionadas (de 398 originais), "
            "as 20 primeiras ja explicam 60% do modelo - eficiencia na selecao."
        ),
        "image": "shap_pareto_cumulative.png",
    },
    {
        "title": "KS Incremental - Contribuicao por Fonte de Dados",
        "subtitle": "Bureau: +27 pp | Recarga: +7 pp | Pagamento + Faturamento: +4 pp",
        "description": (
            "Analise incremental mostrando a contribuicao de cada fonte de dados para o KS final. "
            "Score Bureau externo e a base (36% da importancia), mas dados internos de recarga "
            "adicionam +7 pp de KS - validando a estrategia de enriquecimento com dados Claro."
        ),
        "image": "ks_incremental_dual.png",
    },
]


class PresentationPDF(FPDF):
    def header(self):
        self.set_draw_color(*BLUE)
        self.set_line_width(0.8)
        self.line(10, 8, self.w - 10, 8)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*GRAY)
        self.cell(0, 10, t("Hackathon PoD Academy | Claro + Oracle | Fev 2025"), align="L")
        self.cell(0, 10, f"Pagina {self.page_no()}/{{nb}}", align="R")


def add_cover(pdf):
    pdf.add_page()
    pdf.ln(50)

    pdf.set_font("Helvetica", "B", 32)
    pdf.set_text_color(*BLUE)
    pdf.cell(0, 16, t("Modelo Preditivo de Inadimplencia"), align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(*DARK)
    pdf.cell(0, 14, t("First Payment Default (FPD)"), align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(8)

    pdf.set_font("Helvetica", "", 16)
    pdf.set_text_color(*GRAY)
    pdf.cell(0, 10, t("Migracao Pre-pago para Controle - Claro Telecom"), align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(20)

    kpis = [("KS", "33.97%"), ("AUC", "0.7303"), ("Lift", "2.47x"), ("PSI", "0.0011")]
    box_w = 40
    gap = 6
    total_w = len(kpis) * box_w + (len(kpis) - 1) * gap
    start_x = (pdf.w - total_w) / 2

    for i, (label, value) in enumerate(kpis):
        x = start_x + i * (box_w + gap)
        y = pdf.get_y()

        pdf.set_fill_color(*BLUE)
        pdf.rect(x, y, box_w, 28, style="F")

        pdf.set_xy(x, y + 3)
        pdf.set_font("Helvetica", "B", 20)
        pdf.set_text_color(*WHITE)
        pdf.cell(box_w, 12, value, align="C")

        pdf.set_xy(x, y + 15)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(box_w, 8, label, align="C")

    pdf.set_text_color(*DARK)
    pdf.ln(45)

    pdf.set_font("Helvetica", "I", 12)
    pdf.set_text_color(*GRAY)
    pdf.multi_cell(0, 7, t("59 variaveis selecionadas de 398 | 3.9M registros | 6 safras | Microsoft Fabric"), align="C")

    pdf.ln(15)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*DARK)
    pdf.cell(0, 8, t("Hackathon PoD Academy | Claro + Oracle | Fevereiro 2025"), align="C")


def add_slide(pdf, slide):
    pdf.add_page()
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*BLUE)
    pdf.cell(0, 10, t(slide["title"]), align="L", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*DARK)
    pdf.cell(0, 7, t(slide["subtitle"]), align="L", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(2)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*GRAY)
    pdf.multi_cell(0, 5, t(slide["description"]), align="L")

    pdf.ln(4)

    img_path = os.path.join(PLOTS_DIR, slide["image"])
    if os.path.exists(img_path):
        img = Image.open(img_path)
        img_w, img_h = img.size

        available_w = pdf.w - 20
        available_h = pdf.h - pdf.get_y() - 20

        scale = min(available_w / img_w, available_h / img_h)
        final_w = img_w * scale
        final_h = img_h * scale

        x = (pdf.w - final_w) / 2
        pdf.image(img_path, x=x, y=pdf.get_y(), w=final_w, h=final_h)
    else:
        pdf.set_font("Helvetica", "I", 12)
        pdf.set_text_color(220, 53, 69)
        pdf.cell(0, 10, t(f"[Imagem nao encontrada: {slide['image']}]"), align="C")


def main():
    pdf = PresentationPDF(orientation="L", format="A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=False)

    add_cover(pdf)

    for slide in SLIDES:
        add_slide(pdf, slide)

    pdf.output(OUTPUT)
    print(f"PDF gerado: {OUTPUT}")
    print(f"Total de paginas: {pdf.page_no()}")


if __name__ == "__main__":
    main()
