"""
ReportService — renders investigation reports as Markdown or PDF.

Pure functions — no DB access, no external calls.
Supports the full SRE report format with evidence separation.
"""

from datetime import datetime


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

def render_markdown(investigation: dict) -> str:
    created_at = investigation.get("created_at")
    if isinstance(created_at, datetime):
        created_at_str = created_at.strftime("%Y-%m-%d %H:%M UTC")
    elif created_at:
        created_at_str = str(created_at)
    else:
        created_at_str = "—"

    confidence = investigation.get("confidence", 0)
    confidence_level = investigation.get("confidence_level", _confidence_label(confidence))
    confidence_reasoning = investigation.get("confidence_reasoning", "")
    root_cause_status = investigation.get("root_cause_status", "Likely")
    executive_summary = investigation.get("executive_summary", "")
    incident_summary = investigation.get("incident_summary") or {}
    observed_evidence = investigation.get("observed_evidence") or []
    root_cause = investigation.get("root_cause", "_Not determined_")
    alternative_hypotheses = investigation.get("alternative_hypotheses") or []
    immediate_actions = investigation.get("immediate_actions") or []
    long_term_prevention = investigation.get("long_term_prevention") or []
    evidence_coverage = investigation.get("evidence_coverage") or {}
    ai_reasoning_notes = investigation.get("ai_reasoning_notes", "")
    retrieved_chunks = investigation.get("retrieved_chunks") or investigation.get("sources") or []

    lines: list[str] = []

    # Header
    lines += [
        "# OpsLens Investigation Report",
        "",
        f"**Investigation ID:** {investigation.get('id', '—')}  ",
        f"**Incident ID:** {investigation.get('incident_id', '—')}  ",
        f"**Generated:** {created_at_str}  ",
        f"**Confidence:** {confidence}% — {confidence_level}  ",
        f"**Root Cause Status:** {root_cause_status}",
        "",
        "---",
        "",
    ]

    # Executive Summary
    if executive_summary:
        lines += ["## Executive Summary", "", executive_summary, ""]

    # Incident Summary
    if incident_summary:
        lines += ["## Incident Summary", ""]
        lines += [
            f"| Field | Value |",
            f"|---|---|",
            f"| Title | {incident_summary.get('title', '—')} |",
            f"| Severity | {incident_summary.get('severity', '—')} |",
            f"| Affected Service | {incident_summary.get('affected_service', '—')} |",
            f"| Business Impact | {incident_summary.get('business_impact', '—')} |",
        ]
        if incident_summary.get("timeline_note"):
            lines.append(f"| Timeline | {incident_summary['timeline_note']} |")
        lines.append("")

    # Observed Evidence
    lines += ["## Observed Evidence", ""]
    if observed_evidence:
        for e in observed_evidence:
            lines.append(f"- ✓ {e}")
    else:
        lines.append("_No direct observations recorded._")
    lines.append("")

    # Retrieved Evidence
    lines += ["## Retrieved Evidence", ""]
    if retrieved_chunks:
        for i, chunk in enumerate(retrieved_chunks, 1):
            fname = chunk.get("filename") or f"doc_{chunk.get('document_id')}"
            chunk_num = chunk.get("chunk_index", "?")
            score = chunk.get("score")
            score_str = f"{score:.3f}" if score is not None else "N/A"
            snippet = chunk.get("snippet", "")
            lines += [
                f"**[{i}] {fname}** — Chunk #{chunk_num} — Similarity: `{score_str}`",
                f"> {snippet}" if snippet else "",
                "",
            ]
    else:
        lines += ["_No documentation was retrieved for this investigation._", ""]

    # Root Cause Analysis
    lines += [
        "## Root Cause Analysis",
        "",
        f"**Status:** `{root_cause_status}`",
        "",
        root_cause,
        "",
    ]

    # Confidence
    lines += [
        "## Confidence",
        "",
        f"**{confidence_level}** — {confidence}%",
        "",
    ]
    if confidence_reasoning:
        lines += [f"**Reasoning:** {confidence_reasoning}", ""]

    # Alternative Hypotheses
    lines += ["## Alternative Hypotheses", ""]
    if alternative_hypotheses:
        for i, h in enumerate(alternative_hypotheses, 1):
            pct = h.get("confidence_pct", "?")
            hyp = h.get("hypothesis", "")
            reasoning = h.get("reasoning", "")
            lines += [
                f"**{i}. {hyp}** — Confidence: {pct}%",
                f"   > {reasoning}" if reasoning else "",
                "",
            ]
    else:
        lines += ["_No alternative hypotheses generated._", ""]

    # Immediate Actions
    lines += ["## Immediate Actions", ""]
    if immediate_actions:
        for i, a in enumerate(immediate_actions, 1):
            lines.append(f"{i}. {a}")
    else:
        lines.append("_None recommended._")
    lines.append("")

    # Long-term Prevention
    lines += ["## Long-term Prevention", ""]
    if long_term_prevention:
        for i, p in enumerate(long_term_prevention, 1):
            lines.append(f"{i}. {p}")
    else:
        lines.append("_None recommended._")
    lines.append("")

    # Evidence Coverage
    lines += ["## Evidence Coverage", ""]
    used = evidence_coverage.get("evidence_used") or []
    missing = evidence_coverage.get("missing_evidence") or []
    unknowns = evidence_coverage.get("unknowns") or []
    if used:
        lines += ["**Evidence Used:**"]
        lines += [f"- ✓ {e}" for e in used]
        lines.append("")
    if missing:
        lines += ["**Missing Evidence:**"]
        lines += [f"- ✗ {m}" for m in missing]
        lines.append("")
    if unknowns:
        lines += ["**Unknowns:**"]
        lines += [f"- ? {u}" for u in unknowns]
        lines.append("")

    # AI Reasoning Notes
    if ai_reasoning_notes:
        lines += ["## AI Reasoning Notes", "", f"_{ai_reasoning_notes}_", ""]

    # Sources table
    lines += ["## Sources", ""]
    if retrieved_chunks:
        lines.append("| # | Document | Chunk | Similarity |")
        lines.append("|---|----------|-------|------------|")
        for i, s in enumerate(retrieved_chunks, 1):
            fname = s.get("filename") or f"doc_{s.get('document_id')}"
            chunk_num = s.get("chunk_index", "—")
            score = s.get("score")
            score_str = f"{score:.2%}" if score is not None else "—"
            lines.append(f"| {i} | {fname} | {chunk_num} | {score_str} |")
    else:
        lines.append("_No sources._")

    lines += ["", "---", "", "_Generated by OpsLens AI Investigation Platform_"]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# PDF  (uses fpdf2 — pure Python, no system dependencies)
