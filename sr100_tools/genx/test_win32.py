import os
import subprocess
from colorama import init, Fore
import platform


# Initialize Colorama
init()

# Set up directories and file paths
data_dir = os.path.join(os.getcwd(), 'test_files')
data_dir_keys = os.path.join(os.getcwd(), 'test_files', 'keys')
data_dir_parameters = os.path.join(os.getcwd(), 'test_files', 'parameters')
out_dir = os.path.join(os.getcwd(), 'out')
tool_dir = os.getcwd()

# Define the input variables
in_aes_key = os.path.join(data_dir_keys, 'SCGK_SPK.bin')
in_iv = os.path.join(data_dir_parameters, 'iv_spk.bin')
in_signing_key = os.path.join(data_dir_keys, 'K1_BOOT_A.rsa.priv.pem')
in_signing_key_2048 = os.path.join(data_dir, '2048_priv.pem')
in_seg_id = '0x00000000'
in_seg_id_mask = '0xFFFFFFFF'
in_version = '0x00000000'
in_version_mask = '0xFFFFFFFF'
in_extras = os.path.join(data_dir_parameters, 'in_spk_extras.bin')
in_payload_length = 0
in_payload = os.path.join(data_dir, 'in_dummy_spk.bin')
in_pubkey = os.path.join(data_dir_keys, 'pubkey.pem')
in_payload_extra = os.path.join(data_dir, 'input_extra.bin')

def test_image(image_type, arguments):
    out_py = os.path.join(out_dir, f'{image_type}_py.bin')
    out_c = os.path.join(out_dir, f'{image_type}_c.bin')

    print(f'Testing {image_type} image type')
    subprocess.run(['python', 'main.py', '-t', image_type, '-o', out_py] + arguments.split())


# Create output directory
os.makedirs(out_dir, exist_ok=True)

# Test various image types
test_image('K0_SYNA',   f'-i {in_pubkey}')
test_image('K1_BOOT_A', f'-n {in_signing_key} -s {in_seg_id} -r {in_version} -i {in_pubkey}')
test_image('SPK',       f'-k {in_aes_key} -K {in_iv} -n {in_signing_key} -s {in_seg_id} -r {in_version} -x {in_extras} -l {in_payload_length} -i {in_payload}')
test_image('APBL',      f'-k {data_dir_keys}/SCGK_APBL.bin -K {data_dir_parameters}/iv_apbl.bin -n {data_dir_keys}/K1_SPE_A.rsa.priv.pem -s {in_seg_id} -r {in_version} -x {data_dir_parameters}/in_apbl_extras.bin -l {in_payload_length} -i {data_dir}/in_dummy_apbl.bin')
test_image('TF_M',      f'-k {data_dir_keys}/SCGK_TF_M.bin -K {data_dir_parameters}/iv_tf_m.bin -n {data_dir_keys}/K1_SPE_B.rsa.priv.pem -s {in_seg_id} -r {in_version} -x {data_dir_parameters}/in_tf_m_extras.bin -l {in_payload_length} -i {data_dir}/in_dummy_tf_m.bin')
test_image('RTOS',      f'-k {data_dir_keys}/SCGK_RTOS.bin -K {data_dir_parameters}/iv_rtos.bin -n {data_dir_keys}/K1_NSPE_A.rsa.priv.pem -s {in_seg_id} -r {in_version} -x {data_dir_parameters}/in_rtos_extras.bin -l {in_payload_length} -i {data_dir}/in_dummy_rtos.bin')
test_image('M4_SW',     f'-k {data_dir_keys}/SCGK_M4_SW.bin -K {data_dir_parameters}/iv_m4_sw.bin -n {data_dir_keys}/K1_SPE_C.rsa.priv.pem -s {in_seg_id} -r {in_version} -x {data_dir_parameters}/in_m4_sw_extras.bin -l {in_payload_length} -i {data_dir}/in_dummy_m4_sw.bin')
test_image('LX7_SW',    f'-k {data_dir_keys}/SCGK_LX7_SW.bin -K {data_dir_parameters}/iv_lx7_sw.bin -n {data_dir_keys}/K1_SPE_C.rsa.priv.pem -s {in_seg_id} -r {in_version} -x {data_dir_parameters}/in_lx7_sw_extras.bin -l {in_payload_length} -i {data_dir}/in_dummy_lx7_sw.bin')
test_image('AI_MODEL',  f'-k {data_dir_keys}/SCGK_AI_MODEL.bin -K {data_dir_parameters}/iv_ai_model.bin -n {data_dir_keys}/K1_NSPE_A.rsa.priv.pem -s {in_seg_id} -r {in_version} -x {data_dir_parameters}/in_ai_model_extras.bin -l {in_payload_length} -i {data_dir}/in_dummy_ai_model.bin')
