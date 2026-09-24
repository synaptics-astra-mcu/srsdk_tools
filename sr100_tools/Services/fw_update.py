import os,  time
import image_gen_config
import struct
from Services.utils import *

class FW_Update:

    crcCalculator           = CRC32()

    def __init__(self):
        self.spk_data_byte_array    = bytearray()
        self.apbl_data_byte_array   = bytearray()
        self.sdk_data_byte_array    = bytearray()
        self.model_data_byte_array  = bytearray()

        self.dec_dict_size          = 0
        self.dict_size              = 0
        self.crc_size               = (int)(image_gen_config.LENGTH_8_BITS/2)

        self.dec_spk_size           = 0
        self.spk_size               = ''
        self.spk_offset             = ''

        self.dec_apbl_size           = 0
        self.apbl_size               = ''
        self.apbl_offset             = ''

        self.dec_sdk_size           = 0
        self.sdk_size               = ''
        self.sdk_offset             = ''

        self.dec_model_size         = 0
        self.model_size             = ''
        self.model_offset           = ''

    def create_fw_update_files_and_dict_size_calc(self):
        image_gen_config.BIN_OUTPUT_FOLDER_PATH_FW_UPDATE        = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_COMPONENT_FLASH, "FW_Update_Images")

        if image_gen_config.output_file_name_spk_flash:
                image_gen_config.output_spk_fw_update = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_FW_UPDATE, "SPK_secured.bin")
                image_gen_config.check_path(image_gen_config.output_spk_fw_update)
                image_gen_config.log_file.info(f" Create SPK Update File {image_gen_config.output_spk_fw_update} ")

        if image_gen_config.output_file_name_apbl_flash:
            if image_gen_config.is_sdk_secured:
                image_gen_config.output_apbl_fw_update = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_FW_UPDATE, "APBL_secured.bin")
                image_gen_config.output_spk_apbl_fw_update = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_FW_UPDATE, "SPK_APBL_secured.bin")
                image_gen_config.output_apbl_sdk_fw_update = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_FW_UPDATE, "APBL_SDK_secured.bin")
            else:
                image_gen_config.output_apbl_fw_update = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_FW_UPDATE, "APBL.bin")
                image_gen_config.output_spk_apbl_fw_update = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_FW_UPDATE, "SPK_APBL.bin")
                image_gen_config.output_apbl_sdk_fw_update = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_FW_UPDATE, "APBL_SDK.bin")

            image_gen_config.check_path(image_gen_config.output_apbl_fw_update)
            image_gen_config.log_file.info(f" Create SPK Update File {image_gen_config.output_apbl_fw_update} ")
            image_gen_config.check_path(image_gen_config.output_spk_apbl_fw_update)
            image_gen_config.log_file.info(f" Create SPK and APBL Update File {image_gen_config.output_spk_apbl_fw_update} ")
            image_gen_config.check_path(image_gen_config.output_apbl_sdk_fw_update)
            image_gen_config.log_file.info(f" Create APBL and SDK Update File {image_gen_config.output_apbl_sdk_fw_update} ")


        if image_gen_config.is_sdk_secured:
            image_gen_config.output_sdk_fw_update       = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_FW_UPDATE, "SDK_secured.bin")
            image_gen_config.output_spk_sdk_fw_update   = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_FW_UPDATE, "SPK_SDK_secured.bin")
            image_gen_config.output_spk_apbl_sdk_fw_update   = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_FW_UPDATE, "SPK_APBL_SDK_secured.bin")

            if image_gen_config.output_model_flash:
                image_gen_config.output_sdk_model_fw_update       = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_FW_UPDATE, "SDK_Model_secured.bin")
                image_gen_config.output_spk_sdk_model_fw_update   = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_FW_UPDATE, "SPK_SDK_Model_secured.bin")
                image_gen_config.output_spk_apbl_sdk_model_fw_update   = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_FW_UPDATE, "SPK_APBL_SDK_Model_secured.bin")
        else:
            image_gen_config.output_sdk_fw_update       = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_FW_UPDATE, "SDK.bin")
            image_gen_config.output_spk_sdk_fw_update   = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_FW_UPDATE, "SPK_SDK.bin")
            image_gen_config.output_spk_apbl_sdk_fw_update   = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_FW_UPDATE, "SPK_APBL_SDK.bin")

            if image_gen_config.output_model_flash:
                image_gen_config.output_sdk_model_fw_update       = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_FW_UPDATE, "SDK_Model.bin")
                image_gen_config.output_spk_sdk_model_fw_update   = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_FW_UPDATE, "SPK_SDK_Model.bin")
                image_gen_config.output_spk_apbl_sdk_model_fw_update   = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_FW_UPDATE, "SPK_APBL_SDK_Model.bin")

        image_gen_config.check_path(image_gen_config.output_sdk_fw_update)
        image_gen_config.log_file.info(f" Create SDK FW Update File {image_gen_config.output_sdk_fw_update} ")
        image_gen_config.check_path(image_gen_config.output_spk_sdk_fw_update)
        image_gen_config.log_file.info(f" Create SPK and SDK FW Update File {image_gen_config.output_spk_sdk_fw_update} ")
        image_gen_config.check_path(image_gen_config.output_spk_apbl_sdk_fw_update)
        image_gen_config.log_file.info(f" Create SPK, APBL and SDK FW Update File {image_gen_config.output_spk_apbl_sdk_fw_update} ")

        if image_gen_config.output_model_flash:
            if image_gen_config.is_model_secured:
                image_gen_config.output_model_fw_update           = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_FW_UPDATE, "Model_secured.bin")
            else:
                image_gen_config.output_model_fw_update           = os.path.join(image_gen_config.BIN_OUTPUT_FOLDER_PATH_FW_UPDATE, "Model.bin")
            image_gen_config.check_path(image_gen_config.output_sdk_model_fw_update)
            image_gen_config.check_path(image_gen_config.output_spk_sdk_model_fw_update)
            image_gen_config.check_path(image_gen_config.output_model_fw_update)
            image_gen_config.check_path(image_gen_config.output_spk_apbl_sdk_model_fw_update)
            image_gen_config.log_file.info(f" Create SDK and Model Update File {image_gen_config.output_sdk_model_fw_update} ")
            image_gen_config.log_file.info(f" Create SPK, SDK and Model Update File {image_gen_config.output_spk_sdk_model_fw_update} ")
            image_gen_config.log_file.info(f" Create Model FW  Update File {image_gen_config.output_model_fw_update} ")
            image_gen_config.log_file.info(f" Create Model FW  Update File {image_gen_config.output_spk_apbl_sdk_model_fw_update} ")

        #FW Update Structure Size
        self.dec_dict_size = (int)(len(image_gen_config.dict_multi_image_update_data) * (image_gen_config.LENGTH_8_BITS/2))  + self.crc_size #size in bytes
        self.dict_size = (str((hex)(self.dec_dict_size)))[2:]

    def spk_stand_alone_file(self):
        #Calculate Parameters for SPK Stand Alone file
        if image_gen_config.output_file_name_spk_flash:
            image_gen_config.dict_spk_update_data["enabled_spk"] = align_len_to_8bits(str(1))
            image_gen_config.dict_spk_update_data["enabled_apbl"] = align_len_to_8bits(str(0))
            image_gen_config.dict_spk_update_data["enabled_sdk"]  = align_len_to_8bits(str(0))
            image_gen_config.dict_spk_update_data["enabled_model"]= align_len_to_8bits(str(0))

            self.spk_data_byte_array = read_file_to_array(image_gen_config.output_file_name_spk_flash)
            self.dec_spk_size = os.path.getsize(image_gen_config.output_file_name_spk_flash)
            self.spk_size = (str((hex)(self.dec_spk_size)))[2:]
            self.spk_offset = (str((hex)(self.dec_dict_size)))[2:]

            image_gen_config.dict_spk_update_data["size_spk"] = align_len_to_8bits(self.spk_size)
            image_gen_config.dict_spk_update_data["offset_spk"] = align_len_to_8bits(self.spk_offset)

            #Convert dictionary data to bin array for output_spk_fw_update
            dict_arr = bytearray()
            dict_arr.extend(attr_dict2list(image_gen_config.dict_spk_update_data, self.dec_dict_size - self.crc_size, ''))
            with open(image_gen_config.output_spk_fw_update, 'wb+') as file:
                # Write the new byte array to the beginning of the file
                file.write(bytearray(dict_arr))

            my_arr = read_file_to_array(image_gen_config.output_spk_fw_update)
            crc = self.crcCalculator.calculate_crc32(my_arr)
            with open(image_gen_config.output_spk_fw_update, 'ab') as file:
                #Add CRC to file
                file.write(struct.pack('<I', crc))
                file.write(self.spk_data_byte_array)

    def apbl_stand_alone_file(self):
        #Calculate Parameters for APBL Stand Alone file
        if image_gen_config.output_file_name_apbl_flash:
            image_gen_config.dict_apbl_update_data["enabled_apbl"] = align_len_to_8bits(str(1))
            image_gen_config.dict_apbl_update_data["enabled_spk"] = align_len_to_8bits(str(0))
            image_gen_config.dict_apbl_update_data["enabled_sdk"]  = align_len_to_8bits(str(0))
            image_gen_config.dict_apbl_update_data["enabled_model"]= align_len_to_8bits(str(0))

            self.apbl_data_byte_array = read_file_to_array(image_gen_config.output_file_name_apbl_flash)
            self.dec_apbl_size = os.path.getsize(image_gen_config.output_file_name_apbl_flash)
            self.apbl_size = (str((hex)(self.dec_apbl_size)))[2:]
            self.apbl_offset = (str((hex)(self.dec_dict_size)))[2:]

            image_gen_config.dict_apbl_update_data["size_apbl"] = align_len_to_8bits(self.apbl_size)
            image_gen_config.dict_apbl_update_data["offset_apbl"] = align_len_to_8bits(self.apbl_offset)

            #Convert dictionary data to bin array for output_apbl_fw_update
            dict_arr = bytearray()
            dict_arr.extend(attr_dict2list(image_gen_config.dict_apbl_update_data, self.dec_dict_size - self.crc_size, ''))
            with open(image_gen_config.output_apbl_fw_update, 'wb+') as file:
                # Write the new byte array to the beginning of the file
                file.write(bytearray(dict_arr))

            my_arr = read_file_to_array(image_gen_config.output_apbl_fw_update)
            crc = self.crcCalculator.calculate_crc32(my_arr)
            with open(image_gen_config.output_apbl_fw_update, 'ab') as file:
                #Add CRC to file
                file.write(struct.pack('<I', crc))
                file.write(self.apbl_data_byte_array)

    def sdk_stand_alone_file(self):
        #Create SDK Stand Alone
        if image_gen_config.output_sdk_flash:
            image_gen_config.dict_sdk_update_data["enabled_spk"] = align_len_to_8bits(str(0))
            image_gen_config.dict_sdk_update_data["enabled_apbl"]  = align_len_to_8bits(str(0))
            image_gen_config.dict_sdk_update_data["enabled_sdk"] = align_len_to_8bits(str(1))
            image_gen_config.dict_sdk_update_data["enabled_model"]= align_len_to_8bits(str(0))

            self.sdk_data_byte_array = read_file_to_array(image_gen_config.output_sdk_flash)
            self.dec_sdk_size = os.path.getsize(image_gen_config.output_sdk_flash)
            self.sdk_size = (str((hex)(self.dec_sdk_size)))[2:]
            self.sdk_offset = (str((hex)(self.dec_dict_size)))[2:]

            image_gen_config.dict_sdk_update_data["size_sdk"] = align_len_to_8bits(self.sdk_size)
            image_gen_config.dict_sdk_update_data["offset_sdk"] = align_len_to_8bits(self.sdk_offset)

            #Convert dictionary data to bin array for output_sdk_fw_update
            dict_arr = bytearray()
            dict_arr.extend(attr_dict2list(image_gen_config.dict_sdk_update_data, self.dec_dict_size - self.crc_size, ''))
            with open(image_gen_config.output_sdk_fw_update, 'wb+') as file:
                # Write the new byte array to the beginning of the file
                file.write(bytearray(dict_arr))

            #Calcualte CRC32 value
            my_arr = read_file_to_array(image_gen_config.output_sdk_fw_update)
            crc = self.crcCalculator.calculate_crc32(my_arr)
            with open(image_gen_config.output_sdk_fw_update, 'ab') as file:
                #Add CRC to file
                file.write(struct.pack('<I', crc))
                file.write(self.sdk_data_byte_array)

    def model_stand_alone_file(self):
        #Create ModelK Stand Alone
        image_gen_config.dict_model_update_data["enabled_spk"]  = align_len_to_8bits(str(0))
        image_gen_config.dict_model_update_data["enabled_apbl"] = align_len_to_8bits(str(0))
        image_gen_config.dict_model_update_data["enabled_sdk"]  = align_len_to_8bits(str(0))
        image_gen_config.dict_model_update_data["enabled_model"]  = align_len_to_8bits(str(1))

        self.model_data_byte_array = read_file_to_array(image_gen_config.output_model_flash)
        self.dec_model_size = os.path.getsize(image_gen_config.output_model_flash)
        self.model_size = (str((hex)(self.dec_model_size)))[2:]
        self.model_offset = (str((hex)(self.dec_dict_size)))[2:]

        image_gen_config.dict_model_update_data["size_model"] = align_len_to_8bits(self.model_size)
        image_gen_config.dict_model_update_data["offset_model"] = align_len_to_8bits(self.model_offset)

        #Convert dictionary data to bin array for output_sdk_fw_update
        dict_arr = bytearray()
        dict_arr.extend(attr_dict2list(image_gen_config.dict_model_update_data, self.dec_dict_size - self.crc_size, ''))
        with open(image_gen_config.output_model_fw_update, 'wb+') as file:
            # Write the new byte array to the beginning of the file
            file.write(bytearray(dict_arr))

        #Calcualte CRC32 value
        my_arr = read_file_to_array(image_gen_config.output_model_fw_update)
        crc = self.crcCalculator.calculate_crc32(my_arr)
        with open(image_gen_config.output_model_fw_update, 'ab') as file:
            #Add CRC to file
            file.write(struct.pack('<I', crc))
            file.write(self.model_data_byte_array)

    def sdk_model_file(self):
        #Create SDK and Model in one file
        image_gen_config.dict_multi_image_update_data["enabled_spk"]    = align_len_to_8bits(str(0))
        image_gen_config.dict_multi_image_update_data["size_spk"]       = image_gen_config.FFFFFFFF
        image_gen_config.dict_multi_image_update_data["offset_spk"]     = image_gen_config.FFFFFFFF

        image_gen_config.dict_multi_image_update_data["enabled_apbl"]   = align_len_to_8bits(str(0))
        image_gen_config.dict_multi_image_update_data["size_apbl"]      = image_gen_config.FFFFFFFF
        image_gen_config.dict_multi_image_update_data["offset_apbl"]    = image_gen_config.FFFFFFFF

        image_gen_config.dict_multi_image_update_data["enabled_sdk"] = align_len_to_8bits(str(1))
        image_gen_config.dict_multi_image_update_data["enabled_model"]= align_len_to_8bits(str(1))

        #Calculate SDK Parameters and model for SDK_and_Model Binary File
        image_gen_config.dict_multi_image_update_data["size_sdk"] = align_len_to_8bits(self.sdk_size)
        self.sdk_offset = (str((hex)(self.dec_dict_size)))[2:]
        image_gen_config.dict_multi_image_update_data["offset_sdk"] = align_len_to_8bits(self.sdk_offset)

        image_gen_config.dict_multi_image_update_data["size_model"] = align_len_to_8bits(self.model_size)
        self.model_offset = (str((hex)(self.dec_dict_size + self.dec_sdk_size)))[2:]
        image_gen_config.dict_multi_image_update_data["offset_model"] = align_len_to_8bits(self.model_offset)

        #Convert dictionary data to bin array for output_sdk_model_fw_update
        dict_arr = bytearray()
        dict_arr.extend(attr_dict2list(image_gen_config.dict_multi_image_update_data, self.dec_dict_size - self.crc_size, ''))
        with open(image_gen_config.output_sdk_model_fw_update, 'wb+') as file:
            # Write the new byte array to the beginning of the file
            file.write(bytearray(dict_arr))

        #Calcualte CRC32 value
        my_arr = read_file_to_array(image_gen_config.output_sdk_model_fw_update)
        crc = self.crcCalculator.calculate_crc32(my_arr)
        with open(image_gen_config.output_sdk_model_fw_update, 'ab') as file:
            #Add CRC to file
            file.write(struct.pack('<I', crc))
            file.write(self.sdk_data_byte_array + self.model_data_byte_array)

    def spk_sdk_file(self):
        #Create SPK and SDK in one file
        image_gen_config.dict_multi_image_update_data["enabled_apbl"]   = align_len_to_8bits(str(0))
        image_gen_config.dict_multi_image_update_data["offset_apbl"]    = image_gen_config.FFFFFFFF
        image_gen_config.dict_multi_image_update_data["size_apbl"]      = image_gen_config.FFFFFFFF

        image_gen_config.dict_multi_image_update_data["enabled_model"]  = align_len_to_8bits(str(0))
        image_gen_config.dict_multi_image_update_data["offset_model"]   = image_gen_config.FFFFFFFF
        image_gen_config.dict_multi_image_update_data["size_model"]     = image_gen_config.FFFFFFFF

        image_gen_config.dict_multi_image_update_data["enabled_sdk"]    = align_len_to_8bits(str(1))
        image_gen_config.dict_multi_image_update_data["enabled_spk"]    = align_len_to_8bits(str(1))

        image_gen_config.dict_multi_image_update_data["size_spk"] = align_len_to_8bits(self.spk_size)
        self.spk_offset = (str((hex)(self.dec_dict_size )))[2:]
        image_gen_config.dict_multi_image_update_data["offset_spk"] = align_len_to_8bits(self.spk_offset)

        image_gen_config.dict_multi_image_update_data["size_sdk"] = align_len_to_8bits(self.sdk_size)
        self.sdk_offset = (str((hex)(self.dec_dict_size + self.dec_spk_size)))[2:]
        image_gen_config.dict_multi_image_update_data["offset_sdk"] = align_len_to_8bits(self.sdk_offset)

        #Convert dictionary data to bin array for output_sdk_model_fw_update
        dict_arr = bytearray()
        dict_arr.extend(attr_dict2list(image_gen_config.dict_multi_image_update_data, self.dec_dict_size - self.crc_size, ''))
        with open(image_gen_config.output_spk_sdk_fw_update, 'wb+') as file:
            # Write the new byte array to the beginning of the file
            file.write(bytearray(dict_arr))

        #Calcualte CRC32 value
        my_arr = read_file_to_array(image_gen_config.output_spk_sdk_fw_update)
        crc = self.crcCalculator.calculate_crc32(my_arr)
        with open(image_gen_config.output_spk_sdk_fw_update, 'ab') as file:
            #Add CRC to file
            file.write(struct.pack('<I', crc))
            file.write(self.spk_data_byte_array + self.sdk_data_byte_array)

    def spk_sdk_model_file(self):
        #Create SPK and SDK in one file
        image_gen_config.dict_multi_image_update_data["enabled_apbl"]   = align_len_to_8bits(str(0))
        image_gen_config.dict_multi_image_update_data["size_apbl"]      = image_gen_config.FFFFFFFF
        image_gen_config.dict_multi_image_update_data["offset_apbl"]   = image_gen_config.FFFFFFFF

        image_gen_config.dict_multi_image_update_data["enabled_spk"]    = align_len_to_8bits(str(1))
        image_gen_config.dict_multi_image_update_data["enabled_sdk"]    = align_len_to_8bits(str(1))
        image_gen_config.dict_multi_image_update_data["enabled_model"]  = align_len_to_8bits(str(1))

        image_gen_config.dict_multi_image_update_data["size_spk"] = align_len_to_8bits(self.spk_size)
        self.spk_offset = (str((hex)(self.dec_dict_size )))[2:]
        image_gen_config.dict_multi_image_update_data["offset_spk"] = align_len_to_8bits(self.spk_offset)

        image_gen_config.dict_multi_image_update_data["size_sdk"] = align_len_to_8bits(self.sdk_size)
        self.sdk_offset = (str((hex)(self.dec_dict_size + self.dec_spk_size)))[2:]
        image_gen_config.dict_multi_image_update_data["offset_sdk"] = align_len_to_8bits(self.sdk_offset)

        image_gen_config.dict_multi_image_update_data["size_model"] = align_len_to_8bits(self.model_size)
        self.model_offset = (str((hex)(self.dec_dict_size + + self.dec_spk_size + self.dec_sdk_size)))[2:]
        image_gen_config.dict_multi_image_update_data["offset_model"] = align_len_to_8bits(self.model_offset)

        #Convert dictionary data to bin array for output_sdk_model_fw_update
        dict_arr = bytearray()
        dict_arr.extend(attr_dict2list(image_gen_config.dict_multi_image_update_data, self.dec_dict_size - self.crc_size, ''))
        with open(image_gen_config.output_spk_sdk_model_fw_update, 'wb+') as file:
            # Write the new byte array to the beginning of the file
            file.write(bytearray(dict_arr))

        #Calcualte CRC32 value
        my_arr = read_file_to_array(image_gen_config.output_spk_sdk_model_fw_update)
        crc = self.crcCalculator.calculate_crc32(my_arr)
        with open(image_gen_config.output_spk_sdk_model_fw_update, 'ab') as file:
            #Add CRC to file
            file.write(struct.pack('<I', crc))
            file.write(self.spk_data_byte_array + self.sdk_data_byte_array + self.model_data_byte_array)

    def spk_apbl_file(self):
        #Create SPK and SDK in one file
        image_gen_config.dict_multi_image_update_data["enabled_spk"]    = align_len_to_8bits(str(1))
        image_gen_config.dict_multi_image_update_data["enabled_apbl"]   = align_len_to_8bits(str(1))

        image_gen_config.dict_multi_image_update_data["enabled_sdk"]    = align_len_to_8bits(str(0))
        image_gen_config.dict_multi_image_update_data["offset_sdk"]     = image_gen_config.FFFFFFFF
        image_gen_config.dict_multi_image_update_data["size_sdk"]       = image_gen_config.FFFFFFFF

        image_gen_config.dict_multi_image_update_data["enabled_model"]  = align_len_to_8bits(str(0))
        image_gen_config.dict_multi_image_update_data["size_model"]     = image_gen_config.FFFFFFFF
        image_gen_config.dict_multi_image_update_data["offset_model"]   = image_gen_config.FFFFFFFF

        image_gen_config.dict_multi_image_update_data["size_spk"] = align_len_to_8bits(self.spk_size)
        self.spk_offset = (str((hex)(self.dec_dict_size )))[2:]
        image_gen_config.dict_multi_image_update_data["offset_spk"] = align_len_to_8bits(self.spk_offset)

        image_gen_config.dict_multi_image_update_data["size_apbl"] = align_len_to_8bits(self.apbl_size)
        self.apbl_offset = (str((hex)(self.dec_dict_size + self.dec_spk_size)))[2:]
        image_gen_config.dict_multi_image_update_data["offset_apbl"] = align_len_to_8bits(self.apbl_offset)

        #Convert dictionary data to bin array for output_sdk_model_fw_update
        dict_arr = bytearray()
        dict_arr.extend(attr_dict2list(image_gen_config.dict_multi_image_update_data, self.dec_dict_size - self.crc_size, ''))
        with open(image_gen_config.output_spk_apbl_fw_update, 'wb+') as file:
            # Write the new byte array to the beginning of the file
            file.write(bytearray(dict_arr))

        #Calcualte CRC32 value
        my_arr = read_file_to_array(image_gen_config.output_spk_apbl_fw_update)
        crc = self.crcCalculator.calculate_crc32(my_arr)
        with open(image_gen_config.output_spk_apbl_fw_update, 'ab') as file:
            #Add CRC to file
            file.write(struct.pack('<I', crc))
            file.write(self.spk_data_byte_array + self.apbl_data_byte_array)

    def spk_apbl_sdk_file(self):
        #Create SPK and SDK in one file
        image_gen_config.dict_multi_image_update_data["enabled_spk"]    = align_len_to_8bits(str(1))
        image_gen_config.dict_multi_image_update_data["enabled_apbl"]   = align_len_to_8bits(str(1))
        image_gen_config.dict_multi_image_update_data["enabled_sdk"]    = align_len_to_8bits(str(1))

        image_gen_config.dict_multi_image_update_data["enabled_model"]  = align_len_to_8bits(str(0))
        image_gen_config.dict_multi_image_update_data["size_model"]     = image_gen_config.FFFFFFFF
        image_gen_config.dict_multi_image_update_data["offset_model"]   = image_gen_config.FFFFFFFF

        image_gen_config.dict_multi_image_update_data["size_spk"] = align_len_to_8bits(self.spk_size)
        self.spk_offset = (str((hex)(self.dec_dict_size )))[2:]
        image_gen_config.dict_multi_image_update_data["offset_spk"] = align_len_to_8bits(self.spk_offset)

        image_gen_config.dict_multi_image_update_data["size_apbl"] = align_len_to_8bits(self.apbl_size)
        self.apbl_offset = (str((hex)(self.dec_dict_size + self.dec_spk_size)))[2:]
        image_gen_config.dict_multi_image_update_data["offset_apbl"] = align_len_to_8bits(self.apbl_offset)

        image_gen_config.dict_multi_image_update_data["size_sdk"] = align_len_to_8bits(self.sdk_size)
        self.sdk_offset = (str((hex)(self.dec_dict_size + self.dec_spk_size + self.dec_apbl_size)))[2:]
        image_gen_config.dict_multi_image_update_data["offset_sdk"] = align_len_to_8bits(self.sdk_offset)

        #Convert dictionary data to bin array for output_sdk_model_fw_update
        dict_arr = bytearray()
        dict_arr.extend(attr_dict2list(image_gen_config.dict_multi_image_update_data, self.dec_dict_size - self.crc_size, ''))
        with open(image_gen_config.output_spk_apbl_sdk_fw_update, 'wb+') as file:
            # Write the new byte array to the beginning of the file
            file.write(bytearray(dict_arr))

        #Calcualte CRC32 value
        my_arr = read_file_to_array(image_gen_config.output_spk_apbl_sdk_fw_update)
        crc = self.crcCalculator.calculate_crc32(my_arr)
        with open(image_gen_config.output_spk_apbl_sdk_fw_update, 'ab') as file:
            #Add CRC to file
            file.write(struct.pack('<I', crc))
            file.write(self.spk_data_byte_array + self.apbl_data_byte_array + self.sdk_data_byte_array)

    def apbl_sdk_file(self):
        #Create SPK and SDK in one file
        image_gen_config.dict_multi_image_update_data["enabled_spk"]    = align_len_to_8bits(str(0))
        image_gen_config.dict_multi_image_update_data["enabled_apbl"]   = align_len_to_8bits(str(1))
        image_gen_config.dict_multi_image_update_data["enabled_sdk"]    = align_len_to_8bits(str(1))

        image_gen_config.dict_multi_image_update_data["enabled_model"]  = align_len_to_8bits(str(0))
        image_gen_config.dict_multi_image_update_data["size_model"]     = image_gen_config.FFFFFFFF
        image_gen_config.dict_multi_image_update_data["offset_model"]   = image_gen_config.FFFFFFFF

        image_gen_config.dict_multi_image_update_data["size_apbl"] = align_len_to_8bits(self.apbl_size)
        self.apbl_offset = (str((hex)(self.dec_dict_size)))[2:]
        image_gen_config.dict_multi_image_update_data["offset_apbl"] = align_len_to_8bits(self.apbl_offset)

        image_gen_config.dict_multi_image_update_data["size_sdk"] = align_len_to_8bits(self.sdk_size)
        self.sdk_offset = (str((hex)(self.dec_dict_size  + self.dec_apbl_size)))[2:]
        image_gen_config.dict_multi_image_update_data["offset_sdk"] = align_len_to_8bits(self.sdk_offset)

        #Convert dictionary data to bin array for output_sdk_model_fw_update
        dict_arr = bytearray()
        dict_arr.extend(attr_dict2list(image_gen_config.dict_multi_image_update_data, self.dec_dict_size - self.crc_size, ''))
        with open(image_gen_config.output_apbl_sdk_fw_update, 'wb+') as file:
            # Write the new byte array to the beginning of the file
            file.write(bytearray(dict_arr))

        #Calcualte CRC32 value
        my_arr = read_file_to_array(image_gen_config.output_apbl_sdk_fw_update)
        crc = self.crcCalculator.calculate_crc32(my_arr)
        with open(image_gen_config.output_apbl_sdk_fw_update, 'ab') as file:
            #Add CRC to file
            file.write(struct.pack('<I', crc))
            file.write(self.apbl_data_byte_array + self.sdk_data_byte_array)

    def spk_apbl_sdk_model_file(self):
        #Create SPK and SDK in one file
        image_gen_config.dict_multi_image_update_data["enabled_spk"]    = align_len_to_8bits(str(1))
        image_gen_config.dict_multi_image_update_data["enabled_apbl"]   = align_len_to_8bits(str(1))
        image_gen_config.dict_multi_image_update_data["enabled_sdk"]    = align_len_to_8bits(str(1))
        image_gen_config.dict_multi_image_update_data["enabled_model"]  = align_len_to_8bits(str(1))

        image_gen_config.dict_multi_image_update_data["size_spk"] = align_len_to_8bits(self.spk_size)
        self.spk_offset = (str((hex)(self.dec_dict_size )))[2:]
        image_gen_config.dict_multi_image_update_data["offset_spk"] = align_len_to_8bits(self.spk_offset)

        image_gen_config.dict_multi_image_update_data["size_apbl"] = align_len_to_8bits(self.apbl_size)
        self.apbl_offset = (str((hex)(self.dec_dict_size + self.dec_spk_size)))[2:]
        image_gen_config.dict_multi_image_update_data["offset_apbl"] = align_len_to_8bits(self.apbl_offset)

        image_gen_config.dict_multi_image_update_data["size_sdk"] = align_len_to_8bits(self.sdk_size)
        self.sdk_offset = (str((hex)(self.dec_dict_size + self.dec_spk_size + self.dec_apbl_size)))[2:]
        image_gen_config.dict_multi_image_update_data["offset_sdk"] = align_len_to_8bits(self.sdk_offset)

        image_gen_config.dict_multi_image_update_data["size_model"] = align_len_to_8bits(self.model_size)
        self.model_offset = (str((hex)(self.dec_dict_size + self.dec_spk_size + self.dec_apbl_size + self.dec_sdk_size)))[2:]
        image_gen_config.dict_multi_image_update_data["offset_model"] = align_len_to_8bits(self.model_offset)

        #Convert dictionary data to bin array for output_sdk_model_fw_update
        dict_arr = bytearray()
        dict_arr.extend(attr_dict2list(image_gen_config.dict_multi_image_update_data, self.dec_dict_size - self.crc_size, ''))
        with open(image_gen_config.output_spk_apbl_sdk_model_fw_update, 'wb+') as file:
            # Write the new byte array to the beginning of the file
            file.write(bytearray(dict_arr))

        #Calcualte CRC32 value
        my_arr = read_file_to_array(image_gen_config.output_spk_apbl_sdk_model_fw_update)
        crc = self.crcCalculator.calculate_crc32(my_arr)
        with open(image_gen_config.output_spk_apbl_sdk_model_fw_update, 'ab') as file:
            #Add CRC to file
            file.write(struct.pack('<I', crc))
            file.write(self.spk_data_byte_array + self.apbl_data_byte_array + self.sdk_data_byte_array + self.model_data_byte_array)

def create_fw_update_images():
    fw_update_process = FW_Update()
    fw_update_process.create_fw_update_files_and_dict_size_calc()
    fw_update_process.spk_stand_alone_file()
    fw_update_process.apbl_stand_alone_file()
    fw_update_process.sdk_stand_alone_file()
    fw_update_process.spk_sdk_file()
    fw_update_process.spk_apbl_file()
    fw_update_process.spk_apbl_sdk_file()
    fw_update_process.apbl_sdk_file()
    if image_gen_config.output_model_flash:
        fw_update_process.model_stand_alone_file()
        fw_update_process.sdk_model_file()
        fw_update_process.spk_sdk_model_file()
        fw_update_process.spk_apbl_sdk_model_file()