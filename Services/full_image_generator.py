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
                bin_data_full_flash_image = read_file_to_array(image_gen_config.output_file_name_attr_a)
                while len(bin_data_full_flash_image) < (int)(image_gen_config.addr_configs["ATTR_B_OFFSET"], 16):
                    bin_data_full_flash_image = bin_data_full_flash_image + b"\x00"
                bin_data_full_flash_image = padding_data_for_flash(bin_data_full_flash_image, (int)(image_gen_config.dict_attributes_A["K0_K1_SPK_A_offset"], 16), image_gen_config.output_file_name_attr_b)
                bin_data_full_flash_image = padding_data_for_flash(bin_data_full_flash_image, (int)(image_gen_config.dict_attributes_A["APBL_A_Offset"], 16), image_gen_config.output_file_name_spk_flash)
                bin_data_full_flash_image = padding_data_for_flash(bin_data_full_flash_image, (int)(image_gen_config.dict_attributes_A["K0_K1_SPK_B_offset"], 16), image_gen_config.output_file_name_apbl_flash)
                bin_data_full_flash_image = padding_data_for_flash(bin_data_full_flash_image, (int)(image_gen_config.dict_attributes_A["APBL_B_Offset"], 16), image_gen_config.output_file_name_spk_flash)
                bin_data_full_flash_image = padding_data_for_flash(bin_data_full_flash_image, (int)(image_gen_config.dict_attributes_A["FW_NV_A_offset"], 16), image_gen_config.output_file_name_apbl_flash)
                bin_data_full_flash_image = padding_data_for_flash(bin_data_full_flash_image, (int)(image_gen_config.dict_attributes_A["FW_NV_B_offset"], 16), image_gen_config.nvm_bin_data)
                bin_data_full_flash_image = padding_data_for_flash(bin_data_full_flash_image, (int)(image_gen_config.dict_nvm_data["image_offset_SDK_image_A_offset"], 16), image_gen_config.nvm_bin_data)
                                                            
                if image_gen_config.output_sdk_flash:
                    bin_data_full_flash_image = bin_data_full_flash_image + read_file_to_array(image_gen_config.output_sdk_flash)
                       
                #check that 
                try:
                    #Padding till SDK Image B Offset image_gen_config.dict_attributes_A["SDKImage_B_Offset"] != 'FFFFFFFF'   
                    if (int)(image_gen_config.dict_nvm_data["image_offset_SDK_image_B_offset"], 16) != (int)('FFFFFFFF', 16):
                        bin_data_full_flash_image = padding_data_for_flash(bin_data_full_flash_image, (int)(image_gen_config.dict_nvm_data["image_offset_SDK_image_B_offset"], 16), '')
                        bin_data_full_flash_image = bin_data_full_flash_image + read_file_to_array(image_gen_config.output_sdk_flash)
                    else:
                        print_err_multi_value(error_str1='Wrong SDKImage_B_Offset value = 0x', value_1 = image_gen_config.dict_nvm_data["image_offset_SDK_image_B_offset"])                                    
                except Exception:                
                    print_err_multi_value(error_str1='Wrong SDKImage_B_Offset value = 0x', value_1 = image_gen_config.dict_nvm_data["image_offset_SDK_image_B_offset"])
                    
                #create and write data to flash output file         
                with open(image_gen_config.output_full_flash_file, 'wb+') as file:        
                    file.write(bin_data_full_flash_image)  
        
    except Exception as error:
        # handle the exception
        print("An exception occurred during creating full image: flash :", error)  
    end_time = time.time()
    execution_time = end_time - start_time 
    image_gen_config.total_run_time +=  execution_time              
