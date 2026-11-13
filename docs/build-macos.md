# macOS（Apple Silicon）でデスクトップアプリを作る

`WDF2CSV.app` を Mac 実機でビルドする手順。PyInstaller はクロスコンパイルできないので、Mac 用アプリは Mac の上でしか作れない（Windows では作れない）。

> 状態：試作。この手順と `packaging/build_macos.sh` は Windows 上で書いたもので、**Mac 実機ではまだ一度もビルド・起動していない**。初回の実機ビルドでつまずいたらこの文書を直すこと。
>
> 実機で確かめていない主な点：
> - `.app` のビルド・起動、Gatekeeper の挙動、ダークモードの表示
> - Finder から起動した `.app` での R の検出と同定の実行
> - Finder 起動時は `LANG` などのロケール環境変数が設定されないため、日本語を含むパス（フォルダ名・ファイル名）を Rscript が正しく扱えるか

## 1. 前提

| 項目 | 内容 |
|---|---|
| Mac | Apple Silicon（M1 以降）、macOS 11 Big Sur 以降 |
| Python | **3.12（python.org の macOS 64-bit universal2 インストーラ推奨）**。3.10 以上なら動く想定 |
| Command Line Tools | **必要**。`xcode-select --install` で入れる（Xcode 本体は不要）。PyInstaller は arm64 指定時に universal2 の Python バイナリを `lipo -thin` で切り出すため、`lipo` が要る。`git` も Command Line Tools に含まれる。入っているかは `xcode-select -p` で確認 |
| ディスク | venv とビルドで約 500 MB |

### Python の入手

- **推奨：python.org のインストーラ**  
  https://www.python.org/downloads/macos/ から「macOS 64-bit universal2 installer」（3.12.x）を入れる。Tcl/Tk 8.6 が同梱されていて、そのまま Tkinter が使える。Apple Silicon ではネイティブ（arm64）で動く。  
  入れると `/usr/local/bin/python3.12` ができる。
- **Homebrew の Python を使う場合**  
  Tkinter が別パッケージなので両方入れる：`brew install python@3.12 python-tk@3.12`。  
  Apple Silicon の Homebrew は `/opt/homebrew` にある（`/usr/local` にあるなら Intel 用 Homebrew を Rosetta で使っている。下の「arm64 と x86_64 の混在」参照）。
- **使わないもの**  
  `/usr/bin/python3`（Xcode Command Line Tools 付属）は古い Tk 8.5 で、ウィンドウが崩れたり "The system version of Tk is deprecated" 警告が出る。Anaconda/Miniconda もビルド用には勧めない（動作未確認）。

確認：

```bash
python3.12 -c "import platform, tkinter; print(platform.machine(), tkinter.TkVersion)"
# arm64 8.6  と出れば OK
```

## 2. ビルド（スクリプト）

```bash
git clone https://github.com/moreElf/wdf-openspecy-bridge.git
cd wdf-openspecy-bridge
git checkout feat/macos-app          # マージ後は不要
bash packaging/build_macos.sh
```

`git clone` には Command Line Tools（と private リポジトリへのアクセス権）が要る。git を使わない場合：

1. ブラウザで GitHub にログインし、https://github.com/moreElf/wdf-openspecy-bridge を開く（private リポジトリなのでログインが必要）
2. ブランチを `feat/macos-app` に切り替え（マージ後は `main`）、「Code」→「Download ZIP」
3. 展開してターミナルでそのフォルダに移動し、`bash packaging/build_macos.sh`

（ビルド自体には Command Line Tools がどのみち必要。）

スクリプトがやること（`set -euo pipefail`、途中で失敗したら止まる）：

