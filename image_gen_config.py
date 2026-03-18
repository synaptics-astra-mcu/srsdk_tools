from pathlib import Path
import logging, os, sys
import platform

SRSDK_IMAGE_CENERATOR_VER = "5.0.13"

is_B0_chip      = False

is_flash_image  = False
is_host_image   = False

chip_type       = ""
total_run_time  = 0
is_windows = sys.platform.startswith('win')

#path for Output Folder
def get_output_folder_path():
    out_path = ROOT_DIRECTORY.joinpath('Output/')
    Path(out_path).mkdir(parents=True, exist_ok=True)
    return out_path.resolve()

def setup_logger():
    # Create a logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    # Create a file handler
    logger_file_path = ROOT_DIRECTORY.joinpath('Log').joinpath('Image_generator_Logger.txt')
    if os.path.exists(logger_file_path):
        os.remove(logger_file_path)
    check_path(logger_file_path)
    file_handler = logging.FileHandler(logger_file_path)
    file_handler.setLevel(logging.DEBUG)

    # Create a formatter and set the formatter for the handler
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')#('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    # Add the handler to the logger
    # logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger, file_handler

def close_logger(logger, handler):
    # Remove the handler from the logger
    logger.removeHandler(handler)
    # Close the handler
    handler.close()

def get_output_folder_path_host(chip_type):
    # Host
    out_path = ROOT_DIRECTORY.joinpath('Output').joinpath(chip_type + 'Host/')
    Path(out_path).mkdir(parents=True, exist_ok=True)
    return out_path.resolve()

def get_output_folder_path_sub_images():
    # Host
    out_path = ROOT_DIRECTORY.joinpath('Output').joinpath('Sub_Images /')
    Path(out_path).mkdir(parents=True, exist_ok=True)
    return out_path.resolve()

def get_output_folder_path_flash(chip_type):
    # Flash
    out_path = ROOT_DIRECTORY.joinpath('Output').joinpath(chip_type + 'Flash/')
    Path(out_path).mkdir(parents=True, exist_ok=True)
    return out_path.resolve()

def get_output_folder_path_flash_components(chip_type):
    out_path = ROOT_DIRECTORY.joinpath('Output').joinpath(chip_type + 'Flash/').joinpath('Components/')
    Path(out_path).mkdir(parents=True, exist_ok=True)
    return out_path.resolve()

def get_output_folder_path_host_components(chip_type):
    out_path = ROOT_DIRECTORY.joinpath('Output').joinpath(chip_type + 'Host/').joinpath('Components/')
    Path(out_path).mkdir(parents=True, exist_ok=True)
    return out_path.resolve()

def check_path(output_path):
    # Check if the directory of the output path exists, if not, create it
    output_path = Path(output_path)
    if not output_path.parent.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)

ROOT_DIRECTORY                              =  Path.cwd()
JUMP_ADDR_PREFIX                            = '_run_image.bin'

BIN_OUTPUT_FOLDER_PATH                      = get_output_folder_path()
BIN_OUTPUT_FOLDER_PATH_HOST                 = ""
BIN_OUTPUT_FOLDER_PATH_FLASH                = ""
BIN_OUTPUT_FOLDER_PATH_COMPONENT_HOST       = ""
BIN_OUTPUT_FOLDER_PATH_COMPONENT_FLASH      = ""
BIN_OUTPUT_FOLDER_PATH_FW_UPDATE            = ""

ATTR_SUB_IMAGES_FOLDER                      = "Attr_Sub_Images"
SPK_SUB_IMAGES_FOLDER                       = "SPK_Sub_Images"
APBL_SUB_IMAGES_FOLDER                      = "APBL_Sub_Images"
SDK_SUB_IMAGES_AXI_FOLDER                   = "SDK_Sub_Images_AXI_Enc"
SDK_SUB_IMAGES_BCM_FOLDER                   = "SDK_Sub_Images_BCM_Enc"
NVM_SUB_IMAGES_FOLDER                       = "NVM_Sub_Images"

BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES           = get_output_folder_path_sub_images()
BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES_APBL      = BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES.joinpath(APBL_SUB_IMAGES_FOLDER)
BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES_SDK_AXI   = BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES.joinpath(SDK_SUB_IMAGES_AXI_FOLDER)
BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES_SDK_BCM   = BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES.joinpath(SDK_SUB_IMAGES_BCM_FOLDER)
BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES_SPK       = BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES.joinpath(SPK_SUB_IMAGES_FOLDER)
BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES_ATTR      = BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES.joinpath(ATTR_SUB_IMAGES_FOLDER)
BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES_NVM       = BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES.joinpath(NVM_SUB_IMAGES_FOLDER)
IMAGE_LISTS_JSON_PATH                       = BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES.joinpath('imglst.json')
log_file, log_handler                       = setup_logger()

