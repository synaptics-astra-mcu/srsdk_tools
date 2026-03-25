import os, time
import struct
import shutil

import image_gen_config
from Services.utils import *

def b0_generate_model_image(bin_file_name, offset_length):
    im_addr = 0
    start_time = time.time()
    """
    Generates a binary file to be loaded via host for the M55 device.
    The binary file is created from an AXF/ELF file.
    The function loads data of each section in the AXF/ELF file and writes it to the binary file.
    If there are two sections with the same name, they are loaded together and the size should be an actual loaded size (size1 + size2).
    The function also adds a segment header to each section and a jump address command at the end of the binary file.
    """
    try:
        # Get the absolute path
        absolute_path = os.path.abspath(bin_file_name)
        if os.path.exists(absolute_path):
            # file name with extension
            file_name = os.path.basename(bin_file_name)

            # Open binary file to be loaded via host
            image_gen_config.GLOBAL_COUNTER_AXI += 1

            if image_gen_config.is_model_secured:
                image_gen_config.output_model_flash = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_FLASH,
                                                                        str(image_gen_config.GLOBAL_COUNTER_AXI) + "_" + file_name.split('.')[0] + "_model_flash_secured.bin")
            else:
                image_gen_config.output_model_flash = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_FLASH,
                                                                        str(image_gen_config.GLOBAL_COUNTER_AXI) + "_" + file_name.split('.')[0] + "_model_flash.bin")


            print(f" Create Model A Image File: {image_gen_config.output_model_flash}")
            image_gen_config.log_file.info(f" Create Model A Image File: {image_gen_config.output_model_flash}")

            info_dict = eval(repr(image_gen_config.dict_model_info_flash))
            if image_gen_config.is_model_secured:
                info_dict['Encryption_Type'] = "1"

            #Model Encryption, we will need it in the future
            if int(info_dict['Encryption_Type']) and image_gen_config.is_model_secured:
                output_secure_bin = open(image_gen_config.OUTPUT_TEMP_BIN_FILE, "wb")
                axi_crypto_output_secure_bin = open(image_gen_config.output_model_flash, "wb")
            else:
                output_secure_bin = open(image_gen_config.output_model_flash, "wb")

            pure_bin_data = read_file_to_array(bin_file_name)

            #Align for division on 32 bytes
            while len(pure_bin_data) % image_gen_config.VALUE_32 != 0:
                pure_bin_data = pure_bin_data + b"\x00"

            output_genx_bin_file = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_FLASH, "GenX_Flash.bin")
            image_gen_config.check_path(output_genx_bin_file)

            try:
                if (not os.path.exists(info_dict['SCGK_path'])) or \
                    (not os.path.exists(info_dict['IV_path'])) or \
                    (not os.path.exists(info_dict['Priv_Key_Path'])):
                    print_err('One of key Files (SCGK_APBL, IV or/and Private key) is missing. Please provide Path of these files in APBL_image_attributes.json.The process cannot continue due to an error above.')
            except Exception:
                print_err('One of key Files (SCGK_APBL, IV or/and Private key) is missing. Please provide Path of these files in APBL_image_attributes.json. The process cannot continue due to an error above.')

            required_fields = ['Production_Image_Flag_Value', 'Encryption_Type']
            dict_for_extra_bin = {x:info_dict[x] for x in required_fields}
            convert_dict2apbl_extra_bin(dict_for_extra_bin)

            if not image_gen_config.is_model_secured and not int(info_dict['Encryption_Type']):
                run_Genx_non_secured(info_dict['Priv_Key_Path'], bin_file_name, output_genx_bin_file, 'ai_model_axi')
            else:
                run_Genx_secured(info_dict, len(pure_bin_data), bin_file_name, output_genx_bin_file)

            genx_output_data = read_file_to_array(output_genx_bin_file)

            segment_header_sec = bytearray()
            #Convert Dec Apbl file size to Hex before Genx for Header
            section_size_hex_word, remainder = divmod(len(pure_bin_data), 4)
            try:
                if remainder != 0:
                    print_err('Wrong Model Image Length File', file_name=bin_file_name)
            except Exception:
                print_err(f'Wrong Model Image Length File', file_name= bin_file_name)

            # 624 bytes == 156 words
            num_of_secured_words = (int)(image_gen_config.SUM_OF_SECURITY_HEADER_AND_SIGNATURE/4)

            im_addr  = (int)(image_gen_config.dict_nvm_data['image_offset_Model_A_offset'], 16) + image_gen_config.BOOT_COMMAND_SIZE_BYTES
            exe_addr = im_addr + image_gen_config.SUM_OF_SECURITY_HEADER_AND_SIGNATURE
            fw_image_type = image_gen_config.MODEL_IMAGE_TYPE
            image_gen_config.log_file.info(f'Model: exe address = {hex(exe_addr)}')
            image_gen_config.log_file.info(f'Model: Intermediate address = {hex(im_addr)}')

            # Model Opcode constant = 0x12
            op_code = 0x12

            segment_header_sec.extend([0x5b, 0x5a, 0x33, op_code])
            segment_header_sec.extend(list(image_gen_config.BYTES_4_7))

            if 'model' in image_gen_config.last_image:
                flags = image_gen_config.FLAG_LAST_IMAGE
            else:
                flags = image_gen_config.FLAG_WARM_BOOT

            segment_header_sec.extend(struct.pack("<LLLLLL", num_of_secured_words, section_size_hex_word, exe_addr, im_addr, fw_image_type, flags))
            segment_header_sec.extend(genx_output_data)

            output_secure_bin.write(segment_header_sec)
            output_secure_bin.close()

            if int(info_dict['Encryption_Type']) and image_gen_config.is_model_secured:
                #Model Encryption
                start_addr = (int)(image_gen_config.memory_regions['XSPI_XIP_BASE_ADDRESS'], 16) + (int)(image_gen_config.dict_nvm_data['image_offset_Model_A_offset'], 16)
                image_gen_config.log_file.info(f'Model: Image Flash Start address = {(hex)(start_addr)}')

                run_Genx_AXI_Crypto(output_secure_bin.name, info_dict['AXICrypto_Key_Path'], info_dict['AXICrypto_Nonce_Path'], axi_crypto_output_secure_bin.name, start_addr)

                if os.path.exists(output_secure_bin.name):
                    os.remove(output_secure_bin.name)

                #Add File to the BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES_SDK_AXI Folder
                file2copy =  os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES_SDK_AXI, os.path.basename(axi_crypto_output_secure_bin.name))
                image_gen_config.check_path(file2copy)
                shutil.copy(axi_crypto_output_secure_bin.name, file2copy)
                add_data2imglst(os.path.basename(file2copy), 'ai_model_axi', file2copy)

                #Add Header 12 bytes: 4 bytes start address + 4 bytes offset + 4 bytes nonce index.
                # Read the original binary file
                with open(file2copy, 'rb') as f:
                    original_data = f.read()

                header2add = bytearray()
                start_addr_hex = image_gen_config.dict_nvm_data["image_offset_Model_A_offset"]
                header2add.extend( bytearray(hexStr2ReversedList(start_addr_hex)))
                header2add.extend( bytearray(image_gen_config.CRYPTO_OFFSET))
                header2add.extend( bytearray(image_gen_config.CRYPTO_KEY_NONCE))
                # Write the combined data to a new file (or overwrite the original file)
                with open(file2copy, 'wb') as f:
                    f.write(header2add + original_data)

            if os.path.exists(output_genx_bin_file):
                os.remove(output_genx_bin_file)

            image_gen_config.flash_sub_image_counter += 1

        else:
            print_err('Wrong Input Binary Model File Path or File Name!', file_name= bin_file_name)
    except Exception as e:
        print_err('Something get wrong during create Binary images', an_exception=str(e))

    end_time = time.time()
    execution_time = end_time - start_time
    image_gen_config.total_run_time +=  execution_time

    image_gen_config.log_file.info(f' Run Time for Flash Image Model = {round(execution_time, 2)} seconds')

