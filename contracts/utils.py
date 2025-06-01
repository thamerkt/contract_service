from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256

# Generate a key pair
def generate_keys():
    key = RSA.generate(2048)
    private_key = key.export_key()
    public_key = key.publickey().export_key()
    return private_key, public_key

# Sign a message
def sign_message(message: str, private_key_bytes: bytes):
    key = RSA.import_key(private_key_bytes)
    h = SHA256.new(message.encode('utf-8'))
    signature = pkcs1_15.new(key).sign(h)
    return signature.hex()

# Verify a signature
def verify_signature(message: str, signature_hex: str, public_key_bytes: bytes):
    key = RSA.import_key(public_key_bytes)
    h = SHA256.new(message.encode('utf-8'))
    try:
        pkcs1_15.new(key).verify(h, bytes.fromhex(signature_hex))
        return True
    except (ValueError, TypeError):
        return False
