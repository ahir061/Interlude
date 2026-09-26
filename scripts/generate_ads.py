from interlude.config import get_settings
from interlude.services.brands import load_brands
from interlude.services.creatives import CreativeService

if __name__ == "__main__":
    settings = get_settings()
    brands = CreativeService(settings).ensure(load_brands(settings.brands_path))
    print(f"Verified {sum(len(b.creatives) for b in brands)} playable creatives for {len(brands)} brands.")
