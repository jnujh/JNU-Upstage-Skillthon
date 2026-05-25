from __future__ import annotations
# -*- coding: utf-8 -*-
"""
PDF 검증 리포트 생성 — verify_estimate JSON → 스타일드 HTML → PDF

Playwright(Chromium)로 렌더링하므로 추가 패키지가 필요 없다.

사용법:
    python generate_pdf_report.py verify_result.json
    python generate_pdf_report.py verify_result.json --output report.pdf
"""

import json
import sys
import html
import argparse
from pathlib import Path

from generate_report import _fmt_krw


# ─── CSS ─────────────────────────────────────────────────────────────

CSS = """
@page { size: A4; margin: 0; }

*, *::before, *::after { box-sizing: border-box; }

body {
    font-family: -apple-system, "Apple SD Gothic Neo", "Noto Sans KR",
                 "Malgun Gothic", sans-serif;
    font-size: 11pt;
    line-height: 1.65;
    color: #1a1a2e;
    margin: 0;
    padding: 28mm 18mm 30mm 18mm;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
}

/* ── 헤더 ── */
.report-header {
    border-top: 5px solid #2563eb;
    padding: 20px 0 14px;
    margin-bottom: 22px;
    border-bottom: 1px solid #e5e7eb;
}
.report-header h1 {
    font-size: 20pt;
    font-weight: 700;
    color: #1e3a5f;
    margin: 0 0 4px;
}
.report-header .meta {
    font-size: 9pt;
    color: #6b7280;
}

/* ── 요약 카드 ── */
.summary-cards {
    display: flex;
    gap: 12px;
    margin-bottom: 22px;
}
.card {
    flex: 1;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 14px 16px;
}
.card .label { font-size: 8.5pt; color: #64748b; margin-bottom: 3px; }
.card .value { font-size: 15pt; font-weight: 700; color: #1e293b; }
.card .sub   { font-size: 8.5pt; color: #94a3b8; margin-top: 2px; }

/* ── 종합 판정 ── */
.verdict-box {
    padding: 18px 22px;
    border-radius: 10px;
    margin-bottom: 22px;
}
.verdict-box .verdict-label { font-size: 9pt; color: #64748b; margin-bottom: 4px; }
.verdict-box .verdict-main  { font-size: 16pt; font-weight: 700; margin-bottom: 6px; }
.verdict-box .verdict-desc  { font-size: 10pt; color: #374151; line-height: 1.5; }

.verdict-reasonable    { background: #f0fdf4; border-left: 5px solid #22c55e; }
.verdict-slightly_high { background: #fefce8; border-left: 5px solid #eab308; }
.verdict-high          { background: #fff7ed; border-left: 5px solid #f97316; }
.verdict-insufficient_data { background: #f0f9ff; border-left: 5px solid #3b82f6; }
.verdict-mixed         { background: #fefce8; border-left: 5px solid #eab308; }

/* ── 배지 ── */
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 8.5pt;
    font-weight: 600;
    color: #fff;
    white-space: nowrap;
}
.badge-very_high    { background: #ef4444; }
.badge-high         { background: #f97316; }
.badge-slightly_high { background: #eab308; color: #422006; }
.badge-normal       { background: #22c55e; }
.badge-slightly_low { background: #3b82f6; }
.badge-low          { background: #6366f1; }

/* ── 섹션 제목 ── */
h2 {
    font-size: 13pt;
    font-weight: 700;
    color: #1e3a5f;
    margin: 0 0 10px;
    padding-bottom: 6px;
    border-bottom: 2px solid #e5e7eb;
}

/* ── 테이블 ── */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 0 0 22px;
    font-size: 9.5pt;
}
th {
    background: #1e3a5f;
    color: #fff;
    padding: 9px 10px;
    text-align: left;
    font-weight: 600;
    font-size: 8.5pt;
}
td {
    padding: 7px 10px;
    border-bottom: 1px solid #e5e7eb;
}
tr:nth-child(even) td { background: #f8fafc; }
.price { text-align: right; font-variant-numeric: tabular-nums; }
.center { text-align: center; }
.deviation { text-align: right; font-weight: 600; font-variant-numeric: tabular-nums; }
.dev-pos { color: #dc2626; }
.dev-neg { color: #2563eb; }

/* 행별 판정 배경 */
tr.row-very_high td    { background: #fef2f2 !important; }
tr.row-high td         { background: #fff7ed !important; }
tr.row-slightly_high td { background: #fffbeb !important; }
tr.row-normal td       { background: #f0fdf4 !important; }
tr.row-slightly_low td { background: #eff6ff !important; }
tr.row-low td          { background: #eef2ff !important; }

/* ── 비교불가 항목 ── */
.no-ref-box {
    background: #f0f9ff;
    border: 1px solid #bfdbfe;
    border-radius: 8px;
    padding: 14px 18px;
    margin-bottom: 22px;
}
.no-ref-box .section-note {
    font-size: 8.5pt;
    color: #1e40af;
    margin-bottom: 8px;
}
.no-ref-box ul { margin: 0; padding-left: 18px; }
.no-ref-box li { padding: 3px 0; font-size: 9.5pt; color: #1e3a5f; }

/* ── 웹 검색 보충 ── */
.web-supplement {
    margin-bottom: 22px;
}
.web-supplement table th { background: #0e7490; }

/* ── 제안 ── */
.suggestion-item {
    padding: 10px 14px;
    margin-bottom: 7px;
    background: #fffbeb;
    border-left: 3px solid #f59e0b;
    border-radius: 0 6px 6px 0;
    font-size: 9.5pt;
    line-height: 1.5;
}
.overall-suggestions {
    margin-bottom: 22px;
}
.overall-suggestions li {
    padding: 3px 0;
    font-size: 9.5pt;
    line-height: 1.5;
}

/* ── 면책 조항 ── */
.disclaimer {
    margin-top: 28px;
    padding-top: 14px;
    border-top: 1px solid #d1d5db;
    font-size: 8pt;
    color: #9ca3af;
    line-height: 1.5;
}

/* ── 인쇄 제어 ── */
section { page-break-inside: avoid; }
tr { page-break-inside: avoid; }
table { page-break-inside: auto; }
.verdict-box { page-break-inside: avoid; }
.summary-cards { page-break-inside: avoid; }
"""

