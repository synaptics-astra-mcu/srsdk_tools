import os,  time
import image_gen_config
import struct
from Services.utils import *

def create_nvm_parameters(model_file):
   
    nvm_data_byte_array = bytearray()
       
    if image_gen_config.is_sdk_secured:  
        image_gen_config.nvm_bin_data = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_FLASH, 'nvm_secured.bin')  
    else:    
        image_gen_config.nvm_bin_data = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_FLASH, 'nvm.bin')  

    image_gen_config.check_path(image_gen_config.nvm_bin_data)           
    image_gen_config.log_file.info(f" Create NVM File {image_gen_config.nvm_bin_data} ")
    
    #Update NVM Data From Attributes 
    #SDK_image_A_Offset
    image_gen_config.dict_nvm_data["security_num_section_1_start_offset"] = image_gen_config.dict_nvm_data["image_offset_SDK_image_A_offset"] 
    #SDK_image_B_Offset-1
    temp_value = int(image_gen_config.dict_nvm_data["image_offset_SDK_image_B_offset"], 16) - 1    
    temp_value = (str((hex)(temp_value)))[2:]
    image_gen_config.dict_nvm_data["security_num_section_1_end_offset"] =  align_len_to_8bits(temp_value)
    #SDK_image_B_Offset
    image_gen_config.dict_nvm_data["security_num_section_2_start_offset"] = image_gen_config.dict_nvm_data["image_offset_SDK_image_B_offset"] 
    # "Model_A_Offset-1", 
    temp_value = int(image_gen_config.dict_nvm_data["image_offset_Model_A_offset"], 16) - 1    
    temp_value = (str((hex)(temp_value)))[2:]
    image_gen_config.dict_nvm_data["security_num_section_2_end_offset"] = align_len_to_8bits(temp_value)
    # "SDK_image_A_offset - SDK_image_B_offset"
    temp_value = int(image_gen_config.dict_nvm_data["image_offset_SDK_image_A_offset"], 16) - int(image_gen_config.dict_nvm_data["image_offset_SDK_image_B_offset"], 16)
    hex_representation = hex((1 << image_gen_config.BIT_WIDTH) + temp_value)
    temp_value = (str(hex_representation))[2:]
    image_gen_config.dict_nvm_data["security_num_section_2_crypto_offset"] = align_len_to_8bits(temp_value)
    #"Model_A_offset"
    image_gen_config.dict_nvm_data["security_num_section_3_start_offset"] = image_gen_config.dict_nvm_data["image_offset_Model_A_offset"] 
    
    # fw_nv_size    
    nvm_data_bits = (int)(len(image_gen_config.dict_nvm_data) * (image_gen_config.LENGTH_8_BITS/2)) #size in bytes
    temp_value = (str((hex)(nvm_data_bits)))[2:]     
    image_gen_config.dict_nvm_data["fw_nv_size"] = align_len_to_8bits(temp_value)       

    if not image_gen_config.is_sdk_secured and not image_gen_config.is_model_secured:
        image_gen_config.dict_nvm_data["security_num_of_defined_sections"]    = align_len_to_8bits("0")
        image_gen_config.dict_nvm_data["security_num_section_1_control"]      = align_len_to_8bits("0")
        image_gen_config.dict_nvm_data["security_num_section_2_control"]      = align_len_to_8bits("0")
        image_gen_config.dict_nvm_data["security_num_section_3_control"]      = align_len_to_8bits("0")  
            
    if image_gen_config.is_model_secured:       
        image_gen_config.dict_nvm_data["security_num_section_3_control"]      = align_len_to_8bits("1")  
    else:    
        image_gen_config.dict_nvm_data["security_num_section_3_control"]      = align_len_to_8bits("0")  

    nvm_data_byte_array.extend(attr_dict2list(image_gen_config.dict_nvm_data, len(image_gen_config.dict_nvm_data), 'attr'))
    with open(image_gen_config.nvm_bin_data, 'wb+') as file:
        # Write the new byte array to the beginning of the file
        file.write(bytearray(nvm_data_byte_array))

    #Calcualte CRC32 value
    crcCalculator = CRC32()
    my_arr = read_file_to_array(image_gen_config.nvm_bin_data) 
    crc = crcCalculator.calculate_crc32(my_arr)
    with open(image_gen_config.nvm_bin_data, 'ab') as file:
        #Add CRC to file
        file.write(struct.pack('<I', crc))
    
    #copy attr file to sub-images folders              
    file2copy_attr =  os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES_NVM,  os.path.basename(image_gen_config.nvm_bin_data))                  
    image_gen_config.check_path(file2copy_attr)                  
    shutil.copy(image_gen_config.nvm_bin_data, file2copy_attr)