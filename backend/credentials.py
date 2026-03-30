import os
import json
import tempfile
from typing import Dict, Optional, Any
from pydantic import BaseModel
import asyncio
import aiohttp


class CredentialTest(BaseModel):
    """Model for credential test results"""
    provider: str
    status: str  # "valid", "invalid", "error", "not_configured"
    message: str
    error_details: Optional[str] = None


class CredentialStorage(BaseModel):
    """Model for storing credentials"""
    openai_key: Optional[str] = None
    anthropic_key: Optional[str] = None
    vertex_json: Optional[str] = None  # JSON string for Vertex AI
    azure_openai_key: Optional[str] = None
    azure_openai_endpoint: Optional[str] = None
    azure_openai_deployment: Optional[str] = None
    azure_openai_api_version: Optional[str] = None


async def test_openai_credentials(api_key: str) -> CredentialTest:
    """Test OpenAI API credentials"""
    # Skip standard format check when using Azure key as OPENAI_API_KEY
    azure_mode = os.getenv('OPENAI_API_TYPE', '').lower() == 'azure' or os.getenv('AZURE_OPENAI_API_KEY')
    
    if not api_key:
        return CredentialTest(
            provider="openai",
            status="not_configured",
            message="OPENAI_API_KEY not set in environment"
        )
    
    # If in Azure mode, don't test OpenAI endpoint (use Azure test instead)
    if azure_mode:
        return CredentialTest(
            provider="openai",
            status="valid",
            message="Using Azure OpenAI (configured via OPENAI_API_TYPE=azure)"
        )
    
    # Standard OpenAI key format check
    if not api_key.startswith('sk-'):
        return CredentialTest(
            provider="openai",
            status="invalid",
            message="Invalid OpenAI API key format (should start with 'sk-')"
        )
    
    try:
        # Test with a simple API call
        url = "https://api.openai.com/v1/models"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        connector = aiohttp.TCPConnector(ssl=False)  # Disable SSL verification for testing
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return CredentialTest(
                        provider="openai",
                        status="valid",
                        message="OpenAI credentials are valid"
                    )
                elif response.status == 401:
                    return CredentialTest(
                        provider="openai",
                        status="invalid",
                        message="Invalid OpenAI API key"
                    )
                else:
                    error_text = await response.text()
                    return CredentialTest(
                        provider="openai",
                        status="error",
                        message="Error testing OpenAI credentials",
                        error_details=f"HTTP {response.status}: {error_text}"
                    )
                    
    except Exception as e:
        return CredentialTest(
            provider="openai",
            status="error",
            message="Error connecting to OpenAI API",
            error_details=str(e)
        )


async def test_anthropic_credentials(api_key: str) -> CredentialTest:
    """Test Anthropic API credentials"""
    if not api_key or not api_key.startswith('sk-ant-'):
        return CredentialTest(
            provider="anthropic",
            status="invalid",
            message="Invalid API key format"
        )
    
    try:
        # Test with a simple API call to get available models or make a minimal request
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        # Make a minimal test request
        data = {
            "model": "claude-3-haiku-20240307",
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "Hi"}]
        }
        
        connector = aiohttp.TCPConnector(ssl=False)  # Disable SSL verification for testing
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    return CredentialTest(
                        provider="anthropic",
                        status="valid",
                        message="Anthropic credentials are valid"
                    )
                elif response.status == 401:
                    return CredentialTest(
                        provider="anthropic",
                        status="invalid",
                        message="Invalid Anthropic API key"
                    )
                else:
                    error_text = await response.text()
                    return CredentialTest(
                        provider="anthropic",
                        status="error",
                        message="Error testing Anthropic credentials",
                        error_details=f"HTTP {response.status}: {error_text}"
                    )
                    
    except Exception as e:
        return CredentialTest(
            provider="anthropic",
            status="error",
            message="Error connecting to Anthropic API",
            error_details=str(e)
        )


