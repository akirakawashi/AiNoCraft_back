from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cashews import cache


@dataclass(frozen=True, slots=True)
class CacheKeyspace:
    prefix: str

    @classmethod
    def from_prefix(cls, prefix: str) -> "CacheKeyspace":
        return cls(prefix)

    @classmethod
    def from_file(cls, file_path: str) -> "CacheKeyspace":
        return cls(Path(file_path).stem)

    def scope(self, *parts: str) -> "CacheKeyspace":
        return type(self)(prefix=":".join((self.prefix, *parts)))

    def template(self, template: str = "") -> str:
        return f"{self.prefix}:{template}" if template else self.prefix

    def key(self, template: str, /, **values: Any) -> str:
        return self.template(template).format(**values)

    def cached(self, *, ttl: str, template: str):
        return cache(ttl=ttl, key=self.template(template))

    def invalidate(
        self,
        template: str,
        *,
        defaults: dict[str, Any] | None = None,
        args_map: dict[str, str] | None = None,
    ):
        return cache.invalidate(
            key_template=self.template(template),
            defaults=defaults,
            args_map=args_map,
        )
