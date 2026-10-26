import io
import re
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from dify_plugin.file.entities import FileType
from dify_plugin.file.file import File
from PIL import Image, ImageColor, ImageOps, UnidentifiedImageError

SUPPORTED_FORMATS = {"JPEG", "PNG"}
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}
# 画布像素上限，仅用于防止运行时 OOM；对应 manifest 中 1GB 内存配额
MAX_OUTPUT_PIXELS = 100_000_000
DEFAULT_BACKGROUND = "#FFFFFF"


class ImageMergeError(ValueError):
    pass


class ImageMergeTool(Tool):
    """Merge multiple JPG/PNG images into one image, stacked vertically in file order."""

    def _invoke(
        self, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        files = self._normalize_files(tool_parameters.get("files"))
        gap = self._normalize_gap(tool_parameters.get("gap"))
        background = self._normalize_background(tool_parameters.get("background_color"))
        output_name = self._normalize_output_name(
            tool_parameters.get("output_filename"), files[0]
        )

        # First pass: download and validate every file, collect the rendered size.
        sources: list[tuple[bytes, int, int]] = []
        for index, file in enumerate(files):
            data = self._read_file(file, index)
            image = self._decode(data, index)
            try:
                sources.append((data, image.width, image.height))
            finally:
                image.close()

        width = max(item[1] for item in sources)
        height = sum(item[2] for item in sources) + gap * (len(sources) - 1)
        if width <= 0 or height <= 0:
            raise ImageMergeError("图片尺寸无效，无法拼接")
        if width * height > MAX_OUTPUT_PIXELS:
            raise ImageMergeError(
                f"拼接后的画布过大（{width}×{height} 像素，上限 {MAX_OUTPUT_PIXELS // 10000} 万像素），"
                "请减少图片数量或缩小图片尺寸"
            )

        canvas = Image.new("RGB", (width, height), background)
        top = 0
        for index, (data, image_width, image_height) in enumerate(sources):
            image = self._decode(data, index)
            try:
                left = (width - image_width) // 2
                if self._has_alpha(image):
                    rgba = image.convert("RGBA")
                    canvas.paste(rgba, (left, top), rgba)
                    rgba.close()
                else:
                    canvas.paste(image.convert("RGB"), (left, top))
            finally:
                image.close()
            top += image_height + gap

        buffer = io.BytesIO()
        try:
            canvas.save(buffer, format="PNG")
            payload = buffer.getvalue()
            merged_width, merged_height = canvas.size
        finally:
            buffer.close()
            canvas.close()

        yield self.create_variable_message("width", merged_width)
        yield self.create_variable_message("height", merged_height)
        yield self.create_variable_message("image_count", len(sources))
        yield self.create_blob_message(
            payload,
            meta={"mime_type": "image/png", "filename": output_name},
        )
        yield self.create_json_message(
            {
                "image_count": len(sources),
                "width": merged_width,
                "height": merged_height,
                "mime_type": "image/png",
            }
        )
        yield self.create_text_message(
            f"已按文件顺序将 {len(sources)} 张图片纵向拼接，输出尺寸 {merged_width}×{merged_height}（PNG），文件名 {output_name}。"
        )

    def _normalize_files(self, value: Any) -> list[File]:
        if value is None:
            raise ImageMergeError("请上传至少一张 JPG/PNG 图片")
        if isinstance(value, File):
            files: list[Any] = [value]
        elif isinstance(value, (list, tuple)):
            files = list(value)
        else:
            raise ImageMergeError("参数 files 必须是图片文件列表")
        if not files:
            raise ImageMergeError("请上传至少一张 JPG/PNG 图片")
        for index, item in enumerate(files):
            if not isinstance(item, File):
                raise ImageMergeError(f"第 {index + 1} 个输入不是有效的文件对象")
            if item.type != FileType.IMAGE:
                raise ImageMergeError(f"第 {index + 1} 个文件不是图片：{item.filename or item.url}")
        return files

    def _read_file(self, file: File, index: int) -> bytes:
        extension = (file.extension or "").lower().lstrip(".")
        if extension and extension not in ALLOWED_EXTENSIONS:
            raise ImageMergeError(
                f"第 {index + 1} 个文件（{file.filename or extension}）格式不支持，仅支持 jpg、jpeg、png"
            )
        try:
            data = file.blob
        except Exception as error:
            raise ImageMergeError(f"读取第 {index + 1} 个文件失败：{error}") from error
        if not data:
            raise ImageMergeError(f"第 {index + 1} 个文件内容为空")
        return data

    def _decode(self, data: bytes, index: int) -> Image.Image:
        try:
            image = Image.open(io.BytesIO(data))
            image.load()
        except UnidentifiedImageError as error:
            raise ImageMergeError(f"第 {index + 1} 个文件无法识别为图片") from error
        except Image.DecompressionBombError as error:
            raise ImageMergeError(f"第 {index + 1} 个图片像素过大，无法处理") from error
        except OSError as error:
            raise ImageMergeError(f"第 {index + 1} 个图片解析失败：{error}") from error
        image_format = image.format
        if image_format not in SUPPORTED_FORMATS:
            image.close()
            raise ImageMergeError(
                f"第 {index + 1} 个图片格式为 {image_format}，仅支持 jpg、png"
            )
        transposed = ImageOps.exif_transpose(image)
        if transposed is not image:
            image.close()
        return transposed

    @staticmethod
    def _has_alpha(image: Image.Image) -> bool:
        return image.mode in ("RGBA", "LA") or (
            image.mode == "P" and "transparency" in image.info
        )

    @staticmethod
    def _normalize_gap(value: Any) -> int:
        if value is None or value == "":
            return 0
        try:
            gap = int(float(value))
        except (TypeError, ValueError) as error:
            raise ImageMergeError("图片间距必须是数字") from error
        if gap < 0:
            raise ImageMergeError("图片间距不能小于 0")
        if gap > 1000:
            raise ImageMergeError("图片间距不能大于 1000 像素")
        return gap

    @staticmethod
    def _normalize_output_name(value: Any, first_file: File) -> str:
        name = ImageMergeTool._clean_name(str(value)) if value else ""
        if not name:
            name = ImageMergeTool._clean_name(first_file.filename or "") or "merged"
        return f"{name}.png"

    @staticmethod
    def _clean_name(value: str) -> str:
        name = value.replace("\\", "/").split("/")[-1].strip()
        name = re.sub(r'[:*?"<>|\x00-\x1f]', "_", name).strip(" .")
        lowered = name.lower()
        for suffix in (".png", ".jpg", ".jpeg"):
            if lowered.endswith(suffix):
                name = name[: -len(suffix)]
                break
        return name.strip(" .")[:100]

    @staticmethod
    def _normalize_background(value: Any) -> tuple[int, int, int]:
        color = str(value).strip() if value else DEFAULT_BACKGROUND
        try:
            rgb = ImageColor.getrgb(color)
        except ValueError as error:
            raise ImageMergeError(f"无法识别的背景色：{color}") from error
        if len(rgb) >= 3:
            return rgb[0], rgb[1], rgb[2]
        raise ImageMergeError(f"无法识别的背景色：{color}")
