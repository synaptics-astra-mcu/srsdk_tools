import subprocess
import os, sys
import shutil
import json
import struct
import zipfile
import time
from textwrap import wrap
from pathlib import Path
from Crypto.Cipher import AES
from Crypto.Util import Counter

import image_gen_config


# IEEE CRC calculation
class CRC32:
    def __init__(self):
        self.crc32_table = self.generate_crc32_table()

    @staticmethod
    def generate_crc32_table():
        table = [0] * 256
        for i in range(256):
            crc = i
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xEDB88320
                else:
                    crc >>= 1
            table[i] = crc
        return table

    def calculate_crc32(self, data):
        crc = 0xFFFFFFFF
        crc32_table = self.crc32_table
        xor_mask = 0xFFFFFFFF
        and_mask = 0xFF
        for byte in bytearray(data):
            crc = (crc >> 8) ^ crc32_table[(crc ^ byte) & and_mask]
        return crc ^ xor_mask

def read_file_to_array(input_file_name):
    '''Reads a binary file and returns its content as a byte array., if error occurs print error message'''
    file_bin_data = None
    # Opening the binary file in binary mode as rb(read binary)
    try:
        with open(input_file_name, mode="rb") as f:
            file_bin_data = f.read()
        f.close()
    except Exception as error:
        # handle the exception
        print_err('An exception occurred during read file to array', an_exception=str(error))

    return file_bin_data

def align_len_to_8bits(value):
    while len(value) < image_gen_config.LENGTH_8_BITS:
            value = "0" + value
    return value

def attr_dict2list(dict, length, dict_type):
    header2add_list = []

    for key, value in dict.items():
        while len(value) < image_gen_config.LENGTH_8_BITS:
            value = "0" + value
        dict[key] = value

    for var in dict:
        file_size_list = []
        file_size_list = wrap(dict[var], 2)
        file_size_list.reverse()
        for var_list in file_size_list:
            header2add_list.append(int(var_list, 16))

    if image_gen_config.is_B0_chip:
        if not ('attr' in dict_type):
            while len(header2add_list) < length:
                header2add_list.append((int)(0))
    else:
        while len(header2add_list) < length: #image_gen_config.ATTR_LENGTH
                header2add_list.append((int)(0))

    return header2add_list

# Extract execution address from elf file with readelf
def get_load_address(elf_file_name):
    hex_address = ''
    cmd = [
		"arm-none-eabi-readelf",
		"-l",
		elf_file_name,
	]
    try:
        output = subprocess.check_output(cmd).decode()
        # get line #7 (zero based)
        line = output.splitlines()[7]
        line = line.split()
        # get item #3 (zero based)
        hex_address_str = line[3]
        # convert into hex format
        hex_address = int(hex_address_str[2:], 16)
    except Exception as error:
        # handle the exception
        print_err('An exception occurred during get load address:', file_name= error)

    return hex_address

def convert_dec2hex_file_size(file_size_bytes: int):
    # Convert file size to words
    file_size_word_dec, remainder = divmod(file_size_bytes, 4)
    if remainder != 0:
        file_size_word_dec += 1  #need to add the missing data to bin file

    # remove the 0x prefix
    file_size_hex_word = str((hex)(file_size_word_dec))[2:]
    file_size_hex_word = file_size_hex_word.zfill(image_gen_config.LENGTH_8_BITS)

    return file_size_hex_word, remainder

# convert hex string to reversed list - big endian to little endian
def hexStr2ReversedList(hex_str):
    list2add = []
    string_list = wrap(hex_str, 2)
    string_list.reverse()
    for var in string_list:
        list2add.append(int(var, 16))
    return list2add

def cmd_output(cmd):
    """
    Executes a command and returns its output as a string.

    Args:
        cmd (str): The command to execute.

    Returns:
        str: The output of the command as a string.
    """
    output = subprocess.check_output(cmd)
    return output.decode()

