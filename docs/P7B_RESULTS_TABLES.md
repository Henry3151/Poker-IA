# Tabelas de resultados — p7b_final_report.json (gerado automaticamente por scripts/render_p7_tables.py)

Evaluation run: `e4736a57-b621-5f54-ba77-3ced98f70e1e` · unidades: simulated buy-in units (SIM); no real money

ROI = lucro líquido / custo (buy-in 100 + taxa 10). IC 95% bootstrap sobre torneios. Referência de campo igual: ROI esperado = −9,1% (só a taxa).

## Cenário `baseline`

| candidato | n | ROI | IC 95% | veredito | ITM | vitórias | drawdown máx (SIM) | reentradas |
|---|---|---|---|---|---|---|---|---|
| pushfold_p7 | 400 | -10.3% | [-28.8%, +7.7%] | inconclusive | 21.8% | 45 | 5240 | 0 |
| pushfold_v2_ante | 400 | -7.0% | [-25.0%, +11.8%] | inconclusive | 22.5% | 47 | 4760 | 0 |
| hybrid_v1 | 400 | +89.5% | [+66.6%, +114.4%] | evidence_positive | 42.5% | 108 | 1500 | 0 |
| random | 400 | -41.4% | [-56.1%, -25.5%] | evidence_negative | 13.5% | 30 | 19010 | 0 |
| heuristic | 400 | -31.3% | [-42.7%, -19.3%] | evidence_negative | 26.0% | 1 | 14160 | 0 |
| equity | 400 | -43.3% | [-57.5%, -28.0%] | evidence_negative | 14.5% | 26 | 19040 | 0 |
| lag | 400 | +69.1% | [+47.8%, +90.1%] | evidence_positive | 41.0% | 79 | 1190 | 0 |

Diferença pareada vs `pushfold_p7` (lucro por torneio, em buy-ins de 110):

| candidato | média | IC 95% | n | veredito |
|---|---|---|---|---|
| pushfold_v2_ante | +0.033 | [-0.090, +0.155] | 400 | inconclusive |
| hybrid_v1 | +0.998 | [+0.723, +1.268] | 400 | evidence_positive |
| random | -0.311 | [-0.537, -0.082] | 400 | evidence_negative |
| heuristic | -0.210 | [-0.415, -0.008] | 400 | evidence_negative |
| equity | -0.330 | [-0.521, -0.131] | 400 | evidence_negative |
| lag | +0.794 | [+0.513, +1.042] | 400 | evidence_positive |

## Cenário `field_lag`

| candidato | n | ROI | IC 95% | veredito | ITM | vitórias | drawdown máx (SIM) | reentradas |
|---|---|---|---|---|---|---|---|---|
| pushfold_p7 | 200 | -54.2% | [-69.5%, -37.3%] | evidence_negative | 14.5% | 6 | 12640 | 0 |
| pushfold_v2_ante | 200 | -52.5% | [-68.9%, -33.5%] | evidence_negative | 14.0% | 9 | 12520 | 0 |
| hybrid_v1 | 200 | -22.0% | [-44.4%, +1.5%] | inconclusive | 21.0% | 15 | 5260 | 0 |
| random | 200 | -61.8% | [-77.1%, -44.9%] | evidence_negative | 10.5% | 6 | 13600 | 0 |
| heuristic | 200 | -48.2% | [-62.4%, -32.9%] | evidence_negative | 20.0% | 0 | 10880 | 0 |
| equity | 200 | -59.1% | [-73.3%, -42.7%] | evidence_negative | 13.5% | 4 | 13280 | 0 |
| lag | 200 | +5.8% | [-17.6%, +31.5%] | inconclusive | 30.0% | 18 | 2150 | 0 |

Diferença pareada vs `pushfold_p7` (lucro por torneio, em buy-ins de 110):

