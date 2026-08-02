import hashlib
import hmac

from redis.asyncio import Redis
from redis.exceptions import RedisError

from utag_api.config import get_settings
from utag_api.errors import ApiError
from utag_api.observability import get_logger

logger = get_logger()


def _safe_key(value: str) -> str:
    secret = get_settings().app_secret_key.get_secret_value().encode()
    return hmac.new(secret, value.encode(), hashlib.sha256).hexdigest()


async def enforce_rate_limit(
    bucket: str,
    identity: str,
    *,
    limit: int,
    period_seconds: int,
) -> None:
    settings = get_settings()
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    key = f"rate:{bucket}:{_safe_key(identity)}"
    try:
        async with client.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, period_seconds, nx=True)
            count, _ = await pipe.execute()
    except RedisError:
        logger.exception("rate_limit_backend_unavailable", bucket=bucket)
        if settings.is_production:
            raise ApiError(
                503,
                "security_service_unavailable",
                "Sign-in protection is temporarily unavailable",
            ) from None
        return
    finally:
        await client.aclose()
    if int(count) > limit:
        raise ApiError(
            429,
            "rate_limit_exceeded",
            "Too many attempts. Please wait and try again",
        )
