#!/usr/bin/env python3
"""
Test script to verify Ollama connection and DeepSeek R1 model availability.
Run this to check if your LLM integration is working.
"""

import asyncio
import httpx
import os

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-r1")


async def test_ollama_connection():
    """Test basic connectivity to Ollama."""
    print(f"Testing Ollama connection at: {OLLAMA_HOST}")
    print(f"Expected model: {OLLAMA_MODEL}")
    print("-" * 50)
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test 1: Check if Ollama is up
            print("1. Checking Ollama health...")
            response = await client.get(f"{OLLAMA_HOST}/api/tags")
            
            if response.status_code == 200:
                print("   ✓ Ollama is running")
                data = response.json()
                models = [m.get("name", m.get("model")) for m in data.get("models", [])]
                print(f"   Available models: {models}")
                
                # Check if deepseek-r1 is available
                model_available = any(OLLAMA_MODEL in m for m in models)
                if model_available:
                    print(f"   ✓ {OLLAMA_MODEL} is available")
                else:
                    print(f"   ✗ {OLLAMA_MODEL} NOT found!")
                    print(f"   Run: ollama pull {OLLAMA_MODEL}")
                    return False
            else:
                print(f"   ✗ Ollama returned status {response.status_code}")
                return False
            
            # Test 2: Simple chat completion
            print("\n2. Testing chat completion...")
            response = await client.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": "Say 'Ollama is working!' and nothing else.",
                    "stream": False
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                text = result.get("response", "")
                print(f"   ✓ Model responded: {text[:100]}...")
            else:
                print(f"   ✗ Chat failed: {response.text}")
                return False
            
            # Test 3: Test criteria extraction prompt
            print("\n3. Testing criteria extraction prompt...")
            from app.ai.prompts import CRITERIA_EXTRACTION_PROMPT
            
            sample_text = """
            Tender for Construction of Office Building
            Eligibility Criteria:
            1. Minimum average annual turnover of Rs. 10 Crore over last 3 years
            2. Valid GSTIN registration
            3. Experience of similar projects worth Rs. 5 Crore
            """
            
            prompt = CRITERIA_EXTRACTION_PROMPT.format(text=sample_text[:1000])
            
            response = await client.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 1024
                    }
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                text = result.get("response", "")
                print(f"   ✓ Criteria extraction working")
                print(f"   Response preview: {text[:200]}...")
            else:
                print(f"   ✗ Criteria extraction failed: {response.text}")
                return False
            
            print("\n" + "=" * 50)
            print("✓ All tests passed! Ollama + DeepSeek R1 is ready.")
            return True
            
    except httpx.ConnectError as e:
        print(f"\n✗ Cannot connect to Ollama: {e}")
        print(f"\nTroubleshooting:")
        print(f"1. Ensure Ollama is installed: https://ollama.com/download")
        print(f"2. Ensure Ollama is running: ollama serve")
        print(f"3. Pull the model: ollama pull {OLLAMA_MODEL}")
        print(f"4. Check OLLAMA_HOST env var (current: {OLLAMA_HOST})")
        return False
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_ollama_connection())
    exit(0 if success else 1)
