# P7c: steal e re-steal (tabelas geradas por `scripts/render_p7c_steal.py`)

Fonte: `artifacts/p7c/steal_analysis.json`, calculado sobre `final.db` (somente leitura).
Steal = primeiro a entrar com raise em CO, BTN ou SB. Unidade: bb por mão do herói.
IC 95% por bootstrap de cluster (torneio). Só informação pública foi usada para classificar o defensor.

## Cenário `adaptive_only`

| candidato | oportunidades | taxa de steal | ganha sem showdown | lucro por steal (bb) | EV por oportunidade (bb) | resposta ao re-steal | taxa 1ª/2ª metade |
|---|---|---|---|---|---|---|---|
| hybrid_v1 | 3499 | 48.3% | 71.5% | +1.20 [+1.01; +1.38] (n=182) | +0.58 | call 27%, fold 71%, raise 1% (70) | 42% / 54% |
| hybrid_v2_adaptive | 3373 | 48.6% | 73.0% | +1.17 [+0.96; +1.38] (n=180) | +0.57 | call 60%, fold 39%, raise 1% (77) | 41% / 56% |
| hybrid_v1_bluffcatch | 3421 | 48.8% | 71.8% | +1.10 [+0.90; +1.29] (n=182) | +0.54 | call 29%, fold 70%, raise 1% (83) | 42% / 55% |
| lag | 4088 | 50.1% | 71.7% | +0.98 [+0.84; +1.13] (n=192) | +0.49 | call 13%, fold 78%, raise 10% (126) | 55% / 46% |
| pushfold_p7 | 2761 | 19.8% | 79.9% | +1.31 [+0.85; +1.71] (n=138) | +0.26 | call 100% (10) | 14% / 28% |

**hybrid_v1: lucro por steal por dimensão (bb)**

| dimensão | grupo | estimativa [IC 95%] |
|---|---|---|
| position | BTN | +1.06 [+0.84; +1.26] (n=156) |
| position | CO | +1.16 [+0.67; +1.54] (n=163) |
| position | SB | +1.46 [+1.16; +1.75] (n=148) |
| eff_stack | 10-20bb | +1.35 [+1.00; +1.66] (n=138) |
| eff_stack | 20-40bb | +1.33 [+0.96; +1.74] (n=130) |
| eff_stack | 40bb+ | +0.30 [-1.02; +1.29] (n=97) |
| eff_stack | <10bb | +1.22 [+1.02; +1.40] (n=135) |
| ante | ante | +1.31 [+1.13; +1.48] (n=162) |
| ante | no_ante | +0.69 [-0.02; +1.25] (n=142) |
| defender_class | adaptive | +1.20 [+0.99; +1.38] (n=182) |
| open_size | 2.5-5bb | +1.03 [+0.26; +1.77] (n=25) |
| open_size | <=2.5bb | +0.99 [+0.67; +1.28] (n=173) |
| open_size | shove/large | +1.36 [+1.14; +1.57] (n=143) |

**hybrid_v2_adaptive: lucro por steal por dimensão (bb)**

| dimensão | grupo | estimativa [IC 95%] |
|---|---|---|
| position | BTN | +1.03 [+0.70; +1.34] (n=156) |
| position | CO | +1.28 [+0.73; +1.83] (n=159) |
| position | SB | +1.28 [+0.99; +1.58] (n=135) |
| eff_stack | 10-20bb | +1.45 [+1.07; +1.80] (n=138) |
| eff_stack | 20-40bb | +1.12 [+0.47; +1.76] (n=125) |
| eff_stack | 40bb+ | +0.06 [-1.60; +1.69] (n=95) |
| eff_stack | <10bb | +1.22 [+1.04; +1.41] (n=119) |
| ante | ante | +1.32 [+1.11; +1.47] (n=153) |
| ante | no_ante | +0.49 [-0.44; +1.35] (n=141) |
| defender_class | adaptive | +1.17 [+0.95; +1.38] (n=180) |
| open_size | 2.5-5bb | +1.10 [+0.56; +1.53] (n=27) |
| open_size | <=2.5bb | +1.09 [+0.58; +1.53] (n=171) |
| open_size | shove/large | +1.24 [+1.03; +1.43] (n=133) |

