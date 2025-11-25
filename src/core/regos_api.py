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
                        err_result = data.get("result", {})
                        error_code = err_result.get("error", "Unknown")
                        error_desc = err_result.get("description", "Unknown error")
                        err_msg = f"REGOS API error: {error_code} - {error_desc}"

                        logger.error(err_msg)
                        raise HTTPException(status_code=400, detail=err_msg)

                    # Check if the API returned a valid response
                    result = data.get("result", "There is no result in response")
                    if not isinstance(result, (dict, list)):
                        raise HTTPException(status_code=502, detail=f"Invalid response from REGOS API: {result}")

                    return data

                else:
                    err_msg = f"Error: API returned status code {response.status}"
                    logger.info(err_msg)
                    raise HTTPException(status_code=502, detail=f"REGOS API returned status code {response.status}")

    except asyncio.TimeoutError:
        err_msg = f"REGOS API Error: Request timed out after {timeout_seconds} seconds"
        logger.error(err_msg)
        raise HTTPException(status_code=504, detail=err_msg)

    except aiohttp.ClientError as e:
        err_msg = f"REGOS API Error: Client error occurred - {str(e)}"
        logger.error(err_msg)
        raise HTTPException(status_code=502, detail=err_msg)

    except Exception as e:
        err_msg = f"REGOS API Error: {e}"
        logger.error(err_msg)
        raise HTTPException(status_code=502, detail=err_msg)
