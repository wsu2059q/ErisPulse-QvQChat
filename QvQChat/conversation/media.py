"""回复内联媒体标记：模型在正文里写 [表情:关键词]/[语音:文本]，投递层换成真实媒体。

协议只发生在投递侧：工具桥一像素不动，旧生态模块照常工作。供方发现分两级——
模块经 ``qvq_media`` 约定服务显式声明（可指定服务名/参数名/模式），未声明时按
已知服务名兜底（send_sticker / tts_speak），因此 QvQMemes、TTS 的既有版本
无需升级即可被识别。没有供方时标记按"能救则救"降级：语音保留文字内容，
表情直接省略，绝不把标记原样发给用户。
"""
from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass

from .. import texts, utils

# 标记词表：中英日别名统一收口，括号与冒号兼容全半角
# 只认"括号 + 冒号 + 内容"的完整形态；裸标签 [表情]/[语音] 由 utils 的
# 假媒体清扫处理，两者互不抢口径
_MARKER_RE = re.compile(
    r"[\[［【]\s*(表情包|表情|贴图|sticker|语音|声音|音声|voice|audio)\s*[:：]\s*"
    r"([^\[\]［］【】\n]*?)\s*[\]］】]",
    re.IGNORECASE,
)
_VOICE_WORDS = {"语音", "声音", "音声", "voice", "audio"}
_KIND_STICKER = "sticker"
_KIND_VOICE = "voice"

# 兜底约定：旧版模块的服务名 → (参数名, 模式)。模块显式 qvq_media 声明优先。
# 语音优先走"合成取文件 + 核心代发"：tts_synthesize 返回 ok/path，失败可可靠降级；
# 只有 tts_speak 的模块也能用（send 模式，模块自己发）
WELL_KNOWN = {
    _KIND_STICKER: ("send_sticker", "query", "send"),
    _KIND_VOICE: ("tts_synthesize", "text", "produce"),
}
VOICE_SEND_FALLBACK = ("tts_speak", "text", "send")

MEDIA_CACHE_TTL = 30.0
MEDIA_CALL_TIMEOUT = 90.0
_FAILED = object()


@dataclass
class Provider:
    module: str
    service: str
    arg: str
    mode: str = "send"
    path_keys: tuple = ("file", "audio_path", "path")


def _kind_of(word: str) -> str:
    return _KIND_VOICE if str(word or "").strip().lower() in _VOICE_WORDS else _KIND_STICKER


def split_reply(text: str, limit: int = 3) -> list[tuple[str, str]]:
    """把回复切成按原顺序排列的 ("text"|"sticker"|"voice", 内容) 片段。

    无标记时原样返回 [("text", text)]。超过 limit 的标记连同内容丢弃（防刷屏）；
    空内容标记直接丢弃，不产生空气泡。
    """
    raw = str(text or "")
    markers = list(_MARKER_RE.finditer(raw))
    if not markers:
# 无标记保持原文原样（首尾空白/换行由发送链路按既有口径处理）
        return [("text", raw)]
    parts: list[tuple[str, str]] = []
    cursor = 0
    used = 0
    for match in markers:
        chunk = raw[cursor:match.start()].strip()
        if chunk:
            parts.append(("text", chunk))
        cursor = match.end()
        payload = match.group(2).strip()
        if not payload:
            continue
        if used >= max(1, int(limit or 1)):
            continue
        used += 1
        parts.append((_kind_of(match.group(1)), payload))
    tail = raw[cursor:].strip()
    if tail:
        parts.append(("text", tail))
    if not parts:
        return [("text", "")]
    return parts


def text_of(parts: list[tuple[str, str]]) -> str:
    """片段里的全部文字（标记内容不计）：转发判定/去重/收尾检测用。"""
    return "\n\n".join(value for kind, value in parts if kind == "text" and value).strip()


def has_media(parts: list[tuple[str, str]]) -> bool:
    return any(kind != "text" for kind, _ in parts)


def strip_markers(text: str, keep_voice: bool = True) -> str:
    """去掉内联标记；语音标记按 keep_voice 决定是否保留其文字内容。

    工具直发路径用（send_message 的 text 参数）：工具不做媒体转换，
    但绝不能把标记原样送到用户面前。
    """
    def _replace(match: re.Match) -> str:
        if keep_voice and _kind_of(match.group(1)) == _KIND_VOICE:
            return match.group(2).strip()
        return ""

    cleaned = _MARKER_RE.sub(_replace, str(text or ""))
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


