import os, time

import image_gen_config
from Services.utils import *

# create full image host or flash
def create_images(flash_type, flash_freq, m55_image, full_image_type):
    start_time = time.time()
    bin_data_full_flash_image = bytes()
    try:
        fw_images_names = ''
        if m55_image:
            fw_m55_file_name = os.path.basename(m55_image)
            fw_images_names = fw_m55_file_name.split('.')[0]

        if image_gen_config.is_B0_chip:
            if image_gen_config.is_sdk_secured:
                if 'host' in full_image_type:
                    image_gen_config.output_full_host_file  = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_HOST, image_gen_config.chip_type + "host_full_image_secured.bin")
                if 'flash' in full_image_type:
                    if flash_type and flash_freq:
                        image_gen_config.output_full_flash_file = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_FLASH, image_gen_config.chip_type + "flash_full_image_" + flash_type + "_" + flash_freq + "Mhz_secured.bin")
                    else:
                        image_gen_config.output_full_flash_file = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_FLASH, image_gen_config.chip_type + "flash_full_image_secured.bin")
            else:
                if 'host' in full_image_type:
                    image_gen_config.output_full_host_file  = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_HOST, image_gen_config.chip_type + "host_full_image.bin")
                if 'flash' in full_image_type:
                    if flash_type and flash_freq:
                        image_gen_config.output_full_flash_file = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_FLASH, image_gen_config.chip_type + "flash_full_image_" + flash_type + "_" + flash_freq + "Mhz.bin")
                    else:
                        image_gen_config.output_full_flash_file = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_FLASH, image_gen_config.chip_type + "flash_full_image.bin")
            if 'host' in full_image_type:
                print(f"--- Create full image: {image_gen_config.output_full_host_file}")
                image_gen_config.log_file.info(f" Createted full image: {image_gen_config.output_full_host_file}")
            if 'flash' in full_image_type:
                print(f"--- Create full image: {image_gen_config.output_full_flash_file}")
                image_gen_config.log_file.info(f" Createted full image: {image_gen_config.output_full_flash_file}")

            if m55_image and 'host' in full_image_type:
                host_run_c_cmds_bin_file = create_run_cmds_bin_file(m55_image, 'm55')
                #Add Run Command to Host SDK Image
                with open(image_gen_config.output_sdk_host, 'ab+') as file:
                    file.write( read_file_to_array(host_run_c_cmds_bin_file))
                os.remove(host_run_c_cmds_bin_file)

                #create full flash image
                bin_data_full_host_image =  read_file_to_array(image_gen_config.output_file_name_spk_host) + \
                                            read_file_to_array(image_gen_config.output_file_name_apbl_host) + \
                                            read_file_to_array(image_gen_config.output_sdk_host)

                #create and write data to host output file
                with open(image_gen_config.output_full_host_file, 'wb+') as file:
                    file.write(bin_data_full_host_image)

            #create full flash image
            if 'flash' in full_image_type:
                 # Build: Attr_A → SPK_A → APBL_A → NVM_A → SDK_A
                def pad_to(buf, target_off):
                    if len(buf) > target_off:
                        print_err_multi_value(
                            error_str1='Wrong Length: current len = ', value_1=hex(len(buf)),
                            error_str2='target off = ', value_2=hex(target_off)
                        )
                    # pad with 0x00; change to b'\xFF' * (...) if you prefer erased-fill
                    return buf + bytearray(target_off - len(buf))
                if image_gen_config.single_slot:
                    # 1) Attributes A first
                    bin_data_full_flash_image = read_file_to_array(image_gen_config.output_file_name_attr_a)

                    # 2) SPK A at K0_K1_SPK_A_offset (from attributes A)
                    spk_a_off = int(image_gen_config.dict_attributes_A["K0_K1_SPK_A_offset"], 16)
                    bin_data_full_flash_image = pad_to(bin_data_full_flash_image, spk_a_off)
                    bin_data_full_flash_image += read_file_to_array(image_gen_config.output_file_name_spk_flash)

                    # 3) APBL A at APBL_A_Offset
                    apbl_a_off = int(image_gen_config.dict_attributes_A["APBL_A_Offset"], 16)
                    bin_data_full_flash_image = pad_to(bin_data_full_flash_image, apbl_a_off)
                    bin_data_full_flash_image += read_file_to_array(image_gen_config.output_file_name_apbl_flash)

                    # 4) NVM A at FW_NV_A_offset
                    nvm_a_off = int(image_gen_config.dict_attributes_A["FW_NV_A_offset"], 16)
                    bin_data_full_flash_image = pad_to(bin_data_full_flash_image, nvm_a_off)
                    bin_data_full_flash_image += read_file_to_array(image_gen_config.nvm_bin_data)

                    # 5) SDK A at SDK A offset from NVM (image_offset_SDK_image_A_offset)
                    sdk_a_off = int(image_gen_config.dict_nvm_data["image_offset_SDK_image_A_offset"], 16)
                    bin_data_full_flash_image = pad_to(bin_data_full_flash_image, sdk_a_off)
                    if image_gen_config.output_sdk_flash:
                        bin_data_full_flash_image += read_file_to_array(image_gen_config.output_sdk_flash)

                    # Finish: write the full image
                    with open(image_gen_config.output_full_flash_file, 'wb+') as f:
                        f.write(bin_data_full_flash_image)
                else:
                    # Two-slot order: Attr_A → Attr_B → SPK_A → APBL_A → SPK_B → APBL_B → NVM_A → NVM_B → SDK_A → SDK_B
                    bin_data_full_flash_image = read_file_to_array(image_gen_config.output_file_name_attr_a)

                    # Attributes B at ATTR_B_OFFSET
                    attr_b_off = int(image_gen_config.addr_configs["ATTR_B_OFFSET"], 16)
                    if attr_b_off != 0xFFFFFFFF:
                        bin_data_full_flash_image = pad_to(bin_data_full_flash_image, attr_b_off)
                        bin_data_full_flash_image += read_file_to_array(image_gen_config.output_file_name_attr_b)

                    # SPK A at K0_K1_SPK_A_offset
                    spk_a_off = int(image_gen_config.dict_attributes_A["K0_K1_SPK_A_offset"], 16)
                    bin_data_full_flash_image = pad_to(bin_data_full_flash_image, spk_a_off)
                    bin_data_full_flash_image += read_file_to_array(image_gen_config.output_file_name_spk_flash)

                    # APBL A at APBL_A_Offset
                    apbl_a_off = int(image_gen_config.dict_attributes_A["APBL_A_Offset"], 16)
                    bin_data_full_flash_image = pad_to(bin_data_full_flash_image, apbl_a_off)
                    bin_data_full_flash_image += read_file_to_array(image_gen_config.output_file_name_apbl_flash)

                    # SPK B at K0_K1_SPK_B_offset (skip if FFFFFFFF)
                    spk_b_hex = image_gen_config.dict_attributes_A["K0_K1_SPK_B_offset"]
                    spk_b_off = int(spk_b_hex, 16)
                    if spk_b_off != 0xFFFFFFFF:
                        bin_data_full_flash_image = pad_to(bin_data_full_flash_image, spk_b_off)
                        bin_data_full_flash_image += read_file_to_array(image_gen_config.output_file_name_spk_flash)

                    # APBL B at APBL_B_Offset (skip if FFFFFFFF)
                    apbl_b_hex = image_gen_config.dict_attributes_A["APBL_B_Offset"]
                    apbl_b_off = int(apbl_b_hex, 16)
                    if apbl_b_off != 0xFFFFFFFF:
                        bin_data_full_flash_image = pad_to(bin_data_full_flash_image, apbl_b_off)
                        bin_data_full_flash_image += read_file_to_array(image_gen_config.output_file_name_apbl_flash)

                    # NVM A at FW_NV_A_offset
                    nvm_a_off = int(image_gen_config.dict_attributes_A["FW_NV_A_offset"], 16)
                    bin_data_full_flash_image = pad_to(bin_data_full_flash_image, nvm_a_off)
                    bin_data_full_flash_image += read_file_to_array(image_gen_config.nvm_bin_data)

                    # NVM B at FW_NV_B_offset (skip if FFFFFFFF)
                    nvm_b_hex = image_gen_config.dict_attributes_A["FW_NV_B_offset"]
                    nvm_b_off = int(nvm_b_hex, 16)
                    if nvm_b_off != 0xFFFFFFFF:
                        bin_data_full_flash_image = pad_to(bin_data_full_flash_image, nvm_b_off)
                        bin_data_full_flash_image += read_file_to_array(image_gen_config.nvm_bin_data)

                    # SDK A at NVM SDK A offset
                    sdk_a_off = int(image_gen_config.dict_nvm_data["image_offset_SDK_image_A_offset"], 16)
                    bin_data_full_flash_image = pad_to(bin_data_full_flash_image, sdk_a_off)
                    if image_gen_config.output_sdk_flash:
                        bin_data_full_flash_image += read_file_to_array(image_gen_config.output_sdk_flash)

                    # SDK B at NVM SDK B offset (skip if FFFFFFFF)
                    sdk_b_hex = image_gen_config.dict_nvm_data["image_offset_SDK_image_B_offset"]
                    sdk_b_off = int(sdk_b_hex, 16)
                    if sdk_b_off != 0xFFFFFFFF:
                        bin_data_full_flash_image = pad_to(bin_data_full_flash_image, sdk_b_off)
                        if image_gen_config.output_sdk_flash:
                            bin_data_full_flash_image += read_file_to_array(image_gen_config.output_sdk_flash)

                    with open(image_gen_config.output_full_flash_file, 'wb+') as file:
                        file.write(bin_data_full_flash_image)

    except Exception as error:
        # handle the exception
        print("An exception occurred during creating full image: flash :", error)
    end_time = time.time()
    execution_time = end_time - start_time
    image_gen_config.total_run_time +=  execution_time