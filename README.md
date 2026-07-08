# 風景構成法研究文献データベース

風景構成法（Landscape Montage Technique）の研究文献データベース。
公開URL: https://sasakireijiyagi.github.io/lmt-database/

単一の `index.html`（外部依存なし）で、検索・種別フィルタ・年代フィルタ・並び替えができる。

## 自動更新

毎月1日（日本時間 09:00）に GitHub Actions が CiNii を再取得し、
`index.html` の文献データを自動更新する（`.github/workflows/update.yml`）。
Actions 画面の **Run workflow** から手動実行も可能。

- **CiNii論文**: `build.py` が CiNii OpenSearch（`q=風景構成法`）を全件取得して自動生成。
  変換ロジックは CiNii一目瞭然（cinii-to-excel-cloud）と同一。CiNii 本体の API を
  直接叩く（Streamlit アプリは経由しない）。
- **書籍・英語文献**: CiNii に出ない／別ソースのものがあるため `manual.json` で手動管理する。
  build 時に CiNii 分とマージされ、**自動処理で書き換わることはない**。
- 件数・内容に変化があった時だけ自動 commit → GitHub Pages が再公開。

### 取得の堅牢化（フリップフロップ防止）

CiNii は同じクエリでも件数が 400↔401 のように揺れる（サーバ側の反映ラグ）。
毎月それに振り回されないよう：

- **ウォームアップ＋リトライ**: 本取得前に1発投げて起こし、各リクエストは失敗時に
  バックオフして最大 5 回リトライ。複数パスで取得して crid で union し取りこぼしを回収。
- **加算マージ（additive）**: 既存の公開データを土台に、今回取得で「更新・新規追加」する。
  今回たまたま欠けた論文を自動削除しない → 揺れで論文を失わない・無駄な更新をしない。
- CiNii 側の障害等で極端に少ない取得だった場合は中止し、既存を守る。

genuinely 削除された論文まで反映したい等でゼロから作り直す場合は、
`REBUILD=1 python3 build.py`（完全取得できた時だけ再構築、取りこぼし時は中止）。

### 書籍・英語文献を追加/修正するには

`manual.json` を編集する。1件は次の形式：

```json
{
  "type": "book",           // "book"（書籍）または "english"（英語文献）
  "authors": "著者名",
  "year": 2020,
  "title": "タイトル",
  "journal": "掲載誌・出版社など",
  "volume": "", "issue": "", "pages": "",
  "publisher": "出版社",
  "url": "https://..."       // リンク（任意）
}
```

編集して push すれば、次回の更新時（または手動実行時）に反映される。

## 手動でローカル更新

```bash
python3 build.py   # CiNii 再取得 → index.html を更新（追加依存なし・標準ライブラリのみ）
```
