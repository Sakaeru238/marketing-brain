# ComfyUI Windows Render Worker Context

## Current Goal

Continue POD step `[5] ComfyUI Render Worker` on the Windows machine where ComfyUI is installed.

The Mac project has already completed:

- `[1]` POD strategy
- `[2]` POD design brief
- `[3]` brief evaluation
- `[4]` Open Design / Generative Media Translation Layer

The next task is to read the step `[4]` render bundle and generate product images in ComfyUI for both sides of the product.

## Campaign

- Brand: `BRAND0001`
- Campaign folder:

```text
data/brands/BRAND0001/pod/campaigns/Bộ_polo_huy_hiệu_bóng_bầu_dục_phong_cách_câu_lạc_bộ_golf_cổ_điển/
```

- Product: premium polo with a small heritage crest/badge
- Required first render outputs:

```text
front_flat_mockup
back_flat_mockup
```

Both front and back are required. POD products are treated as two-sided by default.

## Files To Copy To Windows

Copy the full campaign folder if possible:

```text
data/brands/BRAND0001/pod/campaigns/Bộ_polo_huy_hiệu_bóng_bầu_dục_phong_cách_câu_lạc_bộ_golf_cổ_điển/
```

Minimum required files:

```text
04_open_design_translation/comfyui_render_request_bundle.json
04_open_design_translation/chatgpt_image_prompts.json
00_inputs/pod_campaign_intake.json
00_inputs/product_catalog_entry.json
00_inputs/source_snapshot.json
```

If available, also copy:

```text
00_inputs/reference_images/
```

The current bundle references a Google Drive image URL. If ComfyUI cannot fetch it directly, download it manually and place it in ComfyUI input folder.

## Main Input File

Use:

```text
04_open_design_translation/comfyui_render_request_bundle.json
```

It contains:

- `chatgpt_image_prompts`
- `comfyui_render_requests`

Current request IDs:

```text
front_flat_mockup
back_flat_mockup
```

Each request has:

```json
{
  "request_id": "front_flat_mockup",
  "view": "front",
  "output_group": "flat_mockup",
  "workflow_id_hint": "pod_apparel_flat_mockup_front",
  "generation_payload": {
    "positive_prompt": "...",
    "negative_prompt": "...",
    "reference_image_url": "...",
    "seed": null,
    "width": 1024,
    "height": 1024,
    "steps": 30,
    "cfg": 7,
    "sampler": "dpmpp_2m",
    "scheduler": "karras",
    "checkpoint": "realisticVisionV60B1_v51VAE.safetensors"
  }
}
```

## Expected Output On Windows

Create:

```text
05_comfyui_render_worker/
  front_flat_mockup.png
  back_flat_mockup.png
  comfyui_render_result.json
  comfyui_render_worker_log.json
```

`comfyui_render_result.json` should contain:

```json
{
  "status": "success",
  "brand_id": "BRAND0001",
  "campaign_id": "...",
  "generated_images": [
    {
      "request_id": "front_flat_mockup",
      "view": "front",
      "output_group": "flat_mockup",
      "image_path": "05_comfyui_render_worker/front_flat_mockup.png",
      "seed": 123456
    },
    {
      "request_id": "back_flat_mockup",
      "view": "back",
      "output_group": "flat_mockup",
      "image_path": "05_comfyui_render_worker/back_flat_mockup.png",
      "seed": 123457
    }
  ]
}
```

## Jobs To Implement On Windows

### Job 1: Verify ComfyUI API

Confirm ComfyUI is running:

```text
http://127.0.0.1:8188
```

Check:

```text
GET /system_stats
GET /object_info
```

### Job 2: Prepare Workflow Template

Create or choose a ComfyUI workflow JSON for apparel flat mockups.

Need two workflow mappings:

```text
pod_apparel_flat_mockup_front
pod_apparel_flat_mockup_back
```

At minimum the workflow must expose nodes for:

- positive prompt
- negative prompt
- checkpoint/model
- width
- height
- seed
- steps
- cfg
- sampler
- scheduler
- output filename/prefix

If using reference image, also expose:

- LoadImage node
- ControlNet/IPAdapter/reference image node if available

### Job 3: Create Render Worker Script

Create a script on Windows, for example:

```text
tools/windows_comfyui_render_worker.py
```

CLI:

```bash
python tools/windows_comfyui_render_worker.py ^
  --bundle "path\\to\\comfyui_render_request_bundle.json" ^
  --workflow-front "path\\to\\workflow_front_api.json" ^
  --workflow-back "path\\to\\workflow_back_api.json" ^
  --output-dir "path\\to\\05_comfyui_render_worker"
```

The script should:

1. Load `comfyui_render_request_bundle.json`
2. Loop over `comfyui_render_requests`
3. Select workflow by `workflow_id_hint`
4. Inject:
   - positive prompt
   - negative prompt
   - width/height
   - seed
   - steps
   - cfg
   - sampler/scheduler
   - checkpoint if present
5. POST workflow to:

```text
POST http://127.0.0.1:8188/prompt
```

6. Poll queue/history until done
7. Copy output images to:

```text
05_comfyui_render_worker/
```

8. Write `comfyui_render_result.json`

### Job 4: Handle Seeds

If `seed` is `null`, assign deterministic seeds.

Example:

```text
front_flat_mockup: 23800001
back_flat_mockup: 23800002
```

Write the actual seed into result JSON.

### Job 5: Handle Google Drive Reference Image

Current reference image URL may not be directly loadable by ComfyUI:

```text
https://drive.google.com/file/d/1Qqkd4OFTy8yrIFt-MNc-OwPXJUDFe3oF/view?usp=sharing
```

If needed, convert to:

```text
https://drive.google.com/uc?export=download&id=1Qqkd4OFTy8yrIFt-MNc-OwPXJUDFe3oF
```

Or manually download the image and put it in:

```text
ComfyUI/input/
```

Then inject local image filename into the LoadImage node.

### Job 6: Quality Checks Before Returning

For each generated image:

- front output must show the front side only
- back output must show the back side only
- no official NFL logo
- no official Chiefs logo
- no large unwanted jersey number
- no unreadable huge text
- polo shape should remain clear
- crest placement should be left chest for front
- back should remain mostly clean

Do not run visual eval yet. Just produce render worker output.

## Important Notes

- Do not edit brand/campaign strategy files on Windows unless needed.
- Do not regenerate prompts on Windows. Use the JSON bundle from Mac as source of truth.
- Do not call Claude on Windows for this step.
- The Windows task is only ComfyUI rendering from an existing bundle.
- The Mac repo currently has cache for prompt generation. If prompts need to change, do it back on Mac, regenerate step `[4]`, then copy the updated bundle to Windows.

