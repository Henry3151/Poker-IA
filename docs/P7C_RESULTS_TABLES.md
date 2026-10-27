# Tabelas de resultados — p7c_final_report.json (gerado automaticamente por scripts/render_p7_tables.py)

Evaluation run: `0a9c56b9-9690-506e-86c8-75dea356b46e` · unidades: simulated buy-in units (SIM); no real money

ROI = lucro líquido / custo (buy-in 100 + taxa 10). IC 95% bootstrap sobre torneios. Referência de campo igual: ROI esperado = −9,1% (só a taxa).

## Cenário `robust_mix`

| candidato | n | ROI | IC 95% | veredito | ITM | vitórias | drawdown máx (SIM) | reentradas |
|---|---|---|---|---|---|---|---|---|
| hybrid_v1 | 400 | +76.5% | [+53.3%, +100.5%] | evidence_positive | 36.5% | 111 | 1540 | 0 |
| hybrid_v2_adaptive | 400 | +51.6% | [+30.6%, +74.3%] | evidence_positive | 33.0% | 91 | 1960 | 0 |
| hybrid_v1_bluffcatch | 400 | +53.8% | [+32.0%, +77.3%] | evidence_positive | 33.2% | 93 | 1850 | 0 |
| pushfold_p7 | 400 | -17.1% | [-34.5%, +1.7%] | inconclusive | 19.0% | 47 | 8200 | 0 |
| lag | 400 | +67.2% | [+45.6%, +89.0%] | evidence_positive | 41.0% | 78 | 990 | 0 |

Diferença pareada vs `hybrid_v1` (lucro por torneio, em buy-ins de 110):

| candidato | média | IC 95% | n | veredito |
|---|---|---|---|---|
| hybrid_v2_adaptive | -0.248 | [-0.469, -0.035] | 400 | evidence_negative |
| hybrid_v1_bluffcatch | -0.226 | [-0.415, -0.035] | 400 | evidence_negative |
| pushfold_p7 | -0.935 | [-1.222, -0.660] | 400 | evidence_negative |
| lag | -0.093 | [-0.390, +0.188] | 400 | inconclusive |

## Cenário `adaptive_only`

| candidato | n | ROI | IC 95% | veredito | ITM | vitórias | drawdown máx (SIM) | reentradas |
|---|---|---|---|---|---|---|---|---|
| hybrid_v1 | 200 | +33.6% | [+5.8%, +62.0%] | evidence_positive | 32.5% | 33 | 1190 | 0 |
| hybrid_v2_adaptive | 200 | +27.6% | [-0.2%, +58.2%] | inconclusive | 31.0% | 33 | 1720 | 0 |
| hybrid_v1_bluffcatch | 200 | +27.6% | [-0.2%, +56.5%] | inconclusive | 31.0% | 32 | 2080 | 0 |
| pushfold_p7 | 200 | -30.2% | [-53.1%, -6.2%] | evidence_negative | 15.5% | 21 | 6850 | 0 |
| lag | 200 | +41.3% | [+12.4%, +70.2%] | evidence_positive | 35.0% | 32 | 1340 | 0 |

Diferença pareada vs `hybrid_v1` (lucro por torneio, em buy-ins de 110):

| candidato | média | IC 95% | n | veredito |
|---|---|---|---|---|
| hybrid_v2_adaptive | -0.060 | [-0.338, +0.218] | 200 | inconclusive |
| hybrid_v1_bluffcatch | -0.060 | [-0.305, +0.169] | 200 | inconclusive |
| pushfold_p7 | -0.638 | [-0.982, -0.295] | 200 | evidence_negative |
| lag | +0.076 | [-0.262, +0.425] | 200 | inconclusive |

## Cenário `bluff_heavy`

