"""模型 provider 自定义 API 地址校验工具。"""

from ipaddress import ip_address
import socket
from urllib.parse import urlparse


def ensure_public_host(host: str, port: int | None = None) -> None:
    """校验用户提供的主机名只能解析到公网地址。"""
    normalized_host = host.rstrip(".").lower()
    if (
        normalized_host == "localhost"
        or normalized_host.endswith(".localhost")
        or normalized_host.endswith(".local")
    ):
        raise ValueError("用户自定义模型 API 地址不能指向本机地址")

    try:
        host_ip = ip_address(normalized_host)
    except ValueError as exc:
        if normalized_host.replace(".", "").isdigit():
            raise ValueError("模型 API 地址的 IP 地址无效") from exc
    else:
        if not host_ip.is_global:
            raise ValueError("用户自定义模型 API 地址不能指向私网地址")
        return

    try:
        resolved_addresses = socket.getaddrinfo(
            normalized_host,
            port or 443,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise ValueError("无法解析用户自定义模型 API 地址主机") from exc

    resolved_ips = {
        address[0]
        for *_, address in resolved_addresses
        if address and address[0]
    }
    if not resolved_ips:
        raise ValueError("无法解析用户自定义模型 API 地址主机")

    for resolved_ip in resolved_ips:
        try:
            parsed_ip = ip_address(resolved_ip)
        except ValueError as exc:
            raise ValueError("模型 API 地址解析结果无效") from exc

        if not parsed_ip.is_global:
            raise ValueError(
                "用户自定义模型 API 地址不能解析到私网地址"
            )


def validate_public_https_base_url(base_url: str) -> str:
    """规范化用户自定义 API 地址，并拒绝内网或携带凭据的 URL。"""
    normalized_base_url = base_url.strip().rstrip("/")
    if not normalized_base_url:
        raise ValueError("模型 API 地址不能为空")

    parsed_url = urlparse(normalized_base_url)
    host = parsed_url.hostname
    if (
        parsed_url.scheme != "https"
        or parsed_url.username
        or parsed_url.password
        or not host
    ):
        raise ValueError("用户自定义模型 API 地址必须是不含凭据的 HTTPS 地址")

    ensure_public_host(host, parsed_url.port)
    return normalized_base_url
