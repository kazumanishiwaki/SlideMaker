# Layout intent PoC

同じLayout Engineが、原稿とページ役割に応じて異なる余白方針を適用できることを検証する2ページPoCです。

1. `OUT-S001` — `statement` + `intentional_whitespace`
   - 「最短即日」という一つの訴求へ視線を集中
   - 余白を埋めるための写真・アイコン・補足文を追加しない
   - 小さすぎるcontent islandや光学的な偏りは引き続きblocking
2. `OUT-S002` — `grid` + `content_filled`
   - 4項目を2×2で一覧化
   - 3+1の空白象限を作らず、コンテンツキャンバスを広く利用

生成:

```bash
python3 examples/layout-intent-poc/build.py
```

成果物:

- `layout-intent-poc.pptx`
- `statement-intentional-whitespace.png`
- `grid-content-filled.png`
- `statement-layout-plan.json`
- `grid-layout-plan.json`
- `qa.json`
- `decision-trace.jsonl`
- `summary.json`