def parse_objdump_output(output):
    """
    Parses the output of objdump command and returns a list of sections containing CODE or DATA.

    Args:
        output (str): The output of objdump command.

    Returns:
        list: A list of tuples containing section name, address and size.
    """
    sections = []

    lines = output.splitlines()[5:]
    for i in range(0, (len(lines)), 2):
        section_info = lines[i].split()
        section_attr = lines[i+1].split()
        _, name, size, _, address = section_info[:5]
        if not any('EMPTY' in element for element in section_info):
            if ('CODE' in section_attr) or ('DATA' in section_attr):
                sections.append((name, int(address, 16), int(size, 16)))
        else:
            print(f' WARNING: There is an Empty Sector in the FW: name = {name}, size = {size}, address = {address}. \n The Data from this sector will be Not added to the final image')
            image_gen_config.log_file.warning(f' There is an Empty Sector in the FW: name = {name}, size = 0x{size}, address = 0x{address}. \n The Data from this sector will be Not added to the final image')

    return sections

def objcopy_load_segment(section_name, elf_file_name):
    """
    Extracts a specific section from an ELF file and returns its binary data.

    Args:
        section_name (str): The name of the section to extract.
        elf_file_name (str): The name of the ELF file to extract the section from.

    Returns:
        bytes: The binary data of the extracted section.
    """
    tmpfile = section_name + "__section.bin"

    cmd = [
        "arm-none-eabi-objcopy",
        "--input-target=elf32-little",
        "--only-section", section_name,
        "--output-target=binary",
        elf_file_name,
        tmpfile,
    ]

    subprocess.check_call(cmd)

    with open(tmpfile, "rb") as f:
        data = f.read()
    os.remove(tmpfile)
    return data

def get_sections(elf_file_name):
    cmd = [
        "arm-none-eabi-objdump",
        "-h",
        elf_file_name,
    ]
    output = cmd_output(cmd)
    sections = parse_objdump_output(output)

    return sections

def get_entry_point_address(elf_file_name):
    """
    Returns the entry point address of an ELF file.

    Args:
        elf_file_name (str): The name of the ELF file.

    Returns:
        int: The entry point address of the ELF file.
    """
    hex_address = ''
    cmd = [
        "arm-none-eabi-readelf",
        "-h",
        elf_file_name,
    ]
    output = cmd_output(cmd)
    output_list = output.split("\n")
    for var in output_list:
        if image_gen_config.ENTRY_POINT_ADDRESS in var:
            requested_line = var.split()
            for param in requested_line:
                if "0x" in param:
                    hex_address = int(param[2:], 16)
    return hex_address

def convert_axf_elf(input_file):
    '''Converts an axf file to a bin file and returns the path to the bin file.'''
    start_time = time.time()
    output_file_bin = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH, (os.path.basename(input_file)).split('.')[0] + ".bin")
    try:
        if os.path.isfile(input_file):
            sections_infos = []
            sections_infos = get_sections(input_file)
            previous_section = None
            with open(output_file_bin, "ab") as file:
                for sections in sections_infos:
                    section_name, section_address, section_size = sections
                    if (int)(section_size) == 0:
                        continue
                    image_gen_config.log_file.info(f'APBL AXF section name = {section_name}, address = {hex(section_address)}, section_size = {hex(section_size)} bytes')
                    if previous_section != section_name:
                        section_data = objcopy_load_segment(section_name, input_file)
                    else:
                        previous_section = section_name
                        continue
                    previous_section = section_name
                    while len(section_data) % image_gen_config.VALUE_32 != 0:
                        section_data = section_data + b"\x00"
                    file.write(section_data)
            end_time = time.time()
            execution_time = end_time - start_time
            image_gen_config.total_run_time +=  execution_time
            image_gen_config.log_file.info(f' Run time for Method Convert from Axf {input_file} to Bin = {round(execution_time, 2)} seconds')
            return output_file_bin
    except Exception as error:
        # handle the exception
        image_gen_config.log_file.error(f'An exception occurred during convert Axf to Bin: {error}')
        print_err('An exception occurred during convert Axf to Bin:', an_exception= str(error))