## Cenário `baseline_mixed`

| candidato | oportunidades | taxa de steal | ganha sem showdown | lucro por steal (bb) | EV por oportunidade (bb) | resposta ao re-steal | taxa 1ª/2ª metade |
|---|---|---|---|---|---|---|---|
| hybrid_v1 | 3925 | 48.6% | 72.9% | +1.28 [+1.07; +1.48] (n=180) | +0.62 | call 12%, fold 78%, raise 10% (74) | 44% / 53% |
| hybrid_v2_adaptive | 3752 | 48.0% | 72.5% | +1.36 [+1.11; +1.60] (n=178) | +0.65 | call 43%, fold 46%, raise 11% (65) | 42% / 54% |
| hybrid_v1_bluffcatch | 3656 | 49.0% | 72.3% | +1.19 [+0.95; +1.40] (n=177) | +0.58 | call 10%, fold 80%, raise 10% (71) | 43% / 55% |
| lag | 4753 | 48.2% | 72.4% | +1.19 [+1.01; +1.37] (n=184) | +0.57 | call 15%, fold 78%, raise 7% (128) | 55% / 44% |
| pushfold_p7 | 3008 | 20.3% | 81.8% | +1.19 [+0.75; +1.58] (n=136) | +0.24 | call 71%, raise 29% (7) | 12% / 30% |

**hybrid_v1: lucro por steal por dimensão (bb)**

| dimensão | grupo | estimativa [IC 95%] |
|---|---|---|
| position | BTN | +1.30 [+1.03; +1.56] (n=168) |
| position | CO | +1.51 [+0.97; +1.99] (n=156) |
| position | SB | +1.05 [+0.73; +1.37] (n=152) |
| eff_stack | 10-20bb | +1.26 [+0.98; +1.53] (n=141) |
| eff_stack | 20-40bb | +1.77 [+1.15; +2.40] (n=143) |
| eff_stack | 40bb+ | +1.22 [-0.01; +2.42] (n=114) |
| eff_stack | <10bb | +1.09 [+0.92; +1.24] (n=123) |
| ante | ante | +1.21 [+1.03; +1.40] (n=157) |
| ante | no_ante | +1.61 [+0.92; +2.28] (n=161) |
| defender_class | aggressive | +1.00 [+0.69; +1.29] (n=143) |
| defender_class | static_tight | +1.53 [+1.24; +1.81] (n=158) |
| open_size | 2.5-5bb | +0.86 [-0.07; +1.59] (n=22) |
| open_size | <=2.5bb | +1.50 [+1.11; +1.83] (n=178) |
| open_size | shove/large | +1.11 [+0.93; +1.29] (n=142) |

**hybrid_v2_adaptive: lucro por steal por dimensão (bb)**

| dimensão | grupo | estimativa [IC 95%] |
|---|---|---|
| position | BTN | +1.50 [+1.20; +1.77] (n=162) |
| position | CO | +1.39 [+0.88; +1.96] (n=154) |
| position | SB | +1.12 [+0.73; +1.46] (n=145) |
| eff_stack | 10-20bb | +1.15 [+0.77; +1.48] (n=140) |
| eff_stack | 20-40bb | +1.98 [+1.31; +2.69] (n=132) |
| eff_stack | 40bb+ | +1.64 [+0.12; +3.09] (n=112) |
| eff_stack | <10bb | +1.19 [+1.01; +1.36] (n=121) |
| ante | ante | +1.26 [+1.03; +1.46] (n=150) |
| ante | no_ante | +1.81 [+0.91; +2.54] (n=161) |
| defender_class | aggressive | +1.15 [+0.83; +1.45] (n=144) |
| defender_class | static_tight | +1.53 [+1.23; +1.84] (n=153) |
| open_size | 2.5-5bb | +0.84 [-0.02; +1.73] (n=25) |
| open_size | <=2.5bb | +1.54 [+1.03; +1.99] (n=173) |
| open_size | shove/large | +1.24 [+1.05; +1.41] (n=137) |