def b0_generate_npu_c_image(bin_file_name, fw_type, host_type, offset_length):
    im_addr = 0
    start_time = time.time()
    """
    Generates a binary file to be loaded via host for the M55 device.
    The binary file is created from an AXF/ELF file.
    The function loads data of each section in the AXF/ELF file and writes it to the binary file.
    If there are two sections with the same name, they are loaded together and the size should be an actual loaded size (size1 + size2).
    The function also adds a segment header to each section and a jump address command at the end of the binary file.
    """
    try:
        # Get the absolute path
        absolute_path = os.path.abspath(bin_file_name)
        if os.path.exists(absolute_path):
            # file name with extension
            file_name = os.path.basename(bin_file_name)

            # Open binary file to be loaded via host
            if image_gen_config.is_sdk_secured:
                if 'npu_c' in fw_type:
                    if 'host' in host_type:
                        image_gen_config.output_fw_npu_c_secured_host = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_HOST,
                                                                        str(image_gen_config.GLOBAL_COUNTER_BCM) + "_" + str(image_gen_config.host_sub_image_counter) +  "_" + \
                                                                            file_name.split('.')[0] + "_host_secured.bin")
                    else:
                        image_gen_config.output_fw_npu_c_secured_flash = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_FLASH,
                                                                        str(image_gen_config.GLOBAL_COUNTER_AXI) + "_" + str(image_gen_config.flash_sub_image_counter) + "_" + \
                                                                            file_name.split('.')[0] + "_flash_secured.bin")
            else:
                if 'npu_c' in fw_type:
                    if 'host' in host_type:
                        image_gen_config.output_fw_npu_c_secured_host = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_HOST,
                                                                        str(image_gen_config.GLOBAL_COUNTER_BCM) + "_" + str(image_gen_config.host_sub_image_counter) + "_" + \
                                                                            file_name.split('.')[0] + "_host.bin")
                    else:
                        image_gen_config.output_fw_npu_c_secured_flash = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_FLASH,
                                                                        str(image_gen_config.GLOBAL_COUNTER_AXI) + "_" + str(image_gen_config.flash_sub_image_counter) + "_" + \
                                                                            file_name.split('.')[0] + "_flash.bin")
            if 'host' in host_type:
                if 'npu_c' in fw_type:
                    print(f" Add NPU_C {bin_file_name} to SDK Image File: {image_gen_config.output_sdk_host}")
                    image_gen_config.log_file.info(f" Add NPU_C {bin_file_name} to SDK Image File: {image_gen_config.output_sdk_host}")
                    output_secure_bin = open(image_gen_config.output_fw_npu_c_secured_host, "wb")
                    info_dict = eval(repr(image_gen_config.dict_npu_c_info_host))
            else:
                if 'npu_c' in fw_type:
                    print(f" Add NPU_C {bin_file_name} to SDK Image File: {image_gen_config.output_sdk_flash}")
                    image_gen_config.log_file.info(f" Add NPU_C {bin_file_name} to SDK Image File: {image_gen_config.output_sdk_flash}")
                    info_dict = eval(repr(image_gen_config.dict_npu_c_info_flash))
                    if int(info_dict['Encryption_Type']) and image_gen_config.is_sdk_secured:
                        output_secure_bin = open(image_gen_config.OUTPUT_TEMP_BIN_FILE, "wb")
                        axi_crypto_output_secure_bin = open(image_gen_config.output_fw_npu_c_secured_flash, "wb")
                    else:
                        output_secure_bin = open(image_gen_config.output_fw_npu_c_secured_flash, "wb")

            try:
                if (int)(info_dict['Encryption_Type']) and 'host' in host_type:
                    print_err('Wrong Encryption_Type Value for Host Image!')
            except Exception as e:
                print_err('Wrong Encryption_Type Value for Host Image!')

            if 'flash' in host_type:
                m55_offset = (int)(image_gen_config.dict_nvm_data["image_offset_SDK_image_A_offset"], 16)

            pure_bin_data = read_file_to_array(bin_file_name)

            #Align for division on 32 bytes
            while len(pure_bin_data) % image_gen_config.VALUE_32 != 0:
                pure_bin_data = pure_bin_data + b"\x00"

            if 'host' in host_type:
                output_genx_bin_file = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_HOST, "GenX_Host.bin")
            else:
                output_genx_bin_file = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_FLASH, "GenX_Flash.bin")
            image_gen_config.check_path(output_genx_bin_file)

            try:
                if (not os.path.exists(info_dict['SCGK_path'])) or \
                    (not os.path.exists(info_dict['IV_path'])) or \
                    (not os.path.exists(info_dict['Priv_Key_Path'])):
                    print_err('One of key Files (SCGK_APBL, IV or/and Private key) is missing. Please provide Path of these files in APBL_image_attributes.json.The process cannot continue due to an error above.')
            except Exception:
                print_err('One of key Files (SCGK_APBL, IV or/and Private key) is missing. Please provide Path of these files in APBL_image_attributes.json. The process cannot continue due to an error above.')

            required_fields = ['Production_Image_Flag_Value', 'Encryption_Type']
            dict_for_extra_bin = {x:info_dict[x] for x in required_fields}
            convert_dict2apbl_extra_bin(dict_for_extra_bin)

            if not image_gen_config.is_sdk_secured:
                if 'npu_c' in fw_type:
                    run_Genx_non_secured(info_dict['Priv_Key_Path'], bin_file_name, output_genx_bin_file, 'npu_c')
            else:
                run_Genx_secured(info_dict, len(pure_bin_data), bin_file_name, output_genx_bin_file)

            genx_output_data = read_file_to_array(output_genx_bin_file)

            segment_header_sec = bytearray()
            #Convert Dec Apbl file size to Hex before Genx for Header
            section_size_hex_word, remainder = divmod(len(pure_bin_data), 4)
            try:
                if remainder != 0:
                    print_err('Wrong NPU_C Image Length File', file_name=bin_file_name)
            except Exception:
                print_err(f'Wrong NPU_C Image Length File', file_name= bin_file_name)

            # 624 bytes == 156 words
            num_of_secured_words = (int)(image_gen_config.SUM_OF_SECURITY_HEADER_AND_SIGNATURE/4)

            if 'npu_c' in fw_type:
                exe_addr = (int)(image_gen_config.addr_configs['NPU_C_EXE_BASE_ADDR'], 16)
                image_gen_config.log_file.info(f'NPU_C: exe address = {hex(exe_addr)}')
                fw_image_type = image_gen_config.NPU_C_IMAGE_TYPE
                if 'flash' in host_type:
                    im_addr = m55_offset + offset_length + image_gen_config.BOOT_COMMAND_SIZE_BYTES
                    image_gen_config.log_file.info(f'NPU_C: Flash Intermediate address = {(hex)(im_addr)}')

            # ITCM range or DTCM range
            if 'model' in fw_type:
                op_code = 0x12
            else:
                if 'host' in host_type:
                    op_code = 0x12
                    #IM Header Signature
                    if 'npu_c' in fw_type:
                        im_addr  = (int)(image_gen_config.addr_configs['NPU_C_IM_ADDR_HOST_HEADER_SIGN_0x12'], 16)
                        image_gen_config.log_file.info(f'NPU_C: Host Intermediate address = {(hex)(im_addr)}')
                else:
                    op_code = 0x13

            segment_header_sec.extend([0x5b, 0x5a, 0x33, op_code])
            segment_header_sec.extend(list(image_gen_config.BYTES_4_7))

            if 'npu_c' in fw_type and 'npu_c' in image_gen_config.last_image:
                flags = image_gen_config.FLAG_LAST_IMAGE
            else:
                flags = image_gen_config.FLAG_WARM_BOOT

            segment_header_sec.extend(struct.pack("<LLLLLL", num_of_secured_words, section_size_hex_word, exe_addr, im_addr, fw_image_type, flags))
            segment_header_sec.extend(genx_output_data)

            output_secure_bin.write(segment_header_sec)
            output_secure_bin.close()
            if int(info_dict['Encryption_Type']) and image_gen_config.is_sdk_secured and 'flash' in host_type:
                if 'npu_c' in fw_type:
                    start_addr = (int)(image_gen_config.memory_regions['XSPI_XIP_BASE_ADDRESS'], 16) + m55_offset + offset_length
                    image_gen_config.log_file.info(f'NPU_C: Image Flash Start address = {(hex)(start_addr)}')

                run_Genx_AXI_Crypto(output_secure_bin.name, info_dict['AXICrypto_Key_Path'], info_dict['AXICrypto_Nonce_Path'], axi_crypto_output_secure_bin.name, start_addr)

                if os.path.exists(output_secure_bin.name):
                    os.remove(output_secure_bin.name)

            if os.path.exists(output_genx_bin_file):
                os.remove(output_genx_bin_file)

            if 'npu_c' in fw_type:
                if 'host' in host_type:
                    file2copy =  os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES_SDK_BCM,os.path.basename(image_gen_config.output_fw_npu_c_secured_host))
                    image_gen_config.check_path(file2copy)
                    shutil.copy(image_gen_config.output_fw_npu_c_secured_host, file2copy)
                    add_data2imglst(os.path.basename(file2copy), 'npu_c', file2copy)
                    #Add Data to SDK and remove main file
                    with open(image_gen_config.output_sdk_host, 'ab+') as file:
                        file.write(read_file_to_array(image_gen_config.output_fw_npu_c_secured_host) )
                else:
                    file2copy =  os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES_SDK_AXI,os.path.basename(image_gen_config.output_fw_npu_c_secured_flash))
                    image_gen_config.check_path(file2copy)
                    shutil.copy(image_gen_config.output_fw_npu_c_secured_flash, file2copy)
                    add_data2imglst(os.path.basename(file2copy), 'npu_c_axi', file2copy)
                    #Add Data to SDK and remove main file
                    with open(image_gen_config.output_sdk_flash, 'ab+') as file:
                        file.write(read_file_to_array(image_gen_config.output_fw_npu_c_secured_flash) )

                #Add Addres, Offset and Key to the beggining of the file in Sub Image folder
                if int(info_dict['Encryption_Type']) and image_gen_config.is_sdk_secured and 'flash' in host_type:
                    start_addr_hex = (hex)((int)(image_gen_config.memory_regions['XSPI_XIP_BASE_ADDRESS'], 16) + im_addr -image_gen_config.BOOT_COMMAND_SIZE_BYTES)[
                                    2:]
                    image_gen_config.log_file.info(f'NPU_C: Flash Start address for Sub Image = ox{start_addr}')
                    start_addr_hex = start_addr_hex.rjust(8, '0')
                    header2add = bytearray()
                    header2add.extend( bytearray(hexStr2ReversedList(start_addr_hex)))
                    header2add.extend( bytearray(image_gen_config.CRYPTO_OFFSET))
                    header2add.extend( bytearray(image_gen_config.CRYPTO_KEY_NONCE))
                    prepend_bytes_to_file(file2copy, header2add)


            if 'host' in host_type:
                image_gen_config.host_sub_image_counter += 1
            else:
                image_gen_config.flash_sub_image_counter += 1
        else:
            print_err('Wrong Input Binary (NPU_C/Model) )File Path or File Name!', file_name= bin_file_name)
    except Exception as e:
        print_err('Something get wrong during create Binary images', an_exception=str(e))

    end_time = time.time()
    execution_time = end_time - start_time
    image_gen_config.total_run_time +=  execution_time
    if 'npu_c' in fw_type:
        if 'host' in host_type:
            image_gen_config.log_file.info(f' Run Time for Host Image NPU_C = {round(execution_time, 2)} seconds')
        if 'flash' in host_type:
            image_gen_config.log_file.info(f' Run Time for Flash Image NPU_C = {round(execution_time, 2)} seconds')

