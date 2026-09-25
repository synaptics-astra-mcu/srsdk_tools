import os,  time
import image_gen_config
import sys
import binascii
from Services.utils import *


def create_attribute_parameters(flash_type, flash_freq, flash_support_4_bit):
    ''' Create the attribute files from json for the flash image '''
    attr_header_A = bytearray()
    start_time = time.time()

    if image_gen_config.is_B0_chip:
        if flash_type and flash_freq:
            image_gen_config.output_file_name_attr_a = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_FLASH, "Attr_A_" + flash_type + "_" + flash_freq + "Mhz.bin")
            image_gen_config.output_file_name_attr_b = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_FLASH, "Attr_B_" + flash_type + "_" + flash_freq + "Mhz.bin")
        else:
            image_gen_config.output_file_name_attr_a = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_FLASH, "Attr_A.bin")
            image_gen_config.output_file_name_attr_b = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_FLASH, "Attr_B.bin")
        print(f" Created Attribute file: {image_gen_config.output_file_name_attr_a}")
        print(f" Created Attribute file: {image_gen_config.output_file_name_attr_b}")
        image_gen_config.log_file.info(f' Created Attribute file: {image_gen_config.output_file_name_attr_a}; flash_type: {flash_type}; flash_freq {flash_freq}')
        image_gen_config.log_file.info(f' Created Attribute file: {image_gen_config.output_file_name_attr_b}; flash_type: {flash_type}; flash_freq {flash_freq}')

    if flash_type and flash_freq:
        if (flash_type != "MX25U128"):
            image_gen_config.dict_attributes_A["RD_SR2_CMD"] = '00000035'	# Command to read SR2, 1 byte returned
            image_gen_config.dict_attributes_A["SR_QE_BIT"] = '00000009'     # 0-15, bit number for status registers of 1byte or 2byte size

        if (int)(flash_freq) == image_gen_config.DEFAULT_FLASH_MX_FREQ_34:
            image_gen_config.dict_attributes_A["Pll_On_dll_phy_ctrl_reg_val"] = '00000707'
            image_gen_config.dict_attributes_A["Pll_On_dll_master_ctrl_reg_val"] = '001400ff'
            image_gen_config.dict_attributes_A["Pll_On_dll_slave_ctrl_reg_val"] = '00003300'
            image_gen_config.dict_attributes_A["Pll_On_Max_QSPI_Frequency_in_MHz"] = '00000022'

        if (int)(flash_freq) == image_gen_config.DEFAULT_FLASH_MX_FREQ_67:
            image_gen_config.dict_attributes_A["Pll_On_dll_phy_ctrl_reg_val"] = '00000707'
            image_gen_config.dict_attributes_A["Pll_On_dll_master_ctrl_reg_val"] = '0014008e'
            image_gen_config.dict_attributes_A["Pll_On_dll_slave_ctrl_reg_val"] = '00003322'
            image_gen_config.dict_attributes_A["Pll_On_Max_QSPI_Frequency_in_MHz"] = '00000043'

        if (int)(flash_freq) == image_gen_config.FLASH_FREQ_100:
            image_gen_config.dict_attributes_A["Pll_On_dll_phy_ctrl_reg_val"] = '00000707'
            image_gen_config.dict_attributes_A["Pll_On_dll_master_ctrl_reg_val"] = '0014005f'
            image_gen_config.dict_attributes_A["Pll_On_dll_slave_ctrl_reg_val"] = '00003366'
            image_gen_config.dict_attributes_A["Pll_On_Max_QSPI_Frequency_in_MHz"] = '00000064'

        if (int)(flash_freq) == image_gen_config.FLASH_FREQ_134:
            image_gen_config.dict_attributes_A["Pll_On_dll_phy_ctrl_reg_val"] = '00200707'
            image_gen_config.dict_attributes_A["Pll_On_dll_master_ctrl_reg_val"] = '00140047'
            image_gen_config.dict_attributes_A["Pll_On_dll_slave_ctrl_reg_val"] = '00003338'
            image_gen_config.dict_attributes_A["Pll_On_Max_QSPI_Frequency_in_MHz"] = '00000086'


        if flash_support_4_bit == 1:
            image_gen_config.dict_attributes_A["Support_4_bit"] = '00000001'
        else:
            image_gen_config.dict_attributes_A["Support_4_bit"] = '00000000'

    attr_header_A.extend(attr_dict2list(image_gen_config.dict_attributes_A, image_gen_config.ATTR_LENGTH, 'attr'))

    with open(image_gen_config.output_file_name_attr_a, 'wb+') as file:
        # Write the new byte array to the beginning of the file
        file.write(bytearray(attr_header_A))

    #copy attr file to sub-images folders
    file2copy_attr =  os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES_ATTR, os.path.basename(image_gen_config.output_file_name_attr_a))
    image_gen_config.check_path(file2copy_attr)
    shutil.copy(image_gen_config.output_file_name_attr_a, file2copy_attr)

    if image_gen_config.is_B0_chip and image_gen_config.single_slot == False:
        with open(image_gen_config.output_file_name_attr_b, 'wb+') as file:
        # Write the new byte array to the beginning of the file
            file.write(bytearray(attr_header_A))
        #copy attr file to sub-images folders
        file2copy_attr =  os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES_ATTR,  os.path.basename(image_gen_config.output_file_name_attr_b))
        image_gen_config.check_path(file2copy_attr)
        shutil.copy(image_gen_config.output_file_name_attr_b, file2copy_attr)

    end_time = time.time()
    execution_time = end_time - start_time
    image_gen_config.total_run_time +=  execution_time
    image_gen_config.log_file.info(f' Run Time Attributes = {round(execution_time, 2)} seconds')