## Cenário `bluff_heavy`

| candidato | oportunidades | taxa de steal | ganha sem showdown | lucro por steal (bb) | EV por oportunidade (bb) | resposta ao re-steal | taxa 1ª/2ª metade |
|---|---|---|---|---|---|---|---|
| hybrid_v1 | 2549 | 45.5% | 65.2% | +0.90 [+0.59; +1.21] (n=176) | +0.41 | call 27%, fold 67%, raise 6% (104) | 40% / 51% |
| hybrid_v2_adaptive | 2166 | 45.0% | 64.6% | +0.96 [+0.54; +1.36] (n=165) | +0.43 | call 49%, fold 44%, raise 7% (84) | 40% / 51% |
| hybrid_v1_bluffcatch | 2357 | 45.9% | 64.8% | +0.98 [+0.61; +1.31] (n=169) | +0.45 | call 17%, fold 76%, raise 8% (90) | 40% / 52% |
| lag | 3062 | 50.8% | 62.6% | +0.92 [+0.66; +1.19] (n=180) | +0.47 | call 18%, fold 70%, raise 12% (145) | 55% / 47% |
| pushfold_p7 | 1972 | 18.8% | 73.2% | +1.30 [+0.46; +2.25] (n=112) | +0.24 | call 93%, raise 7% (14) | 13% / 27% |

**hybrid_v1: lucro por steal por dimensão (bb)**

| dimensão | grupo | estimativa [IC 95%] |
|---|---|---|
| position | BTN | +0.97 [+0.52; +1.46] (n=139) |
| position | CO | +0.80 [+0.15; +1.45] (n=159) |
| position | SB | +0.93 [+0.37; +1.44] (n=114) |
| eff_stack | 10-20bb | +0.82 [+0.39; +1.22] (n=135) |
| eff_stack | 20-40bb | +1.23 [+0.48; +1.99] (n=111) |
| eff_stack | 40bb+ | +0.29 [-1.68; +2.80] (n=84) |
| eff_stack | <10bb | +0.95 [+0.64; +1.24] (n=103) |
| ante | ante | +1.02 [+0.76; +1.26] (n=154) |
| ante | no_ante | +0.41 [-0.71; +1.43] (n=128) |
| defender_class | aggressive | +0.90 [+0.58; +1.18] (n=176) |
| open_size | 2.5-5bb | +1.26 [+0.44; +1.91] (n=24) |
| open_size | <=2.5bb | +0.86 [+0.31; +1.42] (n=169) |
| open_size | shove/large | +0.92 [+0.59; +1.18] (n=125) |

**hybrid_v2_adaptive: lucro por steal por dimensão (bb)**

| dimensão | grupo | estimativa [IC 95%] |
|---|---|---|
| position | BTN | +0.98 [+0.37; +1.57] (n=120) |
| position | CO | +0.96 [-0.02; +1.90] (n=148) |
| position | SB | +0.94 [+0.23; +1.54] (n=104) |
| eff_stack | 10-20bb | +0.89 [+0.19; +1.55] (n=103) |
| eff_stack | 20-40bb | +1.06 [-0.18; +2.27] (n=99) |
| eff_stack | 40bb+ | +0.36 [-1.86; +2.61] (n=84) |
| eff_stack | <10bb | +1.17 [+0.80; +1.45] (n=97) |
| ante | ante | +1.16 [+0.80; +1.49] (n=125) |
| ante | no_ante | +0.25 [-1.12; +1.64] (n=126) |
| defender_class | aggressive | +0.96 [+0.52; +1.33] (n=165) |
| open_size | 2.5-5bb | +1.16 [+0.36; +1.97] (n=24) |
| open_size | <=2.5bb | +1.00 [+0.19; +1.73] (n=159) |
| open_size | shove/large | +0.91 [+0.46; +1.26] (n=103) |

