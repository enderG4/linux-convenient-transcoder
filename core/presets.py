# core/presets.py

from core.models import CodecConfig, CompressionType

CODEC_PRESETS: list[CodecConfig] = [
    CodecConfig(
        display_name="H.264",
        ffmpeg_codec="libx264",
        default_format=".mp4",
        allowed_formats=[".mp4", ".mkv", ".mov"],
        compression_type=CompressionType.CRF,
    ),
    CodecConfig(
        display_name="H.265 (HEVC)",
        ffmpeg_codec="libx265",
        default_format=".mp4",
        allowed_formats=[".mp4", ".mkv"],
        compression_type=CompressionType.CRF,
    ),
    CodecConfig(
        display_name="Apple ProRes",
        ffmpeg_codec="prores_ks",
        default_format=".mov",
        allowed_formats=[".mov"],
        compression_type=CompressionType.PROFILE,
        profiles=["proxy", "lt", "standard", "hq", "4444"],
    ),
    CodecConfig(
        display_name="Avid DNxHR",
        ffmpeg_codec="dnxhd",
        default_format=".mxf",
        allowed_formats=[".mxf", ".mov"],
        compression_type=CompressionType.PROFILE,
        profiles=["lb", "sq", "hq", "hqx", "444"],
    ),
    CodecConfig(
        display_name="Copy (Remux)",
        ffmpeg_codec="copy",
        default_format=".mov",
        allowed_formats=[".mov", ".mp4", ".mkv", ".mxf"],
        compression_type=CompressionType.NONE,
    ),
]

AUDIO_PRESETS = ["copy", "aac", "pcm_s16le"]