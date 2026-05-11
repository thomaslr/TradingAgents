import os
import time
import socket
import logging
import httpx
import subprocess
import platform
from typing import Optional
from wakeonlan import send_magic_packet

logger = logging.getLogger(__name__)

def ping(host: str) -> bool:
    """
    Returns True if host (str) responds to a ping request.
    """
    # Option for the number of packets as a function of OS
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    # Building the command. Ex: "ping -c 1 google.com"
    command = ['ping', param, '1', host]
    
    try:
        return subprocess.call(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
    except Exception:
        return False

async def check_ollama_api(url: str) -> bool:
    """
    Returns True if the Ollama API responds with a 200 OK.
    """
    # Convert /v1/chat to /api/tags for a lightweight check
    base_url = url.split("/v1")[0]
    tags_url = f"{base_url}/api/tags"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(tags_url, timeout=2.0)
            return response.status_code == 200
    except Exception:
        return False

async def ensure_ollama_ready(
    ollama_url: str, 
    mac_address: Optional[str] = None, 
    timeout: int = 60,
    status_callback = None
) -> bool:
    """
    Ensures the Ollama server is awake and responding.
    If mac_address is provided and the server is down, sends a WOL packet.
    """
    # 1. Immediate Probe
    if await check_ollama_api(ollama_url):
        logger.info("Ollama is already awake and responding.")
        return True

    # 2. If no MAC address, we can't do anything else
    if not mac_address:
        logger.warning(f"Ollama at {ollama_url} is unreachable and no MAC address is configured.")
        return False

    # 3. Send WOL Packet
    logger.info(f"Ollama unreachable. Sending WOL magic packet to {mac_address}...")
    if status_callback:
        status_callback(f"Waking up remote server ({mac_address})...")
    
    try:
        send_magic_packet(mac_address)
    except Exception as e:
        logger.error(f"Failed to send WOL packet: {e}")
        return False

    # 4. Polling Loop
    # Extract IP from URL
    try:
        # Simple extraction: http://192.168.0.100:11434/v1 -> 192.168.0.100
        ip = ollama_url.split("//")[1].split(":")[0]
    except Exception:
        ip = None

    start_time = time.time()
    while time.time() - start_time < timeout:
        # Check Ping first (fast)
        if ip and ping(ip):
            if status_callback:
                status_callback("Server hardware is awake. Waiting for Ollama service...")
            
            # Then check API (ready)
            if await check_ollama_api(ollama_url):
                logger.info("Ollama is now ready!")
                if status_callback:
                    status_callback("Ollama is ready!")
                return True
        else:
            # If we don't have an IP or ping fails, just check the API directly
            if await check_ollama_api(ollama_url):
                logger.info("Ollama is now ready!")
                return True
        
        time.sleep(3)
    
    logger.error(f"Ollama failed to become ready within {timeout} seconds.")
    return False
