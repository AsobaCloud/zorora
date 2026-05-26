"""
Authentication and subscription middleware for Zorora.

Validates JWT tokens issued by the Ona Platform auth service,
checks subscription tier, and enforces usage limits.
"""

import os
import logging
import functools
from datetime import datetime, timezone

import jwt
import boto3
from botocore.exceptions import ClientError
from flask import request, jsonify

logger = logging.getLogger(__name__)

# JWT config — must match the Ona Platform auth Lambda
JWT_SECRET = os.environ.get("ONA_JWT_SECRET", "change-this-secret-key-in-production")
JWT_ALGORITHM = "HS256"

# DynamoDB
_aws_region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "af-south-1"
_dynamodb = boto3.resource("dynamodb", region_name=_aws_region)
_users_table = _dynamodb.Table(os.environ.get("USERS_TABLE", "ona-platform-users"))

# Tier limits
TIER_LIMITS = {
    "explorer": {"research_queries_per_month": 10},
    "professional": {"research_queries_per_month": None},  # unlimited
    "enterprise": {"research_queries_per_month": None},  # unlimited
}

# Gated actions — these require authentication
GATED_PREFIXES = [
    "/api/research",
    "/api/alerts",
    "/api/scouting",
    "/api/settings",
]

# Exempt paths that start with a gated prefix but should be open
EXEMPT_PATHS = [
    "/api/research/history",  # read-only, gated separately if needed
]


def _decode_token(token: str) -> dict | None:
    """Decode and validate a JWT token. Returns payload or None."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def _get_user_subscription(user_id: str) -> tuple:
    """
    Fetch user record from DynamoDB and return (zorora_tier, usage_dict).
    Returns ('none', {}) if no subscription found.
    """
    try:
        response = _users_table.get_item(
            Key={"user_id": user_id},
            ProjectionExpression="subscriptions, #u",
            ExpressionAttributeNames={"#u": "usage"},
        )
        item = response.get("Item", {})
    except ClientError as e:
        logger.error(f"DynamoDB error fetching user {user_id}: {e}")
        return ("none", {})

    # Find zorora subscription
    subscriptions = item.get("subscriptions", [])
    zorora_tier = "none"
    for sub in subscriptions:
        if sub.get("product") == "zorora":
            zorora_tier = sub.get("tier", "explorer")
            break

    usage = item.get("usage", {})
    return (zorora_tier, usage)


def _increment_usage(user_id: str, counter_key: str) -> int:
    """Atomically increment a usage counter. Returns new value."""
    try:
        response = _users_table.update_item(
            Key={"user_id": user_id},
            UpdateExpression="SET usage.#k = if_not_exists(usage.#k, :zero) + :one",
            ExpressionAttributeNames={"#k": counter_key},
            ExpressionAttributeValues={":zero": 0, ":one": 1},
            ReturnValues="UPDATED_NEW",
        )
        return int(response["Attributes"].get("usage", {}).get(counter_key, 1))
    except ClientError as e:
        logger.error(f"DynamoDB error incrementing usage for {user_id}: {e}")
        return -1


def _check_reset_needed(usage: dict) -> bool:
    """Check if the monthly counter needs resetting."""
    reset_at = usage.get("zorora_queries_reset_at")
    if not reset_at:
        return True
    try:
        reset_dt = datetime.fromisoformat(reset_at.replace("Z", "+00:00"))
        return datetime.now(timezone.utc) >= reset_dt
    except (ValueError, TypeError):
        return True


def _reset_usage(user_id: str):
    """Reset monthly query counter and set next reset date."""

    now = datetime.now(timezone.utc)
    # Reset to first of next month
    if now.month == 12:
        next_reset = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        next_reset = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)

    try:
        _users_table.update_item(
            Key={"user_id": user_id},
            UpdateExpression="SET usage.zorora_research_queries = :zero, usage.zorora_queries_reset_at = :reset",
            ExpressionAttributeValues={
                ":zero": 0,
                ":reset": next_reset.isoformat(),
            },
        )
    except ClientError as e:
        logger.error(f"DynamoDB error resetting usage for {user_id}: {e}")


def get_current_user():
    """
    Extract and validate the current user from the request.
    Returns (payload_dict, None) on success, or (None, error_response) on failure.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, None  # No token — anonymous user

    token = auth_header[7:]
    payload = _decode_token(token)
    if payload is None:
        return None, (jsonify({"error": "Invalid or expired token", "auth_required": True}), 401)

    return payload, None


