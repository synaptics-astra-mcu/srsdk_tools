from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Cipher import AES
from Crypto.Hash import SHA384, SHA256
from Crypto.Util import Counter

from Crypto.Random import get_random_bytes
from Crypto.Util.number import long_to_bytes

from .err import *
from .type import StoreParamsT

CRYPTO_AES_KEY_LEN     = 32
CRYPTO_IV_LEN          = 16
CRYPTO_NONCE_LEN       = 12
CRYPTO_CHECKSUM_LEN    = 48
CRYPTO_PUB_MODULUS_LEN = 512
CRYPTO_RSA_SIGN_LEN    = 512

HEX_BASE               = 16
ADDRESS_BYTE_SIZE      = 4
IV_BIT_SIZE            = 128

def crypto_get_rsa_modulus(params: StoreParamsT) -> bool:
    '''
        This function retrieves n from the public key
        and stores it as bytes in the params object
    '''
    if params.payload_input_file == '':
        raise ErrInvalidParam('Did not provide payload input file')
    
    try:
        with open(params.payload_input_file, 'rb') as pub_key:
            cert = pub_key.read()
        key = RSA.import_key(cert)

        if key.n.bit_length() <= 0:
            raise ErrCryptoRsaKey('Invalid n value')

        p_body = long_to_bytes(key.n)
        body_len = len(p_body)
        if body_len == 0:
            raise ErrCryptoRsaKey('Invalid n value')
        
        params.p_body = p_body
        params.body_len = body_len
    except:
        raise ErrFileOpen('Cannot open the provided file')
    
    return True

def crypto_get_random(length: int) -> bytes:
    '''
        This function returns random bytes based on the length provided
    '''
    return get_random_bytes(length)

def crypto_sha256(msg: bytes) -> bytes:
    '''
        This function return the sha256 of the bytes given
    '''
    hashed_data = SHA256.new(msg).digest()
    return hashed_data

def crypto_aes256_enc(plaintext: bytes, key: bytes, iv: bytes = 0x00, mode = AES.MODE_CBC,
                      nonce: bytes = 0x00, start_address=0x00, address_offset=0x00) -> bytes:
    '''
        This function encrypt the plaintext based on the key and the iv using
        aes mode cbc
    '''
    if mode == AES.MODE_CTR:                                                    # mode for AXI Crypto OTF
        start_vaddr = (int(start_address, HEX_BASE) + int(address_offset, HEX_BASE)) & 0xffffffff
        start_counter = start_vaddr >> 4
        start_counter = start_counter.to_bytes(ADDRESS_BYTE_SIZE, 'big')        # convert to byte array
        iv_bytes = nonce + start_counter                                        # concatenate nonce and address
        counter = Counter.new(nbits=IV_BIT_SIZE, initial_value=int.from_bytes(iv_bytes, "big"),
                              little_endian=False)                              # Create a counter object
        cipher = AES.new(key, AES.MODE_CTR, counter=counter)                    # Create the cipher

    else:
        cipher = AES.new(key, mode, iv=iv)
        # Adding padding
        while len(plaintext) % 16 != 0:
            plaintext += b'\x00'

    return cipher.encrypt(plaintext)                                            # Encrypt

def crypto_aes256_dec(ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
    '''
        This function decrypt the ciphertext based on the key and the iv using
        aes mode cbc
    '''
    cipher = AES.new(key, AES.MODE_CBC, iv=iv)
    # removing the NULL padding, if exists
    return cipher.decrypt(ciphertext).rstrip(b'\x00')

def crypto_rsa_sign(msg: bytes, rsa_key_path: str) -> bytes:
    '''
        This functions signs a message using a private rsa
        key using the SHA384 digest
    '''
    with open(rsa_key_path, 'rb') as pub_key:
        cert = pub_key.read()
    
    key = RSA.import_key(cert)
    signature = pkcs1_15.new(key).sign(SHA384.new(msg))
    return signature

def crypto_sha384(msg: bytes) -> bytes:
    '''
        This function return the sha384 of the bytes given
    '''
    hashed_data = SHA384.new(msg).digest()
    return hashed_data

