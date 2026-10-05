# SlideHarness v2 Repository Structure v0.7.0

## 方針

旧SlideHarness v1は破棄し、今回作り直したCoreを唯一の実装基準にする。
旧版のplanning / layout / render / repair / image logicは再利用しない。

## 新構成

```text
SlideHarness/
├── apps/
│   ├── web/
│   └── app-server/
├── packages/
│   ├── core/
│   ├── content-engine/
│   ├── ppt-analyzer/
│   ├── layout-engine/
│   ├── image-engine/
│   ├── ppt-engine/
│   └── qa-engine/
├── engine/                  # v0.7.0 runtime implementation
├── skill/
├── schemas/
├── examples/
├── tests/
└── docs/
```

## v0.7.0での実装状態

- `engine/` は今回の新実装Coreであり、旧版互換層ではない。
- `apps/` と `packages/` は今後の物理分割先として追加済み。
- 旧版のsrc / plugin / MCP / Web UIには依存しない。

## Source of Truth

```text
source_text / semantic_text / render_text を分離
Deck Plan / Visual Plan / Layout Plan を分離
AI Decision / User Override を分離
APPROVED / LOCKED を分離
上流変更は依存する下流だけ STALE
Output PPTX は Source of Truth にしない
```