| candidato | média | IC 95% | n | veredito |
|---|---|---|---|---|
| pushfold_v2_ante | +0.016 | [-0.087, +0.115] | 200 | inconclusive |
| hybrid_v1 | +0.322 | [+0.071, +0.600] | 200 | evidence_positive |
| random | -0.076 | [-0.311, +0.175] | 200 | inconclusive |
| heuristic | +0.060 | [-0.169, +0.284] | 200 | inconclusive |
| equity | -0.049 | [-0.240, +0.158] | 200 | inconclusive |
| lag | +0.600 | [+0.322, +0.873] | 200 | evidence_positive |

## Cenário `turbo_short`

| candidato | n | ROI | IC 95% | veredito | ITM | vitórias | drawdown máx (SIM) | reentradas |
|---|---|---|---|---|---|---|---|---|
| pushfold_p7 | 200 | +9.1% | [-16.0%, +38.5%] | inconclusive | 27.0% | 27 | 2410 | 0 |
| pushfold_v2_ante | 200 | +28.2% | [-0.2%, +58.7%] | inconclusive | 29.5% | 36 | 2100 | 0 |
| hybrid_v1 | 200 | +57.6% | [+26.0%, +88.2%] | evidence_positive | 33.5% | 48 | 1080 | 0 |
| random | 200 | -52.0% | [-70.0%, -30.7%] | evidence_negative | 10.5% | 14 | 11600 | 0 |
| heuristic | 200 | -28.5% | [-45.5%, -11.1%] | evidence_negative | 25.5% | 1 | 6420 | 0 |
| equity | 200 | -13.3% | [-36.7%, +13.5%] | inconclusive | 21.5% | 20 | 3470 | 0 |
| lag | 200 | +63.6% | [+34.7%, +93.6%] | evidence_positive | 39.0% | 40 | 1300 | 0 |

Diferença pareada vs `pushfold_p7` (lucro por torneio, em buy-ins de 110):

| candidato | média | IC 95% | n | veredito |
|---|---|---|---|---|
| pushfold_v2_ante | +0.191 | [+0.027, +0.365] | 200 | evidence_positive |
| hybrid_v1 | +0.485 | [+0.065, +0.867] | 200 | evidence_positive |
| random | -0.611 | [-0.976, -0.267] | 200 | evidence_negative |
| heuristic | -0.376 | [-0.709, -0.076] | 200 | evidence_negative |
| equity | -0.224 | [-0.529, +0.087] | 200 | inconclusive |
| lag | +0.545 | [+0.125, +0.971] | 200 | evidence_positive |

## Cenário `field_tag`

| candidato | n | ROI | IC 95% | veredito | ITM | vitórias | drawdown máx (SIM) | reentradas |
|---|---|---|---|---|---|---|---|---|
| pushfold_p7 | 100 | +200.0% | [+145.5%, +254.5%] | insufficient_sample | 55.0% | 55 | 440 | 0 |
| pushfold_v2_ante | 100 | +225.1% | [+172.7%, +276.4%] | insufficient_sample | 60.0% | 59 | 440 | 0 |
| hybrid_v1 | 100 | +320.0% | [+276.4%, +363.6%] | insufficient_sample | 77.0% | 77 | 220 | 0 |
| random | 100 | +85.5% | [+33.1%, +136.7%] | insufficient_sample | 35.0% | 33 | 990 | 0 |
| heuristic | 100 | +90.9% | [+48.4%, +137.8%] | insufficient_sample | 45.0% | 24 | 770 | 0 |
| equity | 100 | +85.5% | [+36.4%, +135.6%] | insufficient_sample | 36.0% | 32 | 880 | 0 |
| lag | 100 | +359.3% | [+320.0%, +396.4%] | insufficient_sample | 85.0% | 83 | 220 | 0 |

Diferença pareada vs `pushfold_p7` (lucro por torneio, em buy-ins de 110):

| candidato | média | IC 95% | n | veredito |
|---|---|---|---|---|
| pushfold_v2_ante | +0.251 | [-0.109, +0.600] | 100 | insufficient_sample |
| hybrid_v1 | +1.200 | [+0.600, +1.800] | 100 | insufficient_sample |
| random | -1.145 | [-1.822, -0.469] | 100 | insufficient_sample |
| heuristic | -1.091 | [-1.800, -0.404] | 100 | insufficient_sample |
| equity | -1.145 | [-1.745, -0.567] | 100 | insufficient_sample |
| lag | +1.593 | [+0.927, +2.269] | 100 | insufficient_sample |

