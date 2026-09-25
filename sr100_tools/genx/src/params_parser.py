import os

from .type import *
from .crypto import *
from .root_rsa_store import *
from .level1_rsa_store import *
from .boot_image_store import *
from .ddr_fw_image_store import *
from .oem_command_store import *
from .dif_image_store import *
from .npu_image_store import *
from .err import *
from .axicrypto_image_store import *

VERSION = '2.0.0'
NPU_ALIGN_LEN = 64

def check_length(length: str) -> int:
    '''
        This function checks if the length provided 
        by the user via the cli is valid
    '''
    l = int(length, 0)
    if l % CRYPTO_AES_KEY_LEN:
        raise argparse.ArgumentTypeError(f'length should be multuple of {CRYPTO_AES_KEY_LEN}') 
    return l

def auto_int(x) -> int:
    return int(x, 0)

def create_parser() -> argparse.ArgumentParser:
    '''
        This function creates an ArgumentParser object
        for parsing the arguments passed by the user
    '''
    parser = argparse.ArgumentParser(
                prog='main.py',
                description='Generates images for GenX secure stores',
                formatter_class=CustomFormatter)
    
    parser.add_argument('-a', '--start-address', help='AXI OTF start address (32-bits)', type=str)
    parser.add_argument('-A', '--address_offset', help='AXI OTF address offset (32-bits)', type=str)
    parser.add_argument('-f', '--flag', metavar='<flag>', help='0000: devlopment sw, 0001 : production sw', type=auto_int)
    parser.add_argument('-i', '--input', metavar='<file>', help='payload or body for the secure store', type=str)
    parser.add_argument('-I', '--input_extra', metavar='<file>', help='payload or body for the clear store', type=str)
    parser.add_argument('-j', '--nonce', metavar='<file>', help='AXI OTF AES nonce (96-bits)', type=str)
    parser.add_argument('-k', '--enc_key', metavar='<file>', help='AES encryption key (256-bits)', type=str)
    parser.add_argument('-K', '--iv', metavar='<file>', help='AES IV (256-bits)', type=str)
    parser.add_argument('-l', '--length', metavar='<file>', help='Fixed length for payload or body in bytes. Should be multiple of 32', type=check_length)
    parser.add_argument('-n', '--sign_key', metavar='<file>', help='RSA private key for signing in PEM format (4096-bits)', type=str)
    parser.add_argument('-o', '--output', metavar='<file>', help='secure store output file', type=str)
    parser.add_argument('-p', '--hash', metavar='<file>', help='root-rsa header hash output file', type=str)
    parser.add_argument('-r', '--ver', metavar='<ver>', help='Version', type=auto_int)
    parser.add_argument('-R', '--ver_mask', metavar='<ver-mask>', help='Version mask', type=auto_int)
    parser.add_argument('-s', '--seg', metavar='<seg-id>', help='Segment ID', type=auto_int)
    parser.add_argument('-S', '--seg_mask', metavar='<seg-mask>', help='Segment ID mask', type=auto_int)
    parser.add_argument('-t', '--type', metavar='<type>', help='One of root- or level1- or boot- type listed below', type=str)
    parser.add_argument('-x', '--extra', metavar='<file>', help='extra parameters for boot image', type=str)
    parser.add_argument('-Y', '--noenc', help='do not encrypt payload', action='store_true')
    parser.add_argument('-Z', '--nosign', help='do not sign image header', action='store_true')
    parser.add_argument('-v', '--version', action='version', version=f'py_genx_img : {VERSION}')

    return parser

