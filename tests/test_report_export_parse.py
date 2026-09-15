"""
Unit tests para `skills/report-export/recetas/parse_insights.py`.

`parse_insights_markdown` lee el .md que produce `insight-synthesis`
y extrae: title (frontmatter o H1), date, author, summary, y la lista
de insights numerados con sus sub-bloques Qué / Por qué / Ahora qué.

Cobertura:
- Frontmatter YAML basico
- Insights numerados (## Insight N: title)
- Sub-bloques Qué / Por qué / Ahora qué (con y sin tildes)
- Edge cases: MD vacio, MD sin insights, MD con multiples insights
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from report_export import recetas as rex


@pytest.fixture
def md_with_frontmatter(tmp_path: Path) -> Path:
    """MD con frontmatter + 2 insights + sub-bloques Qué/Por qué/Ahora qué."""
    content = textwrap.dedent("""\
        ---
        title: Revenue Q2 2026
        date: 2026-07-15
        author: Bastian
        ---

        # Revenue Q2 2026

        Resumen ejecutivo de revenue para Q2 2026, comparado contra Q1.

        ## Insight 1: Revenue crecio 18% QoQ

        **Qué**: El revenue subio 18% trimestre contra trimestre.

        **Por qué**: La campana de lanzamiento de SKUs premium en mayo empujo
        ticket promedio de $42 a $51.

        **Ahora qué**: Replicar el bundle premium en SKUs de bajo engagement
        en Q3, con meta de +5pp en ticket promedio.

        ## Insight 2: Churn estable

        **Qué**: La tasa de churn mensual se mantuvo en 2.3%.

        **Por qué**: No hubo incidentes de plataforma ni cambios de pricing.

        **Ahora qué**: Mantener el monitoreo, no requiere accion.
    """)
    p = tmp_path / "insights.md"
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def md_without_frontmatter(tmp_path: Path) -> Path:
    """MD sin frontmatter, solo H1 + insights basicos (sin sub-bloques)."""
    content = textwrap.dedent("""\
        # Top clientes Q2

        Reporte rapido.

        ## Insight 1: Cliente A concentra 22% del revenue

        Cliente A represento el 22% del revenue Q2 con USD 145K.

        ## Insight 2: Top 10 cubre 65% del revenue

        Los 10 clientes principales concentran 65% del revenue total.
    """)
    p = tmp_path / "basic.md"
    p.write_text(content, encoding="utf-8")
    return p


# -----------------------------------------------------------------------
# Lectura basica + frontmatter
# -----------------------------------------------------------------------

class TestFrontmatterAndTitle:

    def test_reads_title_from_frontmatter(self, md_with_frontmatter: Path) -> None:
        result = rex.parse_insights_markdown(md_with_frontmatter)
        assert result["title"] == "Revenue Q2 2026"

    def test_reads_date_from_frontmatter(self, md_with_frontmatter: Path) -> None:
        result = rex.parse_insights_markdown(md_with_frontmatter)
        assert result["date"] == "2026-07-15"

    def test_reads_author_from_frontmatter(self, md_with_frontmatter: Path) -> None:
        result = rex.parse_insights_markdown(md_with_frontmatter)
        assert result["author"] == "Bastian"

    def test_falls_back_to_h1_when_no_frontmatter(self, md_without_frontmatter: Path) -> None:
        result = rex.parse_insights_markdown(md_without_frontmatter)
        assert result["title"] == "Top clientes Q2"
        assert result["date"] == ""
        assert result["author"] == ""


# -----------------------------------------------------------------------
# Insights numerados
# -----------------------------------------------------------------------

class TestInsightsExtraction:

    def test_extracts_all_numbered_insights(self, md_with_frontmatter: Path) -> None:
        result = rex.parse_insights_markdown(md_with_frontmatter)
        assert len(result["insights"]) == 2

    def test_insight_numbers_are_correct(self, md_with_frontmatter: Path) -> None:
        result = rex.parse_insights_markdown(md_with_frontmatter)
        assert [i["number"] for i in result["insights"]] == [1, 2]

    def test_insight_titles_extracted(self, md_with_frontmatter: Path) -> None:
        result = rex.parse_insights_markdown(md_with_frontmatter)
        assert result["insights"][0]["title"] == "Revenue crecio 18% QoQ"
        assert result["insights"][1]["title"] == "Churn estable"

    def test_extracts_what_why_now_subblocks(self, md_with_frontmatter: Path) -> None:
        result = rex.parse_insights_markdown(md_with_frontmatter)
        first = result["insights"][0]
        # Match case-insensitive: el fixture usa "revenue" (lowercase) en el cuerpo
        # aunque el titulo use "Revenue".
        assert "revenue" in first["what"].lower() and "18%" in first["what"]
        assert "campana" in first["why"].lower() or "lanzamiento" in first["why"].lower()
        assert "replicar" in first["now"].lower() or "q3" in first["now"].lower()

    def test_handles_que_por_que_ahora_que_without_tildes(self, tmp_path: Path) -> None:
        """Variantes sin tildes: Que / Por que / Ahora que."""
        content = textwrap.dedent("""\
            # Test

            ## Insight 1: Subtildes

            **Que**: El dato sin tildes.

            **Por que**: El porque sin tildes.

            **Ahora que**: El ahora que sin tildes.
        """)
        p = tmp_path / "no_tildes.md"
        p.write_text(content, encoding="utf-8")
        result = rex.parse_insights_markdown(p)
        assert "El dato sin tildes." in result["insights"][0]["what"]
        assert "porque sin tildes" in result["insights"][0]["why"]
        assert "ahora que sin tildes" in result["insights"][0]["now"].lower()

    def test_insight_without_subblocks_puts_all_in_what(self, md_without_frontmatter: Path) -> None:
        result = rex.parse_insights_markdown(md_without_frontmatter)
        first = result["insights"][0]
        assert "22%" in first["what"]
        assert first["why"] == ""
        assert first["now"] == ""


# -----------------------------------------------------------------------
# Edge cases
# -----------------------------------------------------------------------

class TestEdgeCases:

    def test_missing_file_raises_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError) as exc:
            rex.parse_insights_markdown(tmp_path / "nope.md")
        assert "insights" in str(exc.value).lower() or "nope.md" in str(exc.value)

    def test_md_without_insights_returns_empty_list(self, tmp_path: Path) -> None:
        """Un MD sin `## Insight N:` devuelve lista vacia y title='Reporte'."""
        p = tmp_path / "no_insights.md"
        p.write_text("# Solo titulo\n\nTexto sin insights numerados.\n", encoding="utf-8")
        result = rex.parse_insights_markdown(p)
        assert result["insights"] == []

    def test_md_without_h1_or_frontmatter_uses_default_title(self, tmp_path: Path) -> None:
        p = tmp_path / "no_title.md"
        p.write_text("Texto sin titulo ni frontmatter.\n", encoding="utf-8")
        result = rex.parse_insights_markdown(p)
        assert result["title"] == "Reporte"

    def test_summary_extracted_between_h1_and_first_insight(self, md_with_frontmatter: Path) -> None:
        result = rex.parse_insights_markdown(md_with_frontmatter)
        assert "Resumen ejecutivo" in result["summary"]
        assert "Q2 2026" in result["summary"]
