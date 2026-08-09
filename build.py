#!/usr/bin/env python3
"""風景構成法研究文献データベース index.html 更新スクリプト.

CiNii OpenSearch (q=風景構成法) を全件取得し、CiNii一目瞭然
(sasakireijiyagi/cinii-to-excel-cloud) と同じ変換で論文レコードを生成する。
書籍・英語文献 (CiNii に出ない分) は manual.json から読み込んでマージし、
index.html の (1) const DATA = [...] と (2) ヘッダーの件数・最終更新 の
2 箇所"だけ"を差し替える。HTML/CSS/JS の他の部分は一切変更しない。
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode
from urllib.request import urlopen, Request

QUERY = "風景構成法"
BASE = "https://cir.nii.ac.jp/opensearch/articles"
HTML = "index.html"
MANUAL = "manual.json"

# CiNii は初回アクセスが遅い/たまに失敗する。リトライ設定。
RETRIES = 5
BACKOFF = 8          # 秒。失敗ごとに ×(試行回数) で伸ばす
PAGE_PAUSE = 0.7     # ページ取得間の小休止（相手に優しく）
PASSES = 3           # 全件取得の最大パス数（取りこぼし回収用）


def _fetch(start, count=100):
    """CiNii を 1 回叩く。失敗時はバックオフしてリトライ。"""
    url = f"{BASE}?{urlencode({'q': QUERY, 'count': count, 'start': start, 'format': 'json'})}"
    last = None
    for attempt in range(1, RETRIES + 1):
        try:
            req = Request(url, headers={"User-Agent": "lmt-database-updater/1.0"})
            with urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # ネットワーク/タイムアウト/JSON異常すべて
            last = e
            wait = BACKOFF * attempt
            print(f"  [retry] start={start} 試行{attempt}/{RETRIES} 失敗: {e} → {wait}s待機",
                  file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"CiNii 取得失敗（start={start}, {RETRIES}回リトライ後）: {last}")


def _warm_up():
    """本取得前に軽いリクエストを1発送って CiNii を起こす。失敗しても続行。"""
    try:
        url = f"{BASE}?{urlencode({'q': QUERY, 'count': 1, 'start': 1, 'format': 'json'})}"
        req = Request(url, headers={"User-Agent": "lmt-database-updater/1.0"})
        with urlopen(req, timeout=90):
            pass
        print("  [warm-up] CiNii ウォームアップ完了")
    except Exception as e:
        print(f"  [warm-up] ウォームアップ失敗（無視して続行）: {e}", file=sys.stderr)
    time.sleep(3)  # 起き上がる時間を少し与える


def _record_key(r):
    return r["url"] or (r["title"] + r["authors"])


# CiNii が同一文献を複数CRIDで別々に索引しているケース（drop_url -> keep_url）。
# 手動確認済み。ここに無い新規の重複はそのまま残る（要目視チェック）。
DUPLICATE_CRIDS = {
    "https://cir.nii.ac.jp/crid/1390570000439462656": "https://cir.nii.ac.jp/crid/1390007050486043520",  # 佐渡忠洋
    "https://cir.nii.ac.jp/crid/1390001204471698944": "https://cir.nii.ac.jp/crid/1570854177965963520",  # 松井華子
    "https://cir.nii.ac.jp/crid/1570854177965961984": "https://cir.nii.ac.jp/crid/1573668928276403072",  # 角野善宏
    "https://cir.nii.ac.jp/crid/1390001204471703424": "https://cir.nii.ac.jp/crid/1573668928276403072",  # 角野善宏
    "https://cir.nii.ac.jp/crid/1390290700503034880": "https://cir.nii.ac.jp/crid/1572543026666816640",  # 橋本泰子
    "https://cir.nii.ac.jp/crid/1570572700824257024": "https://cir.nii.ac.jp/crid/1571698599858806144",  # 中井久夫（風景構成法その後の発展）
    "https://cir.nii.ac.jp/crid/1573387450017147264": "https://cir.nii.ac.jp/crid/1571698599858806144",  # 中井久夫（同上）
    "https://cir.nii.ac.jp/crid/1571980075487335808": "https://cir.nii.ac.jp/crid/1573668924279446016",  # 中井久夫（精神科治療学）
    "https://cir.nii.ac.jp/crid/1010282256777780503": "https://cir.nii.ac.jp/crid/1010282256777780484",  # 濱野清志ら（スリランカ・カメルーン）
    "https://cir.nii.ac.jp/crid/1010282256777780512": "https://cir.nii.ac.jp/crid/1010282256777780481",  # 濱野清志ら（バリ州）
    "https://cir.nii.ac.jp/crid/1010282256777780507": "https://cir.nii.ac.jp/crid/1010282256777780481",  # 濱野清志ら（同上）
    "https://cir.nii.ac.jp/crid/1572543025086941568": "https://cir.nii.ac.jp/crid/1573668924279443584",  # 山中康裕「事始め」
    "https://cir.nii.ac.jp/crid/1571417124465464960": "https://cir.nii.ac.jp/crid/1573668924279443584",  # 山中康裕「事始め」（表記崩れ）
    "https://cir.nii.ac.jp/crid/1572543025404441216": "https://cir.nii.ac.jp/crid/1572543024372600576",  # 高石恭子「検討」
    "https://cir.nii.ac.jp/crid/1574231874649205760": "https://cir.nii.ac.jp/crid/1572824500063730176",  # 高石恭子「研究」（表記崩れ）
    "https://cir.nii.ac.jp/crid/1573105975040440192": "https://cir.nii.ac.jp/crid/1571980075451025664",  # 皆藤章『風景構成法 その基礎と実践』
    "https://cir.nii.ac.jp/crid/1574231874105877760": "https://cir.nii.ac.jp/crid/1571980075451025664",  # 同上
    "https://cir.nii.ac.jp/crid/1573105974661499648": "https://cir.nii.ac.jp/crid/1571980075451025664",  # 同上（出版社誤表記あり）
    "https://cir.nii.ac.jp/crid/1573950400145169152": "https://cir.nii.ac.jp/crid/1571980075451025664",  # 同上（略記）
    "https://cir.nii.ac.jp/crid/1572824502941087360": "https://cir.nii.ac.jp/crid/1390282679757261312",  # 柳沢和彦ら
    "https://cir.nii.ac.jp/crid/1571698600331485952": "https://cir.nii.ac.jp/crid/1570854174602386304",  # 山中康裕（風景構成法その後の発展）
}


def fetch_cinii():
    """CiNii 論文を全件取得し (records, total, complete) を返す。

    CiNii は同一クエリでもページング取得で稀に1件取りこぼすことがある
    （401→400 のような揺れ）。複数パスで取得して url(crid) で union し、
    取りこぼしを回収する。全件そろえば complete=True、そろわなければ
    complete=False（呼び出し側が加算マージで既存を守る／REBUILDは中止）。"""
    _warm_up()
    best = {}          # key -> record（unionで蓄積、縮まない）
    max_total = 0
    for attempt in range(1, PASSES + 1):
        total = int(_fetch(1, 1).get("opensearch:totalResults", 0))
        if total == 0:
            raise RuntimeError("totalResults=0 — 取得に失敗（CiNii側の異常の可能性）")
        max_total = max(max_total, total)
        start = 1
        while start <= total:
            items = _fetch(start, 100).get("items", [])
            if not items:
                break
            for e in items:
                r = _map(e)
                best[_record_key(r)] = r
            start += 100
            time.sleep(PAGE_PAUSE)
        if len(best) >= max_total:
            break  # 全件そろった
        print(f"  [再取得] pass{attempt}: 収集 {len(best)}/{max_total} — もう一周して回収",
              file=sys.stderr)
        time.sleep(3)

    records = list(best.values())
    complete = len(records) >= max_total
    if not complete:
        print(f"  [警告] CiNii を完全取得できず（{len(records)}/{max_total}）",
              file=sys.stderr)
    return records, max_total, complete


def _map(entry):
    """CiNii一目瞭然 の parse_articles_json と同じフィールド対応。"""
    authors = entry.get("dc:creator", [])
    if isinstance(authors, list):
        authors = "，".join(str(a).replace(" ", "") for a in authors)
    else:
        authors = str(authors).replace(" ", "")
    pubdate = entry.get("prism:publicationDate", "") or ""
    try:
        year = int(pubdate[:4])
    except (ValueError, TypeError):
        year = 0
    spage = entry.get("prism:startingPage", "") or ""
    epage = entry.get("prism:endingPage", "") or ""
    pages = f"{spage}-{epage}" if spage and epage else (spage or epage)
    url = entry.get("@id", "") or ""
    if not url:
        link = entry.get("link", {})
        url = link.get("@id", "") if isinstance(link, dict) else ""
    return {
        "type": "cinii",
        "authors": authors,
        "year": year,
        "title": entry.get("title", "") or "",
        "journal": entry.get("prism:publicationName", "") or "",
        "volume": entry.get("prism:volume", "") or "",
        "issue": entry.get("prism:number", "") or "",
        "pages": pages,
        "publisher": entry.get("dc:publisher", "") or "",
        "url": url,
    }


def load_manual():
    """書籍・英語文献（CiNii以外のソース含む手動管理分）を読む。
    読めない/壊れている/空 の場合は中止する。これらを絶対に失わないため、
    ここで失敗したら index.html には一切触れない。"""
    try:
        manual = json.load(open(MANUAL, encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(f"{MANUAL} を読めない（books/englishを壊さないため中止）: {e}")
    if not isinstance(manual, list) or len(manual) == 0:
        raise RuntimeError(f"{MANUAL} が空/不正（books/englishを壊さないため中止）")
    return manual


def _existing_cinii():
    """現在公開中の index.html に入っている CiNii レコードを返す。"""
    try:
        data = _existing_data(open(HTML, encoding="utf-8").read()) or []
    except Exception:
        return []
    return [d for d in data if d.get("type") == "cinii" and d.get("url") not in DUPLICATE_CRIDS]


def build_data():
    manual = load_manual()  # 先に手動分を確保（取れなければ後段に進まない）
    manual_urls = {d.get("url") for d in manual if d.get("url")}

    fresh, total, complete = fetch_cinii()  # 既に url(crid) で union 済み
    # manual と同一URLの論文は手動分を優先して除外（二重掲載防止）
    fresh = [r for r in fresh if not (r["url"] and r["url"] in manual_urls)]
    # CiNii側の重複索引（既知分）を除外
    fresh = [r for r in fresh if r["url"] not in DUPLICATE_CRIDS]

    if os.environ.get("REBUILD"):
        # メンテ用: 既存を無視して今回取得だけで完全再構築（消えた論文は落ちる）
        if not complete:
            raise RuntimeError(
                f"REBUILD 中止: CiNii を完全取得できず（取りこぼしの疑い）")
        merged = {_record_key(r): r for r in fresh}
    else:
        # 通常: 加算マージ。CiNii の件数は 400↔401 のように揺れるため、
        # 「今回たまたま欠けた論文」を失わない。既存を土台に、今回取得で
        # 上書き（メタデータ更新）＆新規追加する（自動削除はしない）。
        # 既存分にも manual と同一URLが紛れることがある（後から manual に
        # 追加された場合）ので、ここでも除外する（二重掲載防止）。
        merged = {_record_key(r): r for r in _existing_cinii()
                  if not (r.get("url") and r["url"] in manual_urls)}
        for r in fresh:
            merged[_record_key(r)] = r

    cinii = sorted(merged.values(), key=lambda r: (r["year"], r["title"]), reverse=True)
    return cinii + manual, len(cinii), total


def _jp_month(dt):
    return f"{dt.year}年{dt.month}月"


def _existing_data(html):
    m = re.search(r"const DATA = (\[.*?\]);", html, re.S)
    return json.loads(m.group(1)) if m else None


def _norm(data):
    """順序に依存しない比較用の正規化キー（全フィールドを文字列化して安全に比較）。"""
    keys = ("type", "year", "title", "authors", "journal",
            "volume", "issue", "pages", "publisher", "url")
    return sorted(tuple(str(d.get(k, "")) for k in keys) for d in data)


def update_html(data, n_cinii):
    html = open(HTML, encoding="utf-8").read()

    # データ内容（順不同）が既存と同じなら何もしない → 無駄な月次commitを防ぐ
    old = _existing_data(html)
    if old is not None and _norm(old) == _norm(data):
        return None

    n_book = sum(1 for d in data if d["type"] == "book")
    n_eng = sum(1 for d in data if d["type"] == "english")
    total = len(data)
    jst = timezone(timedelta(hours=9))
    ym = _jp_month(datetime.now(jst))

    # (1) DATA 配列
    data_js = json.dumps(data, ensure_ascii=False)
    html, n1 = re.subn(r"const DATA = \[.*?\];",
                       "const DATA = " + data_js + ";", html, count=1, flags=re.S)
    if n1 != 1:
        raise RuntimeError("const DATA = [...] を1箇所置換できなかった")

    # (2) ヘッダーの件数 + 最終更新（データが変わった時だけ進める）
    header = (f"収録 <strong>CiNii論文 {n_cinii}件</strong> ／ "
              f"<strong>書籍 {n_book}件</strong> ／ <strong>英語文献 {n_eng}件</strong>"
              f"　合計 <strong>{total}件</strong>　（最終更新 {ym}）")
    html, n2 = re.subn(
        r"収録 <strong>CiNii論文 \d+件</strong> ／ <strong>書籍 \d+件</strong> ／ "
        r"<strong>英語文献 \d+件</strong>　合計 <strong>\d+件</strong>　（最終更新 [^）]*）",
        header, html, count=1)
    if n2 != 1:
        raise RuntimeError("ヘッダーの件数行を1箇所置換できなかった")

    open(HTML, "w", encoding="utf-8").write(html)
    return n_cinii, n_book, n_eng, total, ym


def main():
    data, n_cinii, total_reported = build_data()
    if n_cinii < 50:
        # 明らかに少なすぎる → CiNii障害とみなし更新中止（既存を守る）
        print(f"[中止] 取得CiNii={n_cinii}件 (report={total_reported}) は異常に少ない", file=sys.stderr)
        sys.exit(1)
    result = update_html(data, n_cinii)
    if result is None:
        print("[変更なし] データに変化なし。index.html は更新しない")
        return
    n_cinii, n_book, n_eng, total, ym = result
    print(f"[更新] CiNii {n_cinii} / 書籍 {n_book} / 英語 {n_eng} / 合計 {total}（最終更新 {ym}）")


if __name__ == "__main__":
    main()
