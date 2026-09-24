from .type import StoreParamsT
from .crypto import *

IMAGE_TYPE_K0_SYNA = 0x00010001
K0_SYNA            = "K0_SYNA"
IMAGE_TYPE_K0_OEM  = 0x00010002
K0_OEM             = "K0_OEM"

IMAGE_TYPE_K0_TEE  = 0x2
K0_TEE             = "K0_TEE"
IMAGE_TYPE_K0_REE  = 0x3
K0_REE             = "K0_REE"

SIZE_OF_ROOT_RSA_HEADER = 0
SIZE_OF_ROOT_RSA_BODY = 512
SIZE_OF_ROOT_RSA_STORE = SIZE_OF_ROOT_RSA_HEADER + SIZE_OF_ROOT_RSA_BODY
SIZE_OF_IMAGE_TYPE_K0_BOOT = SIZE_OF_ROOT_RSA_STORE
SIZE_OF_IMAGE_TYPE_K0_TEE = SIZE_OF_ROOT_RSA_STORE
SIZE_OF_IMAGE_TYPE_K0_REE = SIZE_OF_ROOT_RSA_STORE

def check_params(params: StoreParamsT) -> None:
    '''
        This function checks the parameters for generate_root_rsa_store
        function
    '''
    if params.p_body == b'':
        raise ErrInvalidParam('params.p_body is empty')
    if params.body_len != CRYPTO_PUB_MODULUS_LEN:
        raise ErrInvalidParam('Invalid body length')

def generate_root_rsa_store(params: StoreParamsT) -> None:
    '''
        This function generates the encrypted image based on the
        rsa image format and stores it inside a file
    '''
    check_params(params)
    with open(params.store_output_file, 'wb') as output:
        output.write(params.p_body)
