import pandas as pd
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

# Clave para AES-ECB (debe ser 16, 24 o 32 bytes)
key = b'secret-key-12345'  # 16 bytes

# Función para desencriptar una celda
def decrypt_product_account(value):
    if pd.isnull(value):
        return value
    try:
        # 1. Decode Base64
        encrypted_data = base64.b64decode(value)
        # 2. Create AES cipher in ECB mode
        cipher = AES.new(key, AES.MODE_ECB)
        # 3. Decrypt and unpad
        decrypted_data = unpad(cipher.decrypt(encrypted_data), AES.block_size)
        # 4. Convert to UTF-8 string
        return decrypted_data.decode('utf-8')
    except Exception as e:
        return f"[ERROR: {str(e)}]"