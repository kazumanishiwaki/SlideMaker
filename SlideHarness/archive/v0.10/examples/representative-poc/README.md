# Representative 3-slide PoC (golden sample seed)

Bundled test PPT / manuscriptから、仕様検証用に3種類のページを手動でSlide Plan化したPoCです。

- `OUT-S001`: comparison — source slide 11をADAPTし、既存content regionを**編集可能なPowerPoint table**へ置換
- `OUT-S002`: process — source slide 14をADAPTし、4工程のtext slotsを置換。旧content photoを除去
- `OUT-S003`: four items — source slide 15をADAPTし、4つの主要設定領域へ置換。旧content visualを除去

この3枚は`engine/compose_deck.py`で合成し、`engine/validate_output.py`でblocking 0 / warning 0を確認した基準例です。

目的はデザインの最終正解を固定することではなく、次を回帰テスト可能にすることです。

1. source slideの背景・template chromeが保たれる
2. content-only mutationができる
3. native tableが編集可能なまま生成される
4. multi-column textの実レンダリングが欠落しない
5. real rendered text overflow / overlap QAが機能する
6. 日本語の短すぎる最終行・助詞行頭・括弧孤立・数値/単位分離、Latin複合語分断を検出できる

実際のSol運用では、この手書きPlanを正解としてコピーするのではなく、同じSchemaと品質ゲートを使ってPlanを生成・評価します。