def delete_output_folder():
    dir_path = str(Path.cwd())
    if not "Output" in dir_path:
        #find output folder
        subfolders = [ f.path for f in os.scandir(dir_path) if f.is_dir() ]
        for dirname in subfolders:
            if "Output" in dirname:
                dir_path = Path.cwd().joinpath('Output')
                break
    if "Output" in str(dir_path):
        #Delete files and sub-directories (if exists) in Output folder
        for path in Path(dir_path).iterdir():
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True, onerror=None)
        for f in os.listdir(dir_path):
            os.remove(os.path.join(dir_path, f))

def check_executable_in_path(executable):
    paths = os.environ['PATH'].split(os.pathsep)

    for path in paths:
        if os.path.exists(os.path.join(path, executable)):
            return True

    return False

def convert_json_flash_attr(json_path):
    #Parse JSON to Dictionalries
    with open(json_path) as json_file:
        data = json_file.read()
        attributes_data = json.loads(data)

    if image_gen_config.is_B0_chip:
        return eval(repr(attributes_data["FLASH_ATTRIBUTES_A"]))


def convert_json_2dict_and_copy2other_dict(json_path):
    #Parse JSON to Dictionalries
    with open(json_path) as json_file:
        data = json_file.read()
        info_data = json.loads(data)

    # TODO: try to get rid of eval(repr()) and use json.loads() instead
    if str(image_gen_config.IMAGES_PARAMETERS) in str(json_path):
        image_gen_config.dict_apbl_info           = eval(repr(info_data["APBL_Info"]))
        image_gen_config.dict_m55_info_host       = eval(repr(info_data["M55_Info_Host"]))
        image_gen_config.dict_m55_info_flash      = eval(repr(info_data["M55_Info_Flash"]))
        image_gen_config.dict_m4_info_host        = eval(repr(info_data["M4_Info_Host"]))
        image_gen_config.dict_m4_info_flash       = eval(repr(info_data["M4_Info_Flash"]))
        image_gen_config.dict_npu_c_info_host     = eval(repr(info_data["NPU_C_Info_Host"]))
        image_gen_config.dict_npu_c_info_flash    = eval(repr(info_data["NPU_C_Info_Flash"]))
        image_gen_config.dict_model_info_flash    = eval(repr(info_data["Model_Info_Flash"]))
    elif str(image_gen_config.CONFIG_PARAMS_PATH) in str(json_path):
        image_gen_config.addr_configs             = eval(repr(info_data["ADDR_CONFIGS"]))
        image_gen_config.memory_regions           = eval(repr(info_data["MEMORY_REGIONS"]))
    elif  str(image_gen_config.CONFIG_NVM_DATA_PATH) in str(json_path):
        image_gen_config.dict_nvm_data   = eval(repr(info_data["NVM_Data"]))
    elif  str(image_gen_config.CONFIG_FW_UPDATE_DATA_PATH) in str(json_path):
        #FW Update Dictionaries
        image_gen_config.dict_multi_image_update_data   = eval(repr(info_data["FW_Update_FileHeader"]))
        image_gen_config.dict_model_update_data         = eval(repr(info_data["FW_Update_FileHeader"]))
        image_gen_config.dict_sdk_update_data           = eval(repr(info_data["FW_Update_FileHeader"]))
        image_gen_config.dict_spk_update_data           = eval(repr(info_data["FW_Update_FileHeader"]))
        image_gen_config.dict_apbl_update_data          = eval(repr(info_data["FW_Update_FileHeader"]))

