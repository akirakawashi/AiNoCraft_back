from fastapi import Request


def get_user_agent(request: Request) -> str | None:
    user_agent = request.headers.get("user-agent")
    return user_agent if user_agent else None


def get_client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        first_ip = forwarded_for.split(",", maxsplit=1)[0].strip()
        if first_ip:
            return first_ip

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        real_ip = real_ip.strip()
        if real_ip:
            return real_ip

    forwarded = request.headers.get("forwarded")
    if forwarded:
        # Example: for=192.0.2.60;proto=http;by=203.0.113.43
        for part in forwarded.split(";"):
            key, _, value = part.partition("=")
            if key.strip().lower() != "for":
                continue

            candidate = value.strip().strip('"')
            if candidate.startswith("[") and "]" in candidate:
                candidate = candidate[1 : candidate.index("]")]
            elif ":" in candidate and candidate.count(":") == 1:
                candidate = candidate.rsplit(":", maxsplit=1)[0]

            if candidate:
                return candidate

    if request.client and request.client.host:
        return request.client.host

    return None
