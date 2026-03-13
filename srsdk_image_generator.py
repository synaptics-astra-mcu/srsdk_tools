import os 
import argparse 

import image_gen_config
from Services.utils import *
from Services.attributes_generator import *
from Services.chip_b0_image_generator import *
from Services.full_image_generator import *
from Services.nvm_generator import *
from Services.fw_update import *

class Parameters:
    def __init__(self, spk_image, apbl_image, m55_image, m4_image, npu_c_image, model, 
                        flash_type, flash_freq, Q4, json_attr, parse_attr):
        self.spk_image          = spk_image
        self.apbl_image         = apbl_image
        self.m55_image          = m55_image
        self.m4_image           = m4_image
        self.npu_c_image          = npu_c_image
        self.model              = model
        self.flash_type         = flash_type
        self.flash_freq         = flash_freq
        self.Q4                 = Q4

        # Flash_attributes.json
        self.json_attr          = json_attr

        self.parse_attr         = parse_attr        

    
    def check_input_arguments(self):
        if not self.parse_attr:
            if not self.json_attr:
                if image_gen_config.is_B0_chip: 
                    if image_gen_config.is_model_secured and not image_gen_config.is_sdk_secured:
                        print_err('Model Cannot be secured in case SDK does not secure. Please reconfig and re-run again')                 
                    if not self.spk_image and not self.apbl_image and not self.m55_image and not self.json_attr and not self.parse_attr:
                        parser.print_help()
                        print_err('Missing Flash Input File and/or Json Attribute File and/or SPK/APBL/FW Files')                    
                    if self.npu_c_image and not self.m4_image:
                        parser.print_help()
                        print_err('Missing FW M4 Image. The NPU_C can not run without M4')                    
                
                
                if self.apbl_image and not self.m55_image:
                    parser.print_help()
                    print_err('Missing FW (M55) Input Files')
                
            if  self.m55_image and not self.m4_image and not self.npu_c_image == 0:
                image_gen_config.last_image = 'm55'                  
            elif self.m55_image and self.m4_image and  not self.npu_c_image:
                image_gen_config.last_image = 'm4'       
            elif self.m55_image and self.m4_image and self.npu_c_image:
                image_gen_config.last_image = 'npu_c'   
               
            if params.spk_image:
                if not params.spk_image.lower().endswith('.bin'):
                    print_err('Wrong File extention', file_name=params.spk_image, extention='.bin')
                image_gen_config.log_file.info(f' SPK File: {params.spk_image}')    

            if params.apbl_image:
                if not params.apbl_image.lower().endswith('.axf') and not params.apbl_image.lower().endswith('.elf'):                    
                    print_err('Wrong File extention', file_name=params.apbl_image, extention='.axf')
                    print_err('Wrong File extention', file_name=params.apbl_image, extention='.elf')
                image_gen_config.log_file.info(f' APBL File: {params.apbl_image}')    

            if params.m55_image:
                if not params.m55_image.lower().endswith('.axf') and not params.m55_image.lower().endswith('.elf'):
                    print_err(params.m55_image, '.axf')
                    print_err(params.m55_image, '.elf')
                image_gen_config.log_file.info(f' M55 FW File: {params.m55_image}')     

            if params.m4_image:
                if not params.m4_image.lower().endswith('.axf'):
                    print_err('Wrong File extention', file_name=params.m4_image, extention='.axf')
                image_gen_config.log_file.info(f' M4 FW File: {params.m4_image}')   

            if params.npu_c_image:
                if not params.npu_c_image.lower().endswith('.bin'):
                    print_err('Wrong File extention', file_name=params.npu_c_image, extention='.bin')            
                image_gen_config.log_file.info(f' NPU_C File: {params.npu_c_image}')   

            if params.model:
                if not params.model.lower().endswith('.bin'):
                    print_err('Wrong File extention', file_name=params.model, extention='.bin')           
                image_gen_config.log_file.info(f' Model File: {params.model}')     

        else:
            if not params.parse_attr.lower().endswith('.bin'):
                print_err('Wrong File extention', file_name=params.parse_attr, extention='.bin')
            image_gen_config.log_file.info(f' Flash Bin File for Parsing: {params.parse_attr}')  