# convert dict to bin file
# TODO: rename, used not only for apbl
def convert_dict2apbl_extra_bin(current_dict):
    current_bytearray = []
    current_bytearray.extend(attr_dict2list(current_dict, 12, ''))

    # Write the combined content to EXTRAS_BIN_PATH
    with open(image_gen_config.EXTRAS_BIN_PATH, 'wb+') as file:
        # Write the new byte array to the beginning of the file
        file.write(bytearray(current_bytearray))

def run_Genx_secured(dict, payload_length, input_bin_file, output_bin_file):
    if 'Encryption_Type' in dict:
        if int(dict['Encryption_Type']):
            run_Genx_non_secured(dict["Priv_Key_Path"], input_bin_file, output_bin_file, str(dict['Image_Type']).lower())
            return
    python_exec = sys.executable
    # Get GenX root folder (for PYTHONPATH)
    genx_root = str(Path(image_gen_config.GENX_EXE_PATH).parent)
    python_dir = Path(python_exec).parent
    site_packages_dir = str(python_dir / 'Lib' / 'site-packages')
    start_time = time.time()
    if os.path.exists(output_bin_file):
        # Delete the file
        os.remove(output_bin_file)
    if 'apbl' in str(dict['Image_Type']).lower():
        current_image = 'APBL'
    if 'm55' in str(dict['Image_Type']).lower():
        current_image = 'TF_M'
    if 'm4' in str(dict['Image_Type']).lower():
        current_image = 'M4_SW'
    if 'npu_c' in str(dict['Image_Type']).lower():
        current_image = 'LX7_SW'
    if 'ai_model' in str(dict['Image_Type']).lower():
        current_image = 'AI_MODEL'
    # Force Python interpreter instead of EXE
    if sys.executable.lower().endswith("srsdk_image_generator.exe"):
        python_exec = shutil.which("python") or shutil.which("python3")
    else:
        python_exec = sys.executable
    # create cmd line
    cmd = [python_exec, str(image_gen_config.GENX_EXE_PATH), '-t', current_image, '-o', output_bin_file,
                '-k', dict["SCGK_path"], '-K', dict["IV_path"], '-n', dict["Priv_Key_Path"],
                '--seg', dict["SegID_Value"], '-r', dict["Version_Value"], '-x', str(image_gen_config.EXTRAS_BIN_PATH),
                '-l', str(payload_length), '-i', input_bin_file]
    # Set up environment
    env = os.environ.copy()

    # Final PATH Fix: Add BOTH the GenX root AND the site-packages path
    python_path_list = [genx_root, site_packages_dir]

    # Prepend the paths and include existing PYTHONPATH
    existing_path = env.get("PYTHONPATH", "")
    if existing_path:
        python_path_list.append(existing_path)

    env["PYTHONPATH"] = os.pathsep.join(python_path_list)

    image_gen_config.log_file.info(f"Setting PYTHONPATH to: {env['PYTHONPATH']}") # Log the final path

    # Run the GenX Python source
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, env=env)
        if result.stderr.strip():
            print("[GENX STDERR]:", result.stderr)
    except subprocess.CalledProcessError as e:
        print_err(
            'run_Genx_secured ERROR: GenX Python source failed.',
            an_exception=e.stderr
        )
    except Exception as e:
        print_err(
            'run_Genx_secured ERROR: Unexpected exception.',
            an_exception=str(e)
        )
    end_time = time.time()
    execution_time = end_time - start_time
    image_gen_config.total_run_time +=  execution_time
    image_gen_config.log_file.info(f' Run time for run_Genx_secured = {round(execution_time, 2)} seconds')

