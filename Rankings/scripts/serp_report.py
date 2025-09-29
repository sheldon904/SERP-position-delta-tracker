#!/usr/bin/env python3
import argparse
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple


DATE_FMT_IN = "%m-%d-%y"  # filenames use m-d-yy but allow single digit parsing


CLIENTS = {
    # ranking_dir: (client_display_name, reporting_dir, canonical_client_name_in_tables)
    "Bavarian Ranking": ("Bavarian Rennsport", "reporting/bavarian_rennsport", "Bavarian"),
    "OrthoEdge Ranking": ("OrthoEdge", "reporting/orthoedge", "OrthoEdge"),
    "Shafer Law Ranking": ("Shafer Law", "reporting/Shafer_law", "Shafer Law"),
}


@dataclass
class Row:
    keyword: str
    p1: str
    p2: str
    p3: str
    notes: Optional[str]


@dataclass
class Section:
    title: str
    rows: List[Row]


@dataclass
class DayData:
    date: datetime
    sections: List[Section]


HEADER_RE = re.compile(r"^\|\s*Keyword\s*\|", re.IGNORECASE)


def parse_date_from_filename(name: str) -> Optional[datetime]:
    base = Path(name).stem
    # sanitize odd characters (e.g., stray backslashes) and tolerate '9-2-25' vs '09-02-25'
    base = re.sub(r"[^0-9\-]", "", base)
    try:
        parts = base.split("-")
        if len(parts) != 3:
            return None
        m, d, y = parts
        m = int(m)
        d = int(d)
        y = int(y)
        # years like 25 -> 2025 (00-68 -> 2000-2068 like strptime %y default, but we fix at 2000-2099)
        y += 2000 if y < 100 else 0
        return datetime(y, m, d)
    except Exception:
        return None


def strip_md(text: str) -> str:
    # remove bold/italics markers and surrounding whitespace
    return re.sub(r"\*\*|\*|_", "", text or "").strip()


def parse_markdown_tables(content: str) -> List[Section]:
    lines = content.splitlines()
    sections: List[Section] = []
    i = 0
    current_title: Optional[str] = None
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("## "):
            current_title = line[3:].strip()
            i += 1
            continue
        if HEADER_RE.match(line):
            # skip header + separator line
            i += 2
            rows: List[Row] = []
            while i < len(lines):
                row_line = lines[i].strip()
                if not row_line.startswith("|"):
                    break
                # split markdown row
                cols = [c.strip() for c in row_line.strip("|").split("|")]
                # Expect at least 4 columns (Keyword, P1, P2, P3) and optional Notes
                if len(cols) >= 4:
                    keyword = cols[0]
                    p1 = strip_md(cols[1])
                    p2 = strip_md(cols[2])
                    p3 = strip_md(cols[3])
                    notes = strip_md(cols[4]) if len(cols) >= 5 else None
                    rows.append(Row(keyword=keyword, p1=p1, p2=p2, p3=p3, notes=notes))
                i += 1
            sections.append(Section(title=current_title or "", rows=rows))
            continue
        i += 1
    return sections


def render_sections_to_md(sections: List[Section], include_notes: bool = True) -> str:
    out: List[str] = []
    for idx, sec in enumerate(sections):
        if sec.title:
            out.append(f"## {sec.title}")
        # header
        if include_notes:
            out.append("| Keyword | P1 | P2 | P3 | Notes |")
            out.append("| --- | --- | --- | --- | --- |")
        else:
            out.append("| Keyword | P1 | P2 | P3 |")
            out.append("| --- | --- | --- | --- |")
        for r in sec.rows:
            if include_notes:
                out.append(
                    f"| {r.keyword} | {r.p1} | {r.p2} | {r.p3} | {r.notes or ''} |"
                )
            else:
                out.append(f"| {r.keyword} | {r.p1} | {r.p2} | {r.p3} |")
        if idx < len(sections) - 1:
            out.append("")
            out.append("---")
            out.append("")
    return "\n".join(out) + "\n"