# ---------------------------------------------------------------------------

def render_pdf(investigation: dict) -> bytes:
    """
    Render an investigation report as a PDF using fpdf2.
    Returns raw PDF bytes. No system libraries required.
    """
    from fpdf import FPDF, XPos, YPos

    created_at = investigation.get("created_at")
    if isinstance(created_at, datetime):
        created_at_str = created_at.strftime("%Y-%m-%d %H:%M UTC")
    elif created_at:
        created_at_str = str(created_at)[:19]
    else:
        created_at_str = "—"

    confidence = investigation.get("confidence", 0)
    confidence_level = investigation.get("confidence_level", _confidence_label(confidence))
    root_cause_status = investigation.get("root_cause_status", "Likely")
    executive_summary = investigation.get("executive_summary", "")
    incident_summary = investigation.get("incident_summary") or {}
    observed_evidence = investigation.get("observed_evidence") or []
    root_cause = investigation.get("root_cause", "Not determined")
    alternative_hypotheses = investigation.get("alternative_hypotheses") or []
    immediate_actions = investigation.get("immediate_actions") or []
    long_term_prevention = investigation.get("long_term_prevention") or []
    evidence_coverage = investigation.get("evidence_coverage") or {}
    ai_reasoning_notes = investigation.get("ai_reasoning_notes", "")
    retrieved_chunks = investigation.get("retrieved_chunks") or investigation.get("sources") or []

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_margins(15, 15, 15)

    W = pdf.w - 30  # usable width

    def _safe(text: str) -> str:
        """Replace unsupported unicode chars with ASCII equivalents."""
        return (
            str(text)
            .replace("✓", "[+]")
            .replace("✗", "[-]")
            .replace("→", "->")
            .replace("—", "-")
            .replace("…", "...")
            .replace("\u2019", "'")
            .replace("\u2018", "'")
            .replace("\u201c", '"')
            .replace("\u201d", '"')
            .replace("🟢", "[HIGH]")
            .replace("🟡", "[MED]")
            .replace("🔴", "[LOW]")
            .encode("latin-1", errors="replace")
            .decode("latin-1")
        )

    def heading(text: str, size: int = 12, r: int = 99, g: int = 102, b: int = 241):
        pdf.set_font("Helvetica", "B", size)
        pdf.set_text_color(r, g, b)
        pdf.cell(W, 7, _safe(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(1)

    def subheading(text: str):
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(55, 65, 81)
        pdf.cell(W, 5, _safe(text.upper()), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_draw_color(229, 231, 235)
        pdf.line(15, pdf.get_y(), 15 + W, pdf.get_y())
        pdf.ln(3)
        pdf.set_text_color(0, 0, 0)

    def body(text: str, italic: bool = False):
        pdf.set_font("Helvetica", "I" if italic else "", 9)
        pdf.set_text_color(30, 30, 30)
        pdf.multi_cell(W, 5, _safe(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(1)

    def bullet(text: str, prefix: str = "•", color: tuple = (30, 30, 30)):
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*color)
        pdf.cell(6, 5, _safe(prefix))
        pdf.set_x(pdf.get_x())
        pdf.multi_cell(W - 6, 5, _safe(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(0, 0, 0)

    def numbered(i: int, text: str):
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(99, 102, 241)
        pdf.cell(7, 5, f"{i}.")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(30, 30, 30)
        pdf.multi_cell(W - 7, 5, _safe(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(0.5)

    def badge(text: str, r: int, g: int, b: int):
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(r, g, b)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(0, 5, f"  {_safe(text)}  ", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(0, 0, 0)
        pdf.set_fill_color(255, 255, 255)
        pdf.ln(2)

    def section_gap():
        pdf.ln(4)

    # ── Header ────────────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(17, 24, 39)
    pdf.cell(W, 10, "OpsLens Investigation Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(107, 114, 128)
    pdf.cell(W, 5, "SEE. ANALYZE. RESOLVE.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_draw_color(99, 102, 241)
    pdf.set_line_width(0.8)
    pdf.line(15, pdf.get_y() + 1, 15 + W, pdf.get_y() + 1)
    pdf.ln(6)
    pdf.set_line_width(0.2)
    pdf.set_draw_color(200, 200, 200)

    # ── Meta grid ─────────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(107, 114, 128)
    half = W / 2
    meta = [
        (f"Investigation #{investigation.get('id', '-')}", f"Incident #{investigation.get('incident_id', '-')}"),
        (f"Generated: {created_at_str}", f"Confidence: {confidence}% ({confidence_level})"),
        (f"Status: {root_cause_status}", f"Service: {incident_summary.get('affected_service', '-')}"),
    ]
    for left, right in meta:
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(107, 114, 128)
        pdf.cell(half, 5, _safe(left))
        pdf.cell(half, 5, _safe(right), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)
    section_gap()

    # ── Executive Summary ──────────────────────────────────────────────────────
    if executive_summary:
        subheading("Executive Summary")
        body(executive_summary)
        section_gap()

    # ── Root Cause Analysis ────────────────────────────────────────────────────
    subheading("Root Cause Analysis")
    colors = {"Confirmed": (22, 101, 52), "Likely": (133, 77, 14), "Unable to Determine": (153, 27, 27)}
    rc = colors.get(root_cause_status, (133, 77, 14))
    badge(f"Status: {root_cause_status}", *rc)
    body(root_cause)
    section_gap()

    # ── Confidence ─────────────────────────────────────────────────────────────
    subheading("Confidence")
    conf_colors = {"High": (22, 101, 52), "Medium": (133, 77, 14), "Low": (153, 27, 27)}
    cc = conf_colors.get(confidence_level, (133, 77, 14))
    badge(f"{confidence_level} — {confidence}%", *cc)
    cr = investigation.get("confidence_reasoning", "")
    if cr:
        body(cr, italic=True)
    section_gap()

    # ── Observed Evidence ──────────────────────────────────────────────────────
    if observed_evidence:
        subheading("Observed Evidence")
        for e in observed_evidence:
            bullet(e, prefix="[+]", color=(22, 101, 52))
        section_gap()

    # ── Alternative Hypotheses ─────────────────────────────────────────────────
    if alternative_hypotheses:
        subheading("Alternative Hypotheses")
        for i, h in enumerate(alternative_hypotheses, 1):
            pct = h.get("confidence_pct", "?")
            hyp = h.get("hypothesis", "")
            reasoning = h.get("reasoning", "")
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(30, 30, 30)
            pdf.cell(W - 20, 5, _safe(f"{i}. {hyp}"))
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(99, 102, 241)
            pdf.cell(20, 5, f"{pct}%", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            if reasoning:
                pdf.set_font("Helvetica", "I", 8)
                pdf.set_text_color(107, 114, 128)
                pdf.cell(6)
                pdf.multi_cell(W - 6, 4, _safe(reasoning), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(1)
        section_gap()

    # ── Immediate Actions ──────────────────────────────────────────────────────
    if immediate_actions:
        subheading("Immediate Actions")
        for i, a in enumerate(immediate_actions, 1):
            numbered(i, a)
        section_gap()

    # ── Long-term Prevention ───────────────────────────────────────────────────
    if long_term_prevention:
        subheading("Long-term Prevention")
        for i, p in enumerate(long_term_prevention, 1):
            numbered(i, p)
        section_gap()

    # ── Retrieved Evidence ─────────────────────────────────────────────────────
    if retrieved_chunks:
        subheading("Retrieved Evidence")
        for i, c in enumerate(retrieved_chunks, 1):
            fname = c.get("filename") or f"doc_{c.get('document_id')}"
            chunk_num = c.get("chunk_index", "?")
            score = c.get("score")
            score_str = f"{score:.3f}" if score is not None else "N/A"
            snippet = c.get("snippet", "")

            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(29, 78, 216)
            pdf.cell(W, 5, _safe(f"[{i}] {fname}  |  Chunk #{chunk_num}  |  Similarity: {score_str}"),
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            if snippet:
                pdf.set_font("Helvetica", "I", 8)
                pdf.set_text_color(107, 114, 128)
                pdf.set_x(20)
                pdf.multi_cell(W - 5, 4, _safe(snippet), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(1.5)
        section_gap()

    # ── Evidence Coverage ──────────────────────────────────────────────────────
    used = evidence_coverage.get("evidence_used") or []
    missing = evidence_coverage.get("missing_evidence") or []
    unknowns = evidence_coverage.get("unknowns") or []
    if used or missing or unknowns:
        subheading("Evidence Coverage")
        for e in used:
            bullet(e, prefix="[+]", color=(22, 101, 52))
        for m in missing:
            bullet(m, prefix="[-]", color=(153, 27, 27))
        for u in unknowns:
            bullet(u, prefix="[?]", color=(133, 77, 14))
        section_gap()

    # ── AI Reasoning Notes ─────────────────────────────────────────────────────
    if ai_reasoning_notes:
        subheading("AI Reasoning Notes")
        body(ai_reasoning_notes, italic=True)
        section_gap()

    # ── Footer ─────────────────────────────────────────────────────────────────
    pdf.set_y(-15)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(156, 163, 175)
    pdf.cell(W, 5, _safe(f"Generated by OpsLens AI Investigation Platform  ·  {created_at_str}"),
             align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return bytes(pdf.output())


def _esc(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _confidence_label(confidence: int) -> str:
    if confidence >= 75:
        return "High"
    if confidence >= 50:
        return "Medium"
    return "Low"
