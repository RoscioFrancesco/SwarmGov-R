# Confirmatory Result Tables

Generated from statistical summary CSV files. Canary or partial inputs are technical validation artifacts only.

## Final Mean Regret

| condition | algorithm | n | mean_regret | ci95_low | ci95_high |
| --- | --- | --- | --- | --- | --- |
| clean_dynamic_communication_topologies / ring / dynamic / no_attack / none / mean | mean | 100 | 78.04083999999973 | 77.29745330621797 | 78.78422669378149 |
| clean_dynamic_communication_topologies / ring / dynamic / no_attack / none / median | median | 100 | 367.1473799999952 | 350.22623095664596 | 384.0685290433445 |
| clean_dynamic_communication_topologies / ring / dynamic / no_attack / none / trimmed_mean | trimmed_mean | 100 | 239.98933999999736 | 229.75964458848603 | 250.21903541150868 |
| clean_dynamic_communication_topologies / scale_free / dynamic / no_attack / none / mean | mean | 100 | 78.10725999999971 | 76.74953228198363 | 79.46498771801579 |
| clean_dynamic_communication_topologies / scale_free / dynamic / no_attack / none / median | median | 100 | 411.4087399999951 | 394.41275655078636 | 428.4047234492038 |
| clean_dynamic_communication_topologies / scale_free / dynamic / no_attack / none / trimmed_mean | trimmed_mean | 100 | 308.1091399999969 | 296.83986778824027 | 319.3784122117535 |
| clean_dynamic_communication_topologies / small_world / dynamic / no_attack / none / mean | mean | 100 | 64.10377999999984 | 63.194373242512086 | 65.0131867574876 |
| clean_dynamic_communication_topologies / small_world / dynamic / no_attack / none / median | median | 100 | 294.4434399999968 | 278.85249473556775 | 310.0343852644259 |
| clean_dynamic_communication_topologies / small_world / dynamic / no_attack / none / trimmed_mean | trimmed_mean | 100 | 247.32639999999776 | 229.3576206847276 | 265.29517931526794 |
| clean_static_all_topologies / complete / static / no_attack / none / centralized_clean_reference | centralized_clean_reference | 100 | 14.702499999999992 | 14.383345601080508 | 15.021654398919475 |
| clean_static_all_topologies / complete / static / no_attack / none / independent | independent | 100 | 114.73117999999968 | 114.22038455578023 | 115.24197544421914 |
| clean_static_all_topologies / complete / static / no_attack / none / mean | mean | 100 | 10.876979999999994 | 10.599032960003795 | 11.154927039996194 |
| clean_static_all_topologies / complete / static / no_attack / none / median | median | 100 | 14.433279999999568 | 5.019285774047143 | 23.847274225951992 |
| clean_static_all_topologies / complete / static / no_attack / none / trimmed_mean | trimmed_mean | 100 | 11.420539999999644 | 2.86347395844591 | 19.97760604155338 |
| clean_static_all_topologies / ring / static / no_attack / none / centralized_clean_reference | centralized_clean_reference | 100 | 14.702499999999992 | 14.383345601080508 | 15.021654398919475 |
| clean_static_all_topologies / ring / static / no_attack / none / independent | independent | 100 | 114.73117999999968 | 114.22038455578023 | 115.24197544421914 |
| clean_static_all_topologies / ring / static / no_attack / none / mean | mean | 100 | 78.42217999999968 | 77.74780749072427 | 79.0965525092751 |
| clean_static_all_topologies / ring / static / no_attack / none / median | median | 100 | 388.79913999999405 | 371.35725277114244 | 406.24102722884567 |
| clean_static_all_topologies / ring / static / no_attack / none / trimmed_mean | trimmed_mean | 100 | 211.3834199999962 | 199.10153431455052 | 223.66530568544187 |
| clean_static_all_topologies / scale_free / static / no_attack / none / centralized_clean_reference | centralized_clean_reference | 100 | 14.702499999999992 | 14.383345601080508 | 15.021654398919475 |
| clean_static_all_topologies / scale_free / static / no_attack / none / independent | independent | 100 | 114.73117999999968 | 114.22038455578023 | 115.24197544421914 |
| clean_static_all_topologies / scale_free / static / no_attack / none / mean | mean | 100 | 80.14277999999965 | 78.55753303701452 | 81.72802696298477 |
| clean_static_all_topologies / scale_free / static / no_attack / none / median | median | 100 | 437.655479999994 | 417.52779334955716 | 457.7831666504308 |
| clean_static_all_topologies / scale_free / static / no_attack / none / trimmed_mean | trimmed_mean | 100 | 280.27815999999535 | 268.3474299296367 | 292.208890070354 |
| clean_static_all_topologies / small_world / static / no_attack / none / centralized_clean_reference | centralized_clean_reference | 100 | 14.702499999999992 | 14.383345601080508 | 15.021654398919475 |
| clean_static_all_topologies / small_world / static / no_attack / none / independent | independent | 100 | 114.73117999999968 | 114.22038455578023 | 115.24197544421914 |
| clean_static_all_topologies / small_world / static / no_attack / none / mean | mean | 100 | 61.50783999999982 | 60.71019220833113 | 62.305487791668504 |
| clean_static_all_topologies / small_world / static / no_attack / none / median | median | 100 | 309.1259799999957 | 291.91892106211037 | 326.33303893788104 |
| clean_static_all_topologies / small_world / static / no_attack / none / trimmed_mean | trimmed_mean | 100 | 273.70653999999615 | 253.44914439382524 | 293.96393560616707 |
| coordinated_dynamic_random_and_degree / ring / dynamic / coordinated_target / degree_centrality / mean | mean | 100 | 93.20789999999988 | 91.9513646395162 | 94.46443536048356 |
| ... |  |  |  |  |  |

