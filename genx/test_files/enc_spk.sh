#!/bin/sh

data_dir=${PWD}
out_dir=${PWD}
tool_dir=${PWD}

in_img_type="SPK"
in_aes_key=$data_dir/keys/SCGK_SPK.bin
in_iv=$data_dir/iv_spk.bin
in_signing_key=$data_dir/keys/K1_BOOT_A.rsa.priv.pem
in_seg_id=0x12345678
in_seg_id_mask=0xFFFFFFFF
in_version=0x00000000
in_version_mask=0xFFFFFFFF
in_extras=$data_dir/parameters/in_spk_extras.bin
in_payload_length=0x10000
in_payload=$data_dir/in_dummy_spk.bin
out_SPK=$out_dir/out_spk.bin

#shellCheckCall $fun_dir/gen_img1.sh $in_img_type $in_aes_key $in_signing_key  $in_seg_id  $in_seg_id_mask  $in_version  $in_version_mask $in_extras $in_payload_length $in_payload $out_SPK
${tool_dir}/../genx_img -t $in_img_type -k $in_aes_key -K $in_iv -n $in_signing_key -s $in_seg_id -r $in_version -x $in_extras -l $in_payload_length -i $in_payload -o $out_SPK