def run_Genx_non_secured(private_key_file_path, input_bin_file, output_bin_file, file_type):
    # Ensure the correct Python interpreter and path
    python_exec = sys.executable
    genx_script = str(image_gen_config.GENX_EXE_PATH)  # main.py path
    # ---  Fix: Normalize all Path objects to strings ---
    input_bin_file  = str(input_bin_file)
    output_bin_file = str(output_bin_file)
    private_key_file_path = str(private_key_file_path)

    # Some configs like EXTRAS_BIN_PATH or IV_BIN_ZERO might also be Path objects
    image_gen_config.EXTRAS_BIN_PATH = str(image_gen_config.EXTRAS_BIN_PATH)
    image_gen_config.IV_BIN_ZERO = str(image_gen_config.IV_BIN_ZERO)

    # Add the genx root folder to PYTHONPATH so "src" can be imported
    env = os.environ.copy()
    genx_root = str(Path(image_gen_config.GENX_EXE_PATH).parent)
    env["PYTHONPATH"] = genx_root + os.pathsep + env.get("PYTHONPATH", "")
    start_time = time.time()
    if os.path.exists(output_bin_file):
        # Delete the file
        os.remove(output_bin_file)
    if 'apbl' in file_type:
        current_image = 'APBL'
    if 'm55' in file_type:
        current_image = 'TF_M'
    if 'm4' in file_type:
        current_image = 'M4_SW'
    if 'npu_c' in file_type:
        current_image = 'LX7_SW'
    if 'ai_model' in file_type:
        current_image = 'AI_MODEL'
    if sys.executable.lower().endswith("srsdk_image_generator.exe"):
        python_exec = shutil.which("python") or shutil.which("python3")
    else:
        python_exec = sys.executable
    cmd = [
    python_exec,
    str(genx_script),
    "-t",
    str(current_image),
    "--noenc",
    "-x",
    str(image_gen_config.EXTRAS_BIN_PATH),
    "-n",
    private_key_file_path,
    "-K",
    image_gen_config.IV_BIN_ZERO,
    "-o",
    output_bin_file,
    "-l",
    "0",
    "-i",
    input_bin_file
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, env=env)
    except subprocess.CalledProcessError as e:
        print_err("Run_Genx_non_secured ERROR:", an_exception=e.stderr or str(e))
    except Exception as error:
        print_err("Run_Genx_non_secured: An exception occurred:", an_exception=str(error))

    end_time = time.time()
    execution_time = end_time - start_time
    image_gen_config.total_run_time +=  execution_time
    image_gen_config.log_file.info(f' Run time for Method run_Genx_non_secured = {round(execution_time, 2)} seconds')

def run_Genx_AXI_Crypto(sector_input_bin_data, crypto_key_bin_file, nonce_bin_file, output_bin_file, start_addr):
    start_time = time.time()
    offset_addr = 0
    python_exec = 'python3' if not sys.platform.startswith('win') else 'python'
    #create cmd line
    cmd = [python_exec,
        str(image_gen_config.GENX_EXE_PATH),
        '-i',
        sector_input_bin_data,
        '-k',
        str(crypto_key_bin_file),
        '-j',
        str(nonce_bin_file),
        '-t',
        'AXI_IMAGE',
        '-o',
        output_bin_file,
        '-a',
        (str)((hex)(start_addr)),
        '-A',
        (str)((hex)(offset_addr))
    ]

    try:
        subprocess.check_output(cmd).decode()
    except Exception as error:
        # handle the exception
        print_err('Run_Genx_AXI_Crypto An exception occurred', an_exception= str(error))
    end_time = time.time()
    execution_time = end_time - start_time
    image_gen_config.total_run_time +=  execution_time
    image_gen_config.log_file.info(f' Run time for run_Genx_AXI_Crypto = {round(execution_time, 2)} seconds')