def parse_binary_file_to_attr(flash_image_file):
    list_attr_a_values = []
    list_attr_b_values = []
    start_time = time.time()

    counter = 1

    image_gen_config.output_file_path_attr_a = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_FLASH,'output_binary_file_attr_a.json')
    image_gen_config.output_file_path_attr_b = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_FLASH,'output_binary_file_attr_b.json')
    print(f" Created Attribute File: {image_gen_config.output_file_path_attr_a}")
    print(f" Created Attribute File: {image_gen_config.output_file_path_attr_b}")
    image_gen_config.log_file.info(f" Created Attribute File: {image_gen_config.output_file_path_attr_a}")
    image_gen_config.log_file.info(f" Created Attribute File: {image_gen_config.output_file_path_attr_b}")

    try:
        # Open the binary file in binary mode
        with open(flash_image_file, 'rb') as input_file:
            # Read and write in chunks of 4 bytes
            chunk_size = 4
            while True:
                # Read 4 bytes from the input file
                data = input_file.read(chunk_size)

                # Break the loop if no more data is left
                if not data:
                    break

                hex_string = binascii.hexlify(data).decode('utf-8').upper()

                # Reverse the hex string from big endian to little endian
                reversed_string = ''.join(reversed([hex_string[i:i+2] for i in range(0, len(hex_string), 2)]))

                if counter*chunk_size > image_gen_config.ATTR_LENGTH * 2:
                    break
                else:
                    if counter * chunk_size > image_gen_config.ATTR_LENGTH:
                        list_attr_b_values.append(reversed_string)
                    else:
                        list_attr_a_values.append(reversed_string)

                counter +=1
        #fill the values to the dictionaries
        dict_attr_a = dict(zip(image_gen_config.ATTR_DICT_KEY_LIST, list_attr_a_values))
        dict_attr_b = dict(zip(image_gen_config.ATTR_DICT_KEY_LIST, list_attr_b_values))

        #Write the values to the JSON Files
        # Writing dictionary to a JSON file
        with open(image_gen_config.output_file_path_attr_a, 'w') as json_file:
            json.dump(dict_attr_a, json_file, indent=4)
        with open(image_gen_config.output_file_path_attr_b, 'w') as json_file:
            json.dump(dict_attr_b, json_file, indent=4)
    except Exception as e:
        print_err('Something get wrong during parsing Flash Binary file;', an_exception= str(e))

    end_time = time.time()
    execution_time = end_time - start_time
    image_gen_config.total_run_time +=  execution_time
    image_gen_config.log_file.info(f' Run Time For Parse Attributes = {round(execution_time, 2)} seconds')
    sys.exit(0)