| candidato | n | ROI | IC 95% | veredito | ITM | vitórias | drawdown máx (SIM) | reentradas |
|---|---|---|---|---|---|---|---|---|
| hybrid_v1 | 200 | -1.8% | [-28.0%, +27.6%] | inconclusive | 21.5% | 28 | 3940 | 0 |
| hybrid_v2_adaptive | 200 | -25.8% | [-48.7%, +0.9%] | inconclusive | 17.0% | 20 | 7170 | 0 |
| hybrid_v1_bluffcatch | 200 | -12.2% | [-36.7%, +16.2%] | inconclusive | 19.5% | 25 | 4820 | 0 |
| pushfold_p7 | 200 | -43.3% | [-64.0%, -21.5%] | evidence_negative | 13.0% | 17 | 10110 | 0 |
| lag | 200 | +9.1% | [-17.6%, +38.5%] | inconclusive | 24.5% | 30 | 2270 | 0 |

Diferença pareada vs `hybrid_v1` (lucro por torneio, em buy-ins de 110):

| candidato | média | IC 95% | n | veredito |
|---|---|---|---|---|
| hybrid_v2_adaptive | -0.240 | [-0.524, +0.065] | 200 | inconclusive |
| hybrid_v1_bluffcatch | -0.104 | [-0.393, +0.202] | 200 | inconclusive |
| pushfold_p7 | -0.415 | [-0.736, -0.098] | 200 | evidence_negative |
| lag | +0.109 | [-0.251, +0.480] | 200 | inconclusive |

## Cenário `baseline_mixed`

| candidato | n | ROI | IC 95% | veredito | ITM | vitórias | drawdown máx (SIM) | reentradas |
|---|---|---|---|---|---|---|---|---|
| hybrid_v1 | 200 | +48.9% | [+20.5%, +82.2%] | evidence_positive | 32.5% | 43 | 2580 | 0 |
| hybrid_v2_adaptive | 200 | +45.1% | [+14.0%, +78.4%] | evidence_positive | 31.0% | 43 | 1210 | 0 |
| hybrid_v1_bluffcatch | 200 | +37.5% | [+8.5%, +68.0%] | evidence_positive | 30.0% | 40 | 1410 | 0 |
| pushfold_p7 | 200 | -2.4% | [-28.0%, +26.0%] | inconclusive | 21.5% | 29 | 3940 | 0 |
| lag | 200 | +81.1% | [+52.7%, +110.5%] | evidence_positive | 46.5% | 35 | 770 | 0 |

Diferença pareada vs `hybrid_v1` (lucro por torneio, em buy-ins de 110):

| candidato | média | IC 95% | n | veredito |
|---|---|---|---|---|
| hybrid_v2_adaptive | -0.038 | [-0.344, +0.273] | 200 | inconclusive |
| hybrid_v1_bluffcatch | -0.115 | [-0.355, +0.131] | 200 | inconclusive |
| pushfold_p7 | -0.513 | [-0.873, -0.147] | 200 | evidence_negative |
| lag | +0.322 | [-0.087, +0.715] | 200 | inconclusive |

## Cenário `selfplay_hybrid`

| candidato | n | ROI | IC 95% | veredito | ITM | vitórias | drawdown máx (SIM) | reentradas |
|---|---|---|---|---|---|---|---|---|
| hybrid_v1 | 100 | -10.5% | [-37.8%, +18.9%] | insufficient_sample | 30.0% | 4 | 2600 | 0 |
| hybrid_v2_adaptive | 100 | -31.3% | [-57.5%, -2.9%] | insufficient_sample | 23.0% | 4 | 3570 | 0 |
| hybrid_v1_bluffcatch | 100 | -32.4% | [-57.5%, -2.9%] | insufficient_sample | 22.0% | 4 | 3690 | 0 |
| pushfold_p7 | 100 | -50.9% | [-73.8%, -25.8%] | insufficient_sample | 15.0% | 3 | 5750 | 0 |
| lag | 100 | -8.4% | [-38.9%, +26.5%] | insufficient_sample | 27.0% | 6 | 2770 | 0 |

Diferença pareada vs `hybrid_v1` (lucro por torneio, em buy-ins de 110):

| candidato | média | IC 95% | n | veredito |
|---|---|---|---|---|
| hybrid_v2_adaptive | -0.207 | [-0.491, +0.076] | 100 | insufficient_sample |
| hybrid_v1_bluffcatch | -0.218 | [-0.469, +0.022] | 100 | insufficient_sample |
| pushfold_p7 | -0.404 | [-0.807, -0.022] | 100 | insufficient_sample |
| lag | +0.022 | [-0.393, +0.447] | 100 | insufficient_sample |

