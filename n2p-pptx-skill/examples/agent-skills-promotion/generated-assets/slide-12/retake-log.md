# Retake Log

## v1 - 2026-05-10

Status: adopted
Initial intent: リポジトリのルールをコピーしてAI依頼へ貼り、必要に応じて追加ルールを渡す手順を視覚化する
Prompt file: prompt-v1.md
Generated file: image-v1.png
Adopted in PPTX: yes

## v2 - 2026-05-10

Status: adopted
Human instruction: PPT上での編集は文字のみでOK。前回のバージョンのイラストらしい作り込みは活かす。縦がきつい場合があるので高さに気をつける。
Reason: v1 は画像内テキストが多く、スライド内で高さも詰まりやすかった。文字なしの横長イラストに再生成し、ラベルはPPTX側に分離した。
Prompt changes:
- 文字なしの横長ワークフローイラストとして再生成
- ラベルのみPPTX側の編集可能テキストとして配置
Generated file: image-v2.png
Adopted in PPTX: yes

## v4 - 2026-05-10

Status: adopted
Human instruction: 影はなくす。傾いた表現（遠近）も禁止。イラストがつくりこまれすぎているのでv1程度にする。
Reason: v2 はイラストとして作り込まれすぎていたため、よりシンプルな図解粒度へ戻した。
Prompt changes:
- シンプルなフラットワークフロー図に変更
- 影、遠近、傾き、3D感、過剰なディテールを禁止
- 文字なしを維持し、ラベルはPPTX側に配置
Generated file: image-v4.png
Adopted in PPTX: yes

## v5 - 2026-05-10

Status: adopted
Human instruction: 黄色がPPTと違う。PPT側の黄色に揃える。
Reason: v4 の黄色がPPT側のアクセントカラーよりオレンジ寄りだったため。
Prompt changes:
- 再生成ではなく、黄色系ピクセルをPPT側の `#E8E800` に機械補正
Generated file: image-v5.png
Adopted in PPTX: yes
