define i64 @inst-oldest-taint-bug() {
entry:
  %mem_base = alloca [1 x i64], align 8
  %__mg_1 = getelementptr [1 x i64], ptr %mem_base, i64 0, i64 0
  store volatile i64 0, ptr %__mg_1, align 8
  %probe_mem = alloca [256 x i64], align 64
  %__pg_1 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 0
  store volatile i64 0, ptr %__pg_1, align 8
  %__pg_2 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 1
  store volatile i64 0, ptr %__pg_2, align 8
  %__pg_3 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 2
  store volatile i64 0, ptr %__pg_3, align 8
  %__pg_4 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 3
  store volatile i64 0, ptr %__pg_4, align 8
  %__pg_5 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 4
  store volatile i64 0, ptr %__pg_5, align 8
  %__pg_6 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 5
  store volatile i64 0, ptr %__pg_6, align 8
  %__pg_7 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 6
  store volatile i64 0, ptr %__pg_7, align 8
  %__pg_8 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 7
  store volatile i64 0, ptr %__pg_8, align 8
  %__pg_9 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 8
  store volatile i64 0, ptr %__pg_9, align 8
  %__pg_10 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 9
  store volatile i64 0, ptr %__pg_10, align 8
  %__pg_11 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 10
  store volatile i64 0, ptr %__pg_11, align 8
  %__pg_12 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 11
  store volatile i64 0, ptr %__pg_12, align 8
  %__pg_13 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 12
  store volatile i64 0, ptr %__pg_13, align 8
  %__pg_14 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 13
  store volatile i64 0, ptr %__pg_14, align 8
  %__pg_15 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 14
  store volatile i64 0, ptr %__pg_15, align 8
  %__pg_16 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 15
  store volatile i64 0, ptr %__pg_16, align 8
  %__pg_17 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 16
  store volatile i64 0, ptr %__pg_17, align 8
  %__pg_18 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 17
  store volatile i64 0, ptr %__pg_18, align 8
  %__pg_19 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 18
  store volatile i64 0, ptr %__pg_19, align 8
  %__pg_20 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 19
  store volatile i64 0, ptr %__pg_20, align 8
  %__pg_21 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 20
  store volatile i64 0, ptr %__pg_21, align 8
  %__pg_22 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 21
  store volatile i64 0, ptr %__pg_22, align 8
  %__pg_23 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 22
  store volatile i64 0, ptr %__pg_23, align 8
  %__pg_24 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 23
  store volatile i64 0, ptr %__pg_24, align 8
  %__pg_25 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 24
  store volatile i64 0, ptr %__pg_25, align 8
  %__pg_26 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 25
  store volatile i64 0, ptr %__pg_26, align 8
  %__pg_27 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 26
  store volatile i64 0, ptr %__pg_27, align 8
  %__pg_28 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 27
  store volatile i64 0, ptr %__pg_28, align 8
  %__pg_29 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 28
  store volatile i64 0, ptr %__pg_29, align 8
  %__pg_30 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 29
  store volatile i64 0, ptr %__pg_30, align 8
  %__pg_31 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 30
  store volatile i64 0, ptr %__pg_31, align 8
  %__pg_32 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 31
  store volatile i64 0, ptr %__pg_32, align 8
  %__pg_33 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 32
  store volatile i64 0, ptr %__pg_33, align 8
  %__pg_34 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 33
  store volatile i64 0, ptr %__pg_34, align 8
  %__pg_35 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 34
  store volatile i64 0, ptr %__pg_35, align 8
  %__pg_36 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 35
  store volatile i64 0, ptr %__pg_36, align 8
  %__pg_37 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 36
  store volatile i64 0, ptr %__pg_37, align 8
  %__pg_38 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 37
  store volatile i64 0, ptr %__pg_38, align 8
  %__pg_39 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 38
  store volatile i64 0, ptr %__pg_39, align 8
  %__pg_40 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 39
  store volatile i64 0, ptr %__pg_40, align 8
  %__pg_41 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 40
  store volatile i64 0, ptr %__pg_41, align 8
  %__pg_42 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 41
  store volatile i64 0, ptr %__pg_42, align 8
  %__pg_43 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 42
  store volatile i64 0, ptr %__pg_43, align 8
  %__pg_44 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 43
  store volatile i64 0, ptr %__pg_44, align 8
  %__pg_45 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 44
  store volatile i64 0, ptr %__pg_45, align 8
  %__pg_46 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 45
  store volatile i64 0, ptr %__pg_46, align 8
  %__pg_47 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 46
  store volatile i64 0, ptr %__pg_47, align 8
  %__pg_48 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 47
  store volatile i64 0, ptr %__pg_48, align 8
  %__pg_49 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 48
  store volatile i64 0, ptr %__pg_49, align 8
  %__pg_50 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 49
  store volatile i64 0, ptr %__pg_50, align 8
  %__pg_51 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 50
  store volatile i64 0, ptr %__pg_51, align 8
  %__pg_52 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 51
  store volatile i64 0, ptr %__pg_52, align 8
  %__pg_53 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 52
  store volatile i64 0, ptr %__pg_53, align 8
  %__pg_54 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 53
  store volatile i64 0, ptr %__pg_54, align 8
  %__pg_55 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 54
  store volatile i64 0, ptr %__pg_55, align 8
  %__pg_56 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 55
  store volatile i64 0, ptr %__pg_56, align 8
  %__pg_57 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 56
  store volatile i64 0, ptr %__pg_57, align 8
  %__pg_58 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 57
  store volatile i64 0, ptr %__pg_58, align 8
  %__pg_59 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 58
  store volatile i64 0, ptr %__pg_59, align 8
  %__pg_60 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 59
  store volatile i64 0, ptr %__pg_60, align 8
  %__pg_61 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 60
  store volatile i64 0, ptr %__pg_61, align 8
  %__pg_62 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 61
  store volatile i64 0, ptr %__pg_62, align 8
  %__pg_63 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 62
  store volatile i64 0, ptr %__pg_63, align 8
  %__pg_64 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 63
  store volatile i64 0, ptr %__pg_64, align 8
  %__pg_65 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 64
  store volatile i64 0, ptr %__pg_65, align 8
  %__pg_66 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 65
  store volatile i64 0, ptr %__pg_66, align 8
  %__pg_67 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 66
  store volatile i64 0, ptr %__pg_67, align 8
  %__pg_68 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 67
  store volatile i64 0, ptr %__pg_68, align 8
  %__pg_69 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 68
  store volatile i64 0, ptr %__pg_69, align 8
  %__pg_70 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 69
  store volatile i64 0, ptr %__pg_70, align 8
  %__pg_71 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 70
  store volatile i64 0, ptr %__pg_71, align 8
  %__pg_72 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 71
  store volatile i64 0, ptr %__pg_72, align 8
  %__pg_73 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 72
  store volatile i64 0, ptr %__pg_73, align 8
  %__pg_74 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 73
  store volatile i64 0, ptr %__pg_74, align 8
  %__pg_75 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 74
  store volatile i64 0, ptr %__pg_75, align 8
  %__pg_76 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 75
  store volatile i64 0, ptr %__pg_76, align 8
  %__pg_77 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 76
  store volatile i64 0, ptr %__pg_77, align 8
  %__pg_78 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 77
  store volatile i64 0, ptr %__pg_78, align 8
  %__pg_79 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 78
  store volatile i64 0, ptr %__pg_79, align 8
  %__pg_80 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 79
  store volatile i64 0, ptr %__pg_80, align 8
  %__pg_81 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 80
  store volatile i64 0, ptr %__pg_81, align 8
  %__pg_82 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 81
  store volatile i64 0, ptr %__pg_82, align 8
  %__pg_83 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 82
  store volatile i64 0, ptr %__pg_83, align 8
  %__pg_84 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 83
  store volatile i64 0, ptr %__pg_84, align 8
  %__pg_85 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 84
  store volatile i64 0, ptr %__pg_85, align 8
  %__pg_86 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 85
  store volatile i64 0, ptr %__pg_86, align 8
  %__pg_87 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 86
  store volatile i64 0, ptr %__pg_87, align 8
  %__pg_88 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 87
  store volatile i64 0, ptr %__pg_88, align 8
  %__pg_89 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 88
  store volatile i64 0, ptr %__pg_89, align 8
  %__pg_90 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 89
  store volatile i64 0, ptr %__pg_90, align 8
  %__pg_91 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 90
  store volatile i64 0, ptr %__pg_91, align 8
  %__pg_92 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 91
  store volatile i64 0, ptr %__pg_92, align 8
  %__pg_93 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 92
  store volatile i64 0, ptr %__pg_93, align 8
  %__pg_94 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 93
  store volatile i64 0, ptr %__pg_94, align 8
  %__pg_95 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 94
  store volatile i64 0, ptr %__pg_95, align 8
  %__pg_96 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 95
  store volatile i64 0, ptr %__pg_96, align 8
  %__pg_97 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 96
  store volatile i64 0, ptr %__pg_97, align 8
  %__pg_98 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 97
  store volatile i64 0, ptr %__pg_98, align 8
  %__pg_99 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 98
  store volatile i64 0, ptr %__pg_99, align 8
  %__pg_100 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 99
  store volatile i64 0, ptr %__pg_100, align 8
  %__pg_101 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 100
  store volatile i64 0, ptr %__pg_101, align 8
  %__pg_102 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 101
  store volatile i64 0, ptr %__pg_102, align 8
  %__pg_103 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 102
  store volatile i64 0, ptr %__pg_103, align 8
  %__pg_104 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 103
  store volatile i64 0, ptr %__pg_104, align 8
  %__pg_105 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 104
  store volatile i64 0, ptr %__pg_105, align 8
  %__pg_106 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 105
  store volatile i64 0, ptr %__pg_106, align 8
  %__pg_107 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 106
  store volatile i64 0, ptr %__pg_107, align 8
  %__pg_108 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 107
  store volatile i64 0, ptr %__pg_108, align 8
  %__pg_109 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 108
  store volatile i64 0, ptr %__pg_109, align 8
  %__pg_110 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 109
  store volatile i64 0, ptr %__pg_110, align 8
  %__pg_111 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 110
  store volatile i64 0, ptr %__pg_111, align 8
  %__pg_112 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 111
  store volatile i64 0, ptr %__pg_112, align 8
  %__pg_113 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 112
  store volatile i64 0, ptr %__pg_113, align 8
  %__pg_114 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 113
  store volatile i64 0, ptr %__pg_114, align 8
  %__pg_115 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 114
  store volatile i64 0, ptr %__pg_115, align 8
  %__pg_116 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 115
  store volatile i64 0, ptr %__pg_116, align 8
  %__pg_117 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 116
  store volatile i64 0, ptr %__pg_117, align 8
  %__pg_118 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 117
  store volatile i64 0, ptr %__pg_118, align 8
  %__pg_119 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 118
  store volatile i64 0, ptr %__pg_119, align 8
  %__pg_120 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 119
  store volatile i64 0, ptr %__pg_120, align 8
  %__pg_121 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 120
  store volatile i64 0, ptr %__pg_121, align 8
  %__pg_122 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 121
  store volatile i64 0, ptr %__pg_122, align 8
  %__pg_123 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 122
  store volatile i64 0, ptr %__pg_123, align 8
  %__pg_124 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 123
  store volatile i64 0, ptr %__pg_124, align 8
  %__pg_125 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 124
  store volatile i64 0, ptr %__pg_125, align 8
  %__pg_126 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 125
  store volatile i64 0, ptr %__pg_126, align 8
  %__pg_127 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 126
  store volatile i64 0, ptr %__pg_127, align 8
  %__pg_128 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 127
  store volatile i64 0, ptr %__pg_128, align 8
  %__pg_129 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 128
  store volatile i64 0, ptr %__pg_129, align 8
  %__pg_130 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 129
  store volatile i64 0, ptr %__pg_130, align 8
  %__pg_131 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 130
  store volatile i64 0, ptr %__pg_131, align 8
  %__pg_132 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 131
  store volatile i64 0, ptr %__pg_132, align 8
  %__pg_133 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 132
  store volatile i64 0, ptr %__pg_133, align 8
  %__pg_134 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 133
  store volatile i64 0, ptr %__pg_134, align 8
  %__pg_135 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 134
  store volatile i64 0, ptr %__pg_135, align 8
  %__pg_136 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 135
  store volatile i64 0, ptr %__pg_136, align 8
  %__pg_137 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 136
  store volatile i64 0, ptr %__pg_137, align 8
  %__pg_138 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 137
  store volatile i64 0, ptr %__pg_138, align 8
  %__pg_139 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 138
  store volatile i64 0, ptr %__pg_139, align 8
  %__pg_140 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 139
  store volatile i64 0, ptr %__pg_140, align 8
  %__pg_141 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 140
  store volatile i64 0, ptr %__pg_141, align 8
  %__pg_142 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 141
  store volatile i64 0, ptr %__pg_142, align 8
  %__pg_143 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 142
  store volatile i64 0, ptr %__pg_143, align 8
  %__pg_144 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 143
  store volatile i64 0, ptr %__pg_144, align 8
  %__pg_145 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 144
  store volatile i64 0, ptr %__pg_145, align 8
  %__pg_146 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 145
  store volatile i64 0, ptr %__pg_146, align 8
  %__pg_147 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 146
  store volatile i64 0, ptr %__pg_147, align 8
  %__pg_148 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 147
  store volatile i64 0, ptr %__pg_148, align 8
  %__pg_149 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 148
  store volatile i64 0, ptr %__pg_149, align 8
  %__pg_150 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 149
  store volatile i64 0, ptr %__pg_150, align 8
  %__pg_151 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 150
  store volatile i64 0, ptr %__pg_151, align 8
  %__pg_152 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 151
  store volatile i64 0, ptr %__pg_152, align 8
  %__pg_153 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 152
  store volatile i64 0, ptr %__pg_153, align 8
  %__pg_154 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 153
  store volatile i64 0, ptr %__pg_154, align 8
  %__pg_155 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 154
  store volatile i64 0, ptr %__pg_155, align 8
  %__pg_156 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 155
  store volatile i64 0, ptr %__pg_156, align 8
  %__pg_157 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 156
  store volatile i64 0, ptr %__pg_157, align 8
  %__pg_158 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 157
  store volatile i64 0, ptr %__pg_158, align 8
  %__pg_159 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 158
  store volatile i64 0, ptr %__pg_159, align 8
  %__pg_160 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 159
  store volatile i64 0, ptr %__pg_160, align 8
  %__pg_161 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 160
  store volatile i64 0, ptr %__pg_161, align 8
  %__pg_162 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 161
  store volatile i64 0, ptr %__pg_162, align 8
  %__pg_163 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 162
  store volatile i64 0, ptr %__pg_163, align 8
  %__pg_164 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 163
  store volatile i64 0, ptr %__pg_164, align 8
  %__pg_165 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 164
  store volatile i64 0, ptr %__pg_165, align 8
  %__pg_166 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 165
  store volatile i64 0, ptr %__pg_166, align 8
  %__pg_167 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 166
  store volatile i64 0, ptr %__pg_167, align 8
  %__pg_168 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 167
  store volatile i64 0, ptr %__pg_168, align 8
  %__pg_169 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 168
  store volatile i64 0, ptr %__pg_169, align 8
  %__pg_170 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 169
  store volatile i64 0, ptr %__pg_170, align 8
  %__pg_171 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 170
  store volatile i64 0, ptr %__pg_171, align 8
  %__pg_172 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 171
  store volatile i64 0, ptr %__pg_172, align 8
  %__pg_173 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 172
  store volatile i64 0, ptr %__pg_173, align 8
  %__pg_174 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 173
  store volatile i64 0, ptr %__pg_174, align 8
  %__pg_175 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 174
  store volatile i64 0, ptr %__pg_175, align 8
  %__pg_176 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 175
  store volatile i64 0, ptr %__pg_176, align 8
  %__pg_177 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 176
  store volatile i64 0, ptr %__pg_177, align 8
  %__pg_178 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 177
  store volatile i64 0, ptr %__pg_178, align 8
  %__pg_179 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 178
  store volatile i64 0, ptr %__pg_179, align 8
  %__pg_180 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 179
  store volatile i64 0, ptr %__pg_180, align 8
  %__pg_181 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 180
  store volatile i64 0, ptr %__pg_181, align 8
  %__pg_182 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 181
  store volatile i64 0, ptr %__pg_182, align 8
  %__pg_183 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 182
  store volatile i64 0, ptr %__pg_183, align 8
  %__pg_184 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 183
  store volatile i64 0, ptr %__pg_184, align 8
  %__pg_185 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 184
  store volatile i64 0, ptr %__pg_185, align 8
  %__pg_186 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 185
  store volatile i64 0, ptr %__pg_186, align 8
  %__pg_187 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 186
  store volatile i64 0, ptr %__pg_187, align 8
  %__pg_188 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 187
  store volatile i64 0, ptr %__pg_188, align 8
  %__pg_189 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 188
  store volatile i64 0, ptr %__pg_189, align 8
  %__pg_190 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 189
  store volatile i64 0, ptr %__pg_190, align 8
  %__pg_191 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 190
  store volatile i64 0, ptr %__pg_191, align 8
  %__pg_192 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 191
  store volatile i64 0, ptr %__pg_192, align 8
  %__pg_193 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 192
  store volatile i64 0, ptr %__pg_193, align 8
  %__pg_194 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 193
  store volatile i64 0, ptr %__pg_194, align 8
  %__pg_195 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 194
  store volatile i64 0, ptr %__pg_195, align 8
  %__pg_196 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 195
  store volatile i64 0, ptr %__pg_196, align 8
  %__pg_197 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 196
  store volatile i64 0, ptr %__pg_197, align 8
  %__pg_198 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 197
  store volatile i64 0, ptr %__pg_198, align 8
  %__pg_199 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 198
  store volatile i64 0, ptr %__pg_199, align 8
  %__pg_200 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 199
  store volatile i64 0, ptr %__pg_200, align 8
  %__pg_201 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 200
  store volatile i64 0, ptr %__pg_201, align 8
  %__pg_202 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 201
  store volatile i64 0, ptr %__pg_202, align 8
  %__pg_203 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 202
  store volatile i64 0, ptr %__pg_203, align 8
  %__pg_204 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 203
  store volatile i64 0, ptr %__pg_204, align 8
  %__pg_205 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 204
  store volatile i64 0, ptr %__pg_205, align 8
  %__pg_206 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 205
  store volatile i64 0, ptr %__pg_206, align 8
  %__pg_207 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 206
  store volatile i64 0, ptr %__pg_207, align 8
  %__pg_208 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 207
  store volatile i64 0, ptr %__pg_208, align 8
  %__pg_209 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 208
  store volatile i64 0, ptr %__pg_209, align 8
  %__pg_210 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 209
  store volatile i64 0, ptr %__pg_210, align 8
  %__pg_211 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 210
  store volatile i64 0, ptr %__pg_211, align 8
  %__pg_212 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 211
  store volatile i64 0, ptr %__pg_212, align 8
  %__pg_213 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 212
  store volatile i64 0, ptr %__pg_213, align 8
  %__pg_214 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 213
  store volatile i64 0, ptr %__pg_214, align 8
  %__pg_215 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 214
  store volatile i64 0, ptr %__pg_215, align 8
  %__pg_216 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 215
  store volatile i64 0, ptr %__pg_216, align 8
  %__pg_217 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 216
  store volatile i64 0, ptr %__pg_217, align 8
  %__pg_218 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 217
  store volatile i64 0, ptr %__pg_218, align 8
  %__pg_219 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 218
  store volatile i64 0, ptr %__pg_219, align 8
  %__pg_220 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 219
  store volatile i64 0, ptr %__pg_220, align 8
  %__pg_221 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 220
  store volatile i64 0, ptr %__pg_221, align 8
  %__pg_222 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 221
  store volatile i64 0, ptr %__pg_222, align 8
  %__pg_223 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 222
  store volatile i64 0, ptr %__pg_223, align 8
  %__pg_224 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 223
  store volatile i64 0, ptr %__pg_224, align 8
  %__pg_225 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 224
  store volatile i64 0, ptr %__pg_225, align 8
  %__pg_226 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 225
  store volatile i64 0, ptr %__pg_226, align 8
  %__pg_227 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 226
  store volatile i64 0, ptr %__pg_227, align 8
  %__pg_228 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 227
  store volatile i64 0, ptr %__pg_228, align 8
  %__pg_229 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 228
  store volatile i64 0, ptr %__pg_229, align 8
  %__pg_230 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 229
  store volatile i64 0, ptr %__pg_230, align 8
  %__pg_231 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 230
  store volatile i64 0, ptr %__pg_231, align 8
  %__pg_232 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 231
  store volatile i64 0, ptr %__pg_232, align 8
  %__pg_233 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 232
  store volatile i64 0, ptr %__pg_233, align 8
  %__pg_234 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 233
  store volatile i64 0, ptr %__pg_234, align 8
  %__pg_235 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 234
  store volatile i64 0, ptr %__pg_235, align 8
  %__pg_236 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 235
  store volatile i64 0, ptr %__pg_236, align 8
  %__pg_237 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 236
  store volatile i64 0, ptr %__pg_237, align 8
  %__pg_238 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 237
  store volatile i64 0, ptr %__pg_238, align 8
  %__pg_239 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 238
  store volatile i64 0, ptr %__pg_239, align 8
  %__pg_240 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 239
  store volatile i64 0, ptr %__pg_240, align 8
  %__pg_241 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 240
  store volatile i64 0, ptr %__pg_241, align 8
  %__pg_242 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 241
  store volatile i64 0, ptr %__pg_242, align 8
  %__pg_243 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 242
  store volatile i64 0, ptr %__pg_243, align 8
  %__pg_244 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 243
  store volatile i64 0, ptr %__pg_244, align 8
  %__pg_245 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 244
  store volatile i64 0, ptr %__pg_245, align 8
  %__pg_246 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 245
  store volatile i64 0, ptr %__pg_246, align 8
  %__pg_247 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 246
  store volatile i64 0, ptr %__pg_247, align 8
  %__pg_248 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 247
  store volatile i64 0, ptr %__pg_248, align 8
  %__pg_249 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 248
  store volatile i64 0, ptr %__pg_249, align 8
  %__pg_250 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 249
  store volatile i64 0, ptr %__pg_250, align 8
  %__pg_251 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 250
  store volatile i64 0, ptr %__pg_251, align 8
  %__pg_252 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 251
  store volatile i64 0, ptr %__pg_252, align 8
  %__pg_253 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 252
  store volatile i64 0, ptr %__pg_253, align 8
  %__pg_254 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 253
  store volatile i64 0, ptr %__pg_254, align 8
  %__pg_255 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 254
  store volatile i64 0, ptr %__pg_255, align 8
  %__pg_256 = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 255
  store volatile i64 0, ptr %__pg_256, align 8
  %r10_0 = call i64 asm sideeffect "movq $1, $0", "={r10},r"(i64 0)
  %r11_0 = call i64 asm sideeffect "movq $1, $0", "={r11},r"(i64 0)
  %rax_0 = call i64 asm sideeffect "movq $1, $0", "={rax},r"(i64 0)
  %cond_slot_pc0 = alloca i64, align 64
  store volatile i64 0, ptr %cond_slot_pc0, align 64
  %cond_slot_pc2 = alloca i64, align 64
  store volatile i64 1, ptr %cond_slot_pc2, align 64
  %cond_ptr_slot_pc2 = alloca i64, align 64
  %cond_slot_addr_pc2 = ptrtoint ptr %cond_slot_pc2 to i64
  store volatile i64 %cond_slot_addr_pc2, ptr %cond_ptr_slot_pc2, align 64
  call void asm sideeffect "mfence\0Aclflush ($0)\0Aclflush ($1)\0Aclflush ($2)\0Amfence", "r,r,r,~{memory}"(ptr %cond_slot_pc0, ptr %cond_slot_pc2, ptr %cond_ptr_slot_pc2)
  ; pc=0  Instruction$5  (br_cond)
  ; BTB predicts=fall_through  btb_predicted_pc=1
  %__cond_raw_1 = call i64 asm sideeffect ".globl __litmus_inst_oldest_taint_bug_pc0\0A__litmus_inst_oldest_taint_bug_pc0:\0Amovq ($1), $0", "=&{rsi},{rdx},~{memory}"(ptr %cond_slot_pc0)
  %__cond_i1_1 = icmp ne i64 %__cond_raw_1, 0
  br i1 %__cond_i1_1, label %end_block, label %bb_1
bb_1:
  ; pc=1  Instruction$4  (load)
  %rax_1 = call i64 asm sideeffect ".globl __litmus_inst_oldest_taint_bug_pc1\0A__litmus_inst_oldest_taint_bug_pc1:\0A.globl __litmus_inst_oldest_taint_bug_last_committed\0A__litmus_inst_oldest_taint_bug_last_committed:\0Amovq 0($1), $0", "=&{rax},r,~{memory}"(ptr %mem_base)
  ; pc=2  Instruction$3  (br_cond)
  ; BTB predicts=fall_through  btb_predicted_pc=3
  %__ptr_raw_1 = call i64 asm sideeffect "movq ($1), $0", "=&{rdx},{rsi},~{memory}"(ptr %cond_ptr_slot_pc2)
  %__cond_ptr_1 = inttoptr i64 %__ptr_raw_1 to ptr
  %__cond_raw_2 = call i64 asm sideeffect ".globl __litmus_inst_oldest_taint_bug_pc2\0A__litmus_inst_oldest_taint_bug_pc2:\0A.globl __litmus_inst_oldest_taint_bug_first_noncommitted\0A__litmus_inst_oldest_taint_bug_first_noncommitted:\0Amovq ($1), $0", "=&{rsi},{rdx},~{memory}"(ptr %__cond_ptr_1)
  %__cond_i1_2 = icmp ne i64 %__cond_raw_2, 0
  br i1 %__cond_i1_2, label %end_block, label %bb_3
bb_3:
  ; pc=3  Instruction$2  (load)
  %rcx_1 = call i64 asm sideeffect ".globl __litmus_inst_oldest_taint_bug_pc3\0A__litmus_inst_oldest_taint_bug_pc3:\0Amovq 0($1), $0", "=&{rcx},r,~{memory}"(ptr %mem_base)
  ; pc=4  Instruction$1  (add)
  %rax_2 = call i64 asm sideeffect ".globl __litmus_inst_oldest_taint_bug_pc4\0A__litmus_inst_oldest_taint_bug_pc4:\0Aleaq ($1, $2), $0", "=&{rax},{rax},{rcx}"(i64 %rax_1, i64 %rcx_1)
  ; pc=5  Instruction$0  (load)
  %rax_3 = call i64 asm sideeffect ".globl __litmus_inst_oldest_taint_bug_pc5\0A__litmus_inst_oldest_taint_bug_pc5:\0Amovq ($1, $2, 1), $0", "=&{rax},r,{rax},~{memory}"(ptr %probe_mem, i64 %rax_2)
  br label %end_block
end_block:
  ret i64 0
}
