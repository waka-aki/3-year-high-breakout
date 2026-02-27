# 52週高値ブレイクアウトスクリーナー

東証プライム・スタンダード・グロース市場の日本株を対象とした52週高値ブレイクアウトスクリーナー。
ブレイクアウトを検出し、出来高・ボラティリティ指標でスコアリングし、ブレイクアウト後のパフォーマンスを追跡し、HTMLダッシュボードを出力する。

## セットアップ

```bash
python -m venv 52_breakout
source 52_breakout/bin/activate
pip install -r requirements.txt
```

## 実行方法

```bash
source 52_breakout/bin/activate
python src/main.py --update-tickers   # 初回: 銘柄リストDL + 株価取得
python src/main.py                     # 2回目以降: キャッシュされた銘柄を使用
```

## ダッシュボードの閲覧方法

GitHub Actions により毎日 JST 18:00 にスキャンが自動実行され、結果がリポジトリにコミットされます。

ダッシュボードを閲覧するには、リポジトリをローカルに取得してブラウザで開いてください。

```bash
# 初回
git clone <リポジトリURL>
# ブラウザで開く
open output/dashboard.html        # macOS
xdg-open output/dashboard.html   # Linux
start output/dashboard.html      # Windows

# 2回目以降（最新結果を取得）
git pull
```

## 自動実行 (GitHub Actions)

- **スケジュール**: 毎日 JST 18:00 (UTC 09:00)
- **手動実行**: GitHub リポジトリの Actions タブから `workflow_dispatch` で手動実行も可能
- **対象ファイル**: `data/*.csv`, `output/dashboard.html`, `logs/` が自動コミットされる