## Cenário `robust_mix`

| candidato | oportunidades | taxa de steal | ganha sem showdown | lucro por steal (bb) | EV por oportunidade (bb) | resposta ao re-steal | taxa 1ª/2ª metade |
|---|---|---|---|---|---|---|---|
| hybrid_v1 | 8208 | 49.1% | 73.8% | +1.26 [+1.14; +1.38] (n=377) | +0.62 | call 24%, fold 71%, raise 4% (157) | 42% / 55% |
| hybrid_v2_adaptive | 7595 | 49.1% | 73.8% | +1.17 [+1.03; +1.32] (n=369) | +0.57 | call 54%, fold 43%, raise 3% (136) | 42% / 56% |
| hybrid_v1_bluffcatch | 7776 | 49.4% | 73.6% | +1.19 [+1.05; +1.31] (n=373) | +0.59 | call 24%, fold 73%, raise 3% (148) | 43% / 56% |
| lag | 9069 | 48.6% | 72.4% | +1.16 [+1.04; +1.28] (n=373) | +0.57 | call 9%, fold 80%, raise 11% (214) | 55% / 44% |
| pushfold_p7 | 6209 | 21.1% | 82.1% | +1.12 [+0.89; +1.34] (n=286) | +0.23 | call 90%, fold 5%, raise 5% (19) | 14% / 29% |

**hybrid_v1: lucro por steal por dimensão (bb)**

| dimensão | grupo | estimativa [IC 95%] |
|---|---|---|
| position | BTN | +1.27 [+1.07; +1.47] (n=333) |
| position | CO | +1.36 [+1.13; +1.60] (n=349) |
| position | SB | +1.15 [+0.99; +1.33] (n=313) |
| eff_stack | 10-20bb | +1.41 [+1.18; +1.63] (n=300) |
| eff_stack | 20-40bb | +1.47 [+1.08; +1.83] (n=268) |
| eff_stack | 40bb+ | +0.96 [+0.34; +1.59] (n=230) |
| eff_stack | <10bb | +1.14 [+1.02; +1.24] (n=294) |
| ante | ante | +1.27 [+1.14; +1.38] (n=336) |
| ante | no_ante | +1.20 [+0.81; +1.63] (n=321) |
| defender_class | adaptive | +1.25 [+1.04; +1.47] (n=246) |
| defender_class | aggressive | +1.29 [+1.13; +1.46] (n=306) |
| defender_class | static_tight | +1.22 [+0.96; +1.45] (n=235) |
| open_size | 2.5-5bb | +0.88 [+0.37; +1.33] (n=52) |
| open_size | <=2.5bb | +1.37 [+1.17; +1.59] (n=367) |
| open_size | shove/large | +1.19 [+1.06; +1.32] (n=310) |

**hybrid_v2_adaptive: lucro por steal por dimensão (bb)**

| dimensão | grupo | estimativa [IC 95%] |
|---|---|---|
| position | BTN | +1.27 [+1.04; +1.45] (n=315) |
| position | CO | +1.07 [+0.74; +1.36] (n=331) |
| position | SB | +1.12 [+0.94; +1.29] (n=298) |
| eff_stack | 10-20bb | +1.30 [+1.02; +1.59] (n=280) |
| eff_stack | 20-40bb | +1.61 [+1.10; +2.11] (n=256) |
| eff_stack | 40bb+ | +0.54 [-0.08; +1.24] (n=226) |
| eff_stack | <10bb | +1.05 [+0.92; +1.14] (n=276) |
| ante | ante | +1.24 [+1.08; +1.37] (n=318) |
| ante | no_ante | +0.85 [+0.44; +1.27] (n=317) |
| defender_class | adaptive | +1.08 [+0.81; +1.33] (n=229) |
| defender_class | aggressive | +1.15 [+0.94; +1.37] (n=293) |
| defender_class | static_tight | +1.31 [+1.05; +1.55] (n=223) |
| open_size | 2.5-5bb | +0.88 [+0.38; +1.25] (n=63) |
| open_size | <=2.5bb | +1.23 [+0.98; +1.47] (n=357) |
| open_size | shove/large | +1.14 [+1.00; +1.28] (n=288) |

