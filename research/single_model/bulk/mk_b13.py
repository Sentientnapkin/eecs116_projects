L=open('../learned_c/lc_b6_J3s1.c').read().split('\n'); blk=L[667:14095]
s=open('b6bulk.c').read()
def rep(a,b):
    global s
    assert s.count(a)==1,(a,s.count(a)); s=s.replace(a,b)
rep("static double Hs[3 * MAXD]; /* Jacobian rows of the small updates */\n","static double Hs[3 * MAXD]; /* Jacobian rows of the small updates */\n"+'\n'.join(blk)+"\n")
rep("tt < START_T + (INV_FADE > 0 ? INV_FADE : 0);","tt < START_T + (INV_FADE > 0 ? INV_FADE : 0) && !LC_PRIOR_OFF;")
rep("        initialized = 1;\n        write_state(out);","        initialized = 1;\n        lc_begin(frame, imu, imu_count);\n        write_state(out);")
rep("    vision(frame);\n    write_state(out);","    lc_step(frame, imu, imu_count);\n    vision(frame);\n    write_state(out);")
open('b13_new.c','w').write(s)
