# Retake Log

## v1 - 2026-05-10

Status: adopted
Initial intent: 速いAIモックがそのままでは提案価値にならず、案件理解と意図の追加が必要であることを視覚化する
Prompt file: prompt-v1.md
Generated file: image-v1.png
Adopted in PPTX: yes

## v2 - 2026-05-10

Status: adopted
Human instruction: PPT上での編集は文字のみでOK。前回のバージョンのイラストらしい作り込みは活かす。PPTの文章を優先して、画像は文字ではなく画で説明する。
Reason: v1 は画像内テキストと説明量が多く、PPTX上で編集しにくかった。図形までPPTXで分解するとイラストの作り込みが失われるため、文字なしの作り込んだ画像に再生成した。
Prompt changes:
- 文字なしの作り込んだイラストとして再生成
- ラベルのみPPTX側の編集可能テキストとして配置
Generated file: image-v2.png
Adopted in PPTX: yes

## v4 - 2026-05-10

Status: adopted
Human instruction: 影はなくす。傾いた表現（遠近）も禁止。イラストがつくりこまれすぎているのでv1程度にする。
Reason: v2/v3 は作り込みや立体感が強く、影や遠近に見える表現も残ったため。
Prompt changes:
- シンプルなフラット図解に変更
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
