"""敏感配置的加密与解密工具。"""

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import USER_SETTINGS_ENCRYPTION_KEY


def _get_cipher() -> Fernet:
    """创建用户设置专用的 Fernet 加密器。"""
    if not USER_SETTINGS_ENCRYPTION_KEY:
        raise ValueError("缺少环境变量 USER_SETTINGS_ENCRYPTION_KEY")

    try:
        return Fernet(USER_SETTINGS_ENCRYPTION_KEY.encode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "USER_SETTINGS_ENCRYPTION_KEY 不是有效的 Fernet 密钥"
        ) from exc


def encrypt_secret(plain_text: str) -> str:
    """加密需持久化的敏感字符串并返回可存储的文本密文。"""
    if not plain_text:
        raise ValueError("待加密内容不能为空")

    return _get_cipher().encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_secret(cipher_text: str) -> str:
    """解密数据库中的敏感字符串密文。"""
    if not cipher_text:
        raise ValueError("待解密内容不能为空")

    try:
        return _get_cipher().decrypt(cipher_text.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("用户 API Key 密文无效或加密密钥已变更") from exc
