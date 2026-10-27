# P7 — tabelas de resultados (gerado automaticamente por scripts/render_p7_tables.py)

Evaluation run: `1246355d-dd9b-59ce-a2ff-871085ab32a9` · unidades: simulated buy-in units (SIM); no real money

ROI = lucro líquido / custo (buy-in 100 + taxa 10). IC 95% bootstrap sobre torneios. Referência de campo igual: ROI esperado = −9,1% (só a taxa).

## Cenário `baseline`

| candidato | n | ROI | IC 95% | veredito | ITM | vitórias | drawdown máx (SIM) | reentradas |
|---|---|---|---|---|---|---|---|---|
| random | 400 | -45.7% | [-59.6%, -31.5%] | evidence_negative | 13.0% | 26 | 21920 | 0 |
| heuristic | 400 | -39.2% | [-50.6%, -28.3%] | evidence_negative | 23.8% | 0 | 17350 | 0 |
| equity | 400 | -39.2% | [-53.4%, -24.7%] | evidence_negative | 16.0% | 24 | 17410 | 0 |
| equity_icm_adaptive | 400 | -25.3% | [-39.2%, -10.0%] | evidence_negative | 22.0% | 16 | 13440 | 0 |
| pushfold_policy | 400 | -10.5% | [-27.2%, +7.2%] | inconclusive | 23.0% | 41 | 8240 | 0 |

Diferença pareada vs `heuristic` (lucro por torneio, em buy-ins de 110):

| candidato | média | IC 95% | n | veredito |
|---|---|---|---|---|
| random | -0.065 | [-0.243, +0.120] | 400 | inconclusive |
| equity | -0.000 | [-0.175, +0.183] | 400 | inconclusive |
| equity_icm_adaptive | +0.139 | [-0.022, +0.311] | 400 | inconclusive |
| pushfold_policy | +0.286 | [+0.101, +0.480] | 400 | evidence_positive |

## Cenário `field_lag`

| candidato | n | ROI | IC 95% | veredito | ITM | vitórias | drawdown máx (SIM) | reentradas |
|---|---|---|---|---|---|---|---|---|
| random | 120 | -84.5% | [-95.5%, -70.9%] | insufficient_sample | 5.0% | 1 | 11160 | 0 |
| heuristic | 120 | -58.2% | [-74.5%, -40.0%] | insufficient_sample | 15.8% | 0 | 7700 | 0 |
| equity | 120 | -62.7% | [-81.8%, -41.8%] | insufficient_sample | 11.7% | 3 | 8280 | 0 |
| equity_icm_adaptive | 120 | -52.7% | [-71.8%, -32.7%] | insufficient_sample | 16.7% | 2 | 7510 | 0 |
| pushfold_policy | 120 | -40.0% | [-63.6%, -12.7%] | insufficient_sample | 18.3% | 5 | 6070 | 0 |

Diferença pareada vs `heuristic` (lucro por torneio, em buy-ins de 110):

| candidato | média | IC 95% | n | veredito |
|---|---|---|---|---|
| random | -0.264 | [-0.482, -0.027] | 120 | insufficient_sample |
| equity | -0.045 | [-0.291, +0.200] | 120 | insufficient_sample |
| equity_icm_adaptive | +0.055 | [-0.236, +0.345] | 120 | insufficient_sample |
| pushfold_policy | +0.182 | [-0.118, +0.491] | 120 | insufficient_sample |

## Cenário `field_nit`

| candidato | n | ROI | IC 95% | veredito | ITM | vitórias | drawdown máx (SIM) | reentradas |
|---|---|---|---|---|---|---|---|---|
| random | 120 | +211.8% | [+163.6%, +258.2%] | insufficient_sample | 57.5% | 68 | 770 | 0 |
| heuristic | 120 | +237.3% | [+195.5%, +277.3%] | insufficient_sample | 73.3% | 59 | 550 | 0 |
| equity | 120 | +167.3% | [+119.1%, +216.4%] | insufficient_sample | 50.0% | 57 | 440 | 0 |
| equity_icm_adaptive | 120 | +207.3% | [+158.2%, +254.5%] | insufficient_sample | 56.7% | 67 | 440 | 0 |
| pushfold_policy | 120 | +298.2% | [+255.5%, +336.4%] | insufficient_sample | 74.2% | 86 | 220 | 0 |

