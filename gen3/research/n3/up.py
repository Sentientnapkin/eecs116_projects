from huggingface_hub import HfApi
a=HfApi()
for f in ['ins_patch_C_lo32_kd1.wasm','ins_patch_C_lo32_kd1.c']:
    a.upload_file(path_or_fileobj='/data/backups/rganapa/Sebastian/gen3/research/n3/'+f,path_in_repo=f,repo_id='SentientNapkin/gslv-stage3',repo_type='model',commit_message='n3: IMU ESKF + C_lo32_kd1 velocity net + gyro-compensated patch epipolar gyro-bias aid')
    print('ok',f)