## Cenário `field_nit`

| candidato | n | ROI | IC 95% | veredito | ITM | vitórias | drawdown máx (SIM) | reentradas |
|---|---|---|---|---|---|---|---|---|
| pushfold_p7 | 100 | +276.4% | [+227.3%, +325.5%] | insufficient_sample | 70.0% | 68 | 330 | 0 |
| pushfold_v2_ante | 100 | +296.0% | [+246.9%, +341.8%] | insufficient_sample | 73.0% | 72 | 330 | 0 |
| hybrid_v1 | 100 | +423.6% | [+401.8%, +440.0%] | insufficient_sample | 96.0% | 96 | 110 | 0 |
| random | 100 | +227.3% | [+178.2%, +281.8%] | insufficient_sample | 60.0% | 60 | 330 | 0 |
| heuristic | 100 | +215.3% | [+167.3%, +262.2%] | insufficient_sample | 66.0% | 48 | 440 | 0 |
| equity | 100 | +212.0% | [+160.7%, +263.3%] | insufficient_sample | 60.0% | 55 | 530 | 0 |
| lag | 100 | +423.6% | [+401.8%, +440.0%] | insufficient_sample | 96.0% | 96 | 110 | 0 |

Diferença pareada vs `pushfold_p7` (lucro por torneio, em buy-ins de 110):

| candidato | média | IC 95% | n | veredito |
|---|---|---|---|---|
| pushfold_v2_ante | +0.196 | [-0.044, +0.458] | 100 | insufficient_sample |
| hybrid_v1 | +1.473 | [+0.982, +1.985] | 100 | insufficient_sample |
| random | -0.491 | [-1.233, +0.273] | 100 | insufficient_sample |
| heuristic | -0.611 | [-1.211, +0.000] | 100 | insufficient_sample |
| equity | -0.644 | [-1.244, -0.044] | 100 | insufficient_sample |
| lag | +1.473 | [+1.004, +1.964] | 100 | insufficient_sample |

## Cenário `field_station`

| candidato | n | ROI | IC 95% | veredito | ITM | vitórias | drawdown máx (SIM) | reentradas |
|---|---|---|---|---|---|---|---|---|
| pushfold_p7 | 100 | +97.5% | [+57.1%, +138.9%] | insufficient_sample | 52.0% | 19 | 440 | 0 |
| pushfold_v2_ante | 100 | +92.0% | [+50.5%, +133.5%] | insufficient_sample | 51.0% | 19 | 440 | 0 |
| hybrid_v1 | 100 | +129.1% | [+85.5%, +171.6%] | insufficient_sample | 58.0% | 26 | 440 | 0 |
| random | 100 | -84.7% | [-97.8%, -68.4%] | insufficient_sample | 4.0% | 2 | 9320 | 0 |
| heuristic | 100 | +61.5% | [+34.2%, +87.6%] | insufficient_sample | 58.0% | 0 | 570 | 0 |
| equity | 100 | +97.5% | [+52.7%, +143.3%] | insufficient_sample | 47.0% | 25 | 770 | 0 |
| lag | 100 | +61.5% | [+21.1%, +101.8%] | insufficient_sample | 43.0% | 15 | 770 | 0 |

Diferença pareada vs `pushfold_p7` (lucro por torneio, em buy-ins de 110):

| candidato | média | IC 95% | n | veredito |
|---|---|---|---|---|
| pushfold_v2_ante | -0.055 | [-0.218, +0.065] | 100 | insufficient_sample |
| hybrid_v1 | +0.316 | [-0.185, +0.796] | 100 | insufficient_sample |
| random | -1.822 | [-2.247, -1.407] | 100 | insufficient_sample |
| heuristic | -0.360 | [-0.785, +0.055] | 100 | insufficient_sample |
| equity | -0.000 | [-0.436, +0.415] | 100 | insufficient_sample |
| lag | -0.360 | [-0.862, +0.120] | 100 | insufficient_sample |

