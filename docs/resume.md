# Resume-ready project description

## One-line version

Built a local-first multimodal text-adventure platform that orchestrates an OpenAI-compatible LLM
and ComfyUI through a FastAPI gateway, returning narrative text and GPU-generated scene art in one
chat response.

## Detailed version

- Designed an OpenAI-compatible FastAPI service used by desktop and mobile chat clients.
- Implemented a two-stage LLM pipeline that separates narrative generation from structured visual
  prompt planning, improving alignment between story events and generated scenes.
- Integrated ComfyUI's queue, history, and image APIs with a Core-node SDXL workflow optimized for
  an 8 GB NVIDIA GPU using batch size one and tiled VAE decoding.
- Added command-driven and automatic illustration modes, state persistence, WebP delivery, bearer
  authentication, and private-device access through Tailscale Serve.
- Standardized configuration, tests, linting, CI, security documentation, and reproducible Windows
  setup while keeping model weights and user data outside source control.

## Interview discussion points

- Why text generation and prompt planning are separate calls.
- Why the gateway buffers streaming when one assistant message must include a delayed image.
- How the generation lock prevents overlapping jobs from exhausting limited VRAM.
- How OpenAI compatibility decouples the client from the chosen model provider.
- How localhost binding plus Tailscale reduces exposure compared with public port forwarding.

## Suggested repository topics

`fastapi`, `comfyui`, `sdxl`, `llm`, `text-adventure`, `openai-compatible`, `local-ai`, `tailscale`
