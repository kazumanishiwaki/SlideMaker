# Layout Family v0.9.0 PoC

MIRI Companyテンプレートを利用し、v0.9.0で追加した次のレイアウトを一つの編集可能PPTXとして検証します。

- cover
- section
- timeline
- kpi
- chart
- closing

```bash
python examples/layout-family-v090/build.py
```

出力PPTX・各ページPNG・モンタージュ・`summary.json`を生成し、実レンダリングQAでBlocking / Warningが0であることを確認します。