## Cenário `reentry`

| candidato | n | ROI | IC 95% | veredito | ITM | vitórias | drawdown máx (SIM) | reentradas |
|---|---|---|---|---|---|---|---|---|
| pushfold_p7 | 100 | -10.5% | [-41.3%, +22.9%] | insufficient_sample | 26.0% | 11 | 2960 | 39 |
| pushfold_v2_ante | 100 | -6.2% | [-38.1%, +26.4%] | insufficient_sample | 27.0% | 11 | 2610 | 39 |
| hybrid_v1 | 100 | +84.1% | [+34.2%, +137.1%] | insufficient_sample | 39.0% | 24 | 1210 | 18 |
| random | 100 | -65.0% | [-82.5%, -43.7%] | insufficient_sample | 14.0% | 8 | 16050 | 118 |
| heuristic | 100 | -50.6% | [-72.8%, -25.5%] | insufficient_sample | 16.0% | 1 | 6200 | 7 |
| equity | 100 | -33.3% | [-62.6%, -3.2%] | insufficient_sample | 19.0% | 10 | 5590 | 44 |
| lag | 100 | +48.1% | [+9.7%, +89.5%] | insufficient_sample | 40.0% | 15 | 1320 | 26 |

Diferença pareada vs `pushfold_p7` (lucro por torneio, em buy-ins de 110):

| candidato | média | IC 95% | n | veredito |
|---|---|---|---|---|
| pushfold_v2_ante | +0.060 | [-0.248, +0.378] | 100 | insufficient_sample |
| hybrid_v1 | +1.139 | [+0.448, +1.756] | 100 | insufficient_sample |
| random | -1.270 | [-1.874, -0.675] | 100 | insufficient_sample |
| heuristic | -0.395 | [-0.925, +0.115] | 100 | insufficient_sample |
| equity | -0.334 | [-0.937, +0.221] | 100 | insufficient_sample |
| lag | +0.752 | [+0.100, +1.390] | 100 | insufficient_sample |

## Cenário `top_heavy`

| candidato | n | ROI | IC 95% | veredito | ITM | vitórias | drawdown máx (SIM) | reentradas |
|---|---|---|---|---|---|---|---|---|
| pushfold_p7 | 100 | -55.8% | [-82.0%, -26.4%] | insufficient_sample | 9.0% | 3 | 6590 | 0 |
| pushfold_v2_ante | 100 | -35.1% | [-71.1%, +4.2%] | insufficient_sample | 11.0% | 7 | 5320 | 0 |
| hybrid_v1 | 100 | +72.4% | [+18.4%, +126.9%] | insufficient_sample | 28.0% | 20 | 1990 | 0 |
| random | 100 | -42.2% | [-74.4%, -3.5%] | insufficient_sample | 10.0% | 6 | 5850 | 0 |
| heuristic | 100 | -31.8% | [-61.8%, -1.3%] | insufficient_sample | 17.0% | 1 | 3720 | 0 |
| equity | 100 | -6.2% | [-46.5%, +40.2%] | insufficient_sample | 16.0% | 10 | 2150 | 0 |
| lag | 100 | +96.4% | [+39.1%, +151.5%] | insufficient_sample | 36.0% | 18 | 1230 | 0 |

Diferença pareada vs `pushfold_p7` (lucro por torneio, em buy-ins de 110):

| candidato | média | IC 95% | n | veredito |
|---|---|---|---|---|
| pushfold_v2_ante | +0.207 | [-0.109, +0.556] | 100 | insufficient_sample |
| hybrid_v1 | +1.282 | [+0.671, +1.904] | 100 | insufficient_sample |
| random | +0.136 | [-0.338, +0.616] | 100 | insufficient_sample |
| heuristic | +0.240 | [-0.185, +0.655] | 100 | insufficient_sample |
| equity | +0.496 | [+0.033, +1.015] | 100 | insufficient_sample |
| lag | +1.522 | [+0.944, +2.105] | 100 | insufficient_sample |

