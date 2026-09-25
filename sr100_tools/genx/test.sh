#!/bin/sh

data_dir_apbl=${PWD}/test_files/apbl_example
data_dir=${PWD}/test_files
out_dir=${PWD}/out
tool_dir=${PWD}

in_aes_key=$data_dir/SCGK_SPK.bin
in_iv=$data_dir/iv.bin
in_signing_key=$data_dir/K1_BOOT_A.rsa.priv.pem
in_signing_key_2048=$data_dir/2048_priv.pem
in_seg_id=0x12345678
in_seg_id_mask=0xFFFFFFFF
in_version=0x00000000
in_version_mask=0xFFFFFFFF
in_extras=$data_dir/in_spk_extras.bin
in_payload_length=0x10000
in_payload=$data_dir/in_dummy_spk.bin
in_pubkey=$data_dir/pubkey.pem
in_payload_extra=$data_dir/input_extra.bin

test_image () {
    image_type=$1
    arguments=$2
    out_py=$out_dir/$image_type\_py.bin
    out_c=$out_dir/$image_type\_c.bin

    echo "Testing $image_type image type"
    python3 main.py -t $image_type -o $out_py $arguments
    ./genx_img -t $image_type -o $out_c $arguments
    cmp $out_py $out_c
    if [ $? -eq 0 ]; then
        echo "$image_type image type test passed"
        rm $out_py $out_c
    else
        echo "Different output for $image_type image type"
        return 1
    fi
}

mkdir $out_dir

test_image "K0_SYNA"        "-i $in_pubkey"
test_image "K1_BOOT_A"      "-n $in_signing_key -s $in_seg_id -r $in_version -i $in_pubkey"
test_image "SPK"            "-k $in_aes_key -K $in_iv -n $in_signing_key -s $in_seg_id -r $in_version -x $in_extras -l $in_payload_length -i $in_payload"
test_image "APBL"           "-k $data_dir_apbl/SCGK_APBL.bin -K $data_dir_apbl/iv.bin -n $data_dir_apbl/K1_SPE_A.rsa.priv.pem -s $in_seg_id -r $in_version -x $data_dir_apbl/in_apbl_extras.bin -l $in_payload_length -i $data_dir_apbl/in_dummy_apbl.bin"

# in boot type2 the extras length should be 4
in_extras=$data_dir/extra.txt
echo -n 'AAAA' > $in_extras

test_image "SCS_DATA_PARAM" "-k $in_aes_key -n $in_signing_key -s $in_seg_id -r $in_version -x $in_extras -l $in_payload_length -i $in_payload"

# Possible bug in c code: header size constant is bigger than actual struct size (by 16 bytes)
# test_image "DIF"            "-k $in_aes_key -n $in_signing_key -x $in_extras -l $in_payload_length -i $in_payload -Y"
test_image "DDR_FW0"        "-k $in_aes_key -n $in_signing_key -l $in_payload_length -i $in_payload -Y"

# in model image the extras length should be 16
echo -n 'AAAAAAAAAAAAAAAA' > $in_extras
test_image "MODEL" "-k $in_aes_key -K $in_iv -n $in_signing_key -s $in_seg_id -r $in_version -x $in_extras -l $in_payload_length -i $in_payload -I $in_payload_extra"

rm $in_extras
in_extras=$data_dir/in_spk_extras.bin

# Possible bug in c code: SIZE_OF_OEM_COMMAND_STORE_SIGN is 256, but should be 512
test_image "OEM_COMMAND" "-n $in_signing_key_2048 -i $in_payload"

rmdir $out_dir