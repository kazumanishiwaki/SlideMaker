# Retake Log

## v1 - 2026-05-10

Status: adopted
Initial intent: 曖昧な感覚指示を具体的な制作ルールへ変換するとAI依頼とレビュー観点が揃うことを視覚化する
Prompt file: prompt-v1.md
Generated file: image-v1.png
Adopted in PPTX: yes

## v2 - 2026-05-10

Status: adopted
Human instruction: PPT上での編集は文字のみでOK。前回のバージョンのイラストらしい作り込みは活かす。PPTの文章を優先して、画像は文字ではなく画で説明する。
Reason: v1 は画像内テキストが多く、ラベルやルール文をPPTX上で編集できなかった。図形まで分解せず、文字なしの作り込んだ画像に再生成した。
Prompt changes:
- 文字なしの作り込んだイラストとして再生成
- ラベルのみPPTX側の編集可能テキストとして配置
Generated file: image-v2.png
Adopted in PPTX: yes

## v4 - 2026-05-10

Status: adopted
Human instruction: 影はなくす。傾いた表現（遠近）も禁止。イラストがつくりこまれすぎているのでv1程度にする。
Reason: v2/v3 は図解として強く、黄色面積や作り込みが多かったため。
Prompt changes:
- シンプルなフラット図解に変更
- 影、遠近、傾き、3D感、過剰なディテールを禁止
- 黄色アクセントを小さく制限
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