def load_params(args: argparse.Namespace) -> StoreParamsT:
    '''
        This function converts the arguments from the user
        into a workable object
    '''
    params = StoreParamsT()
    for key, value in vars(args).items():
        if value:
            params.arg_num += 1
            match key:
                case 'start_address':
                    params.start_address = value
                case 'address_offset':
                    params.address_offset = value
                case 'flag':
                    params.production_key_flag = value
                case 'input':
                    params.payload_input_file = value
                case 'input_extra':
                    params.payload_input_file_extra = value
                case 'nonce':
                    params.nonce_input_file = value
                case 'enc_key':
                    params.aes_key_input_file = value
                case 'iv':
                    params.iv_input_file = value
                case 'length':
                    params.requested_length = value
                case 'sign_key':
                    params.rsa_key_input_file = value
                case 'output':
                    params.store_output_file = value
                case 'hash':
                    params.hash_output_file = value
                case 'ver':
                    params.version = value
                case 'ver_mask':
                    params.version_mask = value
                case 'seg':
                    params.seg_id = value
                case 'seg_mask':
                    params.seg_id_mask = value
                case 'type':
                    type = get_type(value)
                    params.image_type = type[0]
                    params.image_format = type[1]
                case 'extra':
                    params.extra_input_file = value
                case 'noenc':
                    print('WARNING: No encrypton selected with [-Y or --noenc]')
                    params.no_encryption = True
                case 'nosign':
                    print('WARNING: No sinagure selected with [-Z or --nosign]')
                    params.no_signature = True
    
    return params

