# app/utils/geo_utils.py
import httpx
import logging
from typing import Optional, Tuple

from app.core.config import settings

logger = logging.getLogger(__name__)

# --- Reverse Geocode (existing) ---
async def reverse_geocode(lat: float, lon: float) -> str:
    # (Implementation from previous steps remains the same)
    api_key = settings.GOOGLE_GEOCODE_API_KEY
    if not api_key:
        logger.error("Google GEOCODE API key (GOOGLE_GEOCODE_API_KEY) is missing.")
        return "Unknown address (API key missing)"
    base_url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "latlng": f"{lat},{lon}", "key": api_key, "language": "en", "region": "gb",
        "result_type": "street_address|route|locality|political",
    }
    try:
        async with httpx.AsyncClient() as client:
            logger.debug(f"Calling Google Reverse Geocoding API for {lat},{lon}")
            response = await client.get(base_url, params=params)
            response.raise_for_status()
            data = response.json()
        if data.get("status") == "OK" and data.get("results"):
            address = data["results"][0].get("formatted_address", "Unknown address")
            logger.info(f"Reverse geocode successful for {lat},{lon}: {address}")
            return address
        else:
            logger.warning(f"Reverse geocode for {lat},{lon} failed. Status: {data.get('status')}, Error: {data.get('error_message')}")
            return "Unknown address"
    except httpx.RequestError as req_err:
        logger.error(f"HTTP Request Error during reverse geocoding: {req_err}")
        return "Unknown address (Request Error)"
    except httpx.HTTPStatusError as status_err:
        logger.error(f"HTTP Status Error during reverse geocoding: {status_err.response.status_code} - {status_err.response.text[:200]}")
        return "Unknown address (API Error)"
    except Exception as e:
        logger.exception("Unexpected error during reverse geocoding.")
        return "Unknown address (Error)"


# --- NEW: Get Static Map Image (Satellite/Aerial) ---
async def get_static_map_image(lat: float, lon: float, zoom: int = 18, size: str = "640x640") -> Optional[bytes]:
    """Fetches a satellite map image from Google Maps Static API."""
    api_key = settings.MAPS_STATIC_API_KEY
    if not api_key:
        logger.error("Google Maps Static API key (Maps_STATIC_API_KEY) is missing.")
        return None
    base_url = "https://maps.googleapis.com/maps/api/staticmap"
    params = {
        "center": f"{lat},{lon}",
        "zoom": str(zoom),
        "size": size,
        "maptype": "satellite", # Use satellite for aerial view
        "key": api_key,
        "format": "jpg", # Specify format (jpg is common)
    }
    try:
        async with httpx.AsyncClient() as client:
            logger.info(f"Fetching static satellite map image for {lat},{lon} (zoom={zoom})")
            response = await client.get(base_url, params=params)
            response.raise_for_status() # Check for HTTP errors
            # Check content type to ensure it's an image
            content_type = response.headers.get("content-type", "").lower()
            if "image" in content_type:
                logger.debug(f"Successfully fetched satellite image ({len(response.content)} bytes)")
                return response.content
            else:
                logger.warning(f"Maps Static API did not return an image. Content-Type: {content_type}, Content: {response.text[:200]}")
                return None
    except httpx.RequestError as req_err:
        logger.error(f"HTTP Request Error fetching static map: {req_err}")
        return None
    except httpx.HTTPStatusError as status_err:
        logger.error(f"HTTP Status Error fetching static map: {status_err.response.status_code} - {status_err.response.text[:200]}")
        return None
    except Exception as e:
        logger.exception("Unexpected error fetching static map image.")
        return None


# --- NEW: Get Street View Image ---
async def get_street_view_image(lat: float, lon: float, size: str = "640x480", heading: int = 0, pitch: int = 0, fov: int = 90) -> Optional[bytes]:
    """Fetches a Street View image from Google Street View Static API."""
    api_key = settings.MAPS_STATIC_API_KEY
    if not api_key:
        logger.error("Google Street View Static API key (Maps_STATIC_API_KEY) is missing.")
        return None
    base_url = "https://maps.googleapis.com/maps/api/streetview"
    params = {
        "location": f"{lat},{lon}",
        "size": size,
        "heading": str(heading), # Direction camera is facing
        "pitch": str(pitch),     # Up/down angle
        "fov": str(fov),         # Field of view (zoom)
        "key": api_key,
        "source": "outdoor",     # Prioritize outdoor imagery
        "return_error_codes": "true", # Get error details if image unavailable
    }
    try:
        async with httpx.AsyncClient() as client:
            logger.info(f"Fetching Street View image for {lat},{lon}")
            response = await client.get(base_url, params=params)

            # Street View returns 200 OK even if no image found, check status header/content
            if response.status_code == 200 and "image" in response.headers.get("content-type", "").lower():
                logger.debug(f"Successfully fetched Street View image ({len(response.content)} bytes)")
                return response.content
            else:
                # Check for specific error status if available (e.g., ZERO_RESULTS)
                # This might require parsing the response if not an image
                logger.warning(f"Street View API did not return an image for {lat},{lon}. Status: {response.status_code}, Content-Type: {response.headers.get('content-type','')}. Content: {response.text[:200]}")
                return None

    except httpx.RequestError as req_err:
        logger.error(f"HTTP Request Error fetching Street View: {req_err}")
        return None
    except httpx.HTTPStatusError as status_err: # Should technically not happen if return_error_codes=true works
        logger.error(f"HTTP Status Error fetching Street View: {status_err.response.status_code} - {status_err.response.text[:200]}")
        return None
    except Exception as e:
        logger.exception("Unexpected error fetching Street View image.")
        return None