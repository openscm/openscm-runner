output_prefix 'output_rbs/test_rcmip'
gaspam_file '../input_RCP/gases_v1RCMIP.txt'
concentration_file 'input/ssp434_conc_RCMIP.txt' 
emission_file 'input/ssp434_em_RCMIP.txt'
scenario_file 'input/ssp434_em_RCMIP.txt'
model_end 2500
emission_start 1751
scenario_start 2015
scenario_end 2500
read_sunvol 1 '! 1: include sunvolc RF, 0: without'
lambda 0.540   !ECS/3.71
akapa 0.341
cpi 0.556
W 1.897
rlamdo 16.618
beto 3.225
mixed 107.277
bmb_forc 0.0000
dirso2_forc -0.457
indso2_forc -0.514
bc_forc 0.200
oc_forc -0.103
tropo3_forc 0.4
ch4_lifetime_mode TAR
post_scen_mode ANNUAL