async def test_vertex_credentials(service_account_json: str) -> CredentialTest:
    """Test Google Vertex AI credentials"""
    try:
        # Parse the JSON to validate format
        try:
            credentials_data = json.loads(service_account_json)
            required_fields = ['type', 'project_id', 'private_key', 'client_email']
            
            for field in required_fields:
                if field not in credentials_data:
                    return CredentialTest(
                        provider="vertex",
                        status="invalid",
                        message=f"Missing required field: {field}"
                    )
                    
            if credentials_data.get('type') != 'service_account':
                return CredentialTest(
                    provider="vertex",
                    status="invalid",
                    message="Invalid service account type"
                )
                
        except json.JSONDecodeError as e:
            return CredentialTest(
                provider="vertex",
                status="invalid",
                message="Invalid JSON format",
                error_details=str(e)
            )
        
        # Try to use the credentials to make a simple API call
        try:
            from google.oauth2 import service_account
            from google.auth.transport.requests import Request
            import google.auth
            
            # Create credentials from the JSON
            credentials = service_account.Credentials.from_service_account_info(
                credentials_data,
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
            
            # Test token refresh
            request = Request()
            credentials.refresh(request)
            
            if credentials.token:
                return CredentialTest(
                    provider="vertex",
                    status="valid",
                    message="Vertex AI credentials are valid",
                )
            else:
                return CredentialTest(
                    provider="vertex",
                    status="error",
                    message="Unable to obtain access token"
                )
                
        except ImportError:
            return CredentialTest(
                provider="vertex",
                status="error",
                message="Google Cloud libraries not installed",
                error_details="Run: pip install google-cloud-aiplatform"
            )
        except Exception as e:
            return CredentialTest(
                provider="vertex",
                status="error",
                message="Error validating Vertex AI credentials",
                error_details=str(e)
            )
            
    except Exception as e:
        return CredentialTest(
            provider="vertex",
            status="error",
            message="Unexpected error testing Vertex AI credentials",
            error_details=str(e)
        )


async def test_all_credentials() -> Dict[str, CredentialTest]:
    """Test all available credentials from environment variables.
    
    Supports dynamic provider fallback:
    - Tests OpenAI first
    - Tests primary Azure OpenAI (AZURE_OPENAI_*)
    - Tests fallback Azure OpenAI (AZURE_OPENAI_FALLBACK_*)
    - If primary Azure fails but fallback succeeds, promotes fallback to active
    """
    results = {}
    
    # Test OpenAI
    openai_key = os.getenv('OPENAI_API_KEY')
    if openai_key:
        results['openai'] = await test_openai_credentials(openai_key)
    else:
        results['openai'] = CredentialTest(
            provider="openai",
            status="not_configured",
            message="OPENAI_API_KEY not set in environment"
        )
    
    # Test Azure OpenAI (primary)
    azure_key = os.getenv('AZURE_OPENAI_API_KEY')
    azure_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
    if azure_key and azure_endpoint:
        azure_deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT', '')
        azure_api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-12-01-preview')
        results['azure_openai'] = await test_azure_openai_credentials(
            azure_key, azure_endpoint, azure_deployment, azure_api_version
        )
    else:
        results['azure_openai'] = CredentialTest(
            provider="azure_openai",
            status="not_configured",
            message="AZURE_OPENAI_API_KEY or AZURE_OPENAI_ENDPOINT not set"
        )
    
    # Test Azure OpenAI (fallback)
    fb_key = os.getenv('AZURE_OPENAI_FALLBACK_API_KEY')
    fb_endpoint = os.getenv('AZURE_OPENAI_FALLBACK_ENDPOINT')
    if fb_key and fb_endpoint:
        fb_deployment = os.getenv('AZURE_OPENAI_FALLBACK_DEPLOYMENT', '')
        fb_api_version = os.getenv('AZURE_OPENAI_FALLBACK_API_VERSION', '2024-12-01-preview')
        results['azure_openai_fallback'] = await test_azure_openai_credentials(
            fb_key, fb_endpoint, fb_deployment, fb_api_version
        )
        # Override provider name for clarity
        results['azure_openai_fallback'].provider = "azure_openai_fallback"
    else:
        results['azure_openai_fallback'] = CredentialTest(
            provider="azure_openai_fallback",
            status="not_configured",
            message="AZURE_OPENAI_FALLBACK_* not set (optional)"
        )
    
    # Dynamic fallback: if primary Azure failed but fallback is valid, promote it
    if (results['azure_openai'].status != 'valid' and 
            results['azure_openai_fallback'].status == 'valid' and
            fb_key and fb_endpoint):
        _promote_azure_fallback(fb_key, fb_endpoint, fb_deployment, fb_api_version)
        results['azure_openai'] = CredentialTest(
            provider="azure_openai",
            status="valid",
            message=f"Using fallback Azure config ({fb_deployment or 'default'})"
        )
    
    # Test Anthropic
    anthropic_key = os.getenv('ANTHROPIC_API_KEY')
    if anthropic_key:
        results['anthropic'] = await test_anthropic_credentials(anthropic_key)
    else:
        results['anthropic'] = CredentialTest(
            provider="anthropic",
            status="not_configured",
            message="ANTHROPIC_API_KEY not set in environment"
        )
    
    # Test Vertex AI
    vertex_creds = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if vertex_creds and os.path.exists(vertex_creds):
        try:
            with open(vertex_creds, 'r') as f:
                vertex_json = f.read()
            results['vertex'] = await test_vertex_credentials(vertex_json)
        except Exception as e:
            results['vertex'] = CredentialTest(
                provider="vertex",
                status="error",
                message="Error reading Vertex AI credentials file",
                error_details=str(e)
            )
    else:
        results['vertex'] = CredentialTest(
            provider="vertex",
            status="not_configured",
            message="GOOGLE_APPLICATION_CREDENTIALS not set or file not found"
        )
    
    return results


async def test_azure_openai_credentials(
    api_key: str,
    endpoint: str,
    deployment: str = "",
    api_version: str = "2024-12-01-preview"
) -> CredentialTest:
    """Test Azure OpenAI API credentials"""
    if not api_key:
        return CredentialTest(
            provider="azure_openai",
            status="invalid",
            message="Azure OpenAI API key is empty"
        )
    if not endpoint:
        return CredentialTest(
            provider="azure_openai",
            status="invalid",
            message="Azure OpenAI endpoint is empty"
        )
    if not deployment:
        # If no deployment specified, try to get from env
        deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt4o')

    try:
        # Test by making a minimal completion request
        base = endpoint.rstrip('/')
        url = f"{base}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
        headers = {
            "api-key": api_key,
            "Content-Type": "application/json"
        }
        data = {
            "messages": [{"role": "user", "content": "Hi"}],
            "max_completion_tokens": 5
        }

        verify_ssl = os.getenv('AZURE_OPENAI_VERIFY_SSL', 'true').lower() != 'false'
        connector = aiohttp.TCPConnector(ssl=verify_ssl)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    return CredentialTest(
                        provider="azure_openai",
                        status="valid",
                        message="Azure OpenAI credentials are valid"
                    )
                elif response.status == 400:
                    # 400 can mean max_tokens reached (credentials valid, just hit limit)
                    # or a genuine bad request. Check the error message.
                    error_text = await response.text()
                    if 'max_tokens' in error_text or 'model output limit' in error_text or 'token' in error_text.lower():
                        return CredentialTest(
                            provider="azure_openai",
                            status="valid",
                            message="Azure OpenAI credentials are valid (token limit hit during test)"
                        )
                    return CredentialTest(
                        provider="azure_openai",
                        status="error",
                        message="Azure OpenAI request error",
                        error_details=f"HTTP 400: {error_text}"
                    )
                elif response.status == 401:
                    return CredentialTest(
                        provider="azure_openai",
                        status="invalid",
                        message="Invalid Azure OpenAI API key"
                    )
                elif response.status == 404:
                    return CredentialTest(
                        provider="azure_openai",
                        status="error",
                        message=f"Azure OpenAI deployment '{deployment}' not found. Check your deployment name.",
                        error_details=f"HTTP 404: {await response.text()}"
                    )
                else:
                    error_text = await response.text()
                    return CredentialTest(
                        provider="azure_openai",
                        status="error",
                        message="Error testing Azure OpenAI credentials",
                        error_details=f"HTTP {response.status}: {error_text}"
                    )

    except Exception as e:
        return CredentialTest(
            provider="azure_openai",
            status="error",
            message="Error connecting to Azure OpenAI API",
            error_details=str(e)
        )


def _promote_azure_fallback(fb_key: str, fb_endpoint: str, fb_deployment: str, fb_api_version: str):
    """Promote fallback Azure credentials to primary env vars.
    
    Called when primary Azure fails but fallback succeeds, so that 
    downstream code (llm_provider, cmbagent) uses the working config.
    """
    os.environ['AZURE_OPENAI_API_KEY'] = fb_key
    os.environ['AZURE_OPENAI_ENDPOINT'] = fb_endpoint
    if fb_deployment:
        os.environ['AZURE_OPENAI_DEPLOYMENT'] = fb_deployment
    if fb_api_version:
        os.environ['AZURE_OPENAI_API_VERSION'] = fb_api_version
    
    # Also set OPENAI_API_KEY for tools that expect it (ChromaDB, etc.)
    os.environ['OPENAI_API_KEY'] = fb_key
    os.environ['OPENAI_API_TYPE'] = 'azure'
    os.environ['OPENAI_API_BASE'] = fb_endpoint
    
    # Refresh LLM provider singleton if available
    try:
        from cmbagent.llm_provider import get_provider_config
        get_provider_config().refresh()
    except ImportError:
        pass


def store_credentials_in_env(credentials: CredentialStorage) -> Dict[str, str]:
    """Store credentials in environment variables (session only)"""
    updates = {}
    
    if credentials.openai_key:
        os.environ['OPENAI_API_KEY'] = credentials.openai_key
        updates['OPENAI_API_KEY'] = 'Updated'
    
    if credentials.anthropic_key:
        os.environ['ANTHROPIC_API_KEY'] = credentials.anthropic_key
        updates['ANTHROPIC_API_KEY'] = 'Updated'
    
    if credentials.vertex_json:
        # Write to temporary file and set environment variable
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                f.write(credentials.vertex_json)
                temp_path = f.name
            
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = temp_path
            updates['GOOGLE_APPLICATION_CREDENTIALS'] = f'Updated (temp file: {temp_path})'
        except Exception as e:
            updates['GOOGLE_APPLICATION_CREDENTIALS'] = f'Error: {str(e)}'
    
    if credentials.azure_openai_key:
        os.environ['AZURE_OPENAI_API_KEY'] = credentials.azure_openai_key
        os.environ['OPENAI_API_KEY'] = credentials.azure_openai_key
        os.environ['OPENAI_API_TYPE'] = 'azure'
        # ChromaDB environment variables for Azure embeddings
        os.environ['CHROMA_OPENAI_API_KEY'] = credentials.azure_openai_key
        os.environ['CHROMA_OPENAI_API_TYPE'] = 'azure'
        updates['AZURE_OPENAI_API_KEY'] = 'Updated'
        updates['OPENAI_API_TYPE'] = 'azure'

    if credentials.azure_openai_endpoint:
        os.environ['AZURE_OPENAI_ENDPOINT'] = credentials.azure_openai_endpoint
        os.environ['OPENAI_API_BASE'] = credentials.azure_openai_endpoint
        # ChromaDB Azure endpoint
        os.environ['CHROMA_OPENAI_API_BASE'] = credentials.azure_openai_endpoint
        updates['AZURE_OPENAI_ENDPOINT'] = 'Updated'

    if credentials.azure_openai_deployment:
        os.environ['AZURE_OPENAI_DEPLOYMENT'] = credentials.azure_openai_deployment
        # ChromaDB uses this for embedding model
        os.environ['CHROMA_OPENAI_MODEL'] = credentials.azure_openai_deployment
        updates['AZURE_OPENAI_DEPLOYMENT'] = 'Updated'

    if credentials.azure_openai_api_version:
        os.environ['AZURE_OPENAI_API_VERSION'] = credentials.azure_openai_api_version
        os.environ['OPENAI_API_VERSION'] = credentials.azure_openai_api_version
        # ChromaDB Azure API version
        os.environ['CHROMA_OPENAI_API_VERSION'] = credentials.azure_openai_api_version
        updates['AZURE_OPENAI_API_VERSION'] = 'Updated'

    return updates