LEVEL_KR = {
    "very_high": "매우 높음",
    "high": "높음",
    "slightly_high": "다소 높음",
    "normal": "적정",
    "slightly_low": "다소 낮음",
    "low": "낮음",
}

VERDICT_KR = {
    "reasonable": "적정",
    "slightly_high": "다소 높음",
    "high": "높음",
    "mixed": "항목별 편차 있음",
    "insufficient_data": "데이터 부족",
}

VERDICT_ICON = {
    "reasonable": "✅",
    "slightly_high": "⚠️",
    "high": "🚨",
    "mixed": "⚠️",
    "insufficient_data": "ℹ️",
}


# ─── 헬퍼 ────────────────────────────────────────────────────────────

def _esc(text) -> str:
    return html.escape(str(text)) if text else ""


def _badge(level: str) -> str:
    kr = LEVEL_KR.get(level, level)
    return f'<span class="badge badge-{level}">{_esc(kr)}</span>'


def _dev_class(pct: float) -> str:
    return "dev-pos" if pct > 0 else "dev-neg" if pct < 0 else ""


# ─── 섹션 빌더 ───────────────────────────────────────────────────────

def _build_header(inp: dict, verified_at: str) -> str:
    ts = verified_at[:19].replace("T", " ") if verified_at else ""
    return f"""
    <div class="report-header">
        <h1>자동차 정비 견적서 검증 리포트</h1>
        <div class="meta">생성일시: {_esc(ts)} &nbsp;|&nbsp; 차량: {_esc(inp.get('vehicle_model', ''))}</div>
    </div>"""


def _build_summary_cards(inp: dict, cov: dict) -> str:
    parts = inp.get("estimate_parts_total", 0)
    labor = inp.get("estimate_labor_total", 0)
    sub = f"부품 {_fmt_krw(parts)} / 공임 {_fmt_krw(labor)}" if parts or labor else ""
    return f"""
    <div class="summary-cards">
        <div class="card">
            <div class="label">차량 정보</div>
            <div class="value">{_esc(inp.get('vehicle_model', '-'))}</div>
        </div>
        <div class="card">
            <div class="label">견적 총액</div>
            <div class="value">{_fmt_krw(inp.get('estimate_grand_total', 0))}</div>
            <div class="sub">{_esc(sub)}</div>
        </div>
        <div class="card">
            <div class="label">검증 커버리지</div>
            <div class="value">{cov.get('coverage_pct', 0):.0f}%</div>
            <div class="sub">전체 {cov.get('total_items', 0)}개 중 공임 {cov.get('labor_comparable', 0)}개 + 부품 {cov.get('parts_comparable', 0)}개</div>
        </div>
    </div>"""