Diferença pareada vs `heuristic` (lucro por torneio, em buy-ins de 110):

| candidato | média | IC 95% | n | veredito |
|---|---|---|---|---|
| random | -0.255 | [-0.882, +0.345] | 120 | insufficient_sample |
| equity | -0.700 | [-1.336, -0.073] | 120 | insufficient_sample |
| equity_icm_adaptive | -0.300 | [-0.909, +0.300] | 120 | insufficient_sample |
| pushfold_policy | +0.609 | [+0.018, +1.191] | 120 | insufficient_sample |

## Cenário `field_station`

| candidato | n | ROI | IC 95% | veredito | ITM | vitórias | drawdown máx (SIM) | reentradas |
|---|---|---|---|---|---|---|---|---|
| random | 120 | -80.0% | [-93.6%, -62.7%] | insufficient_sample | 5.8% | 2 | 10560 | 0 |
| heuristic | 120 | +51.8% | [+26.4%, +76.4%] | insufficient_sample | 56.7% | 1 | 910 | 0 |
| equity | 120 | +60.9% | [+25.5%, +97.3%] | insufficient_sample | 44.2% | 20 | 1270 | 0 |
| equity_icm_adaptive | 120 | +68.2% | [+32.7%, +104.5%] | insufficient_sample | 46.7% | 19 | 790 | 0 |
| pushfold_policy | 120 | +89.1% | [+47.3%, +130.0%] | insufficient_sample | 45.0% | 31 | 770 | 0 |

Diferença pareada vs `heuristic` (lucro por torneio, em buy-ins de 110):

| candidato | média | IC 95% | n | veredito |
|---|---|---|---|---|
| random | -1.318 | [-1.618, -1.000] | 120 | insufficient_sample |
| equity | +0.091 | [-0.318, +0.491] | 120 | insufficient_sample |
| equity_icm_adaptive | +0.164 | [-0.227, +0.573] | 120 | insufficient_sample |
| pushfold_policy | +0.373 | [-0.118, +0.836] | 120 | insufficient_sample |

## Cenário `field_random`

| candidato | n | ROI | IC 95% | veredito | ITM | vitórias | drawdown máx (SIM) | reentradas |
|---|---|---|---|---|---|---|---|---|
| random | 60 | -32.7% | [-63.6%, +3.6%] | insufficient_sample | 20.0% | 1 | 2550 | 0 |
| heuristic | 60 | +223.6% | [+207.3%, +240.0%] | insufficient_sample | 98.3% | 2 | 110 | 0 |
| equity | 60 | +200.0% | [+145.5%, +256.4%] | insufficient_sample | 71.7% | 21 | 440 | 0 |
| equity_icm_adaptive | 60 | +161.8% | [+116.4%, +209.1%] | insufficient_sample | 73.3% | 9 | 220 | 0 |
| pushfold_policy | 60 | +152.7% | [+96.4%, +209.1%] | insufficient_sample | 63.3% | 16 | 440 | 0 |

Diferença pareada vs `heuristic` (lucro por torneio, em buy-ins de 110):

| candidato | média | IC 95% | n | veredito |
|---|---|---|---|---|
| random | -2.564 | [-2.964, -2.127] | 60 | insufficient_sample |
| equity | -0.236 | [-0.745, +0.273] | 60 | insufficient_sample |
| equity_icm_adaptive | -0.618 | [-1.073, -0.182] | 60 | insufficient_sample |
| pushfold_policy | -0.709 | [-1.255, -0.182] | 60 | insufficient_sample |

## Cenário `turbo_short`