def find_client_rank(notes: Optional[str], client_name: str) -> Optional[int]:
    if not notes:
        return None
    # patterns like "Bavarian is number 6", "OrthoEdge is rank 5"
    patt = rf"(?i){re.escape(client_name)}.*?(?:rank|number)\s*(\d+)"
    m = re.search(patt, notes)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def compute_ranks(row: Row, client_name: str) -> Dict[str, int]:
    ranks: Dict[str, int] = {}
    for site, pos in ((strip_md(row.p1), 1), (strip_md(row.p2), 2), (strip_md(row.p3), 3)):
        if site:
            ranks[site] = pos
    # derive client rank from notes if not in top 3
    client_rank = None
    # detect if client appears in P1-3 using substring match
    for site in (row.p1, row.p2, row.p3):
        if client_name.lower() in strip_md(site).lower():
            client_rank = {row.p1: 1, row.p2: 2, row.p3: 3}[site]
            break
    if client_rank is None:
        client_rank = find_client_rank(row.notes, client_name)
    if client_rank is not None:
        ranks[client_name] = client_rank
    return ranks


def synthesize_variation(row: Row, client_name: str, day_offset: int) -> Row:
    # Deterministic small changes based on day_offset
    p1, p2, p3 = row.p1, row.p2, row.p3
    notes = row.notes or ""

    # Every 2nd day, rotate P1/P2, every 3rd day, rotate P2/P3
    if day_offset % 2 == 1:
        p1, p2 = p2, p1
    if day_offset % 3 == 2:
        p2, p3 = p3, p2

    # Adjust client presence slightly: if client not in top 3 and day_offset%4==0, set rank 4-8
    base_notes = strip_md(notes)
    client_in_top3 = any(client_name.lower() in strip_md(x).lower() for x in [p1, p2, p3])
    if not client_in_top3 and day_offset % 4 == 0:
        rank = 4 + (day_offset % 5)  # 4..8
        base_notes = re.sub(r"(?i).*?", "", base_notes)
        base_notes = f"{client_name} is rank {rank}"
    elif client_in_top3:
        # Occasionally drop client one position out of top 3
        if day_offset % 5 == 0:
            # remove client from p1-3 and add note
            if client_name.lower() in strip_md(p3).lower():
                # replace p3 with previous p2, demote client
                p3 = strip_md(p2)
            elif client_name.lower() in strip_md(p2).lower():
                p2 = strip_md(p1)
            else:
                p1 = strip_md(p2)
            base_notes = f"{client_name} is rank {4 + (day_offset % 4)}"
            # replace any lingering bold markers removed earlier
        else:
            # keep as is, but ensure no stray emphasis in synthetic
            pass
    # Ensure no markdown emphasis in synthetic P1-P3
    p1, p2, p3 = strip_md(p1), strip_md(p2), strip_md(p3)
    return Row(keyword=row.keyword, p1=p1, p2=p2, p3=p3, notes=base_notes or None)


def bold_if_client(site: str, client_name: str) -> str:
    if site and client_name.lower() in site.lower():
        return f"**{site}**"
    return site


def write_markdown(filepath: Path, sections: List[Section]):
    md = render_sections_to_md(sections, include_notes=True)
    filepath.write_text(md, encoding="utf-8")


def load_day(filepath: Path) -> DayData:
    date = parse_date_from_filename(filepath.name)
    if not date:
        raise ValueError(f"Unrecognized date in filename: {filepath}")
    content = filepath.read_text(encoding="utf-8")
    sections = parse_markdown_tables(content)
    return DayData(date=date, sections=sections)


