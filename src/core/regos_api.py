import aiohttp
import json
import asyncio
from fastapi import HTTPException
import logging

logger = logging.getLogger("DocVision")

async def regos_async_api_request(endpoint: str, request_data: dict | list, token: str,
                                  timeout_seconds: int = 30) -> dict:
    """
    Make an asynchronous request to the REGOS API.

    Parameters:
        endpoint (str): The specific API endpoint to call.
        request_data (dict | list): The data to send in the request body.
        token (str): Integration token.
        timeout_seconds (int): Timeout in seconds (default: 30).

    Returns:
        dict: The API response.

    Raises:
        HTTPException: For various API errors including timeouts, client errors, and non-200 status codes.
    """
    # Base endpoint URL
    full_url = f"https://integration.regos.uz/gateway/out/{token}/v1/{endpoint}"

    # Required headers
    headers = {
        "Content-Type": "application/json;charset=utf-8"
    }

    # Create timeout configuration
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    try:
        # Make the POST request asynchronously with timeout
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                    full_url,
                    headers=headers,
                    data=json.dumps(request_data)
            ) as response:
                # Check if response is successful (code 200)
                if response.status == 200:
                    data = await response.json()

                    # Check if the API returned an error in the response body
                    if not data.get("ok"):
                        error_info = data.get("result", {})
                        error_code = error_info.get("error", "Unknown")
                        error_desc = error_info.get("description", "Unknown error")

                        logger.error(f"REGOS API error: {error_code} - {error_desc}")
                        raise HTTPException(
                            status_code=400,  # Bad Request - business logic error
                            detail=f"REGOS API error {error_code}: {error_desc}"
                        )

                    return data
                else:
                    logger.info(f"Error: API returned status code {response.status}")
                    raise HTTPException(
                        status_code=502,  # Bad Gateway - external API error
                        detail=f"REGOS API returned status code {response.status}"
                    )

    except asyncio.TimeoutError:
        logger.error(f"Error: Request timed out after {timeout_seconds} seconds")
        raise HTTPException(
            status_code=504,  # Gateway Timeout
            detail=f"REGOS API request timed out after {timeout_seconds} seconds"
        )
    except aiohttp.ClientError as e:
        logger.error(f"Error: Client error occurred - {str(e)}")
        raise HTTPException(
            status_code=502,  # Bad Gateway - external service error
            detail=f"REGOS API client error: {str(e)}"
        )

