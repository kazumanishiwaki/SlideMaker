# Integration Routes

Use direct image generation when available. Treat App Server as an orchestration option for products that need to drive Codex from another UI or service.

## Route 1: Direct gpt-image2 Generation

Preferred route.

Use when Codex has an image generation tool or API access that can choose `gpt-image2`.

Procedure:

1. Build the prompt from `selection-and-style.md`.
2. Request the image with `gpt-image2` when the tool/API supports model selection.
3. Save the returned image as `image-vN.png` or `image-vN.webp`.
4. Keep the exact prompt in `prompt-vN.md`.
5. Copy or export the adopted asset into the web project's public/static asset path when needed.
6. Insert the adopted image into the HTML or component source with stable dimensions and appropriate `alt` text.

If `gpt-image2` is not available in the current runtime, state the limitation and use the closest available image generation path only if the user accepts the substitution.

## Route 2: Codex App Server

Use when a local/product workflow needs to invoke Codex as a service that plans, generates, saves, and inserts HTML page illustrations.

Important constraints:

- App Server embeds Codex into another product; it is not itself an image model endpoint.
- Use it to run the same skill-driven workflow from a client UI or automation layer.
- Verify the current Codex App Server protocol before implementing a client.

Suggested App Server task payload:

```text
Use $n2p-html-illustration on this existing HTML/frontend project. Select only sections where an illustration improves understanding, generate n2p-style images, save intent/prompt/image files under generated-assets, insert adopted images into the HTML/components with editable text kept in HTML, and report generated paths.
```

Stable integration requirements:

- pass the skill as an input item when supported
- set the workspace `cwd` to the website or frontend repository
- stream progress to the client UI
- surface human retake instructions as a new turn or turn steering input
- do not expose unauthenticated non-loopback WebSocket listeners
- keep generated logs/prompts outside the reusable skill directory

## Route 3: Browser-operated ChatGPT Fallback

Use only when the user explicitly asks for browser ChatGPT or no direct generation path exists.

Procedure:

1. Open ChatGPT in the browser.
2. Submit the finalized prompt.
3. Download or otherwise save the generated image into the section asset folder.
4. Record that the image came from browser fallback in `retake-log.md`.
5. Insert the saved local file into the HTML or component source.

Do not use browser fallback silently because it can involve user session state, downloads, and manual UI variability.