## Amostras progressivas (cenário baseline)

| candidato | n | ROI | IC 95% | veredito |
|---|---|---|---|---|
| pushfold_p7 | 50 | -38.9% | [-78.2%, +9.1%] | insufficient_sample |
| pushfold_p7 | 100 | -34.5% | [-64.0%, -2.9%] | insufficient_sample |
| pushfold_p7 | 200 | -15.5% | [-39.5%, +9.6%] | inconclusive |
| pushfold_p7 | 400 | -10.3% | [-28.8%, +7.7%] | inconclusive |
| pushfold_v2_ante | 50 | -25.8% | [-65.1%, +24.4%] | insufficient_sample |
| pushfold_v2_ante | 100 | -28.0% | [-56.4%, +2.5%] | insufficient_sample |
| pushfold_v2_ante | 200 | -13.8% | [-36.7%, +11.3%] | inconclusive |
| pushfold_v2_ante | 400 | -7.0% | [-25.0%, +11.8%] | inconclusive |
| hybrid_v1 | 50 | +48.4% | [-8.4%, +105.1%] | insufficient_sample |
| hybrid_v1 | 100 | +92.0% | [+45.1%, +136.7%] | insufficient_sample |
| hybrid_v1 | 200 | +94.2% | [+62.0%, +126.4%] | evidence_positive |
| hybrid_v1 | 400 | +89.5% | [+66.6%, +114.4%] | evidence_positive |
| random | 50 | -54.2% | [-89.1%, -10.5%] | insufficient_sample |
| random | 100 | -62.9% | [-85.8%, -34.5%] | insufficient_sample |
| random | 200 | -43.3% | [-63.5%, -20.9%] | evidence_negative |
| random | 400 | -41.4% | [-56.1%, -25.5%] | evidence_negative |
| heuristic | 50 | -25.8% | [-56.4%, +6.9%] | insufficient_sample |
| heuristic | 100 | -23.6% | [-47.6%, -0.7%] | insufficient_sample |
| heuristic | 200 | -30.2% | [-46.0%, -13.8%] | evidence_negative |
| heuristic | 400 | -31.3% | [-42.7%, -19.3%] | evidence_negative |
| equity | 50 | -41.1% | [-78.2%, +0.4%] | insufficient_sample |
| equity | 100 | -29.1% | [-61.8%, +3.6%] | insufficient_sample |
| equity | 200 | -37.3% | [-58.0%, -16.0%] | evidence_negative |
| equity | 400 | -43.3% | [-57.5%, -28.0%] | evidence_negative |
| lag | 50 | +85.5% | [+24.4%, +146.5%] | insufficient_sample |
| lag | 100 | +71.3% | [+28.7%, +116.0%] | insufficient_sample |
| lag | 200 | +83.8% | [+53.8%, +116.0%] | evidence_positive |
| lag | 400 | +69.1% | [+47.8%, +90.1%] | evidence_positive |

## Recortes por mão (baseline): bb/mão com IC por cluster (torneios)

### pushfold_p7

| dimensão | faixa | mãos | bb/mão | IC 95% | flag |
|---|---|---|---|---|---|
| phase | early | 3143 | +0.039 | [-0.281, +0.366] | inconclusive |
| phase | final_table | 2785 | +0.009 | [-0.101, +0.109] | inconclusive |
| phase | middle | 11689 | -0.032 | [-0.110, +0.046] | inconclusive |
| position | BB | 3836 | -0.363 | [-0.637, -0.091] | evidence_negative |
| position | BTN | 3750 | +0.068 | [-0.059, +0.190] | inconclusive |
| position | CO | 3106 | +0.134 | [+0.043, +0.220] | evidence_positive |
| position | HJ | 2396 | +0.181 | [+0.044, +0.323] | evidence_positive |
| position | SB | 3380 | -0.038 | [-0.212, +0.126] | inconclusive |
| position | UTG | 1149 | +0.164 | [-0.126, +0.501] | inconclusive |
| stack_bucket | 10-20bb | 5162 | -0.022 | [-0.128, +0.070] | inconclusive |
| stack_bucket | 20-40bb | 5381 | -0.078 | [-0.217, +0.041] | inconclusive |
| stack_bucket | 40bb+ | 4069 | -0.023 | [-0.286, +0.242] | inconclusive |
| stack_bucket | <10bb | 3005 | +0.135 | [+0.040, +0.233] | evidence_positive |