def create_run_cmds_bin_file(axf_file, file_type):
    # Set Jump Address (0xC)" JUMP_ADDR_FILE_NAME
    if ('m55' in file_type):
        run_img_cmd = bytearray([0x5b, 0x5a, 0x33, 0x0d])
    elif  'apbl' in file_type:
        run_img_cmd = bytearray([0x5b, 0x5a, 0x33, 0x0c])

    run_img_cmd.extend(list(image_gen_config.BYTES_4_7))
    run_img_cmd.extend(struct.pack("<L", get_entry_point_address(axf_file)))
    run_img_cmd.extend(list(image_gen_config.BYTES_12_31))

    if 'apbl' in file_type:
        host_run_cmds_bin_file = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES_APBL,
                                                                        str(image_gen_config.GLOBAL_COUNTER_BCM) + '_1_' +  file_type + image_gen_config.JUMP_ADDR_PREFIX)
    else:
        sub_image_run_cmds_bin_file = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES_SDK_BCM,
                                                                         str(image_gen_config.GLOBAL_COUNTER_BCM) + '_' + str(image_gen_config.host_sub_image_counter) + '_' + \
                                                                            file_type + image_gen_config.JUMP_ADDR_PREFIX)
        with open(sub_image_run_cmds_bin_file, "wb") as file:
            file.write(run_img_cmd)
        image_gen_config.GLOBAL_COUNTER_BCM += 1
        host_run_cmds_bin_file = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_HOST,
                                                                        str(image_gen_config.GLOBAL_COUNTER_BCM) + "_" +  str(file_type) + image_gen_config.JUMP_ADDR_PREFIX)
    image_gen_config.check_path(host_run_cmds_bin_file)
    with open(host_run_cmds_bin_file, "wb") as file:
        file.write(run_img_cmd)

    if not 'apbl' in file_type:
        image_gen_config.host_sub_image_counter += 1
    return   host_run_cmds_bin_file

def padding_data_for_flash(bin_data, offset, file_name):
    '''Padding data for flash image'''
    try:
        if file_name:
            bin_data = bin_data + read_file_to_array(file_name)
            if len(bin_data) < offset:
                padding_byte = bytearray(offset - len(bin_data))
                bin_data = bin_data + padding_byte
                return   bin_data
            else:
                print_err_multi_value(error_str1 ='Wrong Length of Binary data during addeding File ',  value_1 = file_name,
                                      error_str2 ='; \n \t\tBin data length with the file = ',  value_2 = (hex)(len(bin_data)),
                                      error_str3 = 'should be ' , value_3 = (hex)(offset))
        else:
            if len(bin_data) < offset:
                padding_byte = bytearray(offset - len(bin_data))
                bin_data = bin_data + padding_byte
                return   bin_data
            else:
                print_err_multi_value(error_str1 ='Wrong Length of Binary data during adding Files ; \n \t\t Current Bin data length = ', value_1 = (hex)(len(bin_data)),
                              error_str2 = 'But Offset = ', value_2 = (hex)(offset))
    except Exception:
        print_err_multi_value(error_str1 ='Wrong Length of Binary data during adding Files ; \n \t\t Current Bin data length = ', value_1 = (hex)(len(bin_data)),
                              error_str2 = 'But Offset = ', value_2 = (hex)(offset))

def prepend_bytes_to_file(file_path, bytes_to_prepend):
    # Read existing file content
    with open(file_path, 'rb') as file:
        existing_content = file.read()

    # Write the combined content
    with open(file_path, 'wb') as file:
        file.write(bytes_to_prepend)
        file.write(existing_content)

# def create_nvm_bin():
#     nvm_bin = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_FLASH, 'nvm.bin')
#     image_gen_config.check_path(nvm_bin)
#     data2add = bytearray()
#     data2add.extend( bytearray(image_gen_config.HEADER_MAGIC_NUMBER))
#     data2add.extend( bytearray(hexStr2ReversedList(image_gen_config.dict_attributes_A["SDKImage_A_Offset"])))
#     data2add.extend( bytearray(image_gen_config.NVM_13_WORDS_EMPTY_DATA))
#     # Write the combined content
#     with open(nvm_bin, 'wb') as file:
#         file.write(data2add)