IMAGES_PARAMETERS                           = Path.cwd().joinpath('Input_Config').joinpath('Images_Parameters.json')

EXTRAS_BIN_PATH                             = Path.cwd().joinpath('in_extras.bin')

system  = platform.system().lower()     # "windows", "linux", "darwin"
machine = platform.machine().lower()    # "x86_64", "amd64", "arm64", "aarch64"

GENX_EXE_PATH = Path.cwd().joinpath("genx/main.py")

CONFIG_NVM_DATA_PATH                    = Path.cwd().joinpath('Input_Config').joinpath('NVM_data.json')
CONFIG_FW_UPDATE_DATA_PATH              = Path.cwd().joinpath('Input_Config').joinpath('Fw_Update_Parameters.json')
CONFIG_PARAMS_PATH                      = Path.cwd().joinpath('Input_Config').joinpath('Config_Parameters.json')
IV_BIN_ZERO                             = Path.cwd().joinpath('GenX_Input_Files').joinpath('parameters').joinpath('iv_zero.bin')

OUTPUT_TEMP_BIN_FILE                        = ""
FLASH_TEMP_BIN_FILE                         = ""
HOST_TEMP_BIN_FILE                          = ""
NPU_C_TEMP_BIN_FILE                         = ""
ZIP_FILE_PATH                               = ""

dict_attributes_A               = []
dict_apbl_info                  = []
dict_m55_info_host              = []
dict_m55_info_flash             = []
dict_m4_info_host               = []
dict_m4_info_flash              = []
dict_npu_c_info_host            = []
dict_npu_c_info_flash           = []
# dict_model_info_host          = []
dict_model_info_flash           = []
addr_configs                    = []
memory_regions                  = []
imglst4json                     = []
dict_nvm_data                   = []
dict_multi_image_update_data    = []
dict_model_update_data          = []
dict_sdk_update_data            = []
dict_spk_update_data            = []
dict_apbl_update_data           = []

FLASH_SIZE_MEGA2BYTES = {
    '1M': '1,048,576',
    '2M': '2,097,152',
    '4M': '4,194,304',
    '8M': '8,388,608',
    '16M': '16,777,216',
    '32M': '33,554,432',
    '64M': '1,048,576',
    '128M': '1,048,576'
}

ENTRY_POINT_ADDRESS             = "Entry point address:"

BIT_WIDTH                       = (int)(32)
#Chip B0 definitions
#SPK sizes for break down, size in bytes
SPK_EXT_HEADER_SIZE             = (int)(32)
SPK_EXTERNAL_HEADER             = "SPK_External_Header.bin"
SPK_K0_SYNA_SIZE                = (int)(512)
SPK_K0_SYNA                     = "SPK_K0_SYNA.bin"
SPK_K0_OEM_SIZE                 = (int)(512)
SPK_K0_OEM                      = "SPK_K0_OEM.bin"
SPK_K1_SIZE                     = (int)(24 + 512 + 512)
SPK_K1_BOOT_A                   = "SPK_K1_BOOT_A.bin"
SPK_K1_SPE_A                    = "SPK_K1_SPE_A.bin"
SPK_K1_SPE_B                    = "SPK_K1_SPE_B.bin"
SPK_K1_SPE_C                    = "SPK_K1_SPE_C.bin"
SPK_K1_NSPE_A                   = "SPK_K1_NSPE_A.bin"
SPK_HEADER_SIGNATURE_BODY       = "SPK_Header_Signature_Body.bin"

#General Defin
HEADER_MAGIC_NUMBER             = ([0x5b] + [0xb0] + [0x00] + [0x55])
GLOBAL_COUNTER_BCM              = (int)(0)
GLOBAL_COUNTER_AXI              = (int)(0)
host_sub_image_counter          = (int)(0)
flash_sub_image_counter         = (int)(0)

FW_M55_IMAGE_TYPE               = (int)(2)
FW_M4_IMAGE_TYPE                = (int)(3)
NPU_C_IMAGE_TYPE                = (int)(4)
MODEL_IMAGE_TYPE                = (int)(5)
FLAG_WARM_BOOT                  = (int)(0)
FLAG_JUMP_ADDRESS               = (int)(2)
FLAG_LAST_IMAGE                 = (int)(4)

