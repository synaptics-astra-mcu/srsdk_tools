#!/bin/sh

data_dir=${PWD}
out_dir=${PWD}
tool_dir=${PWD}

in_img_type="TF_M"
in_aes_key=$data_dir/keys/SCGK_AI_MODEL.bin
in_iv=$data_dir/parameters/iv_ai_model.bin
in_signing_key=$data_dir/keys/K1_SPE_C.rsa.priv.pem
in_seg_id=0x00000000
in_seg_id_mask=0xFFFFFFFF
in_version=0x00000000
in_version_mask=0xFFFFFFFF
in_extras=$data_dir/parameters/in_ai_model_extras.bin
in_payload_length=0x0
in_payload=$data_dir/in_dummy_ai_model.bin
out_TF_M=$out_dir/out_ai_model.bin

${tool_dir}/../genx_img -t $in_img_type -k $in_aes_key -K $in_iv -n $in_signing_key -s $in_seg_id -r $in_version -x $in_extras -l $in_payload_length -i $in_payload -o $out_TF_M