### hybrid_v1

| dimensão | faixa | mãos | bb/mão | IC 95% | flag |
|---|---|---|---|---|---|
| phase | early | 3156 | +0.265 | [-0.023, +0.562] | inconclusive |
| phase | final_table | 4842 | +0.238 | [+0.147, +0.334] | evidence_positive |
| phase | middle | 14054 | +0.411 | [+0.340, +0.477] | evidence_positive |
| position | BB | 5018 | +0.071 | [-0.096, +0.215] | inconclusive |
| position | BTN | 5024 | +0.600 | [+0.481, +0.723] | evidence_positive |
| position | CO | 3747 | +0.574 | [+0.456, +0.694] | evidence_positive |
| position | HJ | 2704 | +0.325 | [+0.180, +0.459] | evidence_positive |
| position | SB | 4343 | +0.278 | [+0.124, +0.426] | evidence_positive |
| position | UTG | 1216 | +0.131 | [-0.103, +0.355] | inconclusive |
| stack_bucket | 10-20bb | 6788 | +0.293 | [+0.216, +0.361] | evidence_positive |
| stack_bucket | 20-40bb | 8399 | +0.441 | [+0.347, +0.528] | evidence_positive |
| stack_bucket | 40bb+ | 4870 | +0.328 | [+0.110, +0.542] | evidence_positive |
| stack_bucket | <10bb | 1995 | +0.237 | [+0.107, +0.353] | evidence_positive |

### heuristic

| dimensão | faixa | mãos | bb/mão | IC 95% | flag |
|---|---|---|---|---|---|
| phase | early | 3169 | +0.038 | [-0.161, +0.242] | inconclusive |
| phase | final_table | 3803 | -0.141 | [-0.170, -0.112] | evidence_negative |
| phase | middle | 17122 | -0.045 | [-0.075, -0.014] | evidence_negative |
| position | BB | 5023 | -0.244 | [-0.343, -0.157] | evidence_negative |
| position | BTN | 5031 | +0.140 | [+0.071, +0.206] | evidence_positive |
| position | CO | 4431 | +0.148 | [+0.070, +0.228] | evidence_positive |
| position | HJ | 3308 | +0.057 | [-0.044, +0.162] | inconclusive |
| position | SB | 4801 | -0.325 | [-0.403, -0.250] | evidence_negative |
| position | UTG | 1500 | +0.036 | [-0.111, +0.174] | inconclusive |
| stack_bucket | 10-20bb | 6199 | -0.036 | [-0.081, +0.012] | inconclusive |
| stack_bucket | 20-40bb | 4770 | +0.018 | [-0.053, +0.096] | inconclusive |
| stack_bucket | 40bb+ | 3594 | +0.043 | [-0.134, +0.217] | inconclusive |
| stack_bucket | <10bb | 9531 | -0.127 | [-0.147, -0.106] | evidence_negative |

### lag

