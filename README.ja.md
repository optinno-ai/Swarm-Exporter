# Swarm Exporter

[English](README.md) | 日本語

Swarmへ専用ブラウザでログインし、自分のチェックイン全履歴をJSONとCSVへ書き出すコマンドラインツールです。

Foursquareへのデータダウンロード申請を待たず、ログイン中のブラウザ通信からチェックインAPI用tokenを自動検出します。Developer ConsoleのClient IDやClient Secret、tokenの手動コピーは不要です。

## 主な機能

- `ja.swarmapp.com`のログイン画面を専用Chromeで起動
- Foursquare v2 APIで利用できるtokenだけを自動判定
- OSのロケールに合わせて施設名、カテゴリ名などを取得
- 最大250件ずつページングし、全チェックインを取得
- 元データを維持した結合JSONを生成
- 日時、場所、住所、座標、カテゴリ、コメントなどをCSVへ変換
- チェックインに添付された写真を既定でダウンロード
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

GitHubから通常インストールします。この方法ではcloneしたフォルダは残らず、インストール後も`swarm-exporter`コマンドを使用できます。

```sh
python3 -m pip install "git+https://github.com/optinno-ai/Swarm-Exporter.git"
```

仮想環境を使う場合：

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install "git+https://github.com/optinno-ai/Swarm-Exporter.git"
```

ソースコードを編集する開発者だけが、cloneしたフォルダを削除せずにeditable installを使用します。

```sh
git clone https://github.com/optinno-ai/Swarm-Exporter.git
cd Swarm-Exporter
python3 -m pip install -e .
```

editable install後にcloneしたフォルダを削除してしまった場合は、通常インストールで修復できます。

```sh
python3 -m pip install --force-reinstall --no-deps "git+https://github.com/optinno-ai/Swarm-Exporter.git"
```

## 使い方

インストール後、シェルから起動します。

```sh
swarm-exporter
```

1. 専用ChromeウィンドウでSwarmのログイン画面が開きます。
2. 自分のSwarmアカウントでログインします。
3. ログインを検出すると、`https://ja.swarmapp.com/history`を自動で開いてAPI通信を発生させます。
4. 有効なAPI tokenが検出されると、ブラウザが自動的に閉じます。
5. 全履歴と写真の取得状況がターミナルに表示されます。
6. カレントディレクトリの`Swarm-Exporter`へJSON、CSV、写真が生成されます。
   同名のディレクトリがある場合は、`Swarm-Exporter(1)`、`Swarm-Exporter(2)`のように連番が付きます。

```text
Swarm-Exporter/
├── swarm_checkins.json
├── swarm_checkins.csv
└── photos/
    └── CHECKIN_ID_PHOTO_ID.jpg
```

写真をダウンロードせず、JSONとCSVだけを取得する場合：

```sh
swarm-exporter --data-only
```

`photos`ディレクトリは、写真がない場合や`--data-only`の場合も作成されます。

APIの表示言語は、既定ではOSのロケールから自動検出します。明示的に指定する場合：

```sh
swarm-exporter --locale ja
```

指定した言語の名称がFoursquareにない項目は、Foursquareが選択した代替表記になります。

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
| `photo_count` | 添付写真数 |
| `photo_urls` | 元画像URL |
| `photo_files` | ダウンロードした画像の相対パス |
| `checkin_url` | SwarmのチェックインURL |

JSONにはAPIから取得したチェックインオブジェクトを加工せず、`items`配列へまとめて格納します。

## セキュリティとプライバシー

- ログインIDとパスワードはSwarmへ直接入力され、このツールは読み取りません。
- 監視対象は、このツールが起動した一時ブラウザ内のSwarm/Foursquare通信だけです。
- tokenは画面、ログ、JSON、CSVへ出力しません。
- tokenはエクスポート中だけメモリに保持します。
- 専用ブラウザの一時プロフィールは終了時に削除します。
- 取得したJSONとCSVには位置履歴が含まれます。公開リポジトリや共有フォルダへ置かないでください。

既定の出力先である`Swarm-Exporter/`には位置履歴が含まれるため、公開・共有しないでください。

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

通常は`https://ja.swarmapp.com/history`へ自動で移動します。自動遷移しない場合は、このURLを専用ブラウザで直接開いてください。Foursquare API通信が発生するとtokenを検出できます。

### `swarm-exporter: command not found`

pipがインストールしたスクリプトのディレクトリが`PATH`に含まれているか確認してください。仮想環境を使用している場合は、先に有効化します。

```sh
source .venv/bin/activate
```

## 注意事項

本ツールはSwarm/Foursquareの非公式ツールです。サービス側のWeb画面、Cookie、API仕様が変更された場合、動作しなくなる可能性があります。利用者自身のアカウントとデータに対して使用してください。
