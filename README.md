# Swarm Exporter

Swarmへ専用ブラウザでログインし、自分のチェックイン全履歴をJSONとCSVへ書き出すコマンドラインツールです。

Foursquareへのデータダウンロード申請を待たず、ログイン中のブラウザ通信からチェックインAPI用tokenを自動検出します。Developer ConsoleのClient IDやClient Secret、tokenの手動コピーは不要です。

## 主な機能

- `ja.swarmapp.com`のログイン画面を専用Chromeで起動
- Foursquare v2 APIで利用できるtokenだけを自動判定
- 最大250件ずつページングし、全チェックインを取得
- 元データを維持した結合JSONを生成
- 日時、場所、住所、座標、カテゴリ、コメントなどをCSVへ変換
- 日本語版Excelでも開きやすいUTF-8 BOM付きCSV
- 一時的な通信失敗とAPI制限に対するリトライ

## 動作環境

- Python 3.10以上
- Google Chrome、Microsoft Edge、Chromiumのいずれか
- Swarmへ接続できるネットワーク環境

ブラウザが見つからない場合は、Playwright用Chromiumをインストールできます。

```sh
python3 -m playwright install chromium
```

## インストール

リポジトリを取得し、そのディレクトリでpipを実行します。

```sh
git clone https://github.com/optinno-ai/Swarm-Exporter.git
cd Swarm-Exporter
python3 -m pip install .
```

仮想環境を使う場合：

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install .
```

開発時はeditable installも利用できます。

```sh
python3 -m pip install -e .
```

## 使い方

インストール後、シェルから起動します。

```sh
swarm-exporter
```

1. 専用ChromeウィンドウでSwarmのログイン画面が開きます。
2. 自分のSwarmアカウントでログインします。
3. 有効なAPI tokenが検出されると、ブラウザが自動的に閉じます。
4. 全履歴の取得状況がターミナルに表示されます。
5. カレントディレクトリの`output`へJSONとCSVが生成されます。

```text
output/
├── swarm_checkins.json
└── swarm_checkins.csv
```

出力先を変更する場合：

```sh
swarm-exporter --output-dir ~/Downloads/swarm-export
```

利用可能なオプションは次のコマンドで確認できます。

```sh
swarm-exporter --help
```

## CSVの列

| 列 | 内容 |
| --- | --- |
| `id` | チェックインID |
| `created_at` | チェックイン先のタイムゾーンを含む日時 |
| `created_at_unix` | UNIX時刻 |
| `timezone_offset_minutes` | UTCからの時差（分） |
| `venue_id` / `venue_name` | 場所のIDと名称 |
| `address` / `city` / `state` / `postal_code` / `country` | 住所情報 |
| `latitude` / `longitude` | 緯度・経度 |
| `category` | 場所の主要カテゴリ |
| `shout` | チェックイン時のコメント |
| `checkin_url` | SwarmのチェックインURL |

JSONにはAPIから取得したチェックインオブジェクトを加工せず、`items`配列へまとめて格納します。

## セキュリティとプライバシー

- ログインIDとパスワードはSwarmへ直接入力され、このツールは読み取りません。
- 監視対象は、このツールが起動した一時ブラウザ内のSwarm/Foursquare通信だけです。
- tokenは画面、ログ、JSON、CSVへ出力しません。
- tokenはエクスポート中だけメモリに保持します。
- 専用ブラウザの一時プロフィールは終了時に削除します。
- 取得したJSONとCSVには位置履歴が含まれます。公開リポジトリや共有フォルダへ置かないでください。

`output/`はGitの追跡対象から除外されています。

## tokenを直接渡す方法

ブラウザを使わず、取得済みtokenで実行する補助スクリプトも同梱しています。

```sh
FOURSQUARE_OAUTH_TOKEN='取得済みtoken' python3 swarm_exporter.py
```

環境変数を設定しない場合、tokenを表示しない対話入力になります。

```sh
python3 swarm_exporter.py
```

## トラブルシューティング

### Chromeが起動しない

Playwright用Chromiumをインストールしてください。

```sh
python3 -m playwright install chromium
```

### ログイン後も処理が始まらない

ログイン後のSwarm画面で、プロフィールやチェックイン履歴が表示されるページへ移動してください。Foursquare API通信が発生するとtokenを検出できます。

### `swarm-exporter: command not found`

pipがインストールしたスクリプトのディレクトリが`PATH`に含まれているか確認してください。仮想環境を使用している場合は、先に有効化します。

```sh
source .venv/bin/activate
```

## 注意事項

本ツールはSwarm/Foursquareの非公式ツールです。サービス側のWeb画面、Cookie、API仕様が変更された場合、動作しなくなる可能性があります。利用者自身のアカウントとデータに対して使用してください。