def _build_verdict(verdict: dict) -> str:
    level = verdict.get("level", "insufficient_data")
    icon = VERDICT_ICON.get(level, "")
    kr = VERDICT_KR.get(level, level)
    summary = verdict.get("summary_kr", "")
    return f"""
    <div class="verdict-box verdict-{level}">
        <div class="verdict-label">종합 판정</div>
        <div class="verdict-main">{icon} {_esc(kr)}</div>
        <div class="verdict-desc">{_esc(summary)}</div>
    </div>"""


def _build_labor_table(items: list) -> str:
    labor_items = [it for it in items
                   if it.get("labor_comparison") and it["labor_comparison"].get("match_reliable")]
    if not labor_items:
        return ""

    rows = []
    for it in labor_items:
        lc = it["labor_comparison"]
        desc = it.get("raw_description", "")
        if len(desc) > 25:
            desc = desc[:23] + ".."
        level = lc["level"]
        pct = lc["deviation_pct"]
        rows.append(f"""
            <tr class="row-{level}">
                <td>{_esc(desc)}</td>
                <td class="price">{_fmt_krw(lc['estimate_price'])}</td>
                <td class="price">{_fmt_krw(lc['reference_price'])}</td>
                <td class="deviation {_dev_class(pct)}">{pct:+.1f}%</td>
                <td class="center">{_badge(level)}</td>
            </tr>""")

    return f"""
    <section>
        <h2>공임 비교</h2>
        <table>
            <thead>
                <tr>
                    <th>항목</th>
                    <th style="text-align:right">견적 공임</th>
                    <th style="text-align:right">공임나라 기준</th>
                    <th style="text-align:right">편차</th>
                    <th style="text-align:center">판정</th>
                </tr>
            </thead>
            <tbody>{''.join(rows)}</tbody>
        </table>
    </section>"""


def _build_parts_table(items: list) -> str:
    parts_items = [it for it in items
                   if it.get("parts_comparison") and it["parts_comparison"].get("match_reliable")]
    if not parts_items:
        return ""

    rows = []
    for it in parts_items:
        pc = it["parts_comparison"]
        desc = it.get("raw_description", "")
        if len(desc) > 25:
            desc = desc[:23] + ".."
        level = pc["level"]
        pct = pc["deviation_pct"]
        qty = pc.get("quantity", 1)
        rows.append(f"""
            <tr class="row-{level}">
                <td>{_esc(desc)}</td>
                <td class="center">{qty}</td>
                <td class="price">{_fmt_krw(pc['estimate_price'])}</td>
                <td class="price">{_fmt_krw(pc['reference_price'])}</td>
                <td class="deviation {_dev_class(pct)}">{pct:+.1f}%</td>
                <td class="center">{_badge(level)}</td>
            </tr>""")

    return f"""
    <section>
        <h2>부품 비교</h2>
        <table>
            <thead>
                <tr>
                    <th>항목</th>
                    <th style="text-align:center">수량</th>
                    <th style="text-align:right">견적 부품비</th>
                    <th style="text-align:right">모비스 정가</th>
                    <th style="text-align:right">편차</th>
                    <th style="text-align:center">판정</th>
                </tr>
            </thead>
            <tbody>{''.join(rows)}</tbody>
        </table>
    </section>"""


def _build_no_reference(items: list) -> str:
    no_ref = [it for it in items
              if it.get("status") in ("no_reference", "low_confidence", "painting")]
    if not no_ref:
        return ""

    lis = []
    for it in no_ref:
        labor = it.get("estimate_labor", 0)
        parts = it.get("estimate_parts", 0)
        total = it.get("estimate_total", 0)
        if labor > 0 and parts == 0:
            price_str = f"공임 {_fmt_krw(labor)}"
        elif parts > 0 and labor == 0:
            price_str = f"부품 {_fmt_krw(parts)}"
        else:
            price_str = _fmt_krw(total)
        lis.append(f"<li><strong>{_esc(it.get('raw_description', ''))}</strong> ({_esc(price_str)})</li>")

    return f"""
    <section>
        <h2>비교 불가 항목</h2>
        <div class="no-ref-box">
            <div class="section-note">공임나라/모비스에서 직접 비교할 수 없는 항목입니다. 웹 검색으로 시장 참고가를 확인하여 보충합니다.</div>
            <ul>{''.join(lis)}</ul>
        </div>
    </section>"""