def get_type(type: str) -> tuple:
    '''
        This function returns the image type and the image
        format based on the given string type
    '''
    types = {
        K0_SYNA            : (IMAGE_TYPE_K0_SYNA,            ImageFormatT.FORMAT_ROOT_RSA),
        K0_OEM             : (IMAGE_TYPE_K0_OEM,             ImageFormatT.FORMAT_ROOT_RSA),
        K0_TEE             : (IMAGE_TYPE_K0_TEE,             ImageFormatT.FORMAT_ROOT_RSA),
        K0_REE             : (IMAGE_TYPE_K0_REE,             ImageFormatT.FORMAT_ROOT_RSA),
        K1_BOOT_A          : (IMAGE_TYPE_K1_BOOT_A,          ImageFormatT.FORMAT_EXT_RSA),
        K1_BOOT_B          : (IMAGE_TYPE_K1_BOOT_B,          ImageFormatT.FORMAT_EXT_RSA),
        K1_SPE_A           : (IMAGE_TYPE_K1_SPE_A,           ImageFormatT.FORMAT_EXT_RSA),
        K1_SPE_B           : (IMAGE_TYPE_K1_SPE_B,           ImageFormatT.FORMAT_EXT_RSA),
        K1_SPE_C           : (IMAGE_TYPE_K1_SPE_C,           ImageFormatT.FORMAT_EXT_RSA),
        K1_TEE_D           : (IMAGE_TYPE_K1_TEE_D,           ImageFormatT.FORMAT_EXT_RSA),
        K1_NSPE_A          : (IMAGE_TYPE_K1_NSPE_A,          ImageFormatT.FORMAT_EXT_RSA),
        K1_REE_B           : (IMAGE_TYPE_K1_REE_B,           ImageFormatT.FORMAT_EXT_RSA),
        K1_REE_C           : (IMAGE_TYPE_K1_REE_C,           ImageFormatT.FORMAT_EXT_RSA),
        K1_REE_D           : (IMAGE_TYPE_K1_REE_D,           ImageFormatT.FORMAT_EXT_RSA),

        SPK                : (IMAGE_TYPE_SPK,                ImageFormatT.FORMAT_BOOT_IMAGE),
        APBL               : (IMAGE_TYPE_APBL,               ImageFormatT.FORMAT_BOOT_IMAGE),
        TF_M               : (IMAGE_TYPE_TF_M,                ImageFormatT.FORMAT_BOOT_IMAGE),
        RTOS               : (IMAGE_TYPE_RTOS,                ImageFormatT.FORMAT_BOOT_IMAGE),
        M4_SW              : (IMAGE_TYPE_M4_SW,              ImageFormatT.FORMAT_BOOT_IMAGE),
        LX7_SW             : (IMAGE_TYPE_LX7_SW,             ImageFormatT.FORMAT_BOOT_IMAGE),
        AI_MODEL           : (IMAGE_TYPE_AI_MODEL,           ImageFormatT.FORMAT_BOOT_IMAGE),
        SCS_DATA_PARAM     : (IMAGE_TYPE_SCS_DATA_PARAM,     ImageFormatT.FORMAT_BOOT_IMAGE_TYPE2),
        BOOTMONITOR        : (IMAGE_TYPE_BOOTMONITOR,        ImageFormatT.FORMAT_BOOT_IMAGE),
        SYS_INIT           : (IMAGE_TYPE_SYS_INIT,           ImageFormatT.FORMAT_BOOT_IMAGE),
        MINILOADER         : (IMAGE_TYPE_MINILOADER,         ImageFormatT.FORMAT_BOOT_IMAGE),
        UBOOT              : (IMAGE_TYPE_UBOOT,              ImageFormatT.FORMAT_BOOT_IMAGE),
        BCM_KERNEL         : (IMAGE_TYPE_BCM_KERNEL,         ImageFormatT.FORMAT_BOOT_IMAGE),
        TZ_KERNEL          : (IMAGE_TYPE_TZ_KERNEL,          ImageFormatT.FORMAT_BOOT_IMAGE),
        ATF                : (IMAGE_TYPE_ATF,                ImageFormatT.FORMAT_BOOT_IMAGE),
        TZK_BOOT_PARAMETER : (IMAGE_TYPE_TZK_BOOT_PARAMETER, ImageFormatT.FORMAT_BOOT_IMAGE),
        TA_ROOT_CERT       : (IMAGE_TYPE_TA_ROOT_CERT,       ImageFormatT.FORMAT_BOOT_IMAGE),
        TA_CERT            : (IMAGE_TYPE_TA_CERT,            ImageFormatT.FORMAT_BOOT_IMAGE),
        TA                 : (IMAGE_TYPE_TA,                 ImageFormatT.FORMAT_BOOT_IMAGE),
        BOOT_LOADER        : (IMAGE_TYPE_BOOT_LOADER,        ImageFormatT.FORMAT_BOOT_IMAGE),
        FASTBOOT           : (IMAGE_TYPE_FASTBOOT,           ImageFormatT.FORMAT_BOOT_IMAGE),
        FASTLOGO           : (IMAGE_TYPE_FASTLOGO,           ImageFormatT.FORMAT_BOOT_IMAGE),
        LINUX_KERNEL       : (IMAGE_TYPE_LINUX_KERNEL,       ImageFormatT.FORMAT_BOOT_IMAGE),
        TZK_OEM_SETTINGS   : (IMAGE_TYPE_TZK_OEM_SETTINGS,   ImageFormatT.FORMAT_BOOT_IMAGE),
        AVB_KEYS           : (IMAGE_TYPE_AVB_KEYS,           ImageFormatT.FORMAT_BOOT_IMAGE),
        GPU_FW             : (IMAGE_TYPE_GPU_FW,             ImageFormatT.FORMAT_BOOT_IMAGE),
        DSP_FW             : (IMAGE_TYPE_DSP_FW,             ImageFormatT.FORMAT_BOOT_IMAGE),
        TSP_FW             : (IMAGE_TYPE_TSP_FW,             ImageFormatT.FORMAT_BOOT_IMAGE),
        SM_FW              : (IMAGE_TYPE_SM_FW,              ImageFormatT.FORMAT_BOOT_IMAGE),
        DDR_FW0            : (IMAGE_TYPE_DDR_FW0,            ImageFormatT.FORMAT_DDR_FW_IMAGE),
        DDR_FW1            : (IMAGE_TYPE_DDR_FW1,            ImageFormatT.FORMAT_DDR_FW_IMAGE),
        DIF                : (IMAGE_TYPE_DIF,                ImageFormatT.FORMAT_DIF_IMAGE),
        MODEL              : (IMAGE_TYPE_MODEL,              ImageFormatT.FORMAT_MODEL_IMAGE),
        OEM_COMMAND        : (IMAGE_TYPE_OEM_COMMAND,        ImageFormatT.FORMAT_OEM_COMMAND_IMAGE),
        DOLBY_AUDIO        : (IMAGE_TYPE_DOLBY_AUDIO,        ImageFormatT.FORMAT_BOOT_IMAGE),
        AXI_IMAGE          : (IMAGE_TYPE_FLASH_AXI,          ImageFormatT.FORMAT_AXI_IMGAE),
    }

    type = type.upper()
    return types.get(type, (0, ImageFormatT.FORMAT_UNKNOWN))


def fetch_root_rsa_params(params: StoreParamsT) -> bool:
    '''
        This function fetches the root rsa parametrs
        into the object
    '''
    if params.store_output_file == '':
        raise ErrParamOutfile('Did not provide store output file')
    
    if crypto_get_rsa_modulus(params):
        if params.body_len != CRYPTO_PUB_MODULUS_LEN:
            raise ErrParamModulus('Invalid modulus length')
    
    return True
    