## Cenário `selfplay_hybrid`

| candidato | oportunidades | taxa de steal | ganha sem showdown | lucro por steal (bb) | EV por oportunidade (bb) | resposta ao re-steal | taxa 1ª/2ª metade |
|---|---|---|---|---|---|---|---|
| hybrid_v1 | 1169 | 43.1% | 28.6% | +0.63 [-0.16; +1.39] (n=93) | +0.27 | call 14%, fold 84%, raise 2% (43) | 41% / 45% |
| hybrid_v2_adaptive | 1056 | 41.7% | 29.3% | +0.37 [-0.55; +1.24] (n=92) | +0.16 | call 29%, fold 66%, raise 6% (35) | 40% / 43% |
| hybrid_v1_bluffcatch | 1049 | 42.4% | 27.2% | +0.57 [-0.38; +1.39] (n=92) | +0.24 | call 8%, fold 86%, raise 5% (37) | 40% / 44% |
| lag | 1318 | 52.0% | 37.8% | +0.85 [+0.22; +1.49] (n=93) | +0.44 | call 16%, fold 82%, raise 2% (88) | 55% / 50% |
| pushfold_p7 | 949 | 13.3% | 55.6% | +0.68 [-1.17; +2.68] (n=60) | +0.09 | call 67%, raise 33% (3) | 9% / 19% |

**hybrid_v1: lucro por steal por dimensão (bb)**

| dimensão | grupo | estimativa [IC 95%] |
|---|---|---|
| position | BTN | +0.83 [-0.42; +2.11] (n=76) |
| position | CO | +1.01 [-0.29; +2.64] (n=65) |
| position | SB | -0.16 [-1.47; +1.02] (n=64) |
| eff_stack | 10-20bb | -0.24 [-1.33; +0.85] (n=64) |
| eff_stack | 20-40bb | +1.19 [-0.35; +2.73] (n=70) |
| eff_stack | 40bb+ | +1.13 [-1.51; +3.89] (n=51) |
| eff_stack | <10bb | +0.75 [-0.62; +2.03] (n=44) |
| ante | ante | +0.22 [-0.63; +0.93] (n=74) |
| ante | no_ante | +1.68 [-0.32; +3.86] (n=79) |
| defender_class | self_or_versions | +0.63 [-0.06; +1.38] (n=93) |
| open_size | 2.5-5bb | +1.36 [+0.00; +3.36] (n=10) |
| open_size | <=2.5bb | +0.90 [-0.22; +1.81] (n=90) |
| open_size | shove/large | -0.04 [-1.30; +1.18] (n=56) |

**hybrid_v2_adaptive: lucro por steal por dimensão (bb)**

| dimensão | grupo | estimativa [IC 95%] |
|---|---|---|
| position | BTN | +0.56 [-1.13; +2.21] (n=70) |
| position | CO | +1.03 [-0.75; +3.02] (n=69) |
| position | SB | -0.85 [-2.68; +0.95] (n=56) |
| eff_stack | 10-20bb | +0.63 [-0.62; +2.24] (n=58) |
| eff_stack | 20-40bb | +0.71 [-1.08; +2.39] (n=68) |
| eff_stack | 40bb+ | -0.57 [-3.69; +3.36] (n=50) |
| eff_stack | <10bb | +0.01 [-1.16; +1.28] (n=38) |
| ante | ante | +0.16 [-0.70; +1.13] (n=66) |
| ante | no_ante | +0.87 [-1.49; +3.38] (n=77) |
| defender_class | self_or_versions | +0.37 [-0.52; +1.23] (n=92) |
| open_size | 2.5-5bb | +0.53 [-2.01; +3.09] (n=10) |
| open_size | <=2.5bb | +0.50 [-0.82; +1.69] (n=89) |
| open_size | shove/large | +0.10 [-1.09; +1.19] (n=50) |