def b0_generate_fw_images(elf_file_name, fw_type, host_type, m55_length):
    counter = 0
    im_addr = 0
    gnex_file_bin_length = []
    length_of_sectors_data = []
    im_addr_list = []
    start_time = time.time()
    """
    Generates a binary file to be loaded via host for the M55 device.
    The binary file is created from an AXF/ELF file.
    The function loads data of each section in the AXF/ELF file and writes it to the binary file.
    If there are two sections with the same name, they are loaded together and the size should be an actual loaded size (size1 + size2).
    The function also adds a segment header to each section and a jump address command at the end of the binary file.
    """
    #Evgeny's original code partially
    try:
        # Get the absolute path
        absolute_path = os.path.abspath(elf_file_name)
        if os.path.exists(absolute_path):
            section_infos = get_sections(elf_file_name)
            # file name with extension
            file_name = os.path.basename(elf_file_name)
            # Open binary file to be loaded via host
            if 'm55' in fw_type:
                if 'host' in host_type:
                    info_dict = eval(repr(image_gen_config.dict_m55_info_host))
                else:
                    info_dict = eval(repr(image_gen_config.dict_m55_info_flash))
            else:
                if 'host' in host_type:
                    info_dict = eval(repr(image_gen_config.dict_m4_info_host))
                else:
                    info_dict = eval(repr(image_gen_config.dict_m4_info_flash))

            if 'host' in host_type:
                    print(f" 1_Add FW {fw_type}: {elf_file_name} to SDK Image File: {image_gen_config.output_sdk_host}")
                    image_gen_config.log_file.info(f" 1_Add FW {fw_type}: {elf_file_name} to SDK Image File: {image_gen_config.output_sdk_host}")
                    output_secure_bin = open(image_gen_config.HOST_TEMP_BIN_FILE, "wb")
            else:
                print(f" 2_Add FW {fw_type}: {elf_file_name} to SDK Image File: {image_gen_config.output_sdk_flash}")
                image_gen_config.log_file.info(f" 2_Add FW {fw_type}: {elf_file_name} to SDK Image File: {image_gen_config.output_sdk_flash}")
                if int(info_dict['Encryption_Type']) and image_gen_config.is_sdk_secured:
                    output_secure_bin = open(image_gen_config.OUTPUT_TEMP_BIN_FILE, "wb")
                    axi_crypto_output_secure_bin = open(image_gen_config.FLASH_TEMP_BIN_FILE, "wb")
                else:
                    output_secure_bin = open(image_gen_config.OUTPUT_TEMP_BIN_FILE, "wb")

            try:
                if (int)(info_dict['Encryption_Type']) and 'host' in host_type:
                    print_err('Wrong Encryption_Type Value for Host Image!')
            except Exception:
                print_err('Wrong Encryption_Type Value for Host Image!')

            if 'flash' in host_type:
                m55_offset = (int)(image_gen_config.dict_nvm_data["image_offset_SDK_image_A_offset"], 16)
                image_gen_config.log_file.info(f' Image M55 SDKImage_A_Offset = {(hex)(m55_offset)} ')

            previous_section_name = "1234"
            section_counter = 0
            last_sector = len(section_infos)
            for section_info in section_infos:
                section_name, section_address, section_size = section_info
                if (int)(section_size) == 0:
                    continue
                image_gen_config.log_file.info(f' Image M55 section name = {section_name}, section address = {(hex)(section_address)}, section size = {(hex)(section_size)} bytes')
                print(f' Image M55 section name = {section_name}, section address = {(hex)(section_address)}, section size = {(hex)(section_size)} bytes')
                if (previous_section_name != section_name):
                    section_data = objcopy_load_segment(section_name, elf_file_name)
                else:
                    print("WARNING: Duplicate section name !!!", section_name)
                    image_gen_config.log_file.warning(f'"WARNING: Duplicate section name !!! {section_name}')
                    print(" Assumed to be adjacent to the previous section with the same name, loaded together, total size=", hex(len(section_data)))
                    image_gen_config.log_file.warning(f'Assumed to be adjacent to the previous section with the same name, loaded together, total size= {hex(len(section_data))}')
                    previous_section_name = section_name
                    continue

                previous_section_name = section_name
                # in case of 2 sections with the same name, they are loaded together

                #Align for division on 32 bytes
                while len(section_data) % image_gen_config.VALUE_32 != 0:
                    section_data = section_data + b"\x00"

                if 'host' in host_type:
                    input_section_name_file = image_gen_config.BIN_OUTPUT_FOLDER_PATH.joinpath("FW_HOST_" + section_name + "_data.bin")
                else:
                    input_section_name_file = image_gen_config.BIN_OUTPUT_FOLDER_PATH.joinpath("FW_FLASH_" + section_name + "_data.bin")
                with open(input_section_name_file, "wb") as file:
                    file.write(section_data)

                if 'host' in host_type:
                    output_genx_fw_bin_file = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH, 'GenX_Host_' + section_name + ".bin")
                    if 'm55' in fw_type:
                        sector_genx_fw_bin_file = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES_SDK_BCM,
                                                               str(image_gen_config.GLOBAL_COUNTER_BCM) + "_" + str(image_gen_config.host_sub_image_counter) + "_" + \
                                                                str(fw_type) + '_GenX_HOST_' + section_name + ".bin")
                        add_data2imglst(os.path.basename(sector_genx_fw_bin_file), 'tfm', sector_genx_fw_bin_file)
                    elif 'm4' in fw_type:
                        sector_genx_fw_bin_file = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES_SDK_BCM,
                                                                str(image_gen_config.GLOBAL_COUNTER_BCM) + "_" + str(image_gen_config.host_sub_image_counter) + "_" + \
                                                                    str(fw_type) + '_GenX_HOST_' + section_name + ".bin")
                        add_data2imglst(os.path.basename(sector_genx_fw_bin_file), 'm4', sector_genx_fw_bin_file)
                else:
                    output_genx_fw_bin_file = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH, 'GenX_Flash_' + section_name + ".bin")
                    if 'm55' in fw_type:
                        sector_genx_fw_bin_file = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES_SDK_AXI,
                                                                str(image_gen_config.GLOBAL_COUNTER_AXI) + "_" + str(image_gen_config.flash_sub_image_counter) + "_" + \
                                                                    str(fw_type) + '_GenX_Flash_' + section_name + ".bin")
                        add_data2imglst(os.path.basename(sector_genx_fw_bin_file), 'tfm_axi', sector_genx_fw_bin_file)
                    elif 'm4' in fw_type:
                        sector_genx_fw_bin_file = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES_SDK_AXI,
                                                                str(image_gen_config.GLOBAL_COUNTER_AXI) + "_" + str(image_gen_config.flash_sub_image_counter) + "_" + \
                                                                    str(fw_type) + '_GenX_Flash_' + section_name + ".bin")
                        add_data2imglst(os.path.basename(sector_genx_fw_bin_file), 'm4_axi', sector_genx_fw_bin_file)
                image_gen_config.check_path(output_genx_fw_bin_file)
                image_gen_config.check_path(sector_genx_fw_bin_file)

                try:
                    if (not os.path.exists(info_dict['SCGK_path'])) or \
                        (not os.path.exists(info_dict['IV_path'])) or \
                        (not os.path.exists(info_dict['Priv_Key_Path'])):
                        print_err('One of key Files (SCGK_APBL, IV or/and Private key) is missing. \n Please provide Path of these files in APBL_image_attributes.json.\nThe process cannot continue due to an error above.')
                except Exception:
                    print_err('One of key Files (SCGK_APBL, IV or/and Private key) is missing. \n Please provide Path of these files in APBL_image_attributes.json.\nThe process cannot continue due to an error above.')

                if counter == 0:
                    gnex_file_bin_length.append(image_gen_config.BOOT_COMMAND_SIZE_BYTES)
                required_fields = ['Production_Image_Flag_Value', 'Encryption_Type']
                dict_for_extra_bin = {x:info_dict[x] for x in required_fields}
                convert_dict2apbl_extra_bin(dict_for_extra_bin)

                if not image_gen_config.is_sdk_secured:
                    run_Genx_non_secured(str(info_dict['Priv_Key_Path']), str(input_section_name_file), str(output_genx_fw_bin_file), fw_type)
                else:
                    run_Genx_secured(info_dict, len(section_data), str(input_section_name_file), str(output_genx_fw_bin_file))

                genx_output_data = read_file_to_array(output_genx_fw_bin_file)

                segment_header_sec = bytearray()
                #Convert Dec file size to Hex before Genx for Header
                section_size_hex_word, remainder = divmod(len(section_data), 4)
                try:
                    if remainder != 0:
                        print_err('Wrong FW Image Length File after Convert to Bin Format', file_name=elf_file_name)
                except Exception:
                    print_err('Wrong FW Image Length File after Convert to Bin Format', file_name=elf_file_name)

                # 624 bytes == 156 words
                num_of_secured_words = (int)(image_gen_config.SUM_OF_SECURITY_HEADER_AND_SIGNATURE/4)
                if 'm4' in fw_type:
                    exe_addr = section_address + (int)(image_gen_config.addr_configs['M4_EXE_BASE_ADDR'], 16)
                    fw_image_type = image_gen_config.FW_M4_IMAGE_TYPE
                    if 'flash' in host_type:
                        if m55_length == 0:
                            if counter == 0:
                                im_addr = m55_offset + gnex_file_bin_length[counter]
                            else:
                                im_addr = im_addr + m55_offset + image_gen_config.BOOT_COMMAND_SIZE_BYTES + gnex_file_bin_length[counter]
                        else:
                            print("[rs.log]m55_length=", m55_length);
                            if counter == 0:
                                im_addr = m55_offset + m55_length + gnex_file_bin_length[counter]
                            else:
                                im_addr = im_addr + image_gen_config.BOOT_COMMAND_SIZE_BYTES + gnex_file_bin_length[counter]
                else:
                    exe_addr = section_address
                    fw_image_type = image_gen_config.FW_M55_IMAGE_TYPE
                    if 'flash' in host_type:
                        if counter == 0:
                            im_addr = m55_offset + gnex_file_bin_length[counter]
                        else:
                            im_addr = im_addr + image_gen_config.BOOT_COMMAND_SIZE_BYTES + gnex_file_bin_length[counter]

                # ITCM range or DTCM range
                if 'host' in host_type:
                    if (int)(image_gen_config.memory_regions["ITCM_LOW"], 16) <= exe_addr <= (int)(image_gen_config.memory_regions["ITCM_HIGH"], 16) or \
                        (int)(image_gen_config.memory_regions["DTCM_LOW"], 16) <= exe_addr <= (int)(image_gen_config.memory_regions["DTCM_HIGH"], 16):
                        op_code = 0x13
                        #IM FULL
                        if 'm55' in fw_type:
                            im_addr  = (int)(image_gen_config.addr_configs['M55_IM_ADDR_HOST_FULL_0x13'], 16)
                        elif 'm4' in fw_type:
                            im_addr  = (int)(image_gen_config.addr_configs['M4_IM_ADDR_HOST_FULL_0x13'], 16)
                    else:
                        op_code = 0x12
                        #IM Header Signature
                        if 'm55' in fw_type:
                            im_addr  = (int)(image_gen_config.addr_configs['M55_IM_ADDR_HOST_HEADER_SIGN_0x12'], 16)
                        elif 'm4' in fw_type:
                            im_addr  = (int)(image_gen_config.addr_configs['M4_IM_ADDR_HOST_HEADER_SIGN_0x12'], 16)
                else:
                    op_code = 0x13
                if 'm4' in fw_type:
                    image_gen_config.log_file.info(f' Image M4 exe address = {(hex)(exe_addr)}, Intermediate address = {(hex)(im_addr)}')
                if 'm55' in fw_type:
                    image_gen_config.log_file.info(f' Image M55 exe address = {(hex)(exe_addr)}, Intermediate address = {(hex)(im_addr)}')

                if 'flash' in host_type:
                    im_addr_list.append(im_addr - image_gen_config.BOOT_COMMAND_SIZE_BYTES)

                # start constructing the sector header in m55/m4 image for bootloader
                segment_header_sec.extend([0x5b, 0x5a, 0x33, op_code])
                if section_counter == 0 and 'm55' in fw_type:
                    segment_header_sec.extend(struct.pack("<L", get_entry_point_address(elf_file_name)))
                    flags = image_gen_config.FLAG_JUMP_ADDRESS
                else:
                    segment_header_sec.extend(list(image_gen_config.BYTES_4_7))

                    if 'm55' in fw_type and 'm55' in image_gen_config.last_image and section_counter == last_sector - 1:
                        flags = image_gen_config.FLAG_LAST_IMAGE
                    elif 'm4' in fw_type and 'm4' in image_gen_config.last_image and section_counter == last_sector - 1:
                        flags = image_gen_config.FLAG_LAST_IMAGE
                    else:
                        flags = image_gen_config.FLAG_WARM_BOOT

                segment_header_sec.extend(struct.pack("<LLLLLL", num_of_secured_words, section_size_hex_word, exe_addr, im_addr, fw_image_type, flags))

                segment_header_sec.extend(genx_output_data)
                with open(sector_genx_fw_bin_file, "wb") as file:
                    length_of_sectors_data.append((len(segment_header_sec)))
                    file.write(segment_header_sec)
                output_secure_bin.write(segment_header_sec)
                # Delete the files
                if os.path.exists(input_section_name_file):
                    os.remove(input_section_name_file)
                if os.path.exists(output_genx_fw_bin_file):
                    gnex_file_bin_length.append((len)(genx_output_data))
                    counter+=1
                    os.remove(output_genx_fw_bin_file)
                section_counter += 1
                if 'host' in host_type:
                    image_gen_config.host_sub_image_counter += 1
                else:
                    image_gen_config.flash_sub_image_counter += 1
            output_secure_bin.close()

            if int(info_dict['Encryption_Type']) and image_gen_config.is_sdk_secured and 'flash' in host_type:
                # Run AXICrypto, for crypto use XSPI_XIP_ADDR + m55_offset/m4_offset
                if 'm55' in fw_type:
                    start_addr = (int)(image_gen_config.memory_regions['XSPI_XIP_BASE_ADDRESS'], 16) + m55_offset
                    image_gen_config.log_file.info(f' Image M55 start address = {(hex)(start_addr)}')
                if 'm4' in fw_type:
                    if m55_length == 0:
                        m4_offset = (int)(image_gen_config.dict_nvm_data["image_offset_SDK_image_A_offset"], 16)
                    else:
                        m4_offset = m55_offset + m55_length
                    start_addr = (int)(image_gen_config.memory_regions['XSPI_XIP_BASE_ADDRESS'], 16) + m4_offset
                    image_gen_config.log_file.info(f' Image M4 start address = {(hex)(start_addr)}')
                run_Genx_AXI_Crypto(output_secure_bin.name, info_dict['AXICrypto_Key_Path'], info_dict['AXICrypto_Nonce_Path'], axi_crypto_output_secure_bin.name, start_addr)
                #Add start address to the beggining of the axi_crypto_output_secure_bin

                if os.path.exists(output_secure_bin.name):
                    os.remove(output_secure_bin.name)

                # Open the original file for reading
                with open(axi_crypto_output_secure_bin.name, 'rb') as original_file:
                    crypto_data = original_file.read()

                #get folder name
                current_folder = os.path.dirname(sector_genx_fw_bin_file)
                # Get all file names in the folder
                file_names = os.listdir(current_folder)
                # Iterate over each file name
                i = 0
                j = 0
                for file_name in file_names:
                   if fw_type in file_name:
                    #create new file
                        axy_crypto_sector_file_name = os.path.join(current_folder, file_name)
                        with open(axy_crypto_sector_file_name, 'wb') as original_file:
                            original_file.write(crypto_data[i:length_of_sectors_data[j] + i])
                        start_addr_hex = (hex)((int)(image_gen_config.memory_regions['XSPI_XIP_BASE_ADDRESS'], 16) + im_addr_list[j])[2:]
                        start_addr_hex = start_addr_hex.rjust(8, '0')
                        header2add = bytearray()
                        header2add.extend( bytearray(hexStr2ReversedList(start_addr_hex)))
                        header2add.extend( bytearray(image_gen_config.CRYPTO_OFFSET))
                        header2add.extend( bytearray(image_gen_config.CRYPTO_KEY_NONCE))

                        i = i + length_of_sectors_data[j]
                        j += 1
                        prepend_bytes_to_file(axy_crypto_sector_file_name, header2add)

            if 'host' in host_type:
                with open(image_gen_config.output_sdk_host, 'ab+') as file:
                    # Write the new byte array to the beginning of the file
                    file.write(read_file_to_array(output_secure_bin.name))
            else:
                if int(info_dict['Encryption_Type']) and image_gen_config.is_sdk_secured:
                    with open(image_gen_config.output_sdk_flash, 'ab+') as file:
                        # Write the new byte array to the beginning of the file
                        file.write(read_file_to_array(axi_crypto_output_secure_bin.name))
                else:
                    with open(image_gen_config.output_sdk_flash, 'ab+') as file:
                    # Write the new byte array to the beginning of the file
                        file.write(read_file_to_array(output_secure_bin.name))

            #Check that M4 size does not bigger then NPU_C_EXE_BASE_ADDR - M4_EXE_BASE_ADDR
            try:
                if ('m4' in fw_type) and ('flash' in host_type):
                    request_size = (int)(image_gen_config.addr_configs["NPU_C_EXE_BASE_ADDR"], 16) - (int)(image_gen_config.addr_configs["M4_EXE_BASE_ADDR"], 16)
                    if  image_gen_config.is_sdk_secured:
                        if os.path.getsize(axi_crypto_output_secure_bin.name) >= request_size:
                            print_err('Wrong Size of FW M4!')
                    else:
                        if os.path.getsize(output_secure_bin.name) >= request_size:
                            print_err('Wrong Size of FW M4!')
            except Exception:
                    print_err('Wrong Size of FW M4! ')
        else:
            print_err('Wrong Input FW (M55/M4) File Path or File Name!', file_name= elf_file_name)
    except Exception as e:
        print_err('Something get wrong during create FW images', an_exception=str(e))

    end_time = time.time()
    execution_time = end_time - start_time
    image_gen_config.total_run_time +=  execution_time
    if 'm55' in fw_type:
        if 'host' in host_type:
            image_gen_config.log_file.info(f' Run Time for Host Image M55 = {round(execution_time, 2)} seconds')
        if 'flash' in host_type:
            image_gen_config.log_file.info(f' Run Time for Flash Image M55 = {round(execution_time, 2)} seconds')
    if 'm4' in fw_type:
        if 'host' in host_type:
            image_gen_config.log_file.info(f' Run Time for Host Image M4 = {round(execution_time, 2)} seconds')
        if 'flash' in host_type:
            image_gen_config.log_file.info(f' Run Time for Flash Image M4 = {round(execution_time, 2)} seconds')

