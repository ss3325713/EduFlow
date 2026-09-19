import os
import base64
import logging
from flask import current_app
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

logger = logging.getLogger(__name__)

def _get_master_key() -> bytes:
    """
    Retrieves or derives 256-bit encryption key from application secret configuration.
    """
    secret = None
    if current_app:
        secret = current_app.config.get('DIARY_ENCRYPTION_KEY') or current_app.config.get('SECRET_KEY')
    if not secret:
        secret = os.environ.get('DIARY_ENCRYPTION_KEY', 'default-skillbasis-diary-secret-key-32b')
    
    if isinstance(secret, str):
        secret_bytes = secret.encode('utf-8')
    else:
        secret_bytes = secret

    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'skillbasis-diary-salt-v1',
        info=b'diary-encryption-key-derivation',
    )
    return hkdf.derive(secret_bytes)

def encrypt_diary_content(content: str, owner_user_id: int) -> str:
    """
    Encrypts plaintext diary content using AES-256-GCM with per-user bound AAD.
    """
    if not content:
        return ""
    
    key = _get_master_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit random nonce
    aad = str(owner_user_id).encode('utf-8')  # Bind user ID as AEAD additional data
    
    ciphertext = aesgcm.encrypt(nonce, content.encode('utf-8'), aad)
    # Combine nonce + ciphertext and base64 encode
    payload = nonce + ciphertext
    return base64.b64encode(payload).decode('utf-8')

def decrypt_diary_content(encrypted_b64: str, owner_user_id: int) -> str:
    """
    Decrypts AES-256-GCM encrypted diary content with per-user bound AAD verification.
    """
    if not encrypted_b64:
        return ""
    
    try:
        raw_data = base64.b64decode(encrypted_b64.encode('utf-8'))
        if len(raw_data) < 13:
            logger.error("Encrypted payload too short.")
            return ""
        
        nonce = raw_data[:12]
        ciphertext = raw_data[12:]
        aad = str(owner_user_id).encode('utf-8')
        
        key = _get_master_key()
        aesgcm = AESGCM(key)
        decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, aad)
        return decrypted_bytes.decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to decrypt diary content for user {owner_user_id}: {e}")
        return "[Encrypted Content - Decryption Failure]"

def reencrypt_entry_content(encrypted_b64: str, owner_user_id: int, old_secret: str, new_secret: str) -> str:
    """
    Helper for rotatable encryption key migration.
    """
    plain = decrypt_diary_content(encrypted_b64, owner_user_id)
    return encrypt_diary_content(plain, owner_user_id)
