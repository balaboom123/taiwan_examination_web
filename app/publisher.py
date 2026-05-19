from __future__ import annotations

import json
from pathlib import Path

from app.models import AliasRule, NormalizedCatalog, NormalizedPaper, SourceExamPage, to_plain_data


def write_data_files(data_dir: Path, raw_pages: list[SourceExamPage], normalized: NormalizedCatalog, aliases: list[AliasRule]) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "exams.raw.json").write_text(json.dumps(to_plain_data(raw_pages), ensure_ascii=False, indent=2), encoding="utf-8")
    (data_dir / "papers.json").write_text(json.dumps(to_plain_data(normalized.papers), ensure_ascii=False, indent=2), encoding="utf-8")
    (data_dir / "review-queue.json").write_text(
        json.dumps(to_plain_data(normalized.review_queue), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (data_dir / "aliases.json").write_text(json.dumps({"rules": to_plain_data(aliases)}, ensure_ascii=False, indent=2), encoding="utf-8")
    (data_dir / "release-assets.json").write_text(
        json.dumps(_collect_release_assets(raw_pages), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _collect_release_assets(raw_pages: list[SourceExamPage]) -> list[dict[str, str]]:
    assets: list[dict[str, str]] = []
    for page in raw_pages:
        for attachment in page.attachments:
            if attachment.storage_key:
                assets.append({"storage_key": attachment.storage_key, "asset_name": attachment.asset_name or attachment.storage_key.replace("/", "__")})
        for paper in page.papers:
            for file_meta in paper.mirror_files.values():
                storage_key = file_meta.get("storage_key")
                if storage_key:
                    assets.append({"storage_key": storage_key, "asset_name": file_meta.get("asset_name", storage_key.replace("/", "__"))})
    deduped = {(asset["storage_key"], asset["asset_name"]): asset for asset in assets}
    return list(deduped.values())


def _group_options(papers: list[NormalizedPaper]) -> tuple[list[str], list[int]]:
    names = sorted({paper.canonical_name for paper in papers})
    years = sorted({paper.year_roc for paper in papers}, reverse=True)
    return names, years


def build_site(site_dir: Path, normalized: NormalizedCatalog) -> None:
    site_dir.mkdir(parents=True, exist_ok=True)
    papers_json = json.dumps(to_plain_data(normalized.papers), ensure_ascii=False)
    canonical_names, years = _group_options(normalized.papers)
    name_options = "".join(f'<option value="{name}">{name}</option>' for name in canonical_names)
    year_options = "".join(f'<option value="{year}">{year}</option>' for year in years)
    html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>考選部考古題鏡像</title>
  <style>
    :root {{ color-scheme: light; --bg: #f2ede4; --card: #fffdf8; --ink: #202020; --accent: #0f766e; --line: #d9d2c5; }}
    body {{ margin: 0; font-family: "Noto Sans TC", "Microsoft JhengHei", sans-serif; background: radial-gradient(circle at top, #fff8e8, var(--bg)); color: var(--ink); }}
    main {{ max-width: 1100px; margin: 0 auto; padding: 32px 20px 80px; }}
    h1 {{ margin-bottom: 8px; font-size: 2rem; }}
    p {{ margin-top: 0; color: #555; }}
    .controls {{ display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); margin: 24px 0; }}
    select {{ width: 100%; padding: 10px 12px; border-radius: 10px; border: 1px solid var(--line); background: white; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--card); border-radius: 16px; overflow: hidden; box-shadow: 0 14px 40px rgba(32,32,32,0.08); }}
    th, td {{ text-align: left; padding: 12px 14px; border-bottom: 1px solid var(--line); vertical-align: top; }}
    th {{ background: #f4efe4; font-weight: 700; }}
    a {{ color: var(--accent); }}
    .muted {{ color: #666; font-size: 0.9rem; }}
  </style>
</head>
<body>
  <main>
    <h1>考選部考古題鏡像</h1>
    <p>先以結構化索引和基本瀏覽為主，保留原始名稱並提供跨年 canonical 聚合。</p>
    <div class="controls">
      <label>類別<select id="canonicalFilter"><option value="">全部</option>{name_options}</select></label>
      <label>年度<select id="yearFilter"><option value="">全部</option>{year_options}</select></label>
    </div>
    <table>
      <thead>
        <tr>
          <th>Canonical</th>
          <th>年度</th>
          <th>科目</th>
          <th>原始類別</th>
          <th>鏡像</th>
          <th>官方來源</th>
        </tr>
      </thead>
      <tbody id="rows"></tbody>
    </table>
  </main>
  <script>
    const papers = {papers_json};
    const rows = document.getElementById('rows');
    const canonicalFilter = document.getElementById('canonicalFilter');
    const yearFilter = document.getElementById('yearFilter');
    function render() {{
      const canonical = canonicalFilter.value;
      const year = yearFilter.value;
      const filtered = papers.filter((paper) => (!canonical || paper.canonical_name === canonical) && (!year || String(paper.year_roc) === year));
      rows.innerHTML = filtered.map((paper) => `
        <tr>
          <td><strong>${{paper.canonical_name}}</strong><div class="muted">${{paper.canonical_id}}</div></td>
          <td>${{paper.year_roc}}</td>
          <td>${{paper.subject_name_raw}}<div class="muted">${{paper.file_type}}</div></td>
          <td>${{paper.category_raw || paper.exam_name_raw}}</td>
          <td>${{paper.download_url_mirror ? `<a href="${{paper.download_url_mirror}}">鏡像檔案</a>` : '<span class="muted">未設定</span>'}}</td>
          <td><a href="${{paper.download_url_source}}">官方連結</a></td>
        </tr>
      `).join('');
    }}
    canonicalFilter.addEventListener('change', render);
    yearFilter.addEventListener('change', render);
    render();
  </script>
</body>
</html>
"""
    (site_dir / "index.html").write_text(html, encoding="utf-8")
