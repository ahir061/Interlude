import shutil
from tempfile import TemporaryFile
from urllib.parse import urlsplit

from interlude.config import Settings
from interlude.services.brands import load_brands


class StartupError(RuntimeError):
    pass


def validate_environment(settings: Settings):
    errors = []
    url = urlsplit(settings.llm_api_url)
    if url.scheme not in ("http", "https") or not url.hostname or not settings.llm_model or not settings.llm_api_key.get_secret_value():
        errors.append("qwen_configuration_invalid")
    if not settings.groq_api_key.get_secret_value():
        errors.append("groq_key_missing")
    if not all((settings.db_host, settings.db_user, settings.db_name, settings.db_password.get_secret_value())) or not 0 < settings.db_port < 65536:
        errors.append("database_configuration_invalid")
    for name, binary in (("ffmpeg", settings.ffmpeg_bin), ("ffprobe", settings.ffprobe_bin)):
        if not shutil.which(binary):
            errors.append(f"{name}_missing")
    try:
        load_brands(settings.brands_path)
    except Exception:
        errors.append("brand_catalogue_invalid")
    try:
        settings.prepare_dirs()
        settings.reports_dir.mkdir(parents=True, exist_ok=True)
        for directory in [settings.reports_dir, *(settings.data_dir/n for n in ("uploads", "work", "ads", "outputs", "semantic_cache"))]:
            with TemporaryFile(dir=directory) as test:
                test.write(b"write-check")
    except OSError:
        errors.append("storage_not_writable")
    if errors:
        raise StartupError(",".join(errors))