## Cenário `versions_mix`

| candidato | n | ROI | IC 95% | veredito | ITM | vitórias | drawdown máx (SIM) | reentradas |
|---|---|---|---|---|---|---|---|---|
| hybrid_v1 | 100 | +41.8% | [+4.7%, +83.3%] | insufficient_sample | 37.0% | 14 | 1500 | 0 |
| hybrid_v2_adaptive | 100 | +15.6% | [-19.3%, +54.9%] | insufficient_sample | 30.0% | 11 | 1750 | 0 |
| hybrid_v1_bluffcatch | 100 | +28.7% | [-9.5%, +66.9%] | insufficient_sample | 33.0% | 13 | 1020 | 0 |
| pushfold_p7 | 100 | -32.4% | [-58.5%, -1.8%] | insufficient_sample | 20.0% | 4 | 4270 | 0 |
| lag | 100 | +35.3% | [+0.4%, +73.5%] | insufficient_sample | 38.0% | 11 | 810 | 0 |

Diferença pareada vs `hybrid_v1` (lucro por torneio, em buy-ins de 110):

| candidato | média | IC 95% | n | veredito |
|---|---|---|---|---|
| hybrid_v2_adaptive | -0.262 | [-0.731, +0.175] | 100 | insufficient_sample |
| hybrid_v1_bluffcatch | -0.131 | [-0.600, +0.338] | 100 | insufficient_sample |
| pushfold_p7 | -0.742 | [-1.222, -0.262] | 100 | insufficient_sample |
| lag | -0.065 | [-0.535, +0.415] | 100 | insufficient_sample |

## Amostras progressivas (cenário baseline)

| candidato | n | ROI | IC 95% | veredito |
|---|---|---|---|---|
| hybrid_v1 | 50 | +76.7% | [+9.1%, +146.5%] | insufficient_sample |
| hybrid_v1 | 100 | +93.1% | [+47.3%, +144.4%] | insufficient_sample |
| hybrid_v1 | 200 | +82.7% | [+49.5%, +117.6%] | evidence_positive |
| hybrid_v1 | 400 | +76.5% | [+53.3%, +100.5%] | evidence_positive |
| hybrid_v2_adaptive | 50 | +44.0% | [-17.1%, +109.5%] | insufficient_sample |
| hybrid_v2_adaptive | 100 | +49.5% | [+5.8%, +95.3%] | insufficient_sample |
| hybrid_v2_adaptive | 200 | +56.0% | [+24.4%, +86.5%] | evidence_positive |
| hybrid_v2_adaptive | 400 | +51.6% | [+30.6%, +74.3%] | evidence_positive |
| hybrid_v1_bluffcatch | 50 | +39.6% | [-19.3%, +102.9%] | insufficient_sample |
| hybrid_v1_bluffcatch | 100 | +52.7% | [+9.1%, +100.7%] | insufficient_sample |
| hybrid_v1_bluffcatch | 200 | +57.6% | [+25.5%, +89.8%] | evidence_positive |
| hybrid_v1_bluffcatch | 400 | +53.8% | [+32.0%, +77.3%] | evidence_positive |
| pushfold_p7 | 50 | -36.7% | [-76.0%, +9.1%] | insufficient_sample |
| pushfold_p7 | 100 | -28.0% | [-58.5%, +5.8%] | insufficient_sample |
| pushfold_p7 | 200 | +1.5% | [-25.3%, +29.3%] | inconclusive |
| pushfold_p7 | 400 | -17.1% | [-34.5%, +1.7%] | inconclusive |
| lag | 50 | +105.1% | [+41.8%, +168.4%] | insufficient_sample |
| lag | 100 | +56.0% | [+15.6%, +100.7%] | insufficient_sample |
| lag | 200 | +48.4% | [+21.1%, +77.3%] | evidence_positive |
| lag | 400 | +67.2% | [+45.6%, +89.0%] | evidence_positive |

## Recortes por mão (baseline): bb/mão com IC por cluster (torneios)

