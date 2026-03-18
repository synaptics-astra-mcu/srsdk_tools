import os
import sys
import subprocess
def install_requirements():
    """Install all dependencies listed in requirements.txt automatically."""
    requirements_path = os.path.join(os.path.dirname(__file__), "requirements.txt")
    if os.path.exists(requirements_path):
        print(f" Ensuring all dependencies from {requirements_path} are installed...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", requirements_path])
        except subprocess.CalledProcessError as e:
            print(f" Failed to install dependencies from requirements.txt\nError: {e}")
            sys.exit(1)
    else:
        print("No requirements.txt found next to main.py. Skipping dependency installation.")

# Run this before importing anything else
install_requirements()
from src.params_parser import *
def main(params: StoreParamsT):
    if any((IMAGE_TYPE_K0_SYNA == params.image_type,
           IMAGE_TYPE_K0_OEM == params.image_type,
           IMAGE_TYPE_K0_TEE == params.image_type,
           IMAGE_TYPE_K0_REE == params.image_type,
           IMAGE_TYPE_SPK == params.image_type,
           IMAGE_TYPE_APBL == params.image_type,
           IMAGE_TYPE_TF_M == params.image_type,
           IMAGE_TYPE_RTOS == params.image_type,
           IMAGE_TYPE_M4_SW == params.image_type,
           IMAGE_TYPE_LX7_SW == params.image_type,
           IMAGE_TYPE_AI_MODEL == params.image_type,
           IMAGE_TYPE_BCM_KERNEL == params.image_type,
           IMAGE_TYPE_K1_BOOT_A == params.image_type,
           IMAGE_TYPE_K1_BOOT_B == params.image_type,
           IMAGE_TYPE_K1_SPE_A == params.image_type,
           IMAGE_TYPE_K1_SPE_B == params.image_type,
           IMAGE_TYPE_K1_SPE_C == params.image_type,
           IMAGE_TYPE_K1_TEE_D == params.image_type,
           IMAGE_TYPE_K1_NSPE_A == params.image_type,
           IMAGE_TYPE_K1_REE_B == params.image_type,
           IMAGE_TYPE_K1_REE_C == params.image_type,
           IMAGE_TYPE_K1_REE_D == params.image_type)):
        params.image_format_version = 0
    else:
        params.image_format_version = 1

    try:
        match params.image_format:
            case ImageFormatT.FORMAT_ROOT_RSA:
                if fetch_root_rsa_params(params):
                    generate_root_rsa_store(params)

            case ImageFormatT.FORMAT_EXT_RSA:
                if fetch_ext_rsa_params(params):
                    generate_level1_rsa_store(params)

            case ImageFormatT.FORMAT_BOOT_IMAGE:
                if fetch_boot_image_params(params):
                    generate_boot_image_store(params)

            case ImageFormatT.FORMAT_BOOT_IMAGE_TYPE2:
                if fetch_boot_image_params(params):
                    generate_boot_image_store_type2(params)

            case ImageFormatT.FORMAT_DIF_IMAGE:
                if fetch_boot_image_params(params):
                    generate_dif_image_store(params)

            case ImageFormatT.FORMAT_DDR_FW_IMAGE:
                if fetch_boot_image_params(params):
                    generate_ddr_fw_image_store(params)

            case ImageFormatT.FORMAT_MODEL_IMAGE:
                if fetch_boot_image_params(params):
                    generate_model_image_store(params)

            case ImageFormatT.FORMAT_OEM_COMMAND_IMAGE:
                if fetch_boot_image_params(params):
                    generate_oem_command_store(params)

            case ImageFormatT.FORMAT_AXI_IMGAE:
                if fetch_boot_image_params(params):
                    generate_axicrypto_image_store(params)
                
            case _:
                raise ErrUnsupportedFormat('Invalid image format provided')
    
    except Exception as e:
        print(f'{type(e).__name__}: {str(e)}')

if __name__ == '__main__':
    parser = create_parser()
    args = parser.parse_args()

    # no arguments were passed
    if not any(vars(args).values()):
        parser.print_help()
        print('\nroot-rsa-types : { K0_BOOT | K0_TEE | K0_REE }\n'
              'level1-rsa-types : { K1_BOOT_[A|B] | K1_TEE_[A|B|C|D] | K1_REE_[A|B|C|D] }\n'
              'boot-img-types : { SPK | APBL | TF_M }')
    else:
        params = load_params(args)
        main(params)