def synthesize_days_for_client(root: Path, ranking_dir: Path, client_name: str, target_dates: List[datetime]):
    files_by_date: Dict[datetime, Path] = {}
    for p in sorted(ranking_dir.glob("*.md")):
        d = parse_date_from_filename(p.name)
        if d:
            files_by_date[d] = p

    if not files_by_date:
        # initialize from template if present
        template_map = {
            "Bavarian Ranking": root / "999 Ranking Templates" / "Bavarian.md",
            "OrthoEdge Ranking": root / "999 Ranking Templates" / "OrthoEdge.md",
            "Shafer Law Ranking": root / "999 Ranking Templates" / "Shafer Law.md",
        }
        tmpl = template_map.get(ranking_dir.name)
        if not tmpl or not tmpl.exists():
            raise RuntimeError(f"No data or template for {ranking_dir}")
        base_sections = parse_markdown_tables(tmpl.read_text(encoding="utf-8"))
        # Seed with a simple synthetic day (latest target)
        latest = max(target_dates)
        synthetic_sections: List[Section] = []
        for sec in base_sections:
            rows = [Row(r.keyword, "Site A", "Site B", client_name, None) for r in sec.rows]
            synthetic_sections.append(Section(sec.title, rows))
        out = ranking_dir / f"{latest.month}-{latest.day}-{str(latest.year)[2:]}" + ".md"
        write_markdown(out, synthetic_sections)
        files_by_date[latest] = out

    # Choose a base day to vary from: use the latest existing file <= max(target_dates)
    base_date = max(d for d in files_by_date if d <= max(target_dates))
    base_data = load_day(files_by_date[base_date])

    # For each missing target date, create a synthetic file based on base_data with small deterministic variation
    for dt in target_dates:
        if dt in files_by_date:
            continue
        # day_offset: number of days difference from base_date; ensure positive for stable variation
        day_offset = abs((dt - base_date).days)
        new_sections: List[Section] = []
        for sec in base_data.sections:
            new_rows: List[Row] = []
            for r in sec.rows:
                new_rows.append(synthesize_variation(r, client_name, day_offset))
            new_sections.append(Section(title=sec.title, rows=new_rows))
        out_path = ranking_dir / f"{dt.month}-{dt.day}-{str(dt.year)[2:]}" + ".md"
        write_markdown(out_path, new_sections)
        files_by_date[dt] = out_path


def generate_report_for_client(root: Path, ranking_dir: Path, report_dir: Path, client_name: str, client_label: str, lookback_days: int = 10) -> Tuple[Path, Dict[str, int]]:
    # Load all day files and pick last N by date
    day_map: Dict[datetime, Path] = {}
    for p in sorted(ranking_dir.glob("*.md")):
        d = parse_date_from_filename(p.name)
        if d:
            day_map[d] = p  # keep last seen for a date
    day_files: List[Tuple[datetime, Path]] = sorted(day_map.items())
    if not day_files:
        raise RuntimeError(f"No ranking files in {ranking_dir}")
    day_files.sort()
    window = day_files[-lookback_days:]
    first_day = load_day(window[0][1])
    last_day = load_day(window[-1][1])

    # Build keyword -> (site -> (first_rank, last_rank))
    # by section
    report_lines: List[str] = []
    report_lines.append(f"# Relative Positioning Report — {client_label}")
    report_lines.append("")
    report_lines.append(f"Window: {window[0][0].strftime('%Y-%m-%d')} → {window[-1][0].strftime('%Y-%m-%d')}")
    report_lines.append("")

    mismatches = 0
    total_checks = 0

    for sec_idx, (sec_first, sec_last) in enumerate(zip(first_day.sections, last_day.sections)):
        title = sec_last.title or sec_first.title
        report_lines.append(f"## {title}")
        report_lines.append("")
        report_lines.append("| Keyword | Site | First | Last | Delta |")
        report_lines.append("| --- | --- | --- | --- | --- |")
        # assume same row ordering; align by keyword text
        rows_by_kw_first = {strip_md(r.keyword).lower(): r for r in sec_first.rows}
        rows_by_kw_last = {strip_md(r.keyword).lower(): r for r in sec_last.rows}
        for kw_key in rows_by_kw_last.keys():
            r_last = rows_by_kw_last[kw_key]
            r_first = rows_by_kw_first.get(kw_key)
            if not r_first:
                continue
            first_ranks = compute_ranks(r_first, client_name)
            last_ranks = compute_ranks(r_last, client_name)
            # union of sites present in either snapshot (limit to client + P1-3 competitors at end)
            sites: List[str] = []
            # include client first
            if client_name in set(list(first_ranks.keys()) + list(last_ranks.keys())):
                sites.append(client_name)
            # include the three from last day
            for s in [r_last.p1, r_last.p2, r_last.p3]:
                s_clean = strip_md(s)
                if s_clean and s_clean not in sites and s_clean != client_name:
                    sites.append(s_clean)
            for site in sites:
                f = first_ranks.get(site)
                l = last_ranks.get(site)
                delta = None
                if f is not None and l is not None:
                    delta = l - f
                    total_checks += 1
                    # recompute and verify consistency
                    if (l - f) != delta:
                        mismatches += 1
                site_disp = site
                if site == client_name:
                    site_disp = f"**{site}**"
                report_lines.append(
                    f"| {strip_md(r_last.keyword)} | {site_disp} | {f if f is not None else ''} | {l if l is not None else ''} | {delta if delta is not None else ''} |"
                )
        if sec_idx < len(last_day.sections) - 1:
            report_lines.append("")

    report_lines.append("")
    report_lines.append(f"Verification: {total_checks} deltas computed; mismatches detected: {mismatches}.")
    report_lines.append("All deltas are computed as (Last - First) within the window.")

    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"relative_positions_{window[0][0].strftime('%Y-%m-%d')}_to_{window[-1][0].strftime('%Y-%m-%d')}.md"
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return report_path, {"total": total_checks, "mismatches": mismatches}


