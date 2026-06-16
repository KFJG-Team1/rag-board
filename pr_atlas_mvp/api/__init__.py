from __future__ import annotations

__all__ = ["app", "create_app"]


def __getattr__(name: str) -> object:
    if name in {"app", "create_app"}:
        from pr_atlas_mvp.api.app import app, create_app

        return app if name == "app" else create_app
    raise AttributeError(name)