class MediaRouter:
    """回复媒体投递：发现供方、按当前会话发送、生成提示词说明。"""

    def __init__(self, main):
        self.main = main
        self.sdk = getattr(main, "sdk", None)
        self._declared: dict[str, Provider] = {}
        self._providers: dict[str, Provider] = {}
        self._scanned_at = 0.0

    # ---------- 供方发现 ----------

    def _catalog(self) -> dict:
        if self.sdk is None:
            return {}
        try:
            data = self.sdk.module.services()
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def _module_allowed(self, module: str) -> bool:
        cfg = self.main.cfg
        include = list(getattr(cfg, "eco_include", []) or [])
        exclude = list(getattr(cfg, "eco_exclude", []) or ["QvQChat"])
        if module in exclude:
            return False
        if include:
            return module in include
        return True

    async def refresh(self) -> None:
        """读取各模块的 qvq_media 声明（异步约定服务；失败静默保持兜底发现）。"""
        declared: dict[str, Provider] = {}
        for module, services in self._catalog().items():
            if not self._module_allowed(module) or not isinstance(services, list):
                continue
            names = {str(item.get("name")) for item in services if isinstance(item, dict)}
            if "qvq_media" not in names or self.sdk is None:
                continue
            try:
                data = await asyncio.wait_for(
                    self.sdk.module.call(module, "qvq_media"), timeout=10.0
                )
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            for kind, spec in data.items():
                kind = str(kind or "").strip().lower()
                if kind not in (_KIND_STICKER, _KIND_VOICE) or not isinstance(spec, dict):
                    continue
                service = str(spec.get("service") or "").strip()
                if not service:
                    continue
                mode = str(spec.get("mode") or "send").strip().lower()
                if mode not in ("send", "produce"):
                    mode = "send"
                path_keys = spec.get("path_keys")
                declared.setdefault(kind, Provider(
                    module=module,
                    service=service,
                    arg=str(spec.get("arg") or ("query" if kind == _KIND_STICKER else "text")),
                    mode=mode,
                    path_keys=tuple(path_keys) if isinstance(path_keys, (list, tuple)) and path_keys else Provider.path_keys,
                ))
        self._declared = declared
        self._scanned_at = 0.0

    def providers(self) -> dict[str, Provider]:
        """当前可用供方（显式声明优先，否则按已知服务名兜底）；30 秒缓存。"""
        now = time.time()
        if self._scanned_at and now - self._scanned_at < MEDIA_CACHE_TTL:
            return self._providers
        found = dict(self._declared)
        catalog = self._catalog()
        candidates = {kind: [spec] for kind, spec in WELL_KNOWN.items()}
        candidates[_KIND_VOICE].append(VOICE_SEND_FALLBACK)
        for kind, specs in candidates.items():
            if kind in found:
                continue
            for service, arg, mode in specs:
                hit = None
                for module, services in catalog.items():
                    if not self._module_allowed(module) or not isinstance(services, list):
                        continue
                    if any(str(item.get("name")) == service for item in services if isinstance(item, dict)):
                        hit = Provider(module=module, service=service, arg=arg, mode=mode)
                        break
                if hit is not None:
                    found[kind] = hit
                    break
        self._providers = found
        self._scanned_at = now
        return found

    def prompt_note(self) -> str:
        """可用标记的系统提示说明；无供方或总开关关闭时为空。"""
        if not bool(getattr(self.main.cfg, "media_markers", True)):
            return ""
        available = self.providers()
        lines = []
        if _KIND_STICKER in available:
            lines.append(texts.t("media_sticker_note"))
        if _KIND_VOICE in available:
            lines.append(texts.t("media_voice_note"))
        return "\n".join(line for line in lines if line)

    # ---------- 发送 ----------

    def _target_of(self, event) -> dict | None:
        try:
            platform = str(event.get_platform() or "")
            detail_type = "group" if event.is_group_message() else "user"
            target_id = str((event.get_group_id() if detail_type == "group" else event.get_user_id()) or "")
        except Exception:
            return None
        if not platform or not target_id:
            return None
        account = ""
        try:
            account = str(event.get_self_account_id() or "")
        except Exception:
            account = ""
        return {"platform": platform, "detail_type": detail_type, "target_id": target_id, "account": account}

    def _allowed(self, provider: Provider, event) -> bool:
        eco = getattr(self.main, "eco", None)
        access = "safe"
        if eco is not None and hasattr(eco, "service_access"):
            try:
                access = eco.service_access(provider.module, provider.service)
            except Exception:
                access = "safe"
        if access != "admin":
            return True
        # 管理员服务不随普通会话自动触发；管理员仍需显式调工具
        try:
            return bool(self.main.is_admin(str(event.get_user_id() or ""), "chat",
                                           str(event.get_platform() or "")))
        except Exception:
            return False

    async def _call(self, provider: Provider, kwargs: dict):
        """调用供方服务；kwargs 不被接受时逐级裁剪（旧模块签名差异）。"""
        if self.sdk is None:
            return _FAILED
        timeout = float(getattr(self.main.cfg, "eco_call_timeout", MEDIA_CALL_TIMEOUT) or MEDIA_CALL_TIMEOUT)
        variants = [dict(kwargs)]
        trimmed = dict(kwargs)
        trimmed.pop("account", None)
        variants.append(trimmed)
        trimmed = dict(trimmed)
        trimmed.pop("target_type", None)
        variants.append(trimmed)