| dimensão | faixa | mãos | bb/mão | IC 95% | flag |
|---|---|---|---|---|---|
| phase | early | 3099 | +0.238 | [-0.140, +0.586] | inconclusive |
| phase | final_table | 5595 | +0.097 | [+0.028, +0.162] | evidence_positive |
| phase | middle | 13824 | +0.296 | [+0.231, +0.357] | evidence_positive |
| position | BB | 5237 | +0.012 | [-0.137, +0.144] | inconclusive |
| position | BTN | 5326 | +0.495 | [+0.381, +0.612] | evidence_positive |
| position | CO | 3723 | +0.456 | [+0.300, +0.606] | evidence_positive |
| position | HJ | 2695 | +0.347 | [+0.157, +0.536] | evidence_positive |
| position | SB | 4327 | -0.037 | [-0.197, +0.109] | inconclusive |
| position | UTG | 1210 | +0.167 | [-0.227, +0.563] | inconclusive |
| stack_bucket | 10-20bb | 6354 | +0.192 | [+0.127, +0.258] | evidence_positive |
| stack_bucket | 20-40bb | 7266 | +0.347 | [+0.243, +0.446] | evidence_positive |
| stack_bucket | 40bb+ | 4633 | +0.259 | [-0.009, +0.494] | inconclusive |
| stack_bucket | <10bb | 4265 | +0.101 | [+0.042, +0.159] | evidence_positive |

### pushfold_v2_ante

| dimensão | faixa | mãos | bb/mão | IC 95% | flag |
|---|---|---|---|---|---|
| phase | early | 3143 | +0.039 | [-0.281, +0.340] | inconclusive |
| phase | final_table | 2667 | +0.051 | [-0.070, +0.164] | inconclusive |
| phase | middle | 11672 | -0.026 | [-0.108, +0.054] | inconclusive |
| position | BB | 3786 | -0.343 | [-0.625, -0.079] | evidence_negative |
| position | BTN | 3683 | +0.085 | [-0.048, +0.209] | inconclusive |
| position | CO | 3120 | +0.128 | [+0.044, +0.218] | evidence_positive |
| position | HJ | 2381 | +0.161 | [+0.037, +0.298] | evidence_positive |
| position | SB | 3365 | -0.008 | [-0.163, +0.151] | inconclusive |
| position | UTG | 1147 | +0.157 | [-0.143, +0.470] | inconclusive |
| stack_bucket | 10-20bb | 5134 | +0.003 | [-0.106, +0.107] | inconclusive |
| stack_bucket | 20-40bb | 5464 | -0.075 | [-0.212, +0.052] | inconclusive |
| stack_bucket | 40bb+ | 4068 | -0.026 | [-0.267, +0.209] | inconclusive |
| stack_bucket | <10bb | 2816 | +0.159 | [+0.067, +0.253] | evidence_positive |

### random

| dimensão | faixa | mãos | bb/mão | IC 95% | flag |
|---|---|---|---|---|---|
| phase | early | 2848 | -2.449 | [-3.095, -1.837] | evidence_negative |
| phase | final_table | 1642 | +0.085 | [-0.101, +0.267] | inconclusive |
| phase | middle | 6140 | -0.055 | [-0.223, +0.106] | inconclusive |
| position | BB | 2266 | -0.511 | [-0.982, -0.136] | evidence_negative |
| position | BTN | 2274 | -0.296 | [-0.759, +0.106] | inconclusive |
| position | CO | 1816 | -0.243 | [-0.715, +0.175] | inconclusive |
| position | HJ | 1424 | -0.966 | [-1.576, -0.375] | evidence_negative |
| position | SB | 2030 | -1.263 | [-1.824, -0.825] | evidence_negative |
| position | UTG | 820 | -1.172 | [-2.076, -0.340] | evidence_negative |
| stack_bucket | 10-20bb | 1950 | -0.136 | [-0.385, +0.078] | inconclusive |
| stack_bucket | 20-40bb | 3330 | -0.212 | [-0.480, +0.034] | inconclusive |
| stack_bucket | 40bb+ | 3762 | -1.677 | [-2.295, -1.121] | evidence_negative |
| stack_bucket | <10bb | 1588 | +0.069 | [-0.078, +0.221] | inconclusive |

### equity