1. macOS か、Command Line Tools があるか、Python が arm64 ネイティブか、Tk 8.6 以上かを確認
2. リポジトリ内に venv `.venv-macos` を作り（既存の venv が別アーキテクチャなら止まる）、`pip install -e ".[app,dev]"`（システムには何も入れない）
3. `pytest` を実行（`SKIP_TESTS=1` で省略）
4. `pyinstaller packaging/wdf2csv.spec --noconfirm`
5. `lipo -archs` でアーキテクチャ、`codesign --verify` で署名を確認
6. `ditto` で配布用 zip を作成

使う Python を指定する場合：`PYTHON=/opt/homebrew/bin/python3.12 bash packaging/build_macos.sh`

## 3. ビルド（手動）

```bash
python3.12 -m venv .venv-macos
source .venv-macos/bin/activate
pip install --upgrade pip
pip install -e ".[app,dev]"
pytest -q
pyinstaller packaging/wdf2csv.spec --noconfirm
```

## 4. 生成物

| パス | 内容 |
|---|---|
| `dist/WDF2CSV.app` | アプリ本体。ダブルクリックか `open dist/WDF2CSV.app` で起動 |
| `dist/WDF2CSV-macos-arm64.zip` | 配布用（スクリプト使用時のみ） |
| `dist/WDF2CSV/` | `.app` を組み立てる前の中間フォルダ。配布には使わない |

`/Applications` に置きたい場合は `WDF2CSV.app` をドラッグでコピーする。

### spec の macOS 設定（`packaging/wdf2csv.spec`）

- `BUNDLE` で `WDF2CSV.app` を作る。`bundle_identifier="io.github.moreelf.wdf2csv"`、`console=False`（= `--windowed`）。
- **`target_arch` は `arm64`**。`universal2` にしない理由：universal2 は依存する全バイナリが fat binary である必要があるが、numpy は arm64 / x86_64 別々の wheel しか出していないためビルドが失敗する。Intel Mac 向けが必要なら Intel Mac（または Rosetta 上の x86_64 Python）で `WDF2CSV_TARGET_ARCH=x86_64` を付けてビルドし、別ファイルとして配る。
- 署名は ad-hoc のみ（`codesign_identity=None`。PyInstaller が自動で ad-hoc 署名する。Apple Silicon では無署名のバイナリは起動しないため必須）。Developer ID 署名・公証（notarization）はしていない。

## 5. 同定機能（OpenSpecy / R）を使う場合

変換（.wdf → CSV）は R なしで動く。同定は Mac に R と OpenSpecy が入っている場合だけ有効になる（入っていないとチェックボックスが "Identify with OpenSpecy (R not found)" で無効になる）。

1. R を入れる。どちらか：
   - **CRAN の公式インストーラ（推奨）**：https://cran.r-project.org/bin/macosx/ から **arm64 版**の `R-4.x.x-arm64.pkg`。`/Library/Frameworks/R.framework` に入る。
   - Homebrew：`brew install r`（`/opt/homebrew/bin/Rscript`）
2. ターミナルで R を起動し `install.packages("OpenSpecy")`。
3. 初回の同定時に OpenSpecy が参照ライブラリを R のパッケージフォルダへダウンロードする。そのフォルダに書き込めないと失敗するので、上の `install.packages` と同じユーザーで使う。

アプリは Rscript を次の順で探す（`src/wdf_openspecy_bridge/platform_utils.py`）：

1. `PATH` 上の `Rscript`
2. `/Library/Frameworks/R.framework/Resources/bin/Rscript`（CRAN 版）
3. `/opt/homebrew/bin/Rscript`（Homebrew, Apple Silicon）
4. `/usr/local/bin/Rscript`（Homebrew, Intel / CRAN 版のシンボリックリンク）

Finder から起動した `.app` は `PATH` が `/usr/bin:/bin:/usr/sbin:/sbin` だけなので、ターミナルで `Rscript` が通っていても 1 では見つからない。そのため 2〜4 を直接探している。これ以外の場所（conda の R、rig で入れた R 等）は見つからない。

## 6. 初回起動（Gatekeeper）

