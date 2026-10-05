# Reconstruction vs Source-slide Adaptation

Both variants use the same template, source manuscript, deck specification, and
eight Slide Recipes. Both pass content, structural, and actual-render QA.

| Criterion | Reconstruct | Source slides |
| --- | --- | --- |
| Composition | New native elements plus repeated chrome | Exact completed-slide OOXML clone plus slot replacement |
| Template-local ornament | Mostly absent | Preserved and fidelity-tested |
| Mean semantic occupancy | 55.2% | 33.3% plus source ornament/chrome |
| Native table | Yes | Yes |
| Editable process | Yes | Yes |
| Template fidelity QA | Not applicable | PASS |
| Recommended use | Master/layout-led template | Completed-slide-heavy template |

Visual review shows that reconstruction is denser and easier to normalize, but
it collapses the template into generic cards and header chrome. Source-slide
adaptation retains the orange diagonal geometry, asymmetric card composition,
timeline styling, cover, section, and closing treatment. Its lower semantic
occupancy is intentional template whitespace rather than missing content; the
source ornaments are measured separately by fidelity QA.

For this template the recommended result is `source-slides`. Keep
`reconstruct` as a deterministic fallback for recipes with weak source-slide
evidence or templates whose design is primarily expressed by masters/layouts.