| candidato | n | ROI | IC 95% | veredito | ITM | vitórias | drawdown máx (SIM) | reentradas |
|---|---|---|---|---|---|---|---|---|
| random | 120 | -36.4% | [-63.6%, -6.4%] | insufficient_sample | 15.0% | 9 | 5010 | 0 |
| heuristic | 120 | -45.5% | [-64.5%, -25.5%] | insufficient_sample | 20.0% | 0 | 6020 | 0 |
| equity | 120 | -14.5% | [-45.5%, +20.0%] | insufficient_sample | 20.0% | 14 | 3380 | 0 |
| equity_icm_adaptive | 120 | -24.5% | [-53.6%, +4.5%] | insufficient_sample | 19.2% | 10 | 3860 | 0 |
| pushfold_policy | 120 | +14.5% | [-19.1%, +50.0%] | insufficient_sample | 27.5% | 18 | 2060 | 0 |

Diferença pareada vs `heuristic` (lucro por torneio, em buy-ins de 110):

| candidato | média | IC 95% | n | veredito |
|---|---|---|---|---|
| random | +0.091 | [-0.236, +0.409] | 120 | insufficient_sample |
| equity | +0.309 | [-0.055, +0.691] | 120 | insufficient_sample |
| equity_icm_adaptive | +0.209 | [-0.127, +0.582] | 120 | insufficient_sample |
| pushfold_policy | +0.600 | [+0.209, +1.009] | 120 | insufficient_sample |

## Cenário `reentry`

| candidato | n | ROI | IC 95% | veredito | ITM | vitórias | drawdown máx (SIM) | reentradas |
|---|---|---|---|---|---|---|---|---|
| random | 120 | -58.9% | [-76.7%, -38.3%] | insufficient_sample | 15.0% | 11 | 15420 | 118 |
| heuristic | 120 | -32.7% | [-54.1%, -8.9%] | insufficient_sample | 24.2% | 0 | 4960 | 10 |
| equity | 120 | -23.7% | [-50.3%, +5.7%] | insufficient_sample | 21.7% | 10 | 4970 | 41 |
| equity_icm_adaptive | 120 | -11.3% | [-37.5%, +17.6%] | insufficient_sample | 29.2% | 9 | 3110 | 41 |
| pushfold_policy | 120 | -37.0% | [-62.1%, -8.1%] | insufficient_sample | 18.3% | 10 | 7660 | 35 |

Diferença pareada vs `heuristic` (lucro por torneio, em buy-ins de 110):

| candidato | média | IC 95% | n | veredito |
|---|---|---|---|---|
| random | -0.814 | [-1.242, -0.358] | 120 | insufficient_sample |
| equity | +0.036 | [-0.371, +0.474] | 120 | insufficient_sample |
| equity_icm_adaptive | +0.202 | [-0.210, +0.625] | 120 | insufficient_sample |
| pushfold_policy | -0.124 | [-0.530, +0.303] | 120 | insufficient_sample |

## Cenário `top_heavy`

| candidato | n | ROI | IC 95% | veredito | ITM | vitórias | drawdown máx (SIM) | reentradas |
|---|---|---|---|---|---|---|---|---|
| random | 120 | -54.5% | [-81.4%, -24.1%] | insufficient_sample | 8.3% | 5 | 7960 | 0 |
| heuristic | 120 | -45.9% | [-68.2%, -20.5%] | insufficient_sample | 14.2% | 0 | 6060 | 0 |
| equity | 120 | -30.5% | [-63.2%, +5.5%] | insufficient_sample | 12.5% | 8 | 5190 | 0 |
| equity_icm_adaptive | 120 | -26.8% | [-59.1%, +9.1%] | insufficient_sample | 14.2% | 7 | 4690 | 0 |
| pushfold_policy | 120 | +19.5% | [-22.3%, +63.2%] | insufficient_sample | 19.2% | 17 | 1870 | 0 |

Diferença pareada vs `heuristic` (lucro por torneio, em buy-ins de 110):

| candidato | média | IC 95% | n | veredito |
|---|---|---|---|---|
| random | -0.086 | [-0.445, +0.286] | 120 | insufficient_sample |
| equity | +0.155 | [-0.209, +0.568] | 120 | insufficient_sample |
| equity_icm_adaptive | +0.191 | [-0.209, +0.618] | 120 | insufficient_sample |
| pushfold_policy | +0.655 | [+0.168, +1.218] | 120 | insufficient_sample |