def fetch_ext_rsa_params(params: StoreParamsT) -> bool:
    '''
        This function fetches the ext rsa parametrs
        into the object
    '''
    if params.store_output_file == '':
        raise ErrParamOutfile('Did not provide store output file')
    if not os.path.exists(params.rsa_key_input_file):
        raise ErrParamOutfile('Could not find the provided rsa key file')

    if crypto_get_rsa_modulus(params):
        if params.body_len != CRYPTO_PUB_MODULUS_LEN:
            raise ErrParamModulus('Invalid modulus length')
    
    return True

def fetch_boot_image_params(params: StoreParamsT) -> bool:
    '''
        This function fetches the boot image parameters
        based on the provided arguments
    '''
    if params.store_output_file == '':
        raise ErrParamOutfile('Did not provide store output file')

    if params.image_type != IMAGE_TYPE_OEM_COMMAND:
        if not params.no_encryption:
            try:
                with open(params.aes_key_input_file, 'rb') as key_file:
                    params.aes_enc_key = bytes(key_file.read())
            except Exception as e:
                raise ErrParamAESKey('Error opening the AES key file')
            if len(params.aes_enc_key) != CRYPTO_AES_KEY_LEN:
                raise ErrParamAESKey('Invalid length of AES key')
            
        try:
            with open(params.iv_input_file, 'rb') as iv_file:
                params.iv = bytes(iv_file.read())
            if len(params.iv) != CRYPTO_IV_LEN:
                raise ErrParamIV('Invalid length of IV')
        except:
            pass
        if params.image_format == ImageFormatT.FORMAT_AXI_IMGAE:
            with open(params.nonce_input_file, 'rb') as nonce_file:
                params.nonce = nonce_file.read()
            if len(params.nonce) != CRYPTO_NONCE_LEN:
                raise ErrParamNonce('Invalid length of nonce')

    if params.image_format != ImageFormatT.FORMAT_DDR_FW_IMAGE and params.image_format != ImageFormatT.FORMAT_AXI_IMGAE:
        if not os.path.exists(params.rsa_key_input_file):
            raise ErrParamRsa('Could not find the provided rsa key file')

    try:
        image_len = os.path.getsize(params.payload_input_file)
        if params.requested_length > image_len:
            params.body_len = params.requested_length
        else:
            params.body_len = image_len
            if params.image_type != IMAGE_TYPE_MODEL:
                padding = params.body_len % CRYPTO_AES_KEY_LEN
                if padding:
                    params.body_len += (CRYPTO_AES_KEY_LEN-padding)
            else:
                padding = params.body_len % NPU_ALIGN_LEN
                if padding:
                    params.body_len += (NPU_ALIGN_LEN-padding)
        with open(params.payload_input_file, 'rb') as payload:
            if params.image_format != ImageFormatT.FORMAT_AXI_IMGAE:
                params.p_body = bytes(payload.read(params.body_len)).ljust(params.body_len, b'\x00')
            else:
                params.p_body = payload.read()
    except:
        raise ErrParamBody('Could not find the provided payload input file')
    
    if params.image_type == IMAGE_TYPE_MODEL:
        try:
            image_len = os.path.getsize(params.payload_input_file_extra)
            params.body_len_extra = image_len
            with open(params.payload_input_file_extra, 'rb') as payload_extra:
                params.p_body_extra = bytes(payload_extra.read(image_len))
        except:
            raise ErrParamBody('Could not find the provided payload input file extra')
    
    if params.image_format != ImageFormatT.FORMAT_DDR_FW_IMAGE and params.image_format != ImageFormatT.FORMAT_OEM_COMMAND_IMAGE \
            and params.image_format != ImageFormatT.FORMAT_AXI_IMGAE:
        try:
            image_len = os.path.getsize(params.extra_input_file)
            params.extras_len = image_len
            with open(params.extra_input_file, 'rb') as extra:
                params.p_extras = bytes(extra.read(image_len))
        except:
            raise ErrParamExtraArg('Could not find the provided extra input file')

    return True