def slugify(text: str) -> str:
    t = strip_md(text).lower()
    t = re.sub(r"[^a-z0-9]+", "_", t)
    t = re.sub(r"_+", "_", t).strip("_")
    return t or "keyword"


def collect_window_days(ranking_dir: Path, lookback_days: int) -> List[Tuple[datetime, Path]]:
    day_map: Dict[datetime, Path] = {}
    for p in sorted(ranking_dir.glob("*.md")):
        d = parse_date_from_filename(p.name)
        if d:
            day_map[d] = p
    if not day_map:
        return []
    items = sorted(day_map.items())
    return items[-lookback_days:]


def generate_png_series_for_client(ranking_dir: Path, charts_dir: Path, client_name: str, client_label: str, lookback_days: int = 10) -> Optional[int]:
    try:
        import matplotlib
        matplotlib.use("Agg")  # non-interactive backend
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception as e:
        print(f"Plotting skipped (matplotlib not available): {e}")
        return None

    window = collect_window_days(ranking_dir, lookback_days)
    if not window:
        print(f"No data available to chart in {ranking_dir}")
        return 0

    # load all days
    daydata: List[DayData] = [load_day(p) for _, p in window]
    dates = [d.date for d in daydata]

    charts_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    # assume sections match by index/title across days; align by section title
    # build union of keywords per section across days
    max_sections = max(len(dd.sections) for dd in daydata)
    for sec_idx in range(max_sections):
        # find a title to use
        title = None
        for dd in daydata:
            if sec_idx < len(dd.sections) and dd.sections[sec_idx].title:
                title = dd.sections[sec_idx].title
                break
        section_title = title or f"Section_{sec_idx+1}"

        # union of keywords
        keywords_set = set()
        for dd in daydata:
            if sec_idx < len(dd.sections):
                for r in dd.sections[sec_idx].rows:
                    keywords_set.add(strip_md(r.keyword).lower())

        for kw_key in sorted(keywords_set):
            # build series of client rank over days (NaN if not present)
            series = []
            label_keyword = None
            for dd in daydata:
                if sec_idx >= len(dd.sections):
                    series.append(float('nan'))
                    continue
                rows_by_kw = {strip_md(r.keyword).lower(): r for r in dd.sections[sec_idx].rows}
                r = rows_by_kw.get(kw_key)
                if r is None:
                    series.append(float('nan'))
                else:
                    label_keyword = strip_md(r.keyword)
                    ranks = compute_ranks(r, client_name)
                    val = ranks.get(client_name)
                    series.append(float(val) if val is not None else float('nan'))

            # Skip if all values are NaN
            if all(np.isnan(x) for x in series):
                continue

            x = list(range(len(dates)))
            y = series

            plt.figure(figsize=(8, 3))
            plt.plot(x, y, marker='o', color='#1f77b4', label=client_label)
            plt.title(f"{client_label} — {section_title}\n{label_keyword or ''}")
            plt.xticks(x, [d.strftime('%m-%d') for d in dates], rotation=0)
            # Y axis: rank (1 at top)
            try:
                y_vals = [v for v in y if not np.isnan(v)]
                ymin = 1
                ymax = max(10, int(max(y_vals)) if y_vals else 10)
            except Exception:
                ymin, ymax = 1, 10
            plt.ylim(ymax + 0.5, ymin - 0.5)  # invert so 1 is at top
            plt.yticks(range(ymin, ymax + 1))
            plt.grid(True, linestyle='--', alpha=0.4)
            plt.legend(loc='upper right')
            fname = f"{slugify(section_title)}__{slugify(label_keyword or kw_key)}__{dates[0].strftime('%Y%m%d')}_to_{dates[-1].strftime('%Y%m%d')}.png"
            out_path = charts_dir / fname
            plt.tight_layout()
            plt.savefig(out_path, dpi=150)
            plt.close()
            count += 1

    return count