def require_auth(f):
    """Decorator: require valid JWT token."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        user, error = get_current_user()
        if error:
            return error
        if user is None:
            return jsonify({"error": "Authentication required", "auth_required": True}), 401
        request.user = user
        return f(*args, **kwargs)
    return wrapper


def require_subscription(product="zorora"):
    """Decorator factory: require active subscription for a product."""
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            user, error = get_current_user()
            if error:
                return error
            if user is None:
                return jsonify({"error": "Authentication required", "auth_required": True}), 401

            user_id = user.get("user_id")
            tier, usage = _get_user_subscription(user_id)

            if tier == "none":
                return jsonify({
                    "error": "Zorora subscription required",
                    "subscription_required": True,
                }), 403

            request.user = user
            request.zorora_tier = tier
            request.zorora_usage = usage
            return f(*args, **kwargs)
        return wrapper
    return decorator


def require_research_quota(f):
    """
    Decorator: require subscription AND check research query quota.
    For explorer tier, enforces 10 queries/month limit.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        user, error = get_current_user()
        if error:
            return error
        if user is None:
            return jsonify({"error": "Authentication required", "auth_required": True}), 401

        user_id = user.get("user_id")
        tier, usage = _get_user_subscription(user_id)

        if tier == "none":
            return jsonify({
                "error": "Zorora subscription required",
                "subscription_required": True,
            }), 403

        # Check quota for explorer tier
        limit = TIER_LIMITS.get(tier, {}).get("research_queries_per_month")
        if limit is not None:
            # Check if counter needs monthly reset
            if _check_reset_needed(usage):
                _reset_usage(user_id)
                current_count = 0
            else:
                current_count = int(usage.get("zorora_research_queries", 0))

            if current_count >= limit:
                return jsonify({
                    "error": f"Monthly research query limit reached ({limit} queries/month on {tier} plan)",
                    "quota_exceeded": True,
                    "tier": tier,
                    "limit": limit,
                    "used": current_count,
                }), 429

            # Increment usage counter
            _increment_usage(user_id, "zorora_research_queries")

        request.user = user
        request.zorora_tier = tier
        return f(*args, **kwargs)
    return wrapper


def get_user_team_context(user_id: str) -> dict:
    """
    Fetch user's team context from DynamoDB for Enterprise sharing.
    Returns dict with team_id and can_share_team_content flag.
    """
    try:
        response = _users_table.get_item(
            Key={"user_id": user_id},
            ProjectionExpression="group_id, team_id, subscriptions",
        )
        item = response.get("Item", {})

        # Check if Enterprise tier
        subscriptions = item.get("subscriptions", [])
        is_enterprise = any(
            sub.get("product") == "zorora" and sub.get("tier") == "enterprise"
            for sub in subscriptions
        )

        team_id = item.get("group_id") or item.get("team_id")

        return {
            "team_id": team_id if is_enterprise else None,
            "can_share_team_content": is_enterprise and team_id is not None,
            "is_enterprise": is_enterprise,
        }
    except ClientError as e:
        logger.error(f"DynamoDB error fetching team context for {user_id}: {e}")
        return {"team_id": None, "can_share_team_content": False, "is_enterprise": False}


def get_accessible_user_ids(user_id: str) -> list:
    """
    Returns list of user IDs the current user can access content for.
    - Always includes the user's own ID
    - For Enterprise users with a team, also includes team members' IDs
    """
    accessible = [user_id]

    team_context = get_user_team_context(user_id)
    if team_context["can_share_team_content"] and team_context["team_id"]:
        try:
            # Query for all team members
            response = _users_table.scan(
                FilterExpression="group_id = :team_id OR team_id = :team_id",
                ExpressionAttributeValues={":team_id": team_context["team_id"]},
                ProjectionExpression="user_id",
            )
            team_members = [item["user_id"] for item in response.get("Items", [])]
            accessible.extend(team_members)
            # Remove duplicates while preserving order
            accessible = list(dict.fromkeys(accessible))
        except ClientError as e:
            logger.error(f"DynamoDB error fetching team members: {e}")

    return accessible