def main(params:Parameters):

    if os.path.exists(image_gen_config.BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES):
        shutil.rmtree(image_gen_config.BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES)    

    #Set Chip Type and Create All Folders 
    # TODO: remove B0
    config_chip_type()

    # Create All Folders 
    create_folder_and_files()

    # Clear list of images which will be sent to sign server
    image_gen_config.imglst4json = []

    #Parser All Jsons
    #get JSON path --> if params.json_attr:
    # Flash_attributes.json
    if params.json_attr:
        json_path = params.json_attr    
    else:
        json_path = get_json_file_path()

    # Parse Parameters Json files to local config Dictionaries
    convert_json_2dict_and_copy2other_dict(image_gen_config.CONFIG_PARAMS_PATH)  
    convert_json_2dict_and_copy2other_dict(image_gen_config.IMAGES_PARAMETERS)  

    # Parse Flash Attr File from Json to Dictionary
    image_gen_config.dict_attributes_A = convert_json_flash_attr(json_path)    

    # Parser NVN json to dictionary
    convert_json_2dict_and_copy2other_dict(image_gen_config.CONFIG_NVM_DATA_PATH)  
    # Parse FW Update JSON Data to dictionary
    convert_json_2dict_and_copy2other_dict(image_gen_config.CONFIG_FW_UPDATE_DATA_PATH)  
        
    # Parse Flash Attributes from Bin Flash Image File to Json
    # TODO: additional feature, not a must
    if params.parse_attr:            
        parse_binary_file_to_attr(params.parse_attr) 
   
    # All configurations and images for chip B0
    if image_gen_config.is_B0_chip: 
        if params.spk_image:
            # handle SPK image
            if image_gen_config.is_host_image:           
                create_k0_k1_spk_full_image(params.spk_image, 'host') 
            if image_gen_config.is_flash_image:          
                create_k0_k1_spk_full_image(params.spk_image, 'flash') 
        
        if params.apbl_image:           
            # handle APBL image
            apbl_bin_file = convert_axf_elf(params.apbl_image)  
            
            if image_gen_config.is_host_image:                
                create_apbl_image(params.apbl_image, apbl_bin_file, 'host')              
            if image_gen_config.is_flash_image:    
                create_apbl_image(params.apbl_image, apbl_bin_file, 'flash')
           
            #create run command for APBL 
            if image_gen_config.is_B0_chip:                
                image_gen_config.output_apbl_run_command = create_run_cmds_bin_file(params.apbl_image, 'apbl') 
            image_gen_config.GLOBAL_COUNTER_BCM += 1  
            image_gen_config.GLOBAL_COUNTER_AXI += 1  
            os.remove(apbl_bin_file)

        # Create empty SDK Files
        create_all_sdk_files()

        if params.m55_image:  
            if image_gen_config.is_host_image:                     
                b0_generate_fw_images(params.m55_image, 'm55', 'host', 0)                  
            if image_gen_config.is_flash_image:                     
                b0_generate_fw_images(params.m55_image, 'm55', 'flash', 0)
                            
        if params.m4_image:   
            if image_gen_config.is_host_image:        
                b0_generate_fw_images(params.m4_image, 'm4', 'host', 0)
            if image_gen_config.is_flash_image:       
                b0_generate_fw_images(params.m4_image, 'm4', 'flash', os.path.getsize(image_gen_config.output_sdk_flash))
                  
        if params.npu_c_image: 
            if image_gen_config.is_host_image:                       
                b0_generate_npu_c_image(params.npu_c_image, 'npu_c', 'host', 0)    
            elif image_gen_config.is_flash_image:                 
                b0_generate_npu_c_image(params.npu_c_image, 'npu_c', 'flash', os.path.getsize(image_gen_config.output_sdk_flash))   
                
        # if model file bin provided
        if (params.model and image_gen_config.is_flash_image):                      
            b0_generate_model_image(params.model, 0)  

        if image_gen_config.is_flash_image:
            #create nvm file from json
            create_nvm_parameters(params.model)                    

        if  params.spk_image and params.apbl_image and params.m55_image:            
            if image_gen_config.is_host_image: 
                create_images(params.flash_type, params.flash_freq, params.m55_image, 'host')  
            if image_gen_config.is_flash_image:      
                # create attribute files from json
                create_attribute_parameters(params.flash_type, params.flash_freq, params.Q4)  
                create_images(params.flash_type, params.flash_freq,params.m55_image, 'flash')       
                #FW Update                
                create_fw_update_images()                                 
    
    #Delete unnessasry files
    delete_temp_files()

    if image_gen_config.is_B0_chip:
        #create json file
        # Writing the dictionary to a JSON file
        image_gen_config.check_path(image_gen_config.IMAGE_LISTS_JSON_PATH)
        with open(image_gen_config.IMAGE_LISTS_JSON_PATH, 'w') as json_file:
            json.dump(image_gen_config.imglst4json, json_file, indent=4)

        # Call the function to zip the folder
        zip_folder(image_gen_config.BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES, image_gen_config.ZIP_FILE_PATH)

    try:
        if os.path.exists(image_gen_config.BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES):
            shutil.rmtree(image_gen_config.BIN_OUTPUT_FOLDER_PATH_SUB_IMAGES)  
    except Exception:                
       print('')
    
    if image_gen_config.is_flash_image and not image_gen_config.is_host_image:
        if len(os.listdir(image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_HOST)) == 0:
            if os.path.exists(image_gen_config.BIN_OUTPUT_FOLDER_PATH_HOST):
                shutil.rmtree(image_gen_config.BIN_OUTPUT_FOLDER_PATH_HOST)  
    
    if image_gen_config.is_host_image and not image_gen_config.is_flash_image:
        if len(os.listdir(image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_FLASH)) == 0:
            if os.path.exists(image_gen_config.BIN_OUTPUT_FOLDER_PATH_FLASH):
                shutil.rmtree(image_gen_config.BIN_OUTPUT_FOLDER_PATH_FLASH)  

    print(" Images Generated Successfully!")      
    image_gen_config.log_file.info(" Images Generated Successfully!")    
    image_gen_config.log_file.info(f' Total (Approximately) Run Time = {round(image_gen_config.total_run_time, 2)} seconds')    
    image_gen_config.close_logger(image_gen_config.log_file, image_gen_config.log_handler)      
    