def _build_web_supplement(web_supplement: list) -> str:
    if not web_supplement:
        return ""

    rows = []
    for ws in web_supplement:
        est = ws.get("estimate_price", 0)
        mkt = ws.get("market_price", 0)
        if mkt > 0:
            pct = round((est - mkt) / mkt * 100, 1)
            dev_cls = _dev_class(pct)
            pct_str = f"{pct:+.1f}%"
        else:
            dev_cls = ""
            pct_str = "-"
        source = ws.get("source_name", "")
        url = ws.get("source_url", "")
        source_html = f'<a href="{_esc(url)}" style="color:#0e7490;text-decoration:none">{_esc(source)}</a>' if url else _esc(source)
        rows.append(f"""
            <tr>
                <td>{_esc(ws.get('description', ''))}</td>
                <td class="price">{_fmt_krw(est)}</td>
                <td class="price">{_fmt_krw(mkt) if mkt else '-'}</td>
                <td class="deviation {dev_cls}">{pct_str}</td>
                <td>{source_html}</td>
            </tr>""")

    return f"""
    <section class="web-supplement">
        <h2>웹 검색 보충 정보</h2>
        <table>
            <thead>
                <tr>
                    <th>항목</th>
                    <th style="text-align:right">견적 금액</th>
                    <th style="text-align:right">시장 참고가</th>
                    <th style="text-align:right">편차</th>
                    <th>출처</th>
                </tr>
            </thead>
            <tbody>{''.join(rows)}</tbody>
        </table>
    </section>"""


def _build_item_details(items: list) -> str:
    attention = [it for it in items if it.get("suggestion")]
    if not attention:
        return ""

    blocks = []
    for it in attention:
        blocks.append(f'<div class="suggestion-item">{_esc(it["suggestion"])}</div>')

    return f"""
    <section>
        <h2>항목별 상세</h2>
        {''.join(blocks)}
    </section>"""


def _build_suggestions(suggestions: list) -> str:
    if not suggestions:
        return ""

    lis = [f"<li>{_esc(s)}</li>" for s in suggestions]
    return f"""
    <section class="overall-suggestions">
        <h2>종합 제안</h2>
        <ul>{''.join(lis)}</ul>
    </section>"""


def _build_disclaimer() -> str:
    return """
    <div class="disclaimer">
        이 리포트는 공임나라 표준 공임비와 현대모비스 순정 부품가를 기준으로 작성되었습니다.
        실제 정비 비용은 정비소 위치, 차량 상태, 부품 등급(순정/호환/재생)에 따라 달라질 수 있습니다.
        본 리포트는 참고 목적이며, 최종 판단은 전문 정비사와 상의하시기 바랍니다.
    </div>"""


# ─── 메인 빌더 ───────────────────────────────────────────────────────

def build_report_html(verify_result: dict, web_supplement: list | None = None) -> str:
    inp = verify_result["input_summary"]
    cov = verify_result["coverage"]
    verdict = verify_result["overall_verdict"]
    items = verify_result["items"]
    suggestions = verify_result.get("suggestions", [])
    verified_at = verify_result.get("verified_at", "")

    sections = [
        _build_header(inp, verified_at),
        _build_summary_cards(inp, cov),
        _build_verdict(verdict),
        _build_labor_table(items),
        _build_parts_table(items),
        _build_no_reference(items),
        _build_web_supplement(web_supplement or []),
        _build_item_details(items),
        _build_suggestions(suggestions),
        _build_disclaimer(),
    ]

    body = "\n".join(s for s in sections if s)
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<style>{CSS}</style>
</head>
<body>
{body}
</body>
</html>"""


def html_to_pdf(html_content: str, output_path: str) -> str:
    from playwright.sync_api import sync_playwright

    out = Path(output_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(html_content, wait_until="networkidle")
        page.pdf(
            path=str(out),
            format="A4",
            print_background=True,
            margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"},
        )
        browser.close()

    return str(out)


def generate_pdf_report(
    verify_result: dict,
    output_path: str,
    web_supplement: list | None = None,
) -> str:
    html_content = build_report_html(verify_result, web_supplement)
    return html_to_pdf(html_content, output_path)


# ─── CLI ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PDF 검증 리포트 생성")
    parser.add_argument("verify_json", help="verify_estimate 결과 JSON 파일")
    parser.add_argument("--output", "-o", default="", help="출력 PDF 파일 경로")
    parser.add_argument("--supplement", "-s", default="", help="웹 검색 보충 JSON 파일")
    args = parser.parse_args()

    path = Path(args.verify_json)
    if not path.exists():
        print(f"파일을 찾을 수 없습니다: {path}", file=sys.stderr)
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    supplement = None
    if args.supplement:
        sp = Path(args.supplement)
        if sp.exists():
            with open(sp, encoding="utf-8") as f:
                supplement = json.load(f)

    output = args.output or str(path.with_suffix(".pdf"))
    result_path = generate_pdf_report(data, output, supplement)
    print(f"PDF 저장: {result_path}", file=sys.stderr)