VALUE_32                        = (int)(32)
BOOT_COMMAND_SIZE_BYTES         = (int)(32)
LENGTH_8_BITS                   = 8 # 2 word, 4 bytes
PAGE_SIZE_IN_BYTES              = 256
SECTOR_SIZE_IN_BYTES            = 4*1024
DEFAULT_FLASH_MX_FREQ_75        = (int)(75)
DEFAULT_FLASH_MX_FREQ_67        = (int)(67)
DEFAULT_FLASH_MX_FREQ_34        = (int)(34)
FLASH_FREQ_100                  = (int)(100)
FLASH_FREQ_134                  = (int)(134)
NVM_13_WORDS_EMPTY_DATA         = (int)(52)
EMPTY_WORD                      = (int)(4)

ATTR_LENGTH                     = (int)(4096) #0x00001000

SYNC_1                          = [0x5b]
SYNC_2                          = [0x5a]
SRV_ID                          = [0x33]

#SPK Defines
OP_CODE_DOWN_SPK_0x11           = [0x11]

CRYPTO_OFFSET                   = [0x00, 0x00, 0x00, 0x00]
CRYPTO_KEY_NONCE                = [0x00, 0x00, 0x00, 0x00]

BYTES_4_7                       = [0x00, 0x00, 0x00, 0x00]
BYTES_8_11                       = [0x00, 0x00, 0x00, 0x00]
BYTES_16_31                      = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
BYTES_12_31                      = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]

#APBL Defines
OP_CODE_SEC_IMG_IN_PLACE_0x12       = [0x12]
OP_CODE_SEC_IMG_NOT_IN_PLACE_0x13   = [0x13]
APBL_IMG_TYPE_FOR_BOOT_LOADER       = [0x01, 0x00, 0x00, 0x00]

SECURITY_HEADER                 = (int)(96) #size in bytes
SECURED_SIGNATURE_SIZE          = (int)(512) #size in bytes
SUM_OF_SECURITY_HEADER_AND_SIGNATURE = SECURITY_HEADER + SECURED_SIGNATURE_SIZE

BITS_28_31                      = [0x00, 0x00, 0x00, 0x00]

HEADER_WRITE_BLOCK_TO_MEMORY    = ([0x5b] + [0x5a] + [0x01] + [0x00])
HEADER_SET_JUMP_ADDRESS         = ([0x5b] + [0x5a] + [0x0b] + [0x00])
HEADER_RUN_IMAGE_BY_CHECKSUM    = ([0x5b] + [0x5a] + [0x0d] + [0x00])
HEADER_ENCRYPTED_MODE           = ([0x5b] + [0x5a] + [0x0f] + [0x00])

FFFFFFFF                        ="FFFFFFFF"
output_file_name_spk_host       = ""
output_file_name_spk_flash      = ""

output_file_name_apbl_host      = ""
output_file_name_apbl_flash     = ""
output_apbl_run_command         = ""
file2copy_apbl                  = ""
nvm_bin_data                    = ""

output_file_name_attr_a         = ""
output_file_name_attr_b         = ""

output_sdk_host                     = ""
output_sdk_flash                    = ""
output_spk_fw_update                = ""
output_apbl_fw_update               = ""
output_model_fw_update              = ""
output_sdk_model_fw_update          = ""
output_apbl_sdk_fw_update           = ""
output_spk_sdk_fw_update            = ""
output_spk_apbl_fw_update           = ""
output_spk_apbl_sdk_fw_update       = ""
output_spk_sdk_model_fw_update      = ""
output_spk_apbl_sdk_model_fw_update = ""

output_fw_npu_c_secured_host      = ""
output_fw_npu_c_secured_flash     = ""
output_fw_m55_secured_host      = ""
output_fw_m55_secured_flash     = ""

output_model_flash              = ""

output_fw_b_secured             = ""
output_fw_m55_secured           = ""

output_full_host_file           = ""
output_full_flash_file          = ""

FW_UPDATE_TEMP_FILE             = "fw_update_temp_file_for_flash.bin"
fw_b_for_flash                  = ""

is_sdk_secured                  = False
is_model_secured                = False
last_image                      = 'm55'
single_slot                     = False