## Paired Mean-Regret Differences

| comparison | n_pairs | mean_difference | ci95_low | ci95_high |
| --- | --- | --- | --- | --- |
| clean_static_all_topologies / complete / static / vs_independent / centralized_clean_reference vs independent | 100 | -100.02867999999968 | -100.67630499999972 | -99.43329199999967 |
| clean_static_all_topologies / ring / static / vs_independent / centralized_clean_reference vs independent | 100 | -100.02867999999968 | -100.67665949999974 | -99.42345299999965 |
| clean_static_all_topologies / scale_free / static / vs_independent / centralized_clean_reference vs independent | 100 | -100.02867999999968 | -100.6301889999997 | -99.4434134999996 |
| clean_static_all_topologies / small_world / static / vs_independent / centralized_clean_reference vs independent | 100 | -100.02867999999968 | -100.63673649999969 | -99.43845149999967 |
| clean_static_all_topologies / complete / static / vs_independent / mean vs independent | 100 | -103.8541999999997 | -104.37568399999974 | -103.3180939999997 |
| clean_static_all_topologies / ring / static / vs_independent / mean vs independent | 100 | -36.30899999999999 | -37.14486549999997 | -35.51493499999998 |
| clean_static_all_topologies / scale_free / static / vs_independent / mean vs independent | 100 | -34.58840000000003 | -36.2383175 | -32.99798900000007 |
| clean_static_all_topologies / small_world / static / vs_independent / mean vs independent | 100 | -53.223339999999865 | -54.1070849999999 | -52.26279449999984 |
| coordinated_static_random_and_degree / ring / static / vs_independent / mean vs independent | 100 | -24.5421249999999 | -25.419428749999888 | -23.63336249999991 |
| coordinated_static_random_and_degree / ring / static / vs_independent / mean vs independent | 100 | -31.854600000000026 | -33.299453750000026 | -30.33264437500007 |
| coordinated_static_random_and_degree / scale_free / static / vs_independent / mean vs independent | 100 | -25.322850000000017 | -27.58770625000002 | -22.957109375000073 |
| coordinated_static_random_and_degree / scale_free / static / vs_independent / mean vs independent | 100 | -32.76737500000001 | -34.75788499999999 | -30.85302312500001 |
| clean_static_all_topologies / complete / static / vs_independent / median vs independent | 100 | -100.29790000000011 | -108.69867399999983 | -89.84066700000044 |
| clean_static_all_topologies / ring / static / vs_independent / median vs independent | 100 | 274.0679599999944 | 256.9527144999947 | 292.10139249999435 |
| clean_static_all_topologies / scale_free / static / vs_independent / median vs independent | 100 | 322.9242999999943 | 301.7718519999943 | 342.92138049999386 |
| clean_static_all_topologies / small_world / static / vs_independent / median vs independent | 100 | 194.394799999996 | 177.23981399999582 | 210.99148399999584 |
| coordinated_static_random_and_degree / ring / static / vs_independent / median vs independent | 100 | 279.20997499999424 | 259.0948974999946 | 300.81116687499417 |
| coordinated_static_random_and_degree / ring / static / vs_independent / median vs independent | 100 | 300.63912499999367 | 281.6182849999941 | 319.1410593749931 |
| coordinated_static_random_and_degree / scale_free / static / vs_independent / median vs independent | 100 | 381.785849999993 | 359.3891506249929 | 405.47899374999247 |
| coordinated_static_random_and_degree / scale_free / static / vs_independent / median vs independent | 100 | 330.4804749999939 | 312.08913562499396 | 349.0383468749943 |
| clean_static_all_topologies / complete / static / vs_independent / trimmed_mean vs independent | 100 | -103.31064000000003 | -111.18607999999978 | -94.86816200000041 |
| clean_static_all_topologies / ring / static / vs_independent / trimmed_mean vs independent | 100 | 96.65223999999651 | 84.65538599999668 | 108.46024599999649 |
| clean_static_all_topologies / scale_free / static / vs_independent / trimmed_mean vs independent | 100 | 165.54697999999564 | 154.04732999999587 | 176.78218249999549 |
| clean_static_all_topologies / small_world / static / vs_independent / trimmed_mean vs independent | 100 | 158.97535999999644 | 138.48452149999665 | 178.6279524999961 |
| coordinated_static_random_and_degree / ring / static / vs_independent / trimmed_mean vs independent | 100 | 105.58929999999614 | 91.68045937499627 | 120.04166374999586 |
| coordinated_static_random_and_degree / ring / static / vs_independent / trimmed_mean vs independent | 100 | 117.88797499999569 | 104.36130687499578 | 131.8878424999952 |
| coordinated_static_random_and_degree / scale_free / static / vs_independent / trimmed_mean vs independent | 100 | 177.88234999999415 | 162.79851999999448 | 194.02387999999343 |
| coordinated_static_random_and_degree / scale_free / static / vs_independent / trimmed_mean vs independent | 100 | 190.65449999999507 | 176.97214374999544 | 203.618893124995 |
| clean_dynamic_communication_topologies / ring / dynamic / vs_mean / median vs mean | 100 | 289.1065399999955 | 273.224549999996 | 305.43508399999564 |
| clean_dynamic_communication_topologies / scale_free / dynamic / vs_mean / median vs mean | 100 | 333.3014799999954 | 317.0510979999957 | 350.3618109999951 |
| ... |  |  |  |  |