## Amostras progressivas (cenário baseline)

| candidato | n | ROI | IC 95% | veredito |
|---|---|---|---|---|
| random | 25 | +35.3% | [-43.3%, +122.5%] | insufficient_sample |
| random | 50 | -8.4% | [-52.0%, +41.8%] | insufficient_sample |
| random | 100 | -21.5% | [-54.2%, +14.5%] | insufficient_sample |
| random | 200 | -40.5% | [-62.4%, -18.2%] | evidence_negative |
| random | 400 | -45.7% | [-59.6%, -31.5%] | evidence_negative |
| heuristic | 25 | -43.3% | [-86.9%, +4.7%] | insufficient_sample |
| heuristic | 50 | -25.8% | [-60.7%, +9.1%] | insufficient_sample |
| heuristic | 100 | -33.5% | [-57.5%, -9.5%] | insufficient_sample |
| heuristic | 200 | -36.2% | [-52.0%, -20.4%] | evidence_negative |
| heuristic | 400 | -39.2% | [-50.6%, -28.3%] | evidence_negative |
| equity | 25 | -21.5% | [-78.2%, +57.1%] | insufficient_sample |
| equity | 50 | -17.1% | [-62.9%, +33.1%] | insufficient_sample |
| equity | 100 | -34.5% | [-65.1%, -1.8%] | insufficient_sample |
| equity | 200 | -32.4% | [-53.1%, -10.0%] | evidence_negative |
| equity | 400 | -39.2% | [-53.4%, -24.7%] | evidence_negative |
| equity_icm_adaptive | 25 | -25.8% | [-78.2%, +39.6%] | insufficient_sample |
| equity_icm_adaptive | 50 | -23.6% | [-60.7%, +15.6%] | insufficient_sample |
| equity_icm_adaptive | 100 | -7.3% | [-37.8%, +24.4%] | insufficient_sample |
| equity_icm_adaptive | 200 | -34.5% | [-53.1%, -14.9%] | evidence_negative |
| equity_icm_adaptive | 400 | -25.3% | [-39.2%, -10.0%] | evidence_negative |
| pushfold_policy | 25 | +39.6% | [-38.9%, +122.5%] | insufficient_sample |
| pushfold_policy | 50 | +24.4% | [-32.4%, +85.5%] | insufficient_sample |
| pushfold_policy | 100 | +22.2% | [-18.2%, +63.6%] | insufficient_sample |
| pushfold_policy | 200 | -1.3% | [-25.8%, +24.9%] | inconclusive |
| pushfold_policy | 400 | -10.5% | [-27.2%, +7.2%] | inconclusive |

## Recortes por mão (baseline): bb/mão com IC por cluster (torneios)

### random

| dimensão | faixa | mãos | bb/mão | IC 95% | flag |
|---|---|---|---|---|---|
| phase | early | 2863 | -2.171 | [-2.807, -1.548] | evidence_negative |
| phase | final_table | 1422 | +0.046 | [-0.210, +0.284] | inconclusive |
| phase | middle | 6509 | -0.124 | [-0.297, +0.026] | inconclusive |
| position | BB | 2256 | -0.610 | [-1.037, -0.208] | evidence_negative |
| position | BTN | 2257 | -0.677 | [-1.110, -0.290] | evidence_negative |
| position | CO | 1902 | -0.434 | [-0.985, +0.059] | inconclusive |
| position | HJ | 1468 | -0.649 | [-1.134, -0.159] | evidence_negative |
| position | SB | 2077 | -0.737 | [-1.231, -0.312] | evidence_negative |
| position | UTG | 834 | -0.889 | [-1.748, -0.077] | evidence_negative |
| stack_bucket | 10-20bb | 1986 | +0.138 | [-0.109, +0.365] | inconclusive |
| stack_bucket | 20-40bb | 3469 | -0.167 | [-0.438, +0.067] | inconclusive |
| stack_bucket | 40bb+ | 3710 | -1.835 | [-2.436, -1.301] | evidence_negative |
| stack_bucket | <10bb | 1629 | +0.098 | [-0.042, +0.212] | inconclusive |

