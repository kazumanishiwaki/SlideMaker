# Retake Workflow

Humans decide retakes. The skill should make retakes cheaper and make repeated retake patterns visible over time.

## Retake Log Format

Append each retake to `retake-log.md`:

```markdown
## v2 - YYYY-MM-DD

Status: generated | adopted | rejected
Human instruction: <verbatim instruction>
Reason: <why v1 did not work>
Prompt changes:
- <specific change>
- <specific change>
Generated file: image-v2.png
Adopted in HTML: yes | no
```

Create the first log entry when `image-v1` is generated:

```markdown
# Retake Log

## v1 - YYYY-MM-DD

Status: generated
Initial intent: <one sentence>
Generated file: image-v1.png
Adopted in HTML: yes | no
```

## Versioning

Never overwrite existing images or prompts.

Use:

- `prompt-v1.md`, `image-v1.png`
- `prompt-v2.md`, `image-v2.png`
- `prompt-v3.md`, `image-v3.png`

Only update HTML/CSS references to the adopted version.

## Common Retake Patterns

Convert vague feedback into concrete prompt changes:

| Human feedback | Prompt change |
|---|---|
| もっとシンプルに | reduce object count, remove background elements, keep 1 core metaphor |
| 作り込まれすぎ | reduce detail to a simple diagram-like illustration; remove micro-details and polished infographic density |
| AIっぽさを消して | remove glow, gradients, overly smooth rendering, decorative particles |
| 黄色を減らして | restrict yellow to one small highlight or remove it |
| 黄色が違う | recolor yellow pixels to n2p `#E8E800` |
| 業務フローとして見えるように | use left-to-right process, handoff arrows, clear actor/system groups |
| 人物を消して | replace people with documents, screens, nodes, or abstract blocks |
| 3D感を弱めて | use flat vector-like diagram, front-facing simple shapes |
| 影をなくして | remove all drop shadows, cast shadows, ambient shadows, and ground shadows |
| 傾き・遠近をなくして | use front-facing orthographic objects; no perspective tilt, skew, angled screens, or isometric view |
| 文字なしにして | remove all image text; leave labels to HTML |
| HTMLで編集したい | keep the illustration image, but move labels and explanation to editable HTML text |
| 一枚画像になりすぎ | regenerate a textless/low-text illustration and place HTML labels/copy around it |
| SPで縦がきつい | reduce height, move to a horizontal/compact layout, or simplify the visual |
| 文章と画像の文字が重複 | remove image text and keep the native HTML text |
| もっとn2pらしく | white background, black/gray linework, sparse `#E8E800` accent, less decoration |

## Reducing Future Retakes

After a retake pattern appears 3 times across pages, update `selection-and-style.md` or the base prompt block. The goal is to reduce repeated human corrections, not just log them.

## Human Review Checklist

Ask the reviewer to judge only these points:

- Does the image clarify the section's argument?
- Does it match the calm n2p web tone?
- Is all important text editable HTML?
- Is there too much decoration?
- Does the image fit desktop and mobile layout without crowding?
- Is the `alt` text accurate?

If the answer is unclear, keep the current version and avoid extra retakes.