# add data to imglst4json - for sign server
def add_data2imglst(name, type, full_path):
    '''Add data to imglst4json - for sign server'''
    current_dict = {"name": "", "type": "", "path": ""}
    full_path = full_path.replace(name, '')
    # Compute the relative path
    relative_path = os.path.relpath(full_path, image_gen_config.BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES)
    # Adjust the format to include './' and replace backslashes with slashes
    relative_path = "./" + relative_path.replace("\\", "/")
    if not relative_path.endswith("/"):
        relative_path += "/"

    current_dict["name"] = name
    current_dict["type"] = type
    current_dict["path"] = relative_path
    image_gen_config.imglst4json.append(current_dict)

def zip_folder(folder_path, zip_path):
    #For Windows
    if image_gen_config.is_windows:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    zipf.write(file_path, os.path.relpath(file_path, folder_path))
    else:
        #For Linux
        # zip -r /path/to/your/zipfile.zip /path/to/your/folder
        command = ["zip", "-r", zip_path, folder_path]
        subprocess.run(command)

def create_all_sdk_files():
    #Create all sdk files: SDK_A_Host, SDK_B_Host, SDK_A_Flash, SDK_B_Flash
    if image_gen_config.is_sdk_secured:
        image_gen_config.output_sdk_host = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_HOST,
                                                                            str(image_gen_config.GLOBAL_COUNTER_BCM) + "_SDK_host_image_secured.bin")
        image_gen_config.output_sdk_flash = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_FLASH,
                                                                            str(image_gen_config.GLOBAL_COUNTER_AXI) + "_SDK_flash_image_secured.bin")
    else:
        image_gen_config.output_sdk_host = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_HOST,
                                                                            str(image_gen_config.GLOBAL_COUNTER_BCM) + "_SDK_host_image.bin")
        image_gen_config.output_sdk_flash = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_FLASH,
                                                                            str(image_gen_config.GLOBAL_COUNTER_AXI) + "_SDK_flash_image.bin")

    if os.path.exists(image_gen_config.output_sdk_host):
        os.remove(image_gen_config.output_sdk_host)
    if os.path.exists(image_gen_config.output_sdk_flash):
        os.remove(image_gen_config.output_sdk_flash)
    image_gen_config.check_path(image_gen_config.output_sdk_host)
    image_gen_config.check_path(image_gen_config.output_sdk_flash)

def delete_temp_files():
    if os.path.exists(image_gen_config.EXTRAS_BIN_PATH):
        os.remove(image_gen_config.EXTRAS_BIN_PATH)
    if os.path.exists(image_gen_config.FLASH_TEMP_BIN_FILE):
        os.remove(image_gen_config.FLASH_TEMP_BIN_FILE)
    if os.path.exists(image_gen_config.HOST_TEMP_BIN_FILE):
        os.remove(image_gen_config.HOST_TEMP_BIN_FILE)
    if os.path.exists(image_gen_config.OUTPUT_TEMP_BIN_FILE):
        os.remove(image_gen_config.OUTPUT_TEMP_BIN_FILE)
    if os.path.exists(image_gen_config.output_fw_npu_c_secured_flash):
        os.remove(image_gen_config.output_fw_npu_c_secured_flash)
    if os.path.exists(image_gen_config.output_fw_npu_c_secured_host):
        os.remove(image_gen_config.output_fw_npu_c_secured_host)

    #if os.path.exists(image_gen_config.output_file_name_spk_flash):
    #    os.remove(image_gen_config.output_file_name_spk_flash)
    #if os.path.exists(image_gen_config.output_file_name_apbl_flash):
    #    os.remove(image_gen_config.output_file_name_apbl_flash)
    #if os.path.exists(image_gen_config.output_sdk_flash):
    #    os.remove(image_gen_config.output_sdk_flash)
    #if os.path.exists(image_gen_config.output_model_flash):
    #    os.remove(image_gen_config.output_model_flash)

def config_chip_type():
    if image_gen_config.is_B0_chip:
        image_gen_config.chip_type = 'B0_'


