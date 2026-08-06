import logging
import os
import time

import jwt

logger = logging.getLogger(__name__)

class TokenService:
    """
    Service to generate internal JWT tokens for rule-triggered actions.
    This allows the Rule Worker to call other microservices (like Sensor Data Service)
    with the necessary permissions.
    """
    def __init__(self):
        self.secret_key = os.getenv("SECRET_KEY")
        self.algorithm = os.getenv("ALGORITHM", "HS256")
        
        if not self.secret_key:
            logger.error("SECRET_KEY not found in environment variables. Actions requiring auth will fail.")

    def generate_service_token(self, expires_in: int = 60) -> str | None:
        """
        Generates a short-lived JWT token with administrative permissions
        to allow internal service-to-service communication.
        """
        if not self.secret_key:
            return None

        now = int(time.time())
        payload = {
            "sub": "rule_worker_internal",
            "iat": now,
            "exp": now + expires_in,
            "jti": f"rule_worker_{now}",
            "g_perms": {
                "w_all": True,  # Give internal worker broad permissions
                "r_all": True
            },
            "access": {}
        }

        try:
            return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        except Exception as e:
            logger.error(f"Failed to generate service token: {e}")
            return None
