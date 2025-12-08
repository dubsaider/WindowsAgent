import json
import hashlib
from domain.models import PCConfiguration


def calc_config_hash(config: PCConfiguration) -> str:
    """Детерминированный хеш полной конфигурации."""
    payload = config.to_dict()
    payload_str = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