### hybrid_v1

| dimensão | faixa | mãos | bb/mão | IC 95% | flag |
|---|---|---|---|---|---|
| phase | early | 3148 | +0.218 | [-0.082, +0.499] | inconclusive |
| phase | final_table | 4251 | +0.349 | [+0.252, +0.440] | evidence_positive |
| phase | middle | 14245 | +0.281 | [+0.218, +0.342] | evidence_positive |
| position | BB | 4812 | +0.004 | [-0.162, +0.157] | inconclusive |
| position | BTN | 4839 | +0.451 | [+0.326, +0.570] | evidence_positive |
| position | CO | 3669 | +0.491 | [+0.347, +0.631] | evidence_positive |
| position | HJ | 2783 | +0.369 | [+0.218, +0.511] | evidence_positive |
| position | SB | 4156 | +0.203 | [+0.056, +0.342] | evidence_positive |
| position | UTG | 1385 | +0.212 | [-0.003, +0.443] | inconclusive |
| stack_bucket | 10-20bb | 7035 | +0.280 | [+0.204, +0.347] | evidence_positive |
| stack_bucket | 20-40bb | 7918 | +0.347 | [+0.260, +0.437] | evidence_positive |
| stack_bucket | 40bb+ | 4305 | +0.199 | [-0.043, +0.406] | inconclusive |
| stack_bucket | <10bb | 2386 | +0.249 | [+0.121, +0.365] | evidence_positive |

### hybrid_v1_bluffcatch

| dimensão | faixa | mãos | bb/mão | IC 95% | flag |
|---|---|---|---|---|---|
| phase | early | 3134 | +0.084 | [-0.245, +0.411] | inconclusive |
| phase | final_table | 4081 | +0.261 | [+0.180, +0.350] | evidence_positive |
| phase | middle | 13316 | +0.251 | [+0.179, +0.322] | evidence_positive |
| position | BB | 4552 | -0.099 | [-0.305, +0.089] | inconclusive |
| position | BTN | 4582 | +0.483 | [+0.348, +0.619] | evidence_positive |
| position | CO | 3462 | +0.446 | [+0.292, +0.607] | evidence_positive |
| position | HJ | 2659 | +0.342 | [+0.175, +0.492] | evidence_positive |
| position | SB | 3931 | +0.052 | [-0.097, +0.207] | inconclusive |
| position | UTG | 1345 | +0.187 | [-0.063, +0.466] | inconclusive |
| stack_bucket | 10-20bb | 6495 | +0.233 | [+0.150, +0.311] | evidence_positive |
| stack_bucket | 20-40bb | 7410 | +0.307 | [+0.215, +0.402] | evidence_positive |
| stack_bucket | 40bb+ | 4334 | +0.077 | [-0.183, +0.323] | inconclusive |
| stack_bucket | <10bb | 2292 | +0.237 | [+0.108, +0.348] | evidence_positive |

### lag

| dimensão | faixa | mãos | bb/mão | IC 95% | flag |
|---|---|---|---|---|---|
| phase | early | 3097 | +0.062 | [-0.320, +0.419] | inconclusive |
| phase | final_table | 5863 | +0.085 | [+0.028, +0.137] | evidence_positive |
| phase | middle | 14322 | +0.288 | [+0.232, +0.344] | evidence_positive |
| position | BB | 5358 | -0.120 | [-0.244, +0.003] | inconclusive |
| position | BTN | 5443 | +0.401 | [+0.295, +0.503] | evidence_positive |
| position | CO | 3810 | +0.509 | [+0.329, +0.680] | evidence_positive |
| position | HJ | 2860 | +0.366 | [+0.189, +0.549] | evidence_positive |
| position | SB | 4479 | +0.006 | [-0.128, +0.127] | inconclusive |
| position | UTG | 1332 | +0.203 | [-0.105, +0.542] | inconclusive |
| stack_bucket | 10-20bb | 7067 | +0.201 | [+0.138, +0.258] | evidence_positive |
| stack_bucket | 20-40bb | 7310 | +0.313 | [+0.226, +0.400] | evidence_positive |
| stack_bucket | 40bb+ | 4439 | +0.143 | [-0.146, +0.406] | inconclusive |
| stack_bucket | <10bb | 4466 | +0.106 | [+0.044, +0.161] | evidence_positive |

