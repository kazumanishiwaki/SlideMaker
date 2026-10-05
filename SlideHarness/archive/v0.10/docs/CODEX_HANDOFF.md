# Codex実機への引き継ぎ — v0.6.0

## 基準状態

本リポジトリは仕様書だけではなく、外部認証なしで次が動作するPoCである。

- Local browser UI
- Codex App Server stdio client
- fake Codex processによるprotocol回帰テスト
- Source of Truth / Decision / Override / STALE / LOCK
- PPT / DOCX deterministic analysis
- Design Continuity / Component Catalog
- editable source-slide clone
- native table / chart
- Layout Engine 8 family
- local/manual image selection / crop / grading
- source Picture in-place replacement
- actual-render QA / Pixel Diff
- Image Harmony / Deck Image Coherence
- Final Export Gate

公式Golden Sample:

- `examples/representative-poc/`
- `examples/layout-intent-poc/`
- `examples/image-harmony-poc/`
- `examples/photo-layout-poc/`

## 初回セットアップ

```bash
python3 -m pip install -r requirements.txt
cp .env.example .env
./scripts/doctor.sh
npm test
npm run test:poc
npm run demo:layout-intent
npm run demo:image-harmony
npm run demo:photo-layout
npm start
```

ブラウザ:

```text
http://127.0.0.1:4317
```

## v0.6 Layout Engine

実行可能family:

```text
grid
process
statement
two_column
photo_text
full_bleed
comparison_matrix
relationship
```

重要ルール:

- モデルは絶対座標を出さない
- family / semantic content / density / fill policy / visual priority / source lineageまでを決める
- geometryは`engine/layout_engine.py`が計算する
- `two_column`の短い本文はcompact content clusterとして光学的に中央配置する
- `photo_text / full_bleed`は画像選定前にprimary visual slotを計画する
- `comparison_matrix`はnative PowerPoint table
- `relationship`はnative nodes / connectors
- `full_bleed` visualはtemplate chromeより背面

## Image Recipe

Recipe targetは次のいずれかを持つ。

```yaml
target:
  source_object_id: SRC-S004-O004
```

または、

```yaml
target:
  layout_slot_id: primary_visual
  bbox: {x, y, w, h}
  aspect_ratio: 1.5
  requested_negative_space: right
```

元Pictureを再利用できる場合は両方を持てる。

slot geometry / aspect / source object / negative-space intentが変わった場合、旧画像を黙って再利用しない。Recipe selectionを無効化し、`image / render / qa / deck_harmony`だけをSTALEにする。

## Renderer / QA safety

- LibreOffice変換ごとに独立user profile
- timeout時はprocess groupを終了
- Popplerにもtimeout
- mutation mask外Pixel DiffはNumPyベクトル化
- NumPyなしの場合のみscalar fallback
- Pixel Diff失敗を、根拠なくmask拡大して回避しない

## Hard invariants

- `inputs/`を変更しない
- output PPTXを上流へ戻さない
- `source_text / semantic_text / render_text`を混ぜない
- User Overrideを勝手に解除しない
- LOCKED要素を変更しない
- STALEのままcomposeしない
- template chromeをreplacement contentとして扱わない
- 余白を埋めるだけの画像・コピー・装飾を追加しない
- source Picture lineageを失ったのに「元PPTを流用」と表示しない
- unsupported layoutを完成したふりにしない
- mock imageをFinal Exportへ通さない
- adapter実装済みをライブ成功済みと報告しない

## ライブ接続は最終工程

ユーザー方針により、以下は最後にまとめて実施する。

- 実Codex CLI + App Server + Sol
- 実OpenAI画像生成

現時点ではfake App Serverとlocal/manual画像で、状態遷移・compose・actual-render QA・Final Export Gateを先に検証する。

最終ライブE2E手順は`docs/NEXT_IMPLEMENTATION.md`を参照する。