## Cenário `versions_mix`

| candidato | oportunidades | taxa de steal | ganha sem showdown | lucro por steal (bb) | EV por oportunidade (bb) | resposta ao re-steal | taxa 1ª/2ª metade |
|---|---|---|---|---|---|---|---|
| hybrid_v1 | 1567 | 45.1% | 27.2% | +1.34 [+0.43; +2.26] (n=96) | +0.61 | call 7%, fold 93% (27) | 44% / 46% |
| hybrid_v2_adaptive | 1466 | 43.0% | 24.0% | +0.99 [+0.14; +1.82] (n=95) | +0.43 | call 28%, fold 72% (25) | 43% / 43% |
| hybrid_v1_bluffcatch | 1525 | 45.2% | 26.0% | +1.19 [+0.40; +2.01] (n=95) | +0.54 | fold 100% (26) | 45% / 45% |
| lag | 1746 | 55.1% | 30.5% | +1.04 [+0.47; +1.59] (n=96) | +0.57 | call 25%, fold 68%, raise 7% (59) | 60% / 51% |
| pushfold_p7 | 1387 | 18.2% | 53.6% | +1.20 [+0.05; +2.36] (n=74) | +0.22 | call 100% (3) | 11% / 28% |

**hybrid_v1: lucro por steal por dimensão (bb)**

| dimensão | grupo | estimativa [IC 95%] |
|---|---|---|
| position | BTN | +2.30 [+0.98; +3.67] (n=87) |
| position | CO | +1.79 [+0.34; +3.41] (n=76) |
| position | SB | -0.58 [-2.26; +0.97] (n=82) |
| eff_stack | 10-20bb | -0.41 [-1.74; +0.88] (n=66) |
| eff_stack | 20-40bb | +1.03 [-0.22; +2.30] (n=80) |
| eff_stack | 40bb+ | +3.84 [+1.52; +5.86] (n=75) |
| eff_stack | <10bb | +0.96 [+0.07; +1.88] (n=56) |
| ante | ante | +0.93 [-0.04; +1.80] (n=76) |
| ante | no_ante | +2.14 [+0.44; +3.96] (n=91) |
| defender_class | self_or_versions | +1.34 [+0.44; +2.17] (n=96) |
| open_size | 2.5-5bb | +3.34 [+1.32; +5.27] (n=10) |
| open_size | <=2.5bb | +2.13 [+0.96; +3.25] (n=95) |
| open_size | shove/large | -0.48 [-1.40; +0.39] (n=73) |

**hybrid_v2_adaptive: lucro por steal por dimensão (bb)**

| dimensão | grupo | estimativa [IC 95%] |
|---|---|---|
| position | BTN | +1.59 [+0.21; +3.07] (n=86) |
| position | CO | +1.85 [+0.00; +3.79] (n=75) |
| position | SB | -0.63 [-2.14; +0.66] (n=80) |
| eff_stack | 10-20bb | +0.15 [-1.45; +1.44] (n=57) |
| eff_stack | 20-40bb | +0.59 [-1.08; +2.19] (n=75) |
| eff_stack | 40bb+ | +2.36 [-0.50; +5.17] (n=74) |
| eff_stack | <10bb | +1.26 [+0.33; +2.24] (n=52) |
| ante | ante | +0.71 [-0.32; +1.70] (n=73) |
| ante | no_ante | +1.47 [-0.54; +3.66] (n=90) |
| defender_class | self_or_versions | +0.99 [-0.06; +1.80] (n=95) |
| open_size | 2.5-5bb | +3.20 [+1.19; +5.74] (n=8) |
| open_size | <=2.5bb | +1.32 [+0.22; +2.39] (n=93) |
| open_size | shove/large | -0.02 [-1.07; +1.04] (n=65) |