def create_apbl_image(apbl_input_file_name, apbl_bin_file, host_type):
    '''Create APBL Image for Host or Flash Loading - arguments: axf, apbl bin file, host_type'''
    global spk_size_with_padding_dec
    start_time = time.time()

    # 32byte APBL header
    apbl_header_array =  bytearray()
    dict_apbl_info_host = []

    #check size of input file name and divide to 4, we need it in words
    try:
        absolute_path = os.path.abspath(apbl_input_file_name)

        if os.path.exists(absolute_path):
            file_name = os.path.basename(apbl_input_file_name)

            if 'host' in host_type:
                if image_gen_config.is_sdk_secured:
                    image_gen_config.output_file_name_apbl_host = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_HOST,
                                                                    str(image_gen_config.GLOBAL_COUNTER_BCM) + "_" + file_name.split('.')[0] + "_host_secured.bin")
                else:
                    image_gen_config.output_file_name_apbl_host = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_HOST,
                                                                    str(image_gen_config.GLOBAL_COUNTER_BCM) + "_" + file_name.split('.')[0] + "_host.bin")
                print(f" Create APBL Image for Host Loading: {image_gen_config.output_file_name_apbl_host}")
                image_gen_config.log_file.info(f" Create APBL Image for Host Loading: {image_gen_config.output_file_name_apbl_host}")
            if 'flash' in host_type:
                if image_gen_config.is_sdk_secured:
                    image_gen_config.output_file_name_apbl_flash = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_FLASH,
                                                                    str(image_gen_config.GLOBAL_COUNTER_AXI) + "_" + file_name.split('.')[0] + "_flash_secured.bin")
                else:
                    image_gen_config.output_file_name_apbl_flash = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_FLASH,
                                                                    str(image_gen_config.GLOBAL_COUNTER_AXI) + "_" + file_name.split('.')[0] + "_flash.bin")
                print(f" Create APBL Images for Flash Loading: {image_gen_config.output_file_name_apbl_flash}")
                image_gen_config.log_file.info(f" Create APBL Images for Flash Loading: {image_gen_config.output_file_name_apbl_flash}")

            genx_apbl_bin_file = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH, 'GenX_' + file_name.split('.')[0] + ".bin")

            #read data from input file and calclualte input file size
            netto_bin_data_for_output = read_file_to_array(apbl_bin_file)

            # Align for division on 32 bytes - genx expects data to be 32bytes aligned
            while len(netto_bin_data_for_output) % image_gen_config.VALUE_32 != 0:
                netto_bin_data_for_output = netto_bin_data_for_output + b"\x00"

            if (not os.path.exists(image_gen_config.dict_apbl_info['SCGK_path'])) or \
                (not os.path.exists(image_gen_config.dict_apbl_info['IV_path'])) or \
                (not os.path.exists(image_gen_config.dict_apbl_info['Priv_Key_Path'])):
                print_err('One of key Files (SCGK_APBL, IV or/and Private key) is missing. \n Please provide Path of these files in APBL_image_attributes.json.\nThe process cannot continue due to an error above.')

            # Get Exe Addr - # Extract execution address from elf file with readelf
            exe_addr = (hex)(get_load_address(apbl_input_file_name))[2:]
            exe_addr = exe_addr.zfill(image_gen_config.LENGTH_8_BITS)
            image_gen_config.log_file.info(f' APBL exe address = 0x{exe_addr}')

            required_fields = ['Production_Image_Flag_Value', 'INITSVTOR_Value', 'Destination_Address_Value']
            if 'flash' in host_type:
                dict_for_extra_bin = {x:image_gen_config.dict_apbl_info[x] for x in required_fields}
            if 'host' in host_type:
                host_extra_bin_path = (hex)(get_entry_point_address(apbl_input_file_name))
                dict_apbl_info_host   = eval(repr(image_gen_config.dict_apbl_info))
                dict_apbl_info_host['INITSVTOR_Value'] = host_extra_bin_path[2:]
                dict_apbl_info_host['Destination_Address_Value'] = exe_addr
                dict_for_extra_bin = {x:dict_apbl_info_host[x] for x in required_fields}

            # convert dict to bin file
            convert_dict2apbl_extra_bin(dict_for_extra_bin)

            # run Genx for APBL
            #if not image_gen_config.is_sdk_secured:
            #run_Genx_non_secured(image_gen_config.dict_apbl_info['Priv_Key_Path'], apbl_bin_file, genx_apbl_bin_file, 'apbl')
            #else:
            run_Genx_secured(image_gen_config.dict_apbl_info, len(netto_bin_data_for_output), apbl_bin_file, genx_apbl_bin_file)

            bin_data_for_output_after_genx = read_file_to_array(genx_apbl_bin_file)

            # Convert Dec Apbl file size to Hex before Genx for Header
            file_size_hex_word, remainder = convert_dec2hex_file_size(len(netto_bin_data_for_output))
            if remainder != 0:
                print_err('Wrong APBL Length File after Convert to Bin Format', file_name= apbl_bin_file)

            # ITCM range or DTCM range - set opcode to 0x13 or 0x12 header 32 bytes
            if(int)(image_gen_config.memory_regions["ITCM_LOW"], 16) <= (int)(exe_addr,16) <= (int)(image_gen_config.memory_regions["ITCM_HIGH"], 16) or \
                (int)(image_gen_config.memory_regions["DTCM_LOW"], 16) <= (int)(exe_addr,16) <= (int)(image_gen_config.memory_regions["DTCM_HIGH"], 16):
                op_code = image_gen_config.OP_CODE_SEC_IMG_NOT_IN_PLACE_0x13
            else:
                op_code = image_gen_config.OP_CODE_SEC_IMG_IN_PLACE_0x12

            #create apbl header
            header2add_list = image_gen_config.SYNC_1 + image_gen_config.SYNC_2 + image_gen_config.SRV_ID + op_code + image_gen_config.BYTES_4_7
            #calculate Num of Word 1: Size of image header + size of signature
            num_words_1_hex, r = convert_dec2hex_file_size(image_gen_config.SUM_OF_SECURITY_HEADER_AND_SIGNATURE)
            header2add_list.extend(hexStr2ReversedList(num_words_1_hex))
            #add to header Num Word 2, Size of image body = file size
            header2add_list.extend(hexStr2ReversedList(file_size_hex_word))
            #add exe addr to header
            header2add_list.extend(hexStr2ReversedList(exe_addr))
            header2add_list.extend(hexStr2ReversedList(image_gen_config.addr_configs['APBL_IM_ADDR']))
            #Add IM Addr and Img Type and Zero Bits
            header2add_list = header2add_list + image_gen_config.APBL_IMG_TYPE_FOR_BOOT_LOADER + image_gen_config.BITS_28_31

            # convert list of bytes to bytes array
            apbl_header_array.extend(header2add_list)

            # Write the opcode 0x0C "Run Image"
            if image_gen_config.is_B0_chip:
                run_img_cmd = bytearray([0x5b, 0x5a, 0x33, 0x0c])
                run_img_cmd.extend(list(image_gen_config.BYTES_4_7))
                run_img_cmd.extend(struct.pack("<L", get_entry_point_address(apbl_input_file_name)))
                run_img_cmd.extend(list(image_gen_config.BYTES_12_31))

            if 'host' in host_type:
                # create apbl file to host and write data
                # Write final data to the host output file: header + bin data genx output + run image command
                with open(image_gen_config.output_file_name_apbl_host, 'wb+') as file:
                    file.write(apbl_header_array + bin_data_for_output_after_genx + run_img_cmd)

            # write the all data to apbl flash: created header and current bun data to the output file
            if 'flash' in host_type:
                with open(image_gen_config.output_file_name_apbl_flash, 'wb+') as file:
                    # Write the new byte array to the beginning of the file
                    # Write final data to the flash output file: header + bin data genx output
                    file.write(apbl_header_array + bin_data_for_output_after_genx)

            # Copy APBL bin file to Sub Images folder
            if not image_gen_config.file2copy_apbl and 'flash' in host_type:
                image_gen_config.file2copy_apbl =  os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES_APBL,str(image_gen_config.GLOBAL_COUNTER_BCM) + "_0_apbl.bin")
                image_gen_config.check_path(image_gen_config.file2copy_apbl)
                shutil.copy(image_gen_config.output_file_name_apbl_flash, image_gen_config.file2copy_apbl)
                add_data2imglst(os.path.basename(image_gen_config.file2copy_apbl), 'apbl', image_gen_config.file2copy_apbl)

            #Write file size to attributes dictionary
            #check that file_size_hex_word is 2 bytes, if not - will add the 0x0
            # TODO: probably need to remove this check
            if 'flash' in host_type:
                apbl_size_with_padding_dec =  (int)(os.path.getsize(image_gen_config.output_file_name_apbl_flash))
                #update dict, size should be with apdding
                spk_abpl_size = (hex)(apbl_size_with_padding_dec + spk_size_with_padding_dec)[2:]

                #padding to 8 bytes length
                spk_abpl_size = spk_abpl_size.zfill(image_gen_config.LENGTH_8_BITS)
                # spk_abpl_size_a = int(image_gen_config.dict_attributes_A["K0_K1_SPK_B_offset"], 16) - int(image_gen_config.dict_attributes_A["K0_K1_SPK_A_offset"], 16)
                # spk_abpl_size_b = int(image_gen_config.dict_nvm_data["image_offset_SDK_image_A_offset"], 16) - int(image_gen_config.dict_attributes_A["K0_K1_SPK_B_offset"], 16)
                # image_gen_config.dict_attributes_A["K0_K1_SPK_A_size_APBL_A_size"] = hex(spk_abpl_size_a)[2:]
                # image_gen_config.dict_attributes_A["K0_K1_SPK_B_size_APBL_B_size"] = hex(spk_abpl_size_b)[2:]

            os.remove(genx_apbl_bin_file)
        else:
            print_err('Wrong Input APBL File Path or File Name!', file_name= apbl_input_file_name)
    except Exception as e:
        print_err('Something get wrong during create APBL images', an_exception=str(e))

    end_time = time.time()
    execution_time = end_time - start_time
    image_gen_config.total_run_time +=  execution_time
    if 'host' in host_type:
        image_gen_config.log_file.info(f' Run Time for Host Image APBL = {round(execution_time, 2)} seconds')
    if 'flash' in host_type:
        image_gen_config.log_file.info(f' Run Time for Flash Image APBL = {round(execution_time, 2)} seconds')