def create_folder_and_files():
    # folders
    image_gen_config.BIN_OUTPUT_FOLDER_PATH_HOST             = image_gen_config.get_output_folder_path_host(image_gen_config.chip_type)
    image_gen_config.BIN_OUTPUT_FOLDER_PATH_FLASH            = image_gen_config.get_output_folder_path_flash(image_gen_config.chip_type)
    image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_HOST   = image_gen_config.get_output_folder_path_host_components(image_gen_config.chip_type)
    image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_FLASH  = image_gen_config.get_output_folder_path_flash_components(image_gen_config.chip_type)

    # temp files
    image_gen_config.OUTPUT_TEMP_BIN_FILE                    = image_gen_config.BIN_OUTPUT_FOLDER_PATH.joinpath('general_temp_bin_file.bin')
    image_gen_config.FLASH_TEMP_BIN_FILE                     = image_gen_config.BIN_OUTPUT_FOLDER_PATH.joinpath('flash_temp_bin_file.bin')
    image_gen_config.HOST_TEMP_BIN_FILE                      = image_gen_config.BIN_OUTPUT_FOLDER_PATH.joinpath('host_temp_bin_file.bin')
    image_gen_config.NPU_C_TEMP_BIN_FILE                     = image_gen_config.BIN_OUTPUT_FOLDER_PATH.joinpath('npu_c_temp_bin_file.bin')

    # final zip result
    image_gen_config.ZIP_FILE_PATH                           = image_gen_config.BIN_OUTPUT_FOLDER_PATH.joinpath('sub_images.zip')


def print_err(error_sting, file_name='', extention='', an_exception=''):
        if error_sting:
            current_error_string = ' Error: ' + error_sting
        else:
            current_error_string =  ' Error: '
        if file_name:
            current_file_extention = file_name.split('.')[-1]
        if not an_exception:
            if extention and file_name:
                image_gen_config.log_file.error(f' {current_error_string}, file name = {file_name}, current_extention = .{current_file_extention}, , should be: {extention}')
                sys.exit(f' {current_error_string}, file name = {file_name}, current_extention = .{current_file_extention}, , should be: {extention}')
            elif not extention and file_name:
                image_gen_config.log_file.error(f'{current_error_string}, file name = {file_name} ')
                sys.exit(f' {current_error_string}, file name = {file_name}')
            else:
                image_gen_config.log_file.error(f'{current_error_string} ')
                sys.exit(f' {current_error_string}')
        else:
            image_gen_config.log_file.error(f'{current_error_string}, Exception = {an_exception} ')
            sys.exit(f' {current_error_string}, Exception = {an_exception}')

def print_err_multi_value(error_str1='', error_str2='', error_str3='', value_1='', value_2='', value_3=''):
    if error_str1 and value_1 and not error_str2 and not value_2 and not error_str3 and not value_3:
        image_gen_config.log_file.error(f' Error: {error_str1}{value_1}')
        sys.exit(f'  Error: {error_str1}{value_1}')
    elif  error_str1 and value_1 and error_str2 and value_2 and not error_str3 and not value_3:
        image_gen_config.log_file.error(f' Error: {error_str1}{value_1}; {error_str2}{value_2}')
        sys.exit(f'  Error: {error_str1} {value_1} {error_str2} {value_2}')
    else:
        image_gen_config.log_file.error(f' Error: {error_str1}{value_1}; {error_str2}{value_2}; {error_str3}{value_3}')
        sys.exit(f'  Error: {error_str1}{value_1}; {error_str2}{value_2}; {error_str3}{value_3}')

def get_json_file_path():
    if image_gen_config.is_windows:
        json_file = image_gen_config.ROOT_DIRECTORY.joinpath('Input_Config').joinpath('Flash_attributes.json')
    else:
        current_path = str(image_gen_config.ROOT_DIRECTORY / "Input_Config")
        json_file = os.path.join(current_path, "Flash_attributes.json")

    if os.path.exists(json_file):
        return json_file
    else:
        print_err('The JSON File cannot be recognized', file_name=json_file)