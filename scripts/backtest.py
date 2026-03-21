"""
回測每日市場報告中各頻道的市場情緒命中率。

用法：
    uv run scripts/backtest.py [--window 1] [--start YYYY-MM-DD] [--end YYYY-MM-DD]

輸出：
    reports/backtest_{start}_{end}_T{window}.md
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from statistics import mean
from typing import Optional

import pandas as pd
import yfinance as yf

REPORTS_DIR = Path(__file__).parent.parent / "reports"

# ── 解析用正則 ────────────────────────────────────────────────────────────────

CHANNEL_BLOCK_RE = re.compile(
    r"^### (.+?)\n(.*?)(?=^### |\Z)",
    re.MULTILINE | re.DOTALL,
)
PUBLISH_DATE_RE = re.compile(r"\*\*發布時間\*\*[：:]\s*(\d{4}-\d{2}-\d{2})")
SENTIMENT_LINE_RE = re.compile(r"\*\*市場情緒判斷\*\*[：:]\s*(.+)")
TICKERS_LINE_RE = re.compile(r"\*\*提及(?:的)?標的\*\*[：:]\s*(.+)")
NO_UPDATE_RE = re.compile(r"今日無更新")

# ── Ticker 正規化 ──────────────────────────────────────────────────────────────

US_TICKER_RE = re.compile(r"\b([A-Z]{2,5})\b")
US_STOPWORDS = {
    "AI", "LNG", "ETF", "IPO", "CEO", "CFO", "IRS", "AGI",
    "VIX", "HBM", "GPU", "CPU", "CNN", "NASA", "OPEC",
    "GDP", "CPI", "FED", "IMF", "SPX", "EPS", "GTC",
    "LBO", "RSS", "AMD",  # AMD is valid but often noise; keep for now
}

TW_TICKER_RE = re.compile(r"[（(](\d{4})[）)]")
YEAR_EXCLUSIONS = {str(y) for y in range(2010, 2035)}


def extract_us_tickers(text: str) -> list[str]:
    raw = US_TICKER_RE.findall(text)
    return [t for t in raw if t not in US_STOPWORDS]


def extract_tw_tickers(text: str) -> list[str]:
    raw = TW_TICKER_RE.findall(text)
    return [f"{t}.TW" for t in raw if t not in YEAR_EXCLUSIONS]


def extract_tickers(tickers_line: str) -> list[str]:
    us = extract_us_tickers(tickers_line)
    tw = extract_tw_tickers(tickers_line)
    seen: set[str] = set()
    result: list[str] = []
    for t in us + tw:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


# ── 資料型別 ──────────────────────────────────────────────────────────────────

@dataclass
class ChannelEntry:
    channel_name: str
    report_date: date
    publish_date: Optional[date]
    sentiment: Optional[str]        # "偏多" | "偏空" | "中性"
    tickers: list[str] = field(default_factory=list)


@dataclass
class SentimentResult:
    channel_name: str
    report_date: date
    sentiment: str
    ixic_return: Optional[float]
    hit: Optional[bool]             # None = 中性 or no data


@dataclass
class TickerResult:
    channel_name: str
    report_date: date
    ticker: str
    implied_direction: str
    ticker_return: Optional[float]
    hit: Optional[bool]


# ── 報告解析 ──────────────────────────────────────────────────────────────────

def normalise_sentiment(raw: str) -> Optional[str]:
    if "偏多" in raw:
        return "偏多"
    if "偏空" in raw:
        return "偏空"
    if "中性" in raw:
        return "中性"
    return None


def parse_report(path: Path) -> list[ChannelEntry]:
    """解析單份日報，回傳所有頻道的 ChannelEntry 列表。"""
    try:
        report_date = date.fromisoformat(path.stem)
    except ValueError:
        return []

    text = path.read_text(encoding="utf-8")

    # 找到「各頻道摘要」之後的內容
    section_match = re.search(r"^## 各頻道摘要\s*\n", text, re.MULTILINE)
    if section_match:
        text = text[section_match.end():]

    entries: list[ChannelEntry] = []
    for m in CHANNEL_BLOCK_RE.finditer(text):
        heading = m.group(1).strip()
        body = m.group(2)

        # 頻道名稱：有全形冒號則取冒號前
        channel_name = heading.split("：")[0].strip() if "：" in heading else heading

        # 今日無更新 → 跳過
        if NO_UPDATE_RE.search(body):
            continue

        # 發布時間
        pm = PUBLISH_DATE_RE.search(body)
        publish_date = date.fromisoformat(pm.group(1)) if pm else None

        # 市場情緒
        sm = SENTIMENT_LINE_RE.search(body)
        sentiment = normalise_sentiment(sm.group(1)) if sm else None

        # 提及標的
        tm = TICKERS_LINE_RE.search(body)
        tickers = extract_tickers(tm.group(1)) if tm else []

        entries.append(ChannelEntry(
            channel_name=channel_name,
            report_date=report_date,
            publish_date=publish_date,
            sentiment=sentiment,
            tickers=tickers,
        ))

    return entries


def find_report_files(start: Optional[date], end: Optional[date]) -> list[Path]:
    """找出 reports/ 下符合日期範圍的日報（YYYY-MM-DD.md 格式）。"""
    pattern = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")
    files = sorted(
        p for p in REPORTS_DIR.glob("*.md") if pattern.match(p.name)
    )
    if start:
        files = [p for p in files if date.fromisoformat(p.stem) >= start]
    if end:
        files = [p for p in files if date.fromisoformat(p.stem) <= end]
    return files


# ── 價格資料 ──────────────────────────────────────────────────────────────────

def fetch_prices(
    symbols: list[str],
    start_date: date,
    end_date: date,
    window: int,
) -> dict[str, pd.Series]:
    """批次抓取所有 symbols 的收盤價格。"""
    buffer_end = end_date + timedelta(days=window + 14)
    all_syms = list(dict.fromkeys(["^IXIC"] + symbols))  # ^IXIC 一定在第一位

    print(f"[backtest] 抓取 {len(all_syms)} 個 symbols 的價格資料...", file=sys.stderr)
    try:
        raw = yf.download(
            all_syms,
            start=start_date.isoformat(),
            end=buffer_end.isoformat(),
            auto_adjust=True,
            progress=False,
            threads=True,
        )
    except Exception as e:
        print(f"[backtest] yfinance 批次下載失敗：{e}", file=sys.stderr)
        return {}

    if raw.empty:
        return {}

    # MultiIndex columns when multiple symbols
    if isinstance(raw.columns, pd.MultiIndex):
        if "Close" in raw.columns.get_level_values(0):
            close_df = raw["Close"]
        else:
            return {}
    else:
        # Single symbol
        close_df = raw[["Close"]].rename(columns={"Close": all_syms[0]})

    result: dict[str, pd.Series] = {}
    for sym in all_syms:
        if sym in close_df.columns:
            series = close_df[sym].dropna()
            if not series.empty:
                result[sym] = series
        else:
            print(f"[backtest] 無法取得 {sym} 的資料，跳過", file=sys.stderr)

    return result


def calc_return(series: pd.Series, t0: date, window: int) -> Optional[float]:
    """計算 T+0 到 T+window 個交易日的報酬率（%）。"""
    idx = series.index
    t0_candidates = idx[idx >= pd.Timestamp(t0)]
    if t0_candidates.empty:
        return None
    actual_t0 = t0_candidates[0]
    t0_pos = idx.get_loc(actual_t0)
    t_n_pos = t0_pos + window
    if t_n_pos >= len(idx):
        return None
    p0 = float(series.iloc[t0_pos])
    pn = float(series.iloc[t_n_pos])
    if p0 == 0:
        return None
    return (pn - p0) / p0 * 100


def is_hit(sentiment: str, ret: Optional[float]) -> Optional[bool]:
    """判斷情緒方向是否命中（中性回傳 None）。"""
    if sentiment == "中性" or ret is None:
        return None
    if sentiment == "偏多":
        return ret > 0
    if sentiment == "偏空":
        return ret < 0
    return None


# ── 評估 ──────────────────────────────────────────────────────────────────────

def eval_channel_sentiment(
    entries: list[ChannelEntry],
    prices: dict[str, pd.Series],
    window: int,
) -> list[SentimentResult]:
    results: list[SentimentResult] = []
    ixic = prices.get("^IXIC")
    for e in entries:
        if not e.sentiment:
            continue
        ixic_ret = calc_return(ixic, e.report_date, window) if ixic is not None else None
        hit = is_hit(e.sentiment, ixic_ret)
        results.append(SentimentResult(
            channel_name=e.channel_name,
            report_date=e.report_date,
            sentiment=e.sentiment,
            ixic_return=ixic_ret,
            hit=hit,
        ))
    return results


def eval_ticker_calls(
    entries: list[ChannelEntry],
    prices: dict[str, pd.Series],
    window: int,
) -> list[TickerResult]:
    results: list[TickerResult] = []
    for e in entries:
        if not e.sentiment or e.sentiment == "中性":
            continue
        for ticker in e.tickers:
            series = prices.get(ticker)
            ret = calc_return(series, e.report_date, window) if series is not None else None
            hit = is_hit(e.sentiment, ret)
            results.append(TickerResult(
                channel_name=e.channel_name,
                report_date=e.report_date,
                ticker=ticker,
                implied_direction=e.sentiment,
                ticker_return=ret,
                hit=hit,
            ))
    return results


# ── 報表輸出 ──────────────────────────────────────────────────────────────────

def fmt_pct(v: Optional[float]) -> str:
    if v is None:
        return "—"
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.2f}%"


def hit_str(hit: Optional[bool]) -> str:
    if hit is None:
        return "—"
    return "✓" if hit else "✗"


def render_markdown(
    sent_results: list[SentimentResult],
    ticker_results: list[TickerResult],
    start: date,
    end: date,
    window: int,
) -> str:
    lines: list[str] = []

    date_range = f"{start}" if start == end else f"{start} ～ {end}"
    lines += [
        f"# 回測報告 {date_range}（T+{window}）",
        "",
        f"**評估期間**：{date_range}  ",
        f"**評估窗口**：T+{window}（{window} 個交易日後）  ",
        f"**基準指數**：NASDAQ (^IXIC)  ",
        f"**報告份數**：{len({r.report_date for r in sent_results})}  ",
        "",
        "---",
        "",
    ]

    # ── 各頻道命中率排名 ──────────────────────────────────────────────────────
    lines.append("## 各頻道市場情緒命中率排名")
    lines.append("")

    # 按頻道聚合
    channel_data: dict[str, list[SentimentResult]] = {}
    for r in sent_results:
        channel_data.setdefault(r.channel_name, []).append(r)

    ranked: list[tuple[str, dict]] = []
    for ch, rlist in channel_data.items():
        valid = [r for r in rlist if r.hit is not None]
        hits = [r for r in valid if r.hit]
        bullish = [r for r in valid if r.sentiment == "偏多" and r.ixic_return is not None]
        bearish = [r for r in valid if r.sentiment == "偏空" and r.ixic_return is not None]

        hit_rate = len(hits) / len(valid) if valid else None
        avg_bull = mean(r.ixic_return for r in bullish) if bullish else None  # type: ignore[arg-type]
        avg_bear = mean(r.ixic_return for r in bearish) if bearish else None  # type: ignore[arg-type]

        ranked.append((ch, {
            "sample": len(valid),
            "hit_rate": hit_rate,
            "avg_bull": avg_bull,
            "avg_bear": avg_bear,
            "results": rlist,
        }))

    # 排序：命中率由高到低，無有效樣本排後
    ranked.sort(key=lambda x: (x[1]["hit_rate"] is None, -(x[1]["hit_rate"] or 0)))

    lines.append("| 排名 | 頻道 | 樣本數 | 命中率 | 偏多均報酬 | 偏空均報酬 |")
    lines.append("|------|------|--------|--------|-----------|-----------|")
    for i, (ch, stats) in enumerate(ranked, 1):
        n = stats["sample"]
        hr = f"{stats['hit_rate']:.1%}" if stats["hit_rate"] is not None else "—"
        note = " ⚠️" if n > 0 and n < 3 else ""
        lines.append(
            f"| {i} | {ch} | {n}{note} | {hr} | "
            f"{fmt_pct(stats['avg_bull'])} | {fmt_pct(stats['avg_bear'])} |"
        )

    lines += [
        "",
        "> 中性判斷不計入命中率。⚠️ 表示樣本數不足 3 筆，結果僅供參考。",
        "",
        "---",
        "",
    ]

    # ── 各頻道詳細回測 ─────────────────────────────────────────────────────────
    lines.append("## 各頻道詳細回測")
    lines.append("")

    for ch, stats in ranked:
        lines.append(f"### {ch}")
        valid = [r for r in stats["results"] if r.hit is not None]
        hits = [r for r in valid if r.hit]
        n = stats["sample"]
        hr = f"{stats['hit_rate']:.1%}" if stats["hit_rate"] is not None else "—"
        lines.append(f"- 樣本數：{n}，命中率：{hr}（{len(hits)}/{n}）")
        lines.append("")
        lines.append(f"| 日期 | 情緒 | NASDAQ T+{window} 報酬 | 命中 |")
        lines.append("|------|------|----------------------|------|")
        for r in sorted(stats["results"], key=lambda x: x.report_date):
            lines.append(
                f"| {r.report_date} | {r.sentiment} | "
                f"{fmt_pct(r.ixic_return)} | {hit_str(r.hit)} |"
            )
        lines.append("")

    lines += ["---", ""]

    # ── 個別標的追蹤 ───────────────────────────────────────────────────────────
    if ticker_results:
        lines.append("## 個別標的追蹤")
        lines.append("")
        lines.append(f"| 標的 | 提及頻道 | 隱含方向 | 日期 | T+{window} 報酬 | 命中 |")
        lines.append("|------|----------|---------|------|----------------|------|")
        for r in sorted(ticker_results, key=lambda x: (x.ticker, x.report_date)):
            lines.append(
                f"| {r.ticker} | {r.channel_name} | {r.implied_direction} | "
                f"{r.report_date} | {fmt_pct(r.ticker_return)} | {hit_str(r.hit)} |"
            )
        lines.append("")

        # 聚合
        lines.append("## 個別標的命中率彙整")
        lines.append("")
        ticker_agg: dict[str, list[TickerResult]] = {}
        for r in ticker_results:
            ticker_agg.setdefault(r.ticker, []).append(r)

        ticker_ranked = []
        for tk, rlist in ticker_agg.items():
            valid = [r for r in rlist if r.hit is not None]
            hits = [r for r in valid if r.hit]
            hr = len(hits) / len(valid) if valid else None
            ticker_ranked.append((tk, len(rlist), len(valid), hr))

        ticker_ranked.sort(key=lambda x: (x[3] is None, -(x[3] or 0)))

        lines.append("| 標的 | 總提及次數 | 有效樣本 | 命中率 |")
        lines.append("|------|-----------|---------|--------|")
        for tk, total, valid_n, hr in ticker_ranked:
            hr_str = f"{hr:.1%}" if hr is not None else "—"
            lines.append(f"| {tk} | {total} | {valid_n} | {hr_str} |")

        lines += ["", "---", ""]

    lines.append("*本報告由 `scripts/backtest.py` 自動生成，僅供回測研究，不構成投資建議。*")
    lines.append("")

    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="回測每日市場報告的情緒命中率")
    p.add_argument("--window", type=int, default=1, metavar="N",
                   help="評估窗口：T+N 個交易日（預設 1）")
    p.add_argument("--start", type=str, default=None, metavar="YYYY-MM-DD",
                   help="起始日期（預設：所有可用報告）")
    p.add_argument("--end", type=str, default=None, metavar="YYYY-MM-DD",
                   help="結束日期（預設：同起始日期）")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    start = date.fromisoformat(args.start) if args.start else None
    end = date.fromisoformat(args.end) if args.end else (start if start else None)

    files = find_report_files(start, end)
    if not files:
        print("[backtest] 找不到符合條件的日報檔案。", file=sys.stderr)
        sys.exit(1)

    print(f"[backtest] 找到 {len(files)} 份日報，開始解析...", file=sys.stderr)
    all_entries: list[ChannelEntry] = []
    for f in files:
        entries = parse_report(f)
        all_entries.extend(entries)
        print(f"  {f.name}: {len(entries)} 個頻道", file=sys.stderr)

    if not all_entries:
        print("[backtest] 無法解析任何頻道資料。", file=sys.stderr)
        sys.exit(1)

    # 蒐集所有 symbols
    all_tickers: list[str] = []
    for e in all_entries:
        all_tickers.extend(e.tickers)
    all_tickers = list(dict.fromkeys(all_tickers))

    # 確定日期範圍
    report_dates = [e.report_date for e in all_entries]
    actual_start = min(report_dates)
    actual_end = max(report_dates)

    prices = fetch_prices(all_tickers, actual_start, actual_end, args.window)

    sent_results = eval_channel_sentiment(all_entries, prices, args.window)
    ticker_results = eval_ticker_calls(all_entries, prices, args.window)

    md = render_markdown(
        sent_results, ticker_results,
        actual_start, actual_end, args.window,
    )

    # 輸出檔名
    if actual_start == actual_end:
        out_name = f"backtest_{actual_start}_T{args.window}.md"
    else:
        out_name = f"backtest_{actual_start}_{actual_end}_T{args.window}.md"
    out_path = REPORTS_DIR / out_name
    out_path.write_text(md, encoding="utf-8")
    print(f"[backtest] 回測報告已儲存：{out_path}", file=sys.stderr)
    print(str(out_path))


if __name__ == "__main__":
    main()