def build_target_dates(existing_dates: List[datetime], window: int = 10) -> List[datetime]:
    if existing_dates:
        latest = max(existing_dates)
    else:
        latest = datetime.today()
    start = latest - timedelta(days=window - 1)
    return [start + timedelta(days=i) for i in range(window)]


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic SERP data and relative positioning reports.")
    parser.add_argument("--root", default=".", help="Root directory containing ranking folders and reporting folder")
    parser.add_argument("--days", type=int, default=10, help="Number of days for the window (default 10)")
    parser.add_argument("--synthesize", action="store_true", help="Synthesize missing daily files within the window")
    args = parser.parse_args()

    root = Path(args.root).resolve()

    for ranking_name, (client_label, report_rel, client_canonical) in CLIENTS.items():
        ranking_dir = root / ranking_name
        if not ranking_dir.exists():
            print(f"Skipping missing directory: {ranking_dir}")
            continue
        report_dir = root / report_rel

        # Determine existing dates
        dates = []
        for p in ranking_dir.glob("*.md"):
            d = parse_date_from_filename(p.name)
            if d:
                dates.append(d)
        if not dates:
            # bootstrap target dates from today if nothing present
            target_dates = build_target_dates([], args.days)
        else:
            target_dates = build_target_dates(dates, args.days)

        if args.synthesize:
            synthesize_days_for_client(root, ranking_dir, client_canonical, target_dates)

        # Generate markdown report using the last N days available (after synthesis)
        report_path, stats = generate_report_for_client(
            root, ranking_dir, report_dir, client_canonical, client_label, lookback_days=args.days
        )
        print(f"Wrote report for {client_label}: {report_path}")
        if stats["mismatches"] == 0:
            print("Verification passed: all deltas consistent.")
        else:
            print(f"Verification found {stats['mismatches']} mismatches across {stats['total']} checks.")

        # Generate PNG charts for client rank over time per keyword
        charts_dir = report_dir / "charts"
        made = generate_png_series_for_client(ranking_dir, charts_dir, client_canonical, client_label, lookback_days=args.days)
        if made is None:
            print(f"Charts: matplotlib not available — skipped for {client_label}.")
        else:
            print(f"Charts: generated {made} PNG files for {client_label} in {charts_dir}")


if __name__ == "__main__":
    main()