| dimensão | faixa | mãos | bb/mão | IC 95% | flag |
|---|---|---|---|---|---|
| phase | early | 3153 | +0.016 | [-0.280, +0.328] | inconclusive |
| phase | final_table | 1955 | -0.123 | [-0.301, +0.029] | inconclusive |
| phase | middle | 10704 | -0.113 | [-0.204, -0.027] | evidence_negative |
| position | BB | 3304 | -0.476 | [-0.791, -0.151] | evidence_negative |
| position | BTN | 3210 | +0.123 | [-0.019, +0.269] | inconclusive |
| position | CO | 2828 | +0.085 | [+0.010, +0.170] | evidence_positive |
| position | HJ | 2293 | +0.121 | [-0.038, +0.308] | inconclusive |
| position | SB | 3053 | -0.220 | [-0.416, -0.023] | evidence_negative |
| position | UTG | 1124 | -0.066 | [-0.358, +0.182] | inconclusive |
| stack_bucket | 10-20bb | 4332 | -0.166 | [-0.277, -0.064] | evidence_negative |
| stack_bucket | 20-40bb | 5140 | -0.024 | [-0.178, +0.129] | inconclusive |
| stack_bucket | 40bb+ | 4095 | -0.138 | [-0.371, +0.103] | inconclusive |
| stack_bucket | <10bb | 2245 | +0.001 | [-0.122, +0.119] | inconclusive |

## Qualidade de decisão (baseline, só informação disponível na decisão)

| candidato | decisões | calls | margem média equity−pot odds (IC) | calls abaixo das pot odds | mix de ações | base da equity |
|---|---|---|---|---|---|---|
| pushfold_p7 | 22985 | 3936 | +0.185 [+0.180, +0.189] | 0.0003 | bet 3%, call 17%, check 18%, fold 53%, raise 9% | {'agent_estimate': 21223, 'vs_uniform_random_hands_mc100': 1762} |
| hybrid_v1 | 25104 | 2576 | +0.182 [+0.175, +0.188] | 0.1471 | bet 5%, call 10%, check 10%, fold 52%, raise 23% | {'vs_uniform_random_hands_mc100': 20455, 'agent_estimate': 4649} |
| heuristic | 23459 | 485 | +0.311 [+0.291, +0.331] | 0.0866 | bet 1%, call 2%, check 3%, fold 86%, raise 8% | {'vs_uniform_random_hands_mc100': 23459} |
| lag | 24689 | 1599 | +0.216 [+0.205, +0.227] | 0.1776 | bet 4%, call 6%, check 8%, fold 55%, raise 26% | {'vs_uniform_random_hands_mc100': 24689} |
| pushfold_v2_ante | 22897 | 3957 | +0.185 [+0.181, +0.190] | 0.0003 | bet 3%, call 17%, check 18%, fold 53%, raise 9% | {'agent_estimate': 21225, 'vs_uniform_random_hands_mc100': 1672} |
| random | 15774 | 4364 | +0.052 [+0.046, +0.059] | 0.4769 | bet 11%, call 28%, check 12%, fold 27%, raise 23% | {'vs_uniform_random_hands_mc100': 15774} |
| equity | 24035 | 5279 | +0.204 [+0.201, +0.208] | 0.0 | bet 4%, call 22%, check 23%, fold 46%, raise 5% | {'agent_estimate': 24035} |

## Sorte de all-in (baseline): resultado − EV de all-in, calculado offline após a mão

| candidato | mãos all-in | sorte total (bb) | sorte média/mão (IC) | EV all-in total (bb) |
|---|---|---|---|---|
| pushfold_p7 | 1165 | -69.0 | -0.06 [-0.69, +0.52] | +816.6 |
| hybrid_v1 | 2067 | +447.5 | +0.22 [-0.14, +0.59] | +533.5 |
| heuristic | 990 | +255.2 | +0.26 [-0.21, +0.78] | +1236.9 |
| lag | 1792 | +140.6 | +0.08 [-0.44, +0.54] | +655.4 |
| pushfold_v2_ante | 1177 | -5.1 | -0.00 [-0.59, +0.58] | +746.4 |
| random | 1500 | -276.8 | -0.18 [-1.00, +0.65] | -6390.5 |
| equity | 1051 | -110.3 | -0.10 [-0.70, +0.46] | +64.1 |
