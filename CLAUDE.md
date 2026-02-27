# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

回答はすべて日本語でお願い

## プロジェクト概要

東証プライム・スタンダード・グロース市場の日本株を対象とした52週高値ブレイクアウトスクリーナー。ブレイクアウトを検出し、出来高・ボラティリティ指標でスコアリングし、ブレイクアウト後のパフォーマンスを追跡し、HTMLダッシュボードを出力する。

## 環境構築

- Python 3.12.3
- 仮想環境の有効化: `source 52_breakout/bin/activate`
- 依存パッケージのインストール: `pip install -r requirements.txt`

## 実行コマンド

```bash
source 52_breakout/bin/activate
python src/main.py --update-tickers   # 初回: 銘柄リストDL + 株価取得
python src/main.py                     # 2回目以降: キャッシュされた銘柄を使用
```

出力ファイル: `output/dashboard.html`
ログファイル: `logs/run_YYYYMMDD_HHMMSS.log`

## アーキテクチャ

### パイプライン構成

`main.py` が以下の7ステップを順次実行するオーケストレーター:

```
ticker_manager → data_fetcher → breakout_detector → scoring → financials → performance_tracker → renderer
```

1. **ticker_manager** — JPXのXLSファイルから銘柄コードを取得し、yfinance形式（コード+".T"）に変換。`data/tickers.csv`にキャッシュ
2. **data_fetcher** — yfinance経由でOHLCVデータを取得。13ヶ月のローリングウィンドウで増分更新。50銘柄/バッチ、2秒間隔。`data/price_cache.csv`にキャッシュ
3. **breakout_detector** — 終値が252日高値を超えた銘柄を検出（最低20日の履歴が必要）
4. **scoring** — 売買代金変化率、ボラティリティ調整済み出来高比率、連続出来高日数（20日平均比較）を算出
5. **financials** — yfinanceから売上成長率・営業利益率を取得（データ欠損時はN/A）
6. **performance_tracker** — ブレイクアウト後5/30/60/90日のリターンを追跡。120日以内のデータのみ対象。`data/breakout_history.csv`と`data/performance_tracking.csv`に保存
7. **renderer** — Jinja2テンプレート（`templates/dashboard.html.j2`）からHTMLダッシュボードを生成。直近30日分を表示

### キャッシュ戦略

全データファイルは`data/`に保存され、増分更新される:
- `tickers.csv` — 銘柄リスト（`--update-tickers`で再取得）
- `price_cache.csv` — 株価データ（ticker, date でユニーク）
- `breakout_history.csv` — 検出されたブレイクアウト（ticker, date でユニーク）
- `performance_tracking.csv` — ブレイクアウト後リターン

### 主要な定数

| 定数 | 値 | モジュール |
|------|-----|-----------|
| 52週ルックバック | 252営業日 | breakout_detector |
| 出来高ルックバック | 20日 | scoring |
| 最小履歴日数 | 20-25日 | breakout_detector, scoring |
| yfinanceバッチサイズ | 50銘柄 | data_fetcher |
| API待機時間 | 2秒/バッチ | data_fetcher |
| パフォーマンス追跡期間 | 120日 | performance_tracker |
| ダッシュボード表示期間 | 30日 | renderer |

### ダッシュボード（テンプレート）

- Tailwind CSS v2.2.19（CDN）使用
- クライアントサイドJavaScriptによるテーブルソート機能（数値・文字列対応）
- 日本語ロケール対応のソート（`localeCompare`）
- 色分け: 緑=正のリターン、赤=負のリターン、グレー=N/A