# Create SPK header, add this header to SPK binary
# Break down spk to subimages according to imglst json for sign server
def create_k0_k1_spk_full_image(spk_input_file_name, host_type: str):
    global spk_size_with_padding_dec
    start_time = time.time()
    spk_header_array =  bytearray()

    #check size of input file name and divide to 4, we need it in words
    try:
        absolute_path = os.path.abspath(spk_input_file_name)
        if os.path.exists(absolute_path):
            file_name = os.path.basename(spk_input_file_name)

            if 'host' in host_type:
                image_gen_config.output_file_name_spk_host = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_HOST,
                                                                str(image_gen_config.GLOBAL_COUNTER_BCM) + "_" + file_name.split('.')[0] + "_host_secured.bin"  )
                print(f" Create SPK Image for Host Loading: {image_gen_config.output_file_name_spk_host}")
                image_gen_config.log_file.info(f" Create SPK Image for Host Loading: {image_gen_config.output_file_name_spk_host}")
                # Check if the directory exists
                directory_host = os.path.dirname(image_gen_config.output_file_name_spk_host)

                if not os.path.exists(directory_host):
                    # If the directory doesn't exist, create it
                    os.makedirs(directory_host)


            if 'flash' in host_type:
                image_gen_config.output_file_name_spk_flash = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_FLASH,
                                                                str(image_gen_config.GLOBAL_COUNTER_AXI) + "_" + file_name.split('.')[0] + "_flash_secured.bin")
                print(f" Create SPK Image for Flash Loading: {image_gen_config.output_file_name_spk_flash}")
                image_gen_config.log_file.info(f" Create SPK Image for Flash Loading: {image_gen_config.output_file_name_spk_flash}")
                directory_flash = os.path.dirname(image_gen_config.output_file_name_spk_flash)
                if not os.path.exists(directory_flash):
                    # If the directory doesn't exist, create it
                    os.makedirs(directory_flash)

                # create files for SPK break down
                file_spk_external_header        =  os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES_SPK,  image_gen_config.SPK_EXTERNAL_HEADER)
                image_gen_config.check_path(file_spk_external_header)
                file_spk_k0_syna                =  os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES_SPK,  image_gen_config.SPK_K0_SYNA)
                image_gen_config.check_path(file_spk_k0_syna)
                file_spk_k0_oem                 =  os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES_SPK,  image_gen_config.SPK_K0_OEM)
                image_gen_config.check_path(file_spk_k0_oem)
                file_spk_k1_boot_a              =  os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES_SPK,  image_gen_config.SPK_K1_BOOT_A)
                image_gen_config.check_path(file_spk_k1_boot_a)
                file_spk_k1_spe_a               =  os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES_SPK,  image_gen_config.SPK_K1_SPE_A)
                image_gen_config.check_path(file_spk_k1_spe_a)
                file_spk_k1_spe_b               =  os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES_SPK,  image_gen_config.SPK_K1_SPE_B)
                image_gen_config.check_path(file_spk_k1_spe_b)
                file_spk_k1_spe_c               =  os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES_SPK,  image_gen_config.SPK_K1_SPE_C)
                image_gen_config.check_path(file_spk_k1_spe_c)
                file_spk_k1_nspe_a              =  os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES_SPK,  image_gen_config.SPK_K1_NSPE_A)
                image_gen_config.check_path(file_spk_k1_nspe_a)
                file_spk_header_signature_body  =  os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES_SPK,  image_gen_config.SPK_HEADER_SIGNATURE_BODY)
                image_gen_config.check_path(file_spk_header_signature_body)

            bin_data_for_output = read_file_to_array(spk_input_file_name)
            file_size_dec = (int)(os.path.getsize(spk_input_file_name))

            # calculate file size in hex and add padding
            file_size_hex_word, remainder = convert_dec2hex_file_size(file_size_dec)
            if remainder != 0:
                pad = b"\x00" * (4-remainder)
                bin_data_for_output = bin_data_for_output + pad

            # create SPK header
            header2add_list = list(image_gen_config.SYNC_1) + list(image_gen_config.SYNC_2) + list(image_gen_config.SRV_ID) + list(image_gen_config.OP_CODE_DOWN_SPK_0x11)  + list(image_gen_config.BYTES_4_7)
            header2add_list.extend( hexStr2ReversedList(file_size_hex_word))
            header2add_list.extend( hexStr2ReversedList(image_gen_config.addr_configs['SPK_IM_ADDR']))
            header2add_list = header2add_list + list(image_gen_config.BYTES_16_31)

            #convert list of bytes to bytes array
            spk_header_array.extend(header2add_list)

            #write data
            if 'host' in host_type:
                with open(image_gen_config.output_file_name_spk_host, 'wb+') as file:
                    file.write(spk_header_array + bin_data_for_output)

            if 'flash' in host_type:
                with open(image_gen_config.output_file_name_spk_flash, 'wb+') as file:
                    # Write the new byte array to the beginning of the file
                    file.write(spk_header_array + bin_data_for_output)

                # SPK Break down to sub images
                with open(file_spk_external_header, 'wb+') as file:
                    # Write the new byte array to the beginning of the file
                    file.write(spk_header_array)

                bin_data_counter = 0
                with open(file_spk_k0_syna, 'wb+') as file:
                    # Write the new byte array to the beginning of the file
                    file.write(bin_data_for_output[:image_gen_config.SPK_K0_SYNA_SIZE])
                bin_data_counter = bin_data_counter + image_gen_config.SPK_K0_SYNA_SIZE
                add_data2imglst(os.path.basename(file_spk_k0_syna), 'k0syna', file_spk_k0_syna)

                with open(file_spk_k0_oem, 'wb+') as file:
                    # Write the new byte array to the beginning of the file
                    file.write(bin_data_for_output[bin_data_counter:bin_data_counter + image_gen_config.SPK_K0_OEM_SIZE])
                bin_data_counter = bin_data_counter + image_gen_config.SPK_K0_OEM_SIZE
                add_data2imglst(os.path.basename(file_spk_k0_oem), 'k0syna', file_spk_k0_oem)

                with open(file_spk_k1_boot_a, 'wb+') as file:
                    # Write the new byte array to the beginning of the file
                    file.write(bin_data_for_output[bin_data_counter:bin_data_counter + image_gen_config.SPK_K1_SIZE])
                bin_data_counter = bin_data_counter + image_gen_config.SPK_K1_SIZE
                add_data2imglst(os.path.basename(file_spk_k1_boot_a), 'k1boota', file_spk_k1_boot_a)

                with open(file_spk_k1_spe_a, 'wb+') as file:
                    # Write the new byte array to the beginning of the file
                    file.write(bin_data_for_output[bin_data_counter:bin_data_counter + image_gen_config.SPK_K1_SIZE])
                bin_data_counter = bin_data_counter + image_gen_config.SPK_K1_SIZE
                add_data2imglst(os.path.basename(file_spk_k1_spe_a), 'k1spea', file_spk_k1_spe_a)

                with open(file_spk_k1_spe_b, 'wb+') as file:
                    # Write the new byte array to the beginning of the file
                    file.write(bin_data_for_output[bin_data_counter:bin_data_counter + image_gen_config.SPK_K1_SIZE])
                bin_data_counter = bin_data_counter + image_gen_config.SPK_K1_SIZE
                add_data2imglst(os.path.basename(file_spk_k1_spe_b), 'k1speb', file_spk_k1_spe_b)

                with open(file_spk_k1_spe_c, 'wb+') as file:
                    # Write the new byte array to the beginning of the file
                    file.write(bin_data_for_output[bin_data_counter:bin_data_counter + image_gen_config.SPK_K1_SIZE])
                bin_data_counter = bin_data_counter + image_gen_config.SPK_K1_SIZE
                add_data2imglst(os.path.basename(file_spk_k1_spe_c), 'k1spec', file_spk_k1_spe_c)

                with open(file_spk_k1_nspe_a, 'wb+') as file:
                    # Write the new byte array to the beginning of the file
                    file.write(bin_data_for_output[bin_data_counter:bin_data_counter + image_gen_config.SPK_K1_SIZE])
                bin_data_counter = bin_data_counter + image_gen_config.SPK_K1_SIZE
                # k1nspea is the customer's key, we do not resign it

                with open(file_spk_header_signature_body, 'wb+') as file:
                    # Write the new byte array to the beginning of the file
                    file.write(bin_data_for_output[bin_data_counter:])
                add_data2imglst(os.path.basename(file_spk_header_signature_body), 'spk', file_spk_header_signature_body)

                # Write file size to attributes dictionary
                spk_size_with_padding_dec = (int)(os.path.getsize(image_gen_config.output_file_name_spk_flash))

            if 'host' in host_type:
                image_gen_config.GLOBAL_COUNTER_BCM += 1

            if 'flash' in host_type:
                image_gen_config.GLOBAL_COUNTER_AXI += 1
        else:
            print_err('Wrong Input SPK File Path or File Name!', file_name= spk_input_file_name)
    except Exception as e:
        print_err('Something get wrong during create SPK images', an_exception=str(e))

    end_time = time.time()
    execution_time = end_time - start_time
    image_gen_config.total_run_time +=  execution_time
    image_gen_config.log_file.info(f' Run Time for SPK = {round(execution_time, 2)} seconds')