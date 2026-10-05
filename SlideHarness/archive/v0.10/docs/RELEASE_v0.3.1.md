# Release v0.3.1 — Layout Intent / Render Reliability

## 実装内容

- ページ単位の `fill_policy` を実装
  - `preserve_source`
  - `intentional_whitespace`
  - `balanced`
  - `content_filled`
  - `full_bleed` は将来の写真系Layout Family予約値として保持し、現行UI/APIでは選択不可
- `LAYOUT_CANVAS_FILL` を廃止し、`LAYOUT_FIT_TO_INTENT` へ置換
- 意図的な余白と、生成失敗・配置不足による accidental dead space を分離
- ページ役割、Layout Family、`design.md`、ユーザーOverrideから実効方針を決定
- 実効方針、選定理由、confidence、QA結果、再実行範囲をDecision Traceへ重複なく保存
- fill policy変更時は該当ページの `layout / render / qa` とDeck HarmonyだけをSTALE化
- UIに「自動判定／元PPTの余白を維持／余白を活かす／バランスよく配置／情報を大きく展開」を追加
- 意味のないコピー、写真、アイコン、装飾による余白埋めを禁止

## Render / QA安定化

- LibreOffice変換ごとに一時ユーザープロファイルを使用
- App Serverの連続・並行変換時に共有profile lockへ待機しない構造へ変更
- PDF画像化は `pdftocairo` を優先し、`pdftoppm`へフォールバック
- 外部変換プロセスへtimeoutを設定
- ページ画像を数値順で正規化し、10ページ以上の資料でも順番を維持

## 検証結果

- `npm test`: 9 / 9 test groups PASS
- representative 3-slide PoC: blocking 0 / warning 0 / harmony warning 0
- Layout Intent PoC:
  - `statement + intentional_whitespace`: occupied area 0.301 / fit score 0.907 / PASS
  - `grid + content_filled`: occupied area 0.825 / fit score 0.964 / PASS
  - actual-render QA: blocking 0 / warning 0

## 未検証

この実行環境にはCodex CLIがないため、実OpenAI Codex App Server + SolによるライブE2Eのみ未検証。fake App Serverを利用したJSONLプロトコル、streaming、approval処理は自動テスト済み。
