# 考選部考古題整併平台

用 `Python` 抓取考選部考畢試題平台，產出：

- `data/exams.raw.json`: 原始來源層
- `data/papers.json`: 正規化後的題庫索引
- `data/review-queue.json`: 待人工確認的異名
- `data/aliases.json`: 人工維護的 alias 規則
- `data/release-assets.json`: GitHub Release 上傳清單
- `site/index.html`: 基本靜態瀏覽頁

## 指令

```bash
python -m app discover
python -m app sync-full
python -m app sync-incremental --years 3
python -m app build-site
```

`sync-incremental --years 3` 代表抓最近 3 個可用年度。

## Mirror URL

若要讓 `papers.json` 帶出鏡像連結，執行同步時請提供 release base URL：

```bash
python -m app sync-full --mirror-base-url "https://github.com/<owner>/<repo>/releases/download/mirror-files"
```

實際 release asset 名稱會把 `storage_key` 的 `/` 轉成 `__`，避免 GitHub release asset 不接受巢狀路徑。

## Alias 規則

`data/aliases.json` 格式：

```json
{
  "rules": [
    {
      "match_type": "exact",
      "raw_pattern": "高等考試_護理師",
      "canonical_id": "nurse",
      "canonical_name": "護理師",
      "year_from": null,
      "year_to": null
    }
  ]
}
```

## 注意

- 主抓取入口使用穩定的 GET 結果頁：`wFrmExamQandASearch.aspx?e=<exam_code>&y=<year_ad>`
- 目前下載型別支援 `Q`、`S`、`M`、`A`、`B`
- 無法安全合併的名稱會保留原始值並進入 review queue