### hybrid_v2_adaptive

| dimensão | faixa | mãos | bb/mão | IC 95% | flag |
|---|---|---|---|---|---|
| phase | early | 3112 | -0.027 | [-0.379, +0.300] | inconclusive |
| phase | final_table | 4041 | +0.248 | [+0.161, +0.333] | evidence_positive |
| phase | middle | 12906 | +0.274 | [+0.197, +0.350] | evidence_positive |
| position | BB | 4446 | -0.080 | [-0.287, +0.125] | inconclusive |
| position | BTN | 4477 | +0.438 | [+0.297, +0.574] | evidence_positive |
| position | CO | 3384 | +0.437 | [+0.278, +0.614] | evidence_positive |
| position | HJ | 2583 | +0.320 | [+0.135, +0.484] | evidence_positive |
| position | SB | 3840 | +0.107 | [-0.063, +0.274] | inconclusive |
| position | UTG | 1329 | +0.107 | [-0.203, +0.407] | inconclusive |
| stack_bucket | 10-20bb | 5997 | +0.249 | [+0.160, +0.332] | evidence_positive |
| stack_bucket | 20-40bb | 7374 | +0.332 | [+0.229, +0.430] | evidence_positive |
| stack_bucket | 40bb+ | 4413 | +0.042 | [-0.237, +0.286] | inconclusive |
| stack_bucket | <10bb | 2275 | +0.148 | [+0.030, +0.257] | evidence_positive |

### pushfold_p7

| dimensão | faixa | mãos | bb/mão | IC 95% | flag |
|---|---|---|---|---|---|
| phase | early | 3116 | -0.442 | [-0.799, -0.114] | evidence_negative |
| phase | final_table | 2702 | +0.079 | [-0.032, +0.180] | inconclusive |
| phase | middle | 11479 | -0.026 | [-0.095, +0.053] | inconclusive |
| position | BB | 3705 | -0.396 | [-0.688, -0.124] | evidence_negative |
| position | BTN | 3616 | +0.113 | [-0.032, +0.237] | inconclusive |
| position | CO | 2998 | -0.042 | [-0.138, +0.045] | inconclusive |
| position | HJ | 2446 | +0.050 | [-0.076, +0.177] | inconclusive |
| position | SB | 3244 | -0.156 | [-0.338, +0.021] | inconclusive |
| position | UTG | 1288 | +0.087 | [-0.148, +0.334] | inconclusive |
| stack_bucket | 10-20bb | 5177 | -0.069 | [-0.171, +0.024] | inconclusive |
| stack_bucket | 20-40bb | 5121 | -0.032 | [-0.176, +0.110] | inconclusive |
| stack_bucket | 40bb+ | 3881 | -0.371 | [-0.700, -0.111] | evidence_negative |
| stack_bucket | <10bb | 3118 | +0.162 | [+0.071, +0.249] | evidence_positive |

## Qualidade de decisão (baseline, só informação disponível na decisão)

| candidato | decisões | calls | margem média equity−pot odds (IC) | calls abaixo das pot odds | mix de ações | base da equity |
|---|---|---|---|---|---|---|

## Sorte de all-in (baseline): resultado − EV de all-in, calculado offline após a mão

| candidato | mãos all-in | sorte total (bb) | sorte média/mão (IC) | EV all-in total (bb) |
|---|---|---|---|---|
| hybrid_v1 | 2044 | +679.9 | +0.33 [-0.08, +0.76] | +370.8 |
| hybrid_v1_bluffcatch | 1925 | +228.7 | +0.12 [-0.32, +0.56] | -60.1 |
| lag | 1893 | -386.3 | -0.20 [-0.67, +0.26] | +593.9 |
| hybrid_v2_adaptive | 1938 | +313.4 | +0.16 [-0.31, +0.64] | -276.7 |
| pushfold_p7 | 1123 | -5.7 | -0.01 [-0.61, +0.60] | -380.8 |