# 只认内容参数的合成类服务（不关心目标）也能调通
        variants.append({provider.arg: kwargs.get(provider.arg, "")})
        for params in variants:
            try:
                return await asyncio.wait_for(
                    self.sdk.module.call(provider.module, provider.service, **params),
                    timeout=timeout if timeout > 0 else None,
                )
            except TypeError:
                continue
            except Exception as e:
                self.main.logger.warning(f"media provider {provider.module}.{provider.service} failed: {e}")
                return _FAILED
        self.main.logger.warning(f"media provider {provider.module}.{provider.service} rejected params")
        return _FAILED

    async def _send_file(self, event, kind: str, path: str, target: dict) -> bool:
        adapter = self.sdk.adapter.get(target["platform"]) if self.sdk is not None else None
        if adapter is None:
            return False
        chain = adapter.Send
        if target["account"]:
            chain = chain.Using(target["account"])
        chain = chain.To(target["detail_type"], target["target_id"])
        method = "Voice" if kind == _KIND_VOICE else "Image"
        try:
            result = await getattr(chain, method)(path)
        except Exception as e:
            self.main.logger.warning(f"media send {method} failed: {e}")
            return False
        return not utils._send_failed(result)

    async def send(self, event, kind: str, payload: str) -> bool:
        """按当前会话投递一个媒体标记；供方缺失/失败返回 False（调用方决定降级）。"""
        provider = self.providers().get(kind)
        target = self._target_of(event)
        text_value = str(payload or "").strip()
        if provider is None or target is None or not text_value:
            return False
        if not self._allowed(provider, event):
            return False
        kwargs = {provider.arg: text_value, "platform": target["platform"],
                  "target_id": target["target_id"], "target_type": target["detail_type"]}
        if provider.mode == "send":
            if target["account"]:
                kwargs["account"] = target["account"]
            result = await self._call(provider, kwargs)
            if result is _FAILED:
                return False
# 约定：显式声明的 send 模式建议回 {"ok": bool}；旧模块字符串返回值按成功处理
            if isinstance(result, dict) and result.get("ok") is False:
                return False
            return True
        data = await self._call(provider, kwargs)
        if not isinstance(data, dict) or data.get("ok") is False:
            return False
        paths: list[str] = []
        for key in provider.path_keys:
            value = data.get(key)
            if not value:
                continue
            if isinstance(value, (list, tuple)):
                paths = [str(item) for item in value if item]
            else:
                paths = [str(value)]
            if paths:
                break
        if not paths:
            return False
# 多段合成产物按序发出；只要有一段送出就算成功（避免再补一条重复文字的语音）
        delivered = 0
        for path in paths:
            if await self._send_file(event, kind, path, target):
                delivered += 1
        return delivered > 0
