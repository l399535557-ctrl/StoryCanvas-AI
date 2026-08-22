# Windows deployment

## 1. Prepare ComfyUI

Use the official Windows Portable NVIDIA build in an SSD path without spaces, for example:

```text
D:\AI\ComfyUI_windows_portable
```

Place one licensed SDXL-compatible checkpoint in:

```text
ComfyUI\models\checkpoints
```

Start ComfyUI on localhost:

```bat
python_embeded\python.exe -s ComfyUI\main.py --windows-standalone-build --listen 127.0.0.1 --port 8188 --preview-method none
```

Verify `http://127.0.0.1:8188/system_stats` before starting StoryCanvas.

### Optional face refinement

The default workflow needs no custom nodes. To enable the optional detected-face refinement path,
install [ComfyUI Impact Pack](https://github.com/ltdrdata/ComfyUI-Impact-Pack) and
[Impact Subpack](https://github.com/ltdrdata/ComfyUI-Impact-Subpack), then place a compatible face
detector such as `face_yolov8m.pt` in:

```text
ComfyUI\models\ultralytics\bbox\face_yolov8m.pt
```

Restart ComfyUI and set `FACE_DETAILER_ENABLED=true`. The example configuration uses one
low-denoise pass and conservative crop settings for 8 GB GPUs. Keep the option disabled if the
extensions are not installed.

## 2. Install StoryCanvas

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

Edit `.env`, then start the gateway with `scripts\start.ps1` or `start.bat`.

## 3. Local verification

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

The result should report `comfyui_ok: true`.

## 4. Private remote access

Install Tailscale on Windows and the client device, sign both into the same Tailnet, then expose
only the localhost gateway:

```powershell
tailscale serve --bg http://127.0.0.1:8000
tailscale serve status
```

Set `PUBLIC_BASE_URL` to the HTTPS hostname printed by Tailscale Serve. Configure the chat client
with the same origin plus `/v1`.

Do not use Funnel, router port forwarding, or a firewall rule open to public networks.

## 5. 8 GB VRAM profile

Start with the defaults:

- 832 x 1216
- batch 1
- 24 steps
- CFG 6
- DPM++ 2M / Karras
- tiled VAE decode

If CUDA runs out of memory, close GPU-heavy applications, test 768 x 1024, then consider ComfyUI's
`--lowvram` option. Avoid adding high-resolution passes or multiple control adapters first.

Sampler choice is checkpoint-specific. The defaults are broadly compatible; for an Illustrious
checkpoint, also test 28 steps, CFG 7, Euler ancestral, and the normal scheduler, then compare with
a fixed seed before changing production settings.
