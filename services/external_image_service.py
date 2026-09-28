from __future__ import annotations

"""外部图片服务：把指定模型名的生图请求转发到第三方 OpenAI 兼容接口。

典型用途：本机账号池没有 gpt-image-2.5 能力（需要 codex + Plus/Team/Pro），
但第三方中转站提供该模型时，可在配置里把 gpt-image-2.5 映射过去。

配置示例（config.json）：
    "external_image": {
        "enabled": true,
        "base_url": "https://image.mlgb7.com",
        "api_key": "lupi_xxx",
        "timeout_sec": 180,
        "external_models": {"gpt-image-2.5": "gpt-image-2.5"}
    }
"""

import base64
from typing import Any, Iterator

from services.config import config
from utils.log import logger

# 懒加载 requests，避免与 utils.helper 的循环导入
_requests = None


def _get_requests():
    global _requests
    if _requests is None:
        from curl_cffi import requests as curl_requests
        _requests = curl_requests
    return _requests


def external_model_map() -> dict[str, str]:
    """返回 {对外模型名: 上游模型名}，未启用时为空。"""
    settings = config.get_external_image_settings()
    if not settings.get("enabled"):
        return {}
    models = settings.get("external_models")
    return dict(models) if isinstance(models, dict) else {}


def is_external_model(model: object) -> bool:
    name = str(model or "").strip()
    return bool(name) and name in external_model_map()


def list_external_models() -> list[str]:
    return sorted(external_model_map().keys())


class ExternalImageError(RuntimeError):
    pass


def _auth_headers() -> dict[str, str]:
    settings = config.get_external_image_settings()
    return {
        "Authorization": f"Bearer {settings.get('api_key', '')}",
        "Content-Type": "application/json",
    }