### equity

| dimensão | faixa | mãos | bb/mão | IC 95% | flag |
|---|---|---|---|---|---|
| phase | early | 3126 | +0.085 | [-0.269, +0.439] | inconclusive |
| phase | final_table | 2211 | -0.143 | [-0.281, -0.015] | evidence_negative |
| phase | middle | 11172 | -0.066 | [-0.155, +0.011] | inconclusive |
| position | BB | 3452 | -0.135 | [-0.446, +0.140] | inconclusive |
| position | BTN | 3345 | +0.021 | [-0.104, +0.143] | inconclusive |
| position | CO | 2960 | +0.082 | [-0.054, +0.217] | inconclusive |
| position | HJ | 2391 | +0.153 | [-0.043, +0.362] | inconclusive |
| position | SB | 3145 | -0.356 | [-0.573, -0.169] | evidence_negative |
| position | UTG | 1216 | +0.100 | [-0.115, +0.325] | inconclusive |
| stack_bucket | 10-20bb | 4459 | -0.123 | [-0.230, -0.019] | evidence_negative |
| stack_bucket | 20-40bb | 5281 | -0.112 | [-0.256, +0.024] | inconclusive |
| stack_bucket | 40bb+ | 4188 | +0.086 | [-0.186, +0.341] | inconclusive |
| stack_bucket | <10bb | 2581 | -0.002 | [-0.120, +0.101] | inconclusive |

### pushfold_policy

| dimensão | faixa | mãos | bb/mão | IC 95% | flag |
|---|---|---|---|---|---|
| phase | early | 3133 | -0.041 | [-0.343, +0.285] | inconclusive |
| phase | final_table | 3020 | -0.025 | [-0.134, +0.065] | inconclusive |
| phase | middle | 12171 | +0.019 | [-0.057, +0.094] | inconclusive |
| position | BB | 3939 | -0.063 | [-0.326, +0.223] | inconclusive |
| position | BTN | 3875 | +0.071 | [-0.035, +0.182] | inconclusive |
| position | CO | 3223 | +0.098 | [-0.003, +0.209] | inconclusive |
| position | HJ | 2576 | +0.105 | [-0.028, +0.238] | inconclusive |
| position | SB | 3522 | -0.124 | [-0.287, +0.029] | inconclusive |
| position | UTG | 1189 | -0.127 | [-0.395, +0.131] | inconclusive |
| stack_bucket | 10-20bb | 5574 | +0.039 | [-0.044, +0.121] | inconclusive |
| stack_bucket | 20-40bb | 5557 | -0.073 | [-0.216, +0.056] | inconclusive |
| stack_bucket | 40bb+ | 4047 | -0.074 | [-0.326, +0.177] | inconclusive |
| stack_bucket | <10bb | 3146 | +0.165 | [+0.074, +0.251] | evidence_positive |

### heuristic

| dimensão | faixa | mãos | bb/mão | IC 95% | flag |
|---|---|---|---|---|---|
| phase | early | 3170 | -0.217 | [-0.415, -0.039] | evidence_negative |
| phase | final_table | 3695 | -0.175 | [-0.204, -0.146] | evidence_negative |
| phase | middle | 16835 | -0.048 | [-0.080, -0.017] | evidence_negative |
| position | BB | 4901 | -0.320 | [-0.392, -0.253] | evidence_negative |
| position | BTN | 4907 | +0.085 | [+0.007, +0.157] | evidence_positive |
| position | CO | 4361 | +0.105 | [+0.025, +0.180] | evidence_positive |
| position | HJ | 3314 | +0.095 | [+0.009, +0.184] | evidence_positive |
| position | SB | 4764 | -0.376 | [-0.440, -0.313] | evidence_negative |
| position | UTG | 1453 | +0.011 | [-0.175, +0.183] | inconclusive |
| stack_bucket | 10-20bb | 5983 | -0.080 | [-0.118, -0.041] | evidence_negative |
| stack_bucket | 20-40bb | 4725 | -0.001 | [-0.083, +0.078] | inconclusive |
| stack_bucket | 40bb+ | 3467 | -0.193 | [-0.366, -0.028] | evidence_negative |
| stack_bucket | <10bb | 9525 | -0.105 | [-0.124, -0.086] | evidence_negative |

