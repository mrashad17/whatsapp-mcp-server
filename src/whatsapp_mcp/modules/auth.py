"""Authentication module for WhatsApp MCP Server."""

import asyncio
import logging
import os
from typing import Dict, Tuple, Any

from dotenv import load_dotenv


# Import the WhatsApp API client
from whatsapp_api_client_python.API import GreenApi

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class WhatsAppClient:
    """WhatsApp client implementation using whatsapp-api-client-python."""

    def __init__(self) -> None:
        self.is_authenticated = False
        self.session_data: Dict[str, Any] = {}
        self.client = None
        self.qr_code = None
        self.state = "DISCONNECTED"

    async def initialize(self) -> bool:
        """Initialize the client."""
        logger.info("Initializing WhatsApp client")
        try:
            # Initialize the WhatsApp API client with GreenAPI credentials from environment variables
            id_instance = os.getenv("GREENAPI_ID_INSTANCE")
            api_token_instance = os.getenv("GREENAPI_API_TOKEN")

            if not id_instance or not api_token_instance:
                logger.error(
                    "Missing required environment variables: GREENAPI_ID_INSTANCE or GREENAPI_API_TOKEN"
                )
                return False

            client = GreenApi(
                idInstance=id_instance, apiTokenInstance=api_token_instance
            )

            # Check the credentials and the instance state before reporting
            # success. Previously any value "worked" until the first send failed.
            response = await asyncio.to_thread(client.account.getStateInstance)
            if getattr(response, "code", None) != 200:
                logger.error(
                    "GreenAPI rejected the credentials (HTTP %s)",
                    getattr(response, "code", None),
                )
                return False
            self.state = (response.data or {}).get("stateInstance", "unknown")
            if self.state != "authorized":
                logger.error("GreenAPI instance is not ready: %s", self.state)
                return False

            self.client = client
            self.is_authenticated = True
            return True
        except Exception as e:
            # Exception text can include the request URL, which contains the
            # API token, so only the exception type is logged.
            logger.error("Failed to initialize WhatsApp client: %s", type(e).__name__)
            return False


class AuthManager:
    """Manager for authentication-related operations."""

    def __init__(self) -> None:
        self.session: WhatsAppClient | None = None

    async def open_session(self) -> Tuple[bool, str]:
        """Open a new session."""
        if self.session:
            return False, "Session already exists"

        client = WhatsAppClient()
        success = await client.initialize()

        if success:
            self.session = client
            return True, "Session created successfully (GreenAPI instance authorized)"

        return False, (
            "Failed to create session: check GREENAPI_ID_INSTANCE and "
            f"GREENAPI_API_TOKEN, and that the instance is authorized (state: {client.state})"
        )

    def is_authenticated(self) -> bool:
        """Check if a session is authenticated."""
        return self.session is not None

    def get_client(self) -> WhatsAppClient | None:
        """Get the client for a session."""
        return self.session


# Create a singleton instance
auth_manager = AuthManager()