def _post_json(path: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    settings = config.get_external_image_settings()
    base_url = str(settings.get("base_url") or "").rstrip("/")
    if not base_url:
        raise ExternalImageError("外部图片服务未配置 base_url")
    requests = _get_requests()
    url = f"{base_url}{path}"
    try:
        response = requests.post(
            url,
            headers=_auth_headers(),
            json=payload,
            timeout=timeout,
        )
    except Exception as exc:  # noqa: BLE001
        raise ExternalImageError(f"外部图片服务请求失败: {exc}") from exc
    if response.status_code != 200:
        detail = ""
        try:
            detail = str(response.json().get("error", {}).get("message") or "")
        except Exception:  # noqa: BLE001
            detail = str(response.text or "")[:300]
        raise ExternalImageError(
            f"外部图片服务返回 {response.status_code}: {detail or 'unknown error'}"
        )
    try:
        data = response.json()
    except Exception as exc:  # noqa: BLE001
        raise ExternalImageError("外部图片服务返回非 JSON 响应") from exc
    if not isinstance(data, dict):
        raise ExternalImageError("外部图片服务返回格式异常")
    return data


def _download_image(url: str, timeout: int) -> bytes:
    requests = _get_requests()
    try:
        response = requests.get(url, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        raise ExternalImageError(f"下载外部图片失败: {exc}") from exc
    if response.status_code != 200:
        raise ExternalImageError(f"下载外部图片返回 {response.status_code}")
    content = response.content or b""
    if not content:
        raise ExternalImageError("外部图片内容为空")
    return content


def _to_b64_items(data: dict[str, Any], timeout: int) -> list[dict[str, Any]]:
    """把外部服务的响应统一转成 [{b64_json, revised_prompt}]。"""
    items: list[dict[str, Any]] = []
    for entry in data.get("data") or []:
        if not isinstance(entry, dict):
            continue
        revised_prompt = str(entry.get("revised_prompt") or "")
        b64_json = str(entry.get("b64_json") or "").strip()
        if b64_json:
            items.append({"b64_json": b64_json, "revised_prompt": revised_prompt})
            continue
        url = str(entry.get("url") or "").strip()
        if not url:
            continue
        image_bytes = _download_image(url, timeout)
        items.append({
            "b64_json": base64.b64encode(image_bytes).decode("ascii"),
            "revised_prompt": revised_prompt,
        })
    if not items:
        message = str(data.get("message") or "").strip()
        raise ExternalImageError(message or "外部图片服务未返回任何图片")
    return items


def generate(
        prompt: str,
        model: str,
        n: int = 1,
        size: str | None = None,
        quality: str = "auto",
        images: list[str] | None = None,
) -> list[dict[str, Any]]:
    """调用外部服务生成图片，返回 [{b64_json, revised_prompt}]。

    images 非空时走图生图（edits），否则走文生图（generations）。
    """
    settings = config.get_external_image_settings()
    timeout = int(settings.get("timeout_sec") or 180)
    upstream_model = external_model_map().get(str(model or "").strip(), "")
    if not upstream_model:
        raise ExternalImageError(f"模型 {model} 未在外部图片服务中映射")

    if images:
        return _generate_edit(prompt, upstream_model, n, size, quality, images, timeout)
    return _generate_text(prompt, upstream_model, n, size, quality, timeout)


def _generate_text(
        prompt: str,
        upstream_model: str,
        n: int,
        size: str | None,
        quality: str,
        timeout: int,
) -> list[dict[str, Any]]:
    payload: dict[str, Any] = {
        "model": upstream_model,
        "prompt": prompt,
        "n": max(1, int(n or 1)),
        "response_format": "url",
    }
    if size:
        payload["size"] = size
    if quality:
        payload["quality"] = quality
    logger.info({
        "event": "external_image_generation_start",
        "model": upstream_model,
        "n": payload["n"],
        "size": payload.get("size"),
    })
    data = _post_json("/v1/images/generations", payload, timeout)
    items = _to_b64_items(data, timeout)
    logger.info({
        "event": "external_image_generation_done",
        "model": upstream_model,
        "count": len(items),
    })
    return items


def _generate_edit(
        prompt: str,
        upstream_model: str,
        n: int,
        size: str | None,
        quality: str,
        images: list[str],
        timeout: int,
) -> list[dict[str, Any]]:
    """图生图：外部接口要求 multipart/form-data 上传图片。"""
    settings = config.get_external_image_settings()
    base_url = str(settings.get("base_url") or "").rstrip("/")
    requests = _get_requests()

    files = []
    for index, encoded in enumerate(images, start=1):
        raw = base64.b64decode(encoded)
        files.append(("image", (f"image_{index}.png", raw, "image/png")))

    form: dict[str, Any] = {
        "model": upstream_model,
        "prompt": prompt,
        "n": str(max(1, int(n or 1))),
    }
    if size:
        form["size"] = size
    if quality:
        form["quality"] = quality

    logger.info({
        "event": "external_image_edit_start",
        "model": upstream_model,
        "images": len(files),
    })
    try:
        response = requests.post(
            f"{base_url}/v1/images/edits",
            headers={"Authorization": f"Bearer {settings.get('api_key', '')}"},
            data=form,
            files=files,
            timeout=timeout,
        )
    except Exception as exc:  # noqa: BLE001
        raise ExternalImageError(f"外部图片服务图生图请求失败: {exc}") from exc
    if response.status_code != 200:
        detail = ""
        try:
            detail = str(response.json().get("error", {}).get("message") or "")
        except Exception:  # noqa: BLE001
            detail = str(response.text or "")[:300]
        raise ExternalImageError(
            f"外部图片服务图生图返回 {response.status_code}: {detail or 'unknown error'}"
        )
    data = response.json()
    if not isinstance(data, dict):
        raise ExternalImageError("外部图片服务图生图返回格式异常")
    items = _to_b64_items(data, timeout)
    logger.info({
        "event": "external_image_edit_done",
        "model": upstream_model,
        "count": len(items),
    })
    return items