if __name__ == '__main__':
   
    parser = argparse.ArgumentParser(description="Srsdk_Image_Generator")  
    
    # Mutual exclusive groups, Chip Groups
    chip_group = parser.add_mutually_exclusive_group(required=False)
    #Define Chips
    chip_group.add_argument('-B0', help='Specify the main chip type: B0', action='store_true') 

    # Mutual exclusive groups, Full Iamge definitions
    full_image_group = parser.add_mutually_exclusive_group(required=False)
    #Define Chips
    full_image_group.add_argument('-flash_image', help='Generate Flash Full Image Only', action='store_true') 
    full_image_group.add_argument('-host_image', help='Generate Host Full Image Only', action='store_true')     

    # Mutual exclusive groups, SDK Secured
    is_sdk_secured = parser.add_mutually_exclusive_group(required=False)
    #Define Secured or not
    is_sdk_secured.add_argument('-sdk_secured', help='Specify SDK secured ', action='store_true') 
    is_sdk_secured.add_argument('-sdk_non_secured', help='Specify SDK not secured', action='store_true') 

    # Mutual exclusive groups, Model Secured
    is_model_secured = parser.add_mutually_exclusive_group(required=False)
    #Define Secured or not
    is_model_secured.add_argument('-model_secured', help='Specify Model secured ', action='store_true') 
    is_model_secured.add_argument('-model_non_secured', help='Specify Model not secured', action='store_true') 

    #Arguments      
    parser.add_argument('-spk', '--spk_input_file_name', type=str, help='SPK input file name', default = "")
    parser.add_argument('-apbl', '--apbl_input_file_name', type=str, help='APBL input file name', default= "")    
    parser.add_argument('-m55_image', '--m55_image', type=str, help='Input M55 Image file name', default= "")  
    parser.add_argument('-m4_image', '--m4_image', type=str, help='Input M4 Image file name', default= "")  
    parser.add_argument('-npu_c_image', '--npu_c_image', type=str, help='Input NPU_C Image file name', default= "")  
    parser.add_argument('-model', '--model', type=str, help='Input Model Image file name', default= "")      
    parser.add_argument('-flash_type', '--flash_type', type=str, choices=['GD25LE128', 'W25Q128', 'MX25U128'], help='Flash Type', default='')
    # parser.add_argument('-flash_size', '--flash_size', type=str, choices=['1M', '2M', '4M', '8M', '16M', '32M', '64M', '128M'], help='Flash Type', default='')
    parser.add_argument('-flash_freq', '--flash_freq', type=str, choices=['34','67', '100', '134'], help='Flash frequency : 34/67/100/134 (MHz)', default='')
    parser.add_argument('-Q4', '--flash_support_4_bit', type=int, choices=[1, 0], help='Flash Support 4 Bit', default=1)              
    parser.add_argument('-json_attr', '--json_attr', type=str, help='Take flash attributes from input Json', default="")
    parser.add_argument('-parse_attr', '--parse_attr', type=str, help='Read Flash Attributes', default="")    
    parser.add_argument('-v', '--version', action='version', version=f'\n The SRSDK Image Generator Version is: {image_gen_config.SRSDK_IMAGE_CENERATOR_VER}\n')

    args = parser.parse_args()  

    if args.sdk_secured:
        image_gen_config.is_sdk_secured = True        
    else:
        image_gen_config.is_sdk_secured = False  

    if args.model_secured:
        image_gen_config.is_model_secured = True        
    else:
        image_gen_config.is_model_secured = False        

    image_gen_config.log_file.info(f' The SRSDK Image Generator Version is: {image_gen_config.SRSDK_IMAGE_CENERATOR_VER}')
    # Check if version argument was provided
    version_provided = hasattr(args, 'version') and args.version

    if not version_provided:
        print(f'\n The SRSDK Image Generator Version is: {image_gen_config.SRSDK_IMAGE_CENERATOR_VER}')
    
    if args.B0:
        image_gen_config.is_B0_chip = True  
        print(' We Will Generate Images for Chip B0')  
        image_gen_config.log_file.info(' We Will Generate Images for Chip B0')     
    else: 
        print_err('Please provide parameters. For Help run srsdk_image_generator -h')     
    
    if args.flash_image and not args.host_image:
        image_gen_config.is_flash_image   = True
        image_gen_config.is_host_image    = False
    elif args.host_image and not args.flash_image:
        image_gen_config.is_host_image    = True
        image_gen_config.is_flash_image   = False
    else:      
        image_gen_config.is_flash_image   = True  
        image_gen_config.is_host_image    = True  
    
    print(f' Flash Full Image Required = {image_gen_config.is_flash_image}, Host Full Image required = {image_gen_config.is_host_image}')  
    image_gen_config.log_file.info(f' Flash Full Image Required = {image_gen_config.is_flash_image}, Host Full Image required = {image_gen_config.is_host_image}')

    params = Parameters(spk_image = args.spk_input_file_name, apbl_image = args.apbl_input_file_name, m55_image = args.m55_image, 
                        m4_image = args.m4_image, npu_c_image = args.npu_c_image, model = args.model, 
                        flash_type = args.flash_type, flash_freq = args.flash_freq, Q4 = args.flash_support_4_bit,
                        json_attr = args.json_attr, parse_attr = args.parse_attr)
    params.check_input_arguments()
 
    main(params)
    