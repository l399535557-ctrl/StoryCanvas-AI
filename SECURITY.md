# Security policy

## Supported version

Security updates target the latest release on the `main` branch.

## Deployment rules

- Never commit `.env` or API keys.
- Bind the gateway and ComfyUI to localhost by default.
- Use a long, independent `GATEWAY_API_KEY`.
- Use Tailscale Serve for private cross-device access.
- Do not use Tailscale Funnel or public router port forwarding.
- Treat generated image URLs as accessible to anyone inside the trusted network who knows the URL.
- Treat `story_memory.sqlite3` as private local data because it contains extracted story history.
- Keep the memory database outside synchronized/public folders and rely on the repository ignore
  rules before committing.
- Review checkpoint and LoRA licenses before distributing model-derived assets.

## Reporting

Open a private security advisory in the repository rather than a public issue when disclosing a
credential leak, authentication bypass, path traversal, or remote-code-execution risk.
