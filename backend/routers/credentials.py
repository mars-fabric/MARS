"""
API credentials management endpoints.
"""

import time
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/credentials", tags=["Credentials"])

# Import credentials module (loaded at runtime to avoid import errors)
_credentials_module = None


def _get_credentials_module():
    """Lazy load credentials module."""
    global _credentials_module
    if _credentials_module is None:
        try:
            from credentials import (
                test_all_credentials,
                test_openai_credentials,
                test_anthropic_credentials,
                test_vertex_credentials,
                test_azure_openai_credentials,
                store_credentials_in_env,
                CredentialStorage,
                CredentialTest
            )
            _credentials_module = {
                "test_all_credentials": test_all_credentials,
                "test_openai_credentials": test_openai_credentials,
                "test_anthropic_credentials": test_anthropic_credentials,
                "test_vertex_credentials": test_vertex_credentials,
                "test_azure_openai_credentials": test_azure_openai_credentials,
                "store_credentials_in_env": store_credentials_in_env,
                "CredentialStorage": CredentialStorage,
                "CredentialTest": CredentialTest,
            }
        except ImportError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Credentials module not available: {str(e)}"
            )
    return _credentials_module


@router.get("/test-all")
async def test_all_api_credentials():
    """Test all configured API credentials."""
    try:
        creds = _get_credentials_module()
        results = await creds["test_all_credentials"]()
        return {
            "status": "success",
            "results": results,
            "timestamp": time.time()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error testing credentials: {str(e)}")


@router.post("/test")
async def test_specific_credentials(credentials: dict):
    """Test specific credentials provided by the user."""
    try:
        creds = _get_credentials_module()
        CredentialStorage = creds["CredentialStorage"]

        # Parse credentials into storage object
        storage = CredentialStorage(**credentials)
        results = {}

        if storage.openai_key:
            results['openai'] = await creds["test_openai_credentials"](storage.openai_key)

        if storage.anthropic_key:
            results['anthropic'] = await creds["test_anthropic_credentials"](storage.anthropic_key)

        if storage.vertex_json:
            results['vertex'] = await creds["test_vertex_credentials"](storage.vertex_json)

        if storage.azure_openai_key and storage.azure_openai_endpoint:
            results['azure_openai'] = await creds["test_azure_openai_credentials"](
                storage.azure_openai_key,
                storage.azure_openai_endpoint,
                storage.azure_openai_deployment or "",
                storage.azure_openai_api_version or "2024-12-01-preview"
            )

        return {
            "status": "success",
            "results": results,
            "timestamp": time.time()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error testing credentials: {str(e)}")


@router.post("/store")
async def store_api_credentials(credentials: dict):
    """Store API credentials in environment variables (session only)."""
    try:
        creds = _get_credentials_module()
        CredentialStorage = creds["CredentialStorage"]

        # Parse credentials into storage object
        storage = CredentialStorage(**credentials)
        updates = creds["store_credentials_in_env"](storage)

        # Test the newly stored credentials
        test_results = await creds["test_all_credentials"]()

        return {
            "status": "success",
            "message": "Credentials stored successfully",
            "updates": updates,
            "test_results": test_results,
            "timestamp": time.time()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error storing credentials: {str(e)}")


@router.get("/status")
async def get_credentials_status():
    """Get current status of all API credentials."""
    try:
        creds = _get_credentials_module()
        results = await creds["test_all_credentials"]()

        # Determine which LLM providers are usable
        openai_valid = results.get('openai') and results['openai'].status == 'valid'
        azure_valid = results.get('azure_openai') and results['azure_openai'].status == 'valid'
        has_llm_provider = openai_valid or azure_valid
        
        # Determine active provider
        if openai_valid:
            active_provider = 'openai'
        elif azure_valid:
            active_provider = 'azure'
        else:
            active_provider = 'none'

        # Create summary status
        summary = {
            "total": len(results),
            "valid": sum(1 for r in results.values() if r.status == "valid"),
            "invalid": sum(1 for r in results.values() if r.status == "invalid"),
            "not_configured": sum(1 for r in results.values() if r.status == "not_configured"),
            "errors": sum(1 for r in results.values() if r.status == "error"),
            "has_llm_provider": has_llm_provider,
            "active_provider": active_provider
        }

        return {
            "status": "success",
            "summary": summary,
            "results": results,
            "timestamp": time.time()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting credentials status: {str(e)}")