署名・公証していないので、ダウンロードした zip から展開したアプリは初回に「開発元を確認できない」「壊れている」と止められる。どれか一つで開く：

- **Finder で右クリック（Control+クリック）→「開く」→「開く」**（macOS 14 以前）
- **システム設定 → プライバシーとセキュリティ → 下の方の「"WDF2CSV" は開発元を確認できないため…」の「このまま開く」**（macOS 15 Sequoia 以降はこちらしか出ない）。一度ダブルクリックして止められた後に表示される。
- ターミナルで隔離属性を外す：

  ```bash
  xattr -dr com.apple.quarantine /Applications/WDF2CSV.app
  ```

自分の Mac でビルドしてそのまま起動する場合は quarantine 属性が付かないので、通常この手順は要らない。

## 7. つまずきと対処

| 症状 | 原因 | 対処 |
|---|---|---|
| "DEPRECATION WARNING: The system version of Tk is deprecated" / ウィンドウが真っ黒・崩れる | `/usr/bin/python3`（Tk 8.5）を使っている | python.org の Python 3.12 でビルドし直す |
| `ModuleNotFoundError: No module named '_tkinter'` | Homebrew Python に Tk が入っていない | `brew install python-tk@3.12`（Python のバージョンに合わせる） |
| ダークモードで文字が読みにくい・ログ欄だけ白い | Tk のバージョンによってダークモード対応が不完全 | Tk 8.6.13 以降（python.org 3.12 同梱）を使う。それでも駄目なら spec の `info_plist` に `"NSRequiresAquaSystemAppearance": True` を足してライトモード固定でビルド |
| `xcrun: error: invalid active developer path` / ビルド中に `lipo` が失敗する | Command Line Tools が入っていない（macOS のアップデート後に消えることもある） | `xcode-select --install` |
| `.venv-macos runs as x86_64 but the target is arm64` で止まる / 以前と違う Python に替えたらおかしい | `.venv-macos` が別の Python・別アーキテクチャで作られている | `rm -rf .venv-macos` で消してスクリプトをやり直す |
| 同定が "R not found" のまま | R がアプリの探す場所にない | 5 の場所に入れる。`ls /Library/Frameworks/R.framework/Resources/bin/Rscript` で確認 |
| ターミナルの `wdf2csv-gui` では R が見つかるのに `.app` では見つからない | Finder 起動時は PATH が最小 | 同上（PATH の設定では解決しない） |
| スクリプトが "runs as x86_64 but the target is arm64" で止まる | Rosetta 上の Python / Intel 版 Homebrew（`/usr/local`）の Python | `arch` と `which python3.12` を確認し、python.org 版か `/opt/homebrew` の Python を使う |
| ビルドは通るが起動直後に落ちる（`Killed: 9`） | arm64 バイナリの署名が壊れている | `codesign --force --deep --sign - dist/WDF2CSV.app` で ad-hoc 署名し直す。zip を作り直すときは `ditto` を使う |
| zip で渡したら「壊れている」と出る／起動しない | `zip -r` でシンボリックリンクや署名が壊れた | `ditto -c -k --keepParent dist/WDF2CSV.app WDF2CSV.zip`（または Finder の「圧縮」）。受け取った側は 6 の手順 |
| `universal2` でビルドすると numpy のエラー | numpy に universal2 wheel がない | arm64 のままにする（4 参照） |
| 起動ログを見たい | `.app` はコンソールを出さない | `dist/WDF2CSV.app/Contents/MacOS/WDF2CSV` をターミナルから直接実行するとエラーが表示される |

## 8. 出力ファイルの書き込み先

CSV と同定結果は、出力フォルダを指定しなければ **入力 .wdf と同じフォルダ** に書く。アプリ（`.app` の中）には何も書かない。`.app` は Gatekeeper の App Translocation で読み取り専用の場所から実行されることがあるため、アプリ内に書く設計にはしていない。