### equity_icm_adaptive

| dimensão | faixa | mãos | bb/mão | IC 95% | flag |
|---|---|---|---|---|---|
| phase | early | 3126 | +0.085 | [-0.263, +0.432] | inconclusive |
| phase | final_table | 3215 | -0.127 | [-0.196, -0.053] | evidence_negative |
| phase | middle | 11257 | -0.059 | [-0.141, +0.021] | inconclusive |
| position | BB | 3884 | -0.131 | [-0.392, +0.129] | inconclusive |
| position | BTN | 3785 | -0.012 | [-0.127, +0.097] | inconclusive |
| position | CO | 3028 | +0.103 | [-0.021, +0.229] | inconclusive |
| position | HJ | 2399 | +0.163 | [-0.023, +0.387] | inconclusive |
| position | SB | 3298 | -0.330 | [-0.530, -0.136] | evidence_negative |
| position | UTG | 1204 | +0.108 | [-0.133, +0.338] | inconclusive |
| stack_bucket | 10-20bb | 4435 | -0.105 | [-0.212, -0.006] | evidence_negative |
| stack_bucket | 20-40bb | 5323 | -0.117 | [-0.274, +0.012] | inconclusive |
| stack_bucket | 40bb+ | 4178 | +0.080 | [-0.179, +0.337] | inconclusive |
| stack_bucket | <10bb | 3662 | -0.015 | [-0.083, +0.048] | inconclusive |

## Qualidade de decisão (baseline, só informação disponível na decisão)

| candidato | decisões | calls | margem média equity−pot odds (IC) | calls abaixo das pot odds | mix de ações | base da equity |
|---|---|---|---|---|---|---|
| random | 16045 | 4356 | +0.043 [+0.037, +0.050] | 0.4945 | bet 11%, call 27%, check 12%, fold 28%, raise 23% | {'vs_uniform_random_hands_mc100': 16045} |
| equity | 24957 | 5416 | +0.206 [+0.202, +0.210] | 0.0 | bet 4%, call 22%, check 23%, fold 46%, raise 5% | {'agent_estimate': 24957} |
| pushfold_policy | 23871 | 4087 | +0.184 [+0.180, +0.188] | 0.0 | bet 4%, call 17%, check 17%, fold 54%, raise 8% | {'agent_estimate': 22079, 'vs_uniform_random_hands_mc100': 1792} |
| heuristic | 22926 | 507 | +0.322 [+0.302, +0.340] | 0.0927 | bet 1%, call 2%, check 3%, fold 85%, raise 8% | {'vs_uniform_random_hands_mc100': 22926} |
| equity_icm_adaptive | 26275 | 5697 | +0.209 [+0.205, +0.213] | 0.0002 | bet 4%, call 22%, check 23%, fold 46%, raise 5% | {'agent_estimate': 26275} |

## Sorte de all-in (baseline): resultado − EV de all-in, calculado offline após a mão

| candidato | mãos all-in | sorte total (bb) | sorte média/mão (IC) | EV all-in total (bb) |
|---|---|---|---|---|
| random | 1458 | -432.7 | -0.30 [-1.10, +0.61] | -6966.5 |
| equity | 1043 | +108.5 | +0.10 [-0.53, +0.77] | -55.7 |
| pushfold_policy | 1187 | +313.1 | +0.26 [-0.23, +0.76] | +417.7 |
| heuristic | 1036 | -276.2 | -0.27 [-0.75, +0.17] | +645.2 |
| equity_icm_adaptive | 1163 | +215.3 | +0.19 [-0.41, +0.78] | +129.1 |
