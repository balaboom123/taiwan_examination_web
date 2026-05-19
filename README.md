# 考選部考古題整併平台

用 `Python` 抓取考選部考畢試題平台，先把原始檔下載到本地 `mirror/`，再依 canonical 類別重組成跨年度整併包。

產物：

- `data/exams.raw.json`: 原始來源層
- `data/papers.json`: 正規化後的題庫索引
- `data/bundles.json`: 以 canonical 類別聚合後的整併下載索引
- `data/review-queue.json`: 待人工確認的異名
- `data/sync-failures.json`: 同步或打包時被跳過的失敗項目
- `data/aliases.json`: 人工維護的 alias 規則
- `data/release-assets.json`: GitHub Release 上傳清單
- `bundles/<canonical_id>.zip`: 本地產生的整併下載包
- `site/index.html`: 基本靜態瀏覽頁

## 指令

```bash
python -m app discover
python -m app sync-full
python -m app sync-incremental --years 1
python -m app build-site
```

`sync-incremental --years 1` 代表抓最新 1 個可用年度，並重新產生受影響 canonical 的 zip。排程 workflow 目前每週執行一次。

## Bundle URL

若要讓 `papers.json` 與 `bundles.json` 帶出 GitHub Releases 下載連結，執行同步時請提供 bundle base URL：

```bash
python -m app sync-full --bundle-base-url "https://github.com/<owner>/<repo>/releases/download/moex-bundles"
```

目前公開下載單位是每個 canonical 類別一個 zip，例如：

- `bundles/nurse.zip`
- `bundles/psychologist.zip`

zip 內部會再按年度與官方考試代碼分層，例如：

- `115/115030/高等考試_護理師/0101_基礎醫學/question.pdf`
- `114/114170/專門職業及技術人員高等考試護理師考試/0101_基礎醫學/question.pdf`

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
- GitHub workflow 只會上傳 `bundles/*.zip`，不再把每一份 PDF 當 release asset
- incremental workflow 會先下載現有 release bundles，再只重建受影響的 canonical zip