#------------------- Images Definitions -------------------
ATTR_DICT_KEY_LIST = [  "Header_Magic_Num",
                        "Pll_Off_Max_QSPI_Frequency_in_MHz",
                        "Pll_On_Max_QSPI_Frequency_in_MHz",
                        "Support_4_bit",
                        "QuadRead_Num_Dummy_Cycles",
                        "RD_SR1_CMD",
                        "RD_SR2_CMD",
                        "WR_SR_CMD",
                        "SR_QE_BIT",
                        "Enable_QE_CMD",
                        "Disable_QE_CMD",
                        "Pll_Off_PHY_Parameters_valid",
                        "Pll_Off_dq_timing_reg_val",
                        "Pll_Off_dqs_timing_reg_val",
                        "Pll_Off_gate_lpbk_ctrl_reg_val",
                        "Pll_Off_dll_master_ctrl_reg_val",
                        "Pll_Off_dll_slave_ctrl_reg_val",
                        "Pll_Off_phy_ctrl_reg_val",
                        "Pll_Off_dll_phy_ctrl_reg_val",
                        "Pll_On_PHY_Parameters_valid",
                        "Pll_On_dq_timing_reg_val",
                        "Pll_On_dqs_timing_reg_val",
                        "Pll_On_gate_lpbk_ctrl_reg_val",
                        "Pll_On_dll_master_ctrl_reg_val",
                        "Pll_On_dll_slave_ctrl_reg_val",
                        "Pll_On_phy_ctrl_reg_val",
                        "Pll_On_dll_phy_ctrl_reg_val",
                        "Delay_after_switch_to_DIRECT_MODE",
                        "Reserved",
                        "K0_K1_SPK_A_offset",
                        "K0_K1_SPK_A_size_APBL_A_size",
                        "K0_K1_SPK_B_offset",
                        "K0_K1_SPK_B_size_APBL_B_size",
                        "APBL_A_Offset",
                        "APBL_A_size",
                        "APBL_B_Offset",
                        "APBL_B_size",
                        "FW_NV_A_offset",
                        "FW_NV_B_offset"]

