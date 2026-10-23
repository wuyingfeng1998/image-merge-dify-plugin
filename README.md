## image-merge

**Author:** wuyingfeng
**Version:** 0.0.2
**Type:** tool
**Source repository:** https://github.com/wuyingfeng1998/image-merge-dify-plugin

### Description

Merge multiple JPG/PNG images into a single image. Images are stacked vertically in the order of the input file list, so the first file appears at the top and the last file at the bottom.

### Setup

No credentials or API keys are required. Runtime dependencies are `dify_plugin` and `Pillow`, pinned in `requirements.txt`.

### Usage

1. Install the plugin in Dify from the marketplace, or from a local package (`.difypkg`).
2. Add the **Merge Images Vertically** tool to a Workflow / Chatflow tool node, or use it in an Agent.
3. Fill in the parameters:

| Parameter | Required | Description |
| --- | --- | --- |
| Image files (`files`) | Yes | Ordered list of JPG/PNG images. The merge order follows the list order (top to bottom). |
| Gap (`gap`) | No | Vertical spacing in pixels between adjacent images. Default `0`. |
| Background color (`background_color`) | No | Fills padding and transparent areas, e.g. `#FFFFFF` or `white`. Default `#FFFFFF`. |

The wider image defines the canvas width; narrower images are centered horizontally. The tool outputs one PNG file plus `width`, `height` and `image_count` variables.

### Notes

- Only JPG/JPEG and PNG inputs are supported; other formats raise an error.
- EXIF orientation of photos is applied before merging.
- The merged canvas is limited to 100 megapixels to protect the plugin runner's memory (the manifest requests 1 GB).

### Building a fully offline package

`scripts/build_offline.py` produces a self-contained `.difypkg` for hosts without internet access. It downloads every dependency as a Linux x86_64 / CPython 3.12 wheel into `wheels/`, points `requirements.txt` at that local wheelhouse, and adds the matching `[tool.uv]` configuration:

```shell
python scripts/build_offline.py --dify /path/to/dify --output dist/image-merge-0.0.2-offline.difypkg
```

The resulting package installs and starts on a Linux x86_64 Dify plugin daemon with no network access. Dependencies are still installed by the daemon at install time, but only from the bundled wheels.