#--------------------------------------------------------
#------------------- NVM Definitions -------------------
NVM_DICT_KEY_LIST = [   "magic_number",
                        "fw_nv_size",
                        "apbl_slot",
                        "image_offset_SDK_image_A_offset",
                        "image_offset_SDK_image_B_offset",
                        "image_offset_App_Image_A_offset",
                        "image_offset_App_image_B_offset",
                        "image_offset_Model_A_offset",
                        "image_offset_Model_B_offset",
                        "image_offset_reserved_1",
                        "image_offset_reserved_2 ",
                        "security_num_of_defined_sections",
                        "security_num_section_1_control",
                        "security_num_section_1_key",
                        "security_num_section_1_start_offset",
                        "security_num_section_1_end_offset",
                        "security_num_section_1_crypto_offset",
                        "security_num_section_2_control",
                        "security_num_section_2_key",
                        "security_num_section_2_start_offset",
                        "security_num_section_2_end_offset",
                        "security_num_section_2_crypto_offset",
                        "security_num_section_3_control",
                        "security_num_section_3_key",
                        "security_num_section_3_start_offset",
                        "security_num_section_3_end_offset",
                        "security_num_section_3_crypto_offset",
                        "security_num_section_4_control",
                        "security_num_section_4_key",
                        "security_num_section_4_start_offset",
                        "security_num_section_4_end_offset",
                        "security_num_section_4_crypto_offset",
                        "security_num_section_5_control",
                        "security_num_section_5_key",
                        "security_num_section_5_start_offset",
                        "security_num_section_5_end_offset",
                        "security_num_section_5_crypto_offset",
                        "security_num_section_6_control",
                        "security_num_section_6_key",
                        "security_num_section_6_start_offset",
                        "security_num_section_6_end_offset",
                        "security_num_section_6_crypto_offset",
                        "security_num_section_7_control",
                        "security_num_section_7_key",
                        "security_num_section_7_start_offset",
                        "security_num_section_7_end_offset",
                        "security_num_section_7_crypto_offset",
                        "security_num_section_8_control",
                        "security_num_section_8_key",
                        "security_num_section_8_start_offset",
                        "security_num_section_8_end_offset",
                        "security_num_section_8_crypto_offset",
                        "sw_update_state",
                        "sw_update_reset_cause",
                        "sw_update_failure_cause",
                        "sw_update_num_components",
                        "sw_update_st_fw_update_component_0_state",
                        "sw_update_st_fw_update_component_0_failure_cause",
                        "sw_update_st_fw_update_component_0_max_size",
                        "sw_update_st_fw_update_component_0_num_slots",
                        "sw_update_st_fw_update_component_0_primary_slot",
                        "sw_update_st_fw_update_component_0_secondary_slot",
                        "sw_update_st_fw_update_component_0_st_image_slot_0_slot_address",
                        "sw_update_st_fw_update_component_0_st_image_slot_0_image_is_bootable",
                        "sw_update_st_fw_update_component_0_st_image_slot_0_image_is_functional",
                        "sw_update_st_fw_update_component_0_st_image_slot_1_slot_address",
                        "sw_update_st_fw_update_component_0_st_image_slot_1_image_is_bootable",
                        "sw_update_st_fw_update_component_0_st_image_slot_1_image_is_functional",
                        "sw_update_st_fw_update_component_1_state",
                        "sw_update_st_fw_update_component_1_failure_cause",
                        "sw_update_st_fw_update_component_1_max_size",
                        "sw_update_st_fw_update_component_1_num_slots",
                        "sw_update_st_fw_update_component_1_primary_slot",
                        "sw_update_st_fw_update_component_1_secondary_slot",
                        "sw_update_st_fw_update_component_1_st_image_slot_0_slot_address",
                        "sw_update_st_fw_update_component_1_st_image_slot_0_image_is_bootable",
                        "sw_update_st_fw_update_component_1_st_image_slot_0_image_is_functional",
                        "sw_update_st_fw_update_component_1_st_image_slot_1_slot_address",
                        "sw_update_st_fw_update_component_1_st_image_slot_1_image_is_bootable",
                        "sw_update_st_fw_update_component_1_st_image_slot_1_image_is_functional",
                        "sw_update_st_fw_update_component_2_state",
                        "sw_update_st_fw_update_component_2_failure_cause",
                        "sw_update_st_fw_update_component_2_max_size",
                        "sw_update_st_fw_update_component_2_num_slots",
                        "sw_update_st_fw_update_component_2_primary_slot",
                        "sw_update_st_fw_update_component_2_secondary_slot",
                        "sw_update_st_fw_update_component_2_st_image_slot_0_slot_address",
                        "sw_update_st_fw_update_component_2_st_image_slot_0_image_is_bootable",
                        "sw_update_st_fw_update_component_2_st_image_slot_0_image_is_functional",
                        "sw_update_st_fw_update_component_2_st_image_slot_1_slot_address",
                        "sw_update_st_fw_update_component_2_st_image_slot_1_image_is_bootable",
                        "sw_update_st_fw_update_component_2_st_image_slot_1_image_is_functional",
                        "sw_update_st_fw_update_component_3_state",
                        "sw_update_st_fw_update_component_3_failure_cause",
                        "sw_update_st_fw_update_component_3_max_size",
                        "sw_update_st_fw_update_component_3_num_slots",
                        "sw_update_st_fw_update_component_3_primary_slot",
                        "sw_update_st_fw_update_component_3_secondary_slot",
                        "sw_update_st_fw_update_component_3_st_image_slot_0_slot_address",
                        "sw_update_st_fw_update_component_3_st_image_slot_0_image_is_bootable",
                        "sw_update_st_fw_update_component_3_st_image_slot_0_image_is_functional",
                        "sw_update_st_fw_update_component_3_st_image_slot_1_slot_address",
                        "sw_update_st_fw_update_component_3_st_image_slot_1_image_is_bootable",
                        "sw_update_st_fw_update_component_3_st_image_slot_1_image_is_functional",
                        "sw_update_st_fw_update_component_4_state",
                        "sw_update_st_fw_update_component_4_failure_cause",
                        "sw_update_st_fw_update_component_4_max_size",
                        "sw_update_st_fw_update_component_4_num_slots",
                        "sw_update_st_fw_update_component_4_primary_slot",
                        "sw_update_st_fw_update_component_4_secondary_slot",
                        "sw_update_st_fw_update_component_4_st_image_slot_0_slot_address",
                        "sw_update_st_fw_update_component_4_st_image_slot_0_image_is_bootable",
                        "sw_update_st_fw_update_component_4_st_image_slot_0_image_is_functional",
                        "sw_update_st_fw_update_component_4_st_image_slot_1_slot_address",
                        "sw_update_st_fw_update_component_4_st_image_slot_1_image_is_bootable",
                        "sw_update_st_fw_update_component_4_st_image_slot_1_image_is_functional",
                        "tracking_wd_reset",
                        "tracking_oom_reset",
                        "tracking_fault_reset",
                        "tracking_os_panic",
                        "tracking_program_reset",
                        "tracking_fw_update_failure",
                        "tracking_app_sw_reset",
                        "tracking_fw_update_reset_cause",
                        "tracking_reserved_1",
                        "tracking_reserved_2"]
#--------------------------------------------